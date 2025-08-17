"""
Modular page generator that uses real page configuration from the database.
This replaces the monolithic generate_pages.py with a clean, maintainable structure.
"""
from pathlib import Path
from typing import List, Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from sapy.models import Application, DbTable, ApplicationTable, Page, PageTable, Menu, ApplicationMenu, MenuPage

from .page_generators.config_loader import ConfigLoader, PageConfig
from .page_generators.template_generator import TemplateGenerator
from .page_generators.file_manager import FileManager, GeneratedContent
from .page_generators.service_manager import ServiceManager


class Command(BaseCommand):
    help = "Generate CRUD pages and modals using real page configuration from database"

    def add_arguments(self, parser):
        parser.add_argument('--app', required=True, help='Target app name (e.g., facxy)')
        parser.add_argument('--tables', help='Comma-separated table names; omit for --all-assigned')
        parser.add_argument('--all-assigned', action='store_true', help='Use all tables assigned to the app')
        parser.add_argument('--btn-title', help='Default button title for opening modals')
        parser.add_argument('--with-modals', action='store_true', default=True, help='Generate modals (default: yes)')
        parser.add_argument('--menu', help='Menu slug to integrate pages into (optional)')
        parser.add_argument('--overwrite', action='store_true', help='Overwrite existing sapy-auto blocks')
        parser.add_argument('--reload', action='store_true', help='Attempt to reload service after generation')
        parser.add_argument('--reload-service', help='Explicit systemd service name to reload (e.g., gunicorn@app)')

    @transaction.atomic
    def handle(self, *args, **options):
        # Parse and validate arguments
        app_name = options['app']
        btn_title = options.get('btn_title')
        overwrite = options.get('overwrite', False)
        with_modals = options.get('with_modals', True)
        menu_slug = options.get('menu')
        do_reload = options.get('reload', False)
        reload_service = options.get('reload_service')

        # Get application
        application = self._get_application(app_name)
        
        # Get tables to process
        tables = self._get_tables(application, options)
        
        # Initialize components
        base_path = Path(application.base_path.rstrip('/')) / app_name
        template_generator = TemplateGenerator(app_name, base_path)
        file_manager = FileManager(app_name, base_path)
        
        # Track results
        all_created_files = []
        all_updated_files = []
        
        # Process each table
        has_errors = False
        
        for table in tables:
            try:
                result = self._process_table(
                    table, app_name, template_generator, file_manager,
                    overwrite, with_modals, menu_slug, application, btn_title
                )
                all_created_files.extend(result['created'])
                all_updated_files.extend(result['updated'])
                
            except Exception as e:
                has_errors = True
                self.stdout.write(
                    self.style.ERROR(f"Error processing table {table.name}: {e}")
                )
                import traceback
                traceback.print_exc()
                continue

        # Report results
        if has_errors:
            self.stdout.write(
                self.style.ERROR('Page generation completed with ERRORS!')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('Page generation completed successfully!')
            )

        # Report file details
        self._report_results(all_created_files, all_updated_files)

        # Handle service reload
        if do_reload or reload_service:
            ServiceManager.reload_service(app_name, reload_service)

    def _get_application(self, app_name: str) -> Application:
        """Get and validate application."""
        application = Application.objects.filter(name=app_name).first()
        if not application:
            raise CommandError(f"Application '{app_name}' not found")
        return application

    def _get_tables(self, application: Application, options: dict) -> List[DbTable]:
        """Get tables to process based on options."""
        if options.get('all_assigned'):
            assigned_tables = application.assigned_tables.select_related('table').all()
            return [at.table for at in assigned_tables]
        else:
            tables_arg = options.get('tables')
            if not tables_arg:
                raise CommandError('Must specify --tables or --all-assigned')
            
            table_names = [name.strip() for name in tables_arg.split(',') if name.strip()]
            return list(DbTable.objects.filter(name__in=table_names))

    def _process_table(self, table: DbTable, app_name: str, template_generator: TemplateGenerator,
                      file_manager: FileManager, overwrite: bool, with_modals: bool,
                      menu_slug: Optional[str], application: Application, btn_title: Optional[str]) -> dict:
        """Process a single table and generate all its files."""
        
        # Load real configuration from database
        config = ConfigLoader.load_page_config(table.name)
        
        if not config:
            # Use fallback configuration if real config not available
            self.stdout.write(
                self.style.WARNING(f"No page configuration found for table {table.name}, using fallback")
            )
            config = ConfigLoader.get_fallback_config(table.name, getattr(table, 'alias', None))

        # Generate all content using real configuration
        content = GeneratedContent(table.name)
        
        # Generate templates
        content.list_template = template_generator.generate_list_template(table.name, config)
        
        if with_modals:
            content.modal_template = template_generator.generate_modal_template(table.name, config)
        
        content.form_template = template_generator.generate_form_template(table.name, config)
        content.confirm_delete_template = template_generator.generate_confirm_delete_template(table.name, config)
        
        # Generate code blocks
        content.views_block = template_generator.generate_views_block(table.name, config)
        content.urls_block = template_generator.generate_urls_block(table.name)
        content.template_tags_utils = template_generator.create_template_tags_utils()

        # Write ALL files (templates + shared files)
        result = file_manager.write_generated_content(content, overwrite)
        
        # Create/update Page and PageTable objects
        self._ensure_page_objects(table, config)

        # Handle menu integration
        if menu_slug:
            self._integrate_with_menu(table, menu_slug, application)

        self.stdout.write(
            self.style.SUCCESS(f"Generated content for table: {table.name}")
        )
        
        return result

    def _ensure_page_objects(self, table: DbTable, config: PageConfig):
        """Ensure Page and PageTable objects exist."""
        page, created = Page.objects.get_or_create(
            slug=table.name,
            defaults={
                'title': config.page_title,
                'db_table': table,
                'route_path': f"/{table.name}/",
            }
        )
        
        PageTable.objects.get_or_create(
            page=page,
            db_table=table,
            defaults={'title': config.table_title}
        )
        
        if created:
            self.stdout.write(f"Created Page object for {table.name}")

    def _integrate_with_menu(self, table: DbTable, menu_slug: str, application: Application):
        """Integrate page with specified menu."""
        menu, _ = Menu.objects.get_or_create(
            name=menu_slug,
            defaults={'title': menu_slug.title()}
        )
        
        ApplicationMenu.objects.get_or_create(
            application=application,
            menu=menu
        )
        
        page = Page.objects.filter(slug=table.name).first()
        if page:
            MenuPage.objects.get_or_create(
                menu=menu,
                page=page,
                defaults={'order_index': 1}
            )

    def _report_results(self, created_files: List[str], updated_files: List[str]):
        """Report file details."""
        if created_files:
            self.stdout.write('\nFiles created:')
            for file_path in created_files:
                self.stdout.write(f"  + {file_path}")
        
        if updated_files:
            self.stdout.write('\nFiles updated:')
            for file_path in updated_files:
                self.stdout.write(f"  ~ {file_path}")
        
        if not created_files and not updated_files:
            self.stdout.write(self.style.WARNING('No files were created or updated.'))
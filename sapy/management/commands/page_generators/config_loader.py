"""
Configuration loader that uses the real page configuration from the database.
This replaces the hardcoded field guessing in the original script.
"""
import json
from typing import Dict, List, Optional, Any
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser, User

from sapy.models import Page, DbTable
from sapy.views import page_effective_config


class PageConfig:
    """Represents the effective configuration for a page/table."""
    
    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data
        self.page_info = data.get('page', {})
        self.table_config = data.get('table', {})
        self.columns = data.get('columns', [])
        self.modals = data.get('modals', [])
    
    @property
    def page_title(self) -> str:
        """Get the configured page title."""
        return self.page_info.get('title', '')
    
    @property
    def page_slug(self) -> str:
        """Get the page slug."""
        return self.page_info.get('slug', '')
    
    @property
    def table_name(self) -> str:
        """Get the database table name."""
        return self.table_config.get('name', '')
    
    @property
    def table_title(self) -> str:
        """Get the configured table title."""
        return self.table_config.get('title', self.page_title)
    
    def get_visible_columns(self) -> List[Dict[str, Any]]:
        """Get columns that should be visible in the table list."""
        return [col for col in self.columns if col.get('visible', True)]
    
    def get_form_fields(self) -> List[Dict[str, Any]]:
        """Get form fields from the first modal (create/edit modal)."""
        if not self.modals:
            return []
        
        first_modal = self.modals[0]
        form_data = first_modal.get('form', {})
        return form_data.get('fields', [])
    
    def get_modal_config(self) -> Dict[str, Any]:
        """Get modal configuration from the first modal."""
        if not self.modals:
            return {
                'title': f'Nuevo {self.page_title}',
                'size': 'lg',
                'submit_button_label': 'Guardar',
                'cancel_button_label': 'Cancelar'
            }
        
        modal = self.modals[0]
        return {
            'title': modal.get('title', f'Nuevo {self.page_title}'),
            'size': modal.get('size', 'lg'),
            'submit_button_label': modal.get('submit_button_label', 'Guardar'),
            'cancel_button_label': modal.get('cancel_button_label', 'Cancelar'),
            'close_on_backdrop': modal.get('close_on_backdrop', True),
            'close_on_escape': modal.get('close_on_escape', True),
        }


class ConfigLoader:
    """Loads page configuration from the database using page_effective_config."""
    
    @staticmethod
    def load_page_config(table_name: str, user=None) -> Optional[PageConfig]:
        """
        Load effective page configuration for a table.
        
        Args:
            table_name: Name of the database table
            user: User for the request (optional, uses AnonymousUser if not provided)
            
        Returns:
            PageConfig object with the loaded configuration, or None if not found
        """
        try:
            # Find the page for this table
            page = Page.objects.filter(slug=table_name).first()
            if not page:
                # Try to find by db_table name as fallback
                db_table = DbTable.objects.filter(name=table_name).first()
                if db_table:
                    page = Page.objects.filter(db_table=db_table).first()
            
            if not page:
                return None
            
            # Create a fake request to call page_effective_config
            rf = RequestFactory()
            fake_request = rf.get('/_internal/', HTTP_HOST='localhost')
            fake_request.user = user or User.objects.first() or AnonymousUser()
            
            # Get the effective configuration
            response = page_effective_config(fake_request, page.id)
            
            if response.status_code != 200:
                return None
            
            # Parse the JSON response
            config_data = json.loads(response.content.decode('utf-8'))
            
            return PageConfig(config_data)
            
        except Exception as e:
            # Log the error but don't crash the generation
            print(f"Warning: Could not load config for table {table_name}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def load_page_config_by_id(page_id: int, user=None) -> Optional[PageConfig]:
        """
        Load effective page configuration by page ID.
        
        Args:
            page_id: ID of the page
            user: User for the request (optional, uses AnonymousUser if not provided)
            
        Returns:
            PageConfig object with the loaded configuration, or None if not found
        """
        try:
            # Create a fake request to call page_effective_config
            rf = RequestFactory()
            fake_request = rf.get('/_internal/', HTTP_HOST='localhost')
            fake_request.user = user or User.objects.first() or AnonymousUser()
            
            # Get the effective configuration
            response = page_effective_config(fake_request, page_id)
            
            if response.status_code != 200:
                return None
            
            # Parse the JSON response
            config_data = json.loads(response.content.decode('utf-8'))
            
            return PageConfig(config_data)
            
        except Exception as e:
            # Log the error but don't crash the generation
            print(f"Warning: Could not load config for page {page_id}: {e}")
            return None
    
    @staticmethod
    def get_fallback_config(table_name: str, table_alias: str = None) -> PageConfig:
        """
        Create a fallback configuration when the real config cannot be loaded.
        This mimics the old behavior but with cleaner structure.
        """
        # Create basic fallback data
        page_title = (table_alias or table_name).replace('_', ' ').title()
        
        fallback_data = {
            'page': {
                'title': page_title,
                'slug': table_name,
            },
            'table': {
                'name': table_name,
                'title': page_title,
            },
            'columns': [],  # Will be empty, forcing field introspection
            'modals': [{
                'title': f'Nuevo {page_title}',
                'size': 'lg',
                'submit_button_label': 'Guardar',
                'cancel_button_label': 'Cancelar',
                'form': {
                    'fields': []  # Will be empty, forcing field introspection
                }
            }]
        }
        
        return PageConfig(fallback_data)
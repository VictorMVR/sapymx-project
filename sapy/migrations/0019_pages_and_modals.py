from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sapy', '0018_applicationtable'),
    ]

    operations = [
        migrations.CreateModel(
            name='Page',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(help_text='Identificador URL, ej: productos', max_length=150, unique=True)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('source_type', models.CharField(choices=[('dbtable', 'Desde tabla BD'), ('custom', 'Personalizada')], default='dbtable', max_length=20)),
                ('icon', models.CharField(blank=True, max_length=100)),
                ('layout', models.CharField(blank=True, max_length=100)),
                ('route_path', models.CharField(help_text='Ruta relativa ej: /productos/', max_length=200, unique=True)),
                ('activo', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('db_table', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sapy.dbtable')),
            ],
            options={
                'db_table': 'app_generator_pages',
                'ordering': ['slug'],
                'verbose_name': 'Página',
                'verbose_name_plural': 'Páginas',
            },
        ),
        migrations.CreateModel(
            name='Modal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('purpose', models.CharField(choices=[('create_edit', 'Crear/Editar'), ('custom', 'Personalizado')], default='create_edit', max_length=20)),
                ('title', models.CharField(max_length=200)),
                ('size', models.CharField(choices=[('sm', 'Pequeño'), ('md', 'Mediano'), ('lg', 'Grande'), ('xl', 'Extra grande'), ('full', 'Pantalla completa')], default='lg', max_length=10)),
                ('icon', models.CharField(blank=True, max_length=100)),
                ('close_on_backdrop', models.BooleanField(default=True)),
                ('close_on_escape', models.BooleanField(default=True)),
                ('prevent_close_on_enter', models.BooleanField(default=False)),
                ('prevent_close_on_space', models.BooleanField(default=False)),
                ('submit_button_label', models.CharField(default='Guardar', max_length=100)),
                ('submit_button_icon', models.CharField(blank=True, max_length=100)),
                ('cancel_button_label', models.CharField(default='Cancelar', max_length=100)),
                ('activo', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'app_generator_modals',
                'verbose_name': 'Modal',
                'verbose_name_plural': 'Modales',
            },
        ),
        migrations.CreateModel(
            name='PageModal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order_index', models.IntegerField(default=0)),
                ('activo', models.BooleanField(default=True)),
                ('modal', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='pages', to='sapy.modal')),
                ('page', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='page_modals', to='sapy.page')),
            ],
            options={
                'db_table': 'app_generator_pages_modals',
                'verbose_name': 'Modal de Página',
                'verbose_name_plural': 'Modales de Página',
                'unique_together': {('page', 'modal')},
            },
        ),
        migrations.CreateModel(
            name='ModalForm',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('layout_columns_per_row', models.PositiveIntegerField(default=2)),
                ('activo', models.BooleanField(default=True)),
                ('db_table', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sapy.dbtable')),
                ('modal', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='form', to='sapy.modal')),
            ],
            options={
                'db_table': 'app_generator_modal_forms',
                'verbose_name': 'Formulario de Modal',
                'verbose_name_plural': 'Formularios de Modales',
            },
        ),
        migrations.CreateModel(
            name='PageTable',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('searchable', models.BooleanField(default=True)),
                ('export_csv', models.BooleanField(default=True)),
                ('export_xlsx', models.BooleanField(default=True)),
                ('export_pdf', models.BooleanField(default=True)),
                ('page_size', models.PositiveIntegerField(default=25)),
                ('default_sort', models.JSONField(default=dict, help_text='Ej: {"by":"id","dir":"desc"}')),
                ('show_inactive', models.BooleanField(default=False)),
                ('activo', models.BooleanField(default=True)),
                ('db_table', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='sapy.dbtable')),
                ('page', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='page_tables', to='sapy.page')),
            ],
            options={
                'db_table': 'app_generator_page_tables',
                'verbose_name': 'Tabla de Página',
                'verbose_name_plural': 'Tablas de Página',
                'unique_together': {('page', 'db_table')},
            },
        ),
        migrations.CreateModel(
            name='PageTableColumnOverride',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order_index', models.IntegerField(blank=True, null=True)),
                ('width_px', models.IntegerField(blank=True, null=True)),
                ('title_override', models.CharField(blank=True, max_length=200, null=True)),
                ('format', models.CharField(blank=True, choices=[('text', 'Texto'), ('currency', 'Moneda'), ('decimal', 'Decimal'), ('percent', 'Porcentaje'), ('date', 'Fecha'), ('datetime', 'Fecha/Hora'), ('button', 'Botón'), ('badge', 'Insignia'), ('link', 'Enlace')], max_length=20, null=True)),
                ('visible', models.BooleanField(default=True)),
                ('is_action_button', models.BooleanField(default=False)),
                ('action_type', models.CharField(blank=True, choices=[('edit', 'Editar'), ('delete', 'Eliminar'), ('toggle_active', 'Alternar Activo'), ('custom', 'Personalizada')], max_length=20, null=True)),
                ('link_url_template', models.TextField(blank=True, null=True)),
                ('activo', models.BooleanField(default=True)),
                ('db_column', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='sapy.dbcolumn')),
                ('form_question', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='sapy.formquestion')),
                ('page_table', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='column_overrides', to='sapy.pagetable')),
                ('ui_column', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='sapy.uicolumn')),
            ],
            options={
                'db_table': 'app_generator_page_table_col_overrides',
                'verbose_name': 'Override de Columna de Tabla',
                'verbose_name_plural': 'Overrides de Columnas de Tabla',
            },
        ),
        migrations.CreateModel(
            name='ModalFormFieldOverride',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order_index', models.IntegerField(blank=True, null=True)),
                ('label_override', models.CharField(blank=True, max_length=200, null=True)),
                ('placeholder', models.CharField(blank=True, max_length=200, null=True)),
                ('width_fraction', models.CharField(choices=[('1/1', '1/1'), ('1/2', '1/2'), ('1/3', '1/3'), ('2/3', '2/3'), ('1/4', '1/4'), ('3/4', '3/4')], default='1/1', max_length=10)),
                ('required_override', models.BooleanField(blank=True, null=True)),
                ('help_text', models.CharField(blank=True, max_length=300, null=True)),
                ('visible', models.BooleanField(default=True)),
                ('default_value', models.JSONField(blank=True, null=True)),
                ('activo', models.BooleanField(default=True)),
                ('db_column', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='sapy.dbcolumn')),
                ('form_question', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='sapy.formquestion')),
                ('modal_form', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='field_overrides', to='sapy.modalform')),
            ],
            options={
                'db_table': 'app_generator_modal_form_field_overrides',
                'verbose_name': 'Override de Campo de Formulario',
                'verbose_name_plural': 'Overrides de Campos de Formulario',
            },
        ),
        migrations.CreateModel(
            name='PageShortcut',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=150)),
                ('icon', models.CharField(blank=True, max_length=100)),
                ('order_index', models.IntegerField(default=0)),
                ('activo', models.BooleanField(default=True)),
                ('page', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shortcuts', to='sapy.page')),
                ('target_page', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='incoming_shortcuts', to='sapy.page')),
            ],
            options={
                'db_table': 'app_generator_page_shortcuts',
                'verbose_name': 'Acceso Directo de Página',
                'verbose_name_plural': 'Accesos Directos de Página',
            },
        ),
    ]



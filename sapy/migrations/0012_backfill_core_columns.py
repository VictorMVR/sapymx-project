from django.db import migrations


def ensure_core_columns(apps, schema_editor):
    DbTable = apps.get_model('sapy', 'DbTable')
    DbColumn = apps.get_model('sapy', 'DbColumn')
    DbColumnTemplate = apps.get_model('sapy', 'DbColumnTemplate')

    # Templates helper
    templates = {t.name: t for t in DbColumnTemplate.objects.all()}

    def add_col(table, name, defaults):
        if DbColumn.objects.filter(table_id=table.id, name=name).exists():
            return 0
        pos = (DbColumn.objects.filter(table_id=table.id)
               .order_by('-position').values_list('position', flat=True).first() or 0) + 1
        data = {
            'table_id': table.id,
            'name': name,
            'data_type': defaults.get('data_type', 'varchar'),
            'length': defaults.get('length'),
            'numeric_precision': defaults.get('numeric_precision'),
            'numeric_scale': defaults.get('numeric_scale'),
            'is_nullable': defaults.get('is_nullable', False),
            'is_unique': defaults.get('is_unique', False),
            'is_index': defaults.get('is_index', False),
            'is_primary_key': False,
            'is_auto_increment': False,
            'default_value': defaults.get('default_value', ''),
            'position': pos,
            'notes': defaults.get('notes', ''),
        }
        DbColumn.objects.create(**data)
        return 1

    added = 0
    for table in DbTable.objects.all():
        # activo en todas las tablas
        added += add_col(table, 'activo', {
            'data_type': templates.get('activo').data_type if templates.get('activo') else 'boolean',
            'is_nullable': False,
            'is_index': True,
            'default_value': templates.get('activo').default_value if templates.get('activo') else 'true',
            'notes': 'Columna de activación lógica',
        })

        if table.table_kind == 'transaction':
            # created_at
            added += add_col(table, 'created_at', {
                'data_type': templates.get('created_at').data_type if templates.get('created_at') else 'timestamp',
                'is_nullable': False,
                'default_value': templates.get('created_at').default_value if templates.get('created_at') else 'now()',
                'notes': 'Auto timestamp al crear',
            })
            # updated_at
            added += add_col(table, 'updated_at', {
                'data_type': templates.get('updated_at').data_type if templates.get('updated_at') else 'timestamp',
                'is_nullable': False,
                'default_value': templates.get('updated_at').default_value if templates.get('updated_at') else 'now()',
                'notes': 'Auto timestamp al actualizar',
            })
            # id_auth_user
            added += add_col(table, 'id_auth_user', {
                'data_type': templates.get('id_auth_user').data_type if templates.get('id_auth_user') else 'integer',
                'is_nullable': False,
                'is_index': True,
                'notes': 'Usuario autenticado',
            })


class Migration(migrations.Migration):
    dependencies = [
        ('sapy', '0011_uicolumn_is_toggle'),
    ]

    operations = [
        migrations.RunPython(ensure_core_columns, migrations.RunPython.noop),
    ]



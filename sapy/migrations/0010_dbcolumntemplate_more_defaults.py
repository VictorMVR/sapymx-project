from django.db import migrations


def seed_more_templates(apps, schema_editor):
    DbColumnTemplate = apps.get_model('sapy', 'DbColumnTemplate')

    def upsert(name, data):
        DbColumnTemplate.objects.update_or_create(name=name, defaults=data)

    # activo: boolean not null default true
    upsert('activo', {
        'data_type': 'boolean',
        'length': None,
        'numeric_precision': None,
        'numeric_scale': None,
        'is_nullable': False,
        'is_unique': False,
        'is_index': True,
        'is_primary_key': False,
        'is_auto_increment': False,
        'default_value': 'true',
        'notes': 'Columna de activación lógica',
    })

    # created_at: timestamp not null default now()
    upsert('created_at', {
        'data_type': 'timestamp',
        'length': None,
        'numeric_precision': None,
        'numeric_scale': None,
        'is_nullable': False,
        'is_unique': False,
        'is_index': False,
        'is_primary_key': False,
        'is_auto_increment': False,
        'default_value': 'now()',
        'notes': 'Auto timestamp al crear',
    })

    # updated_at: timestamp not null default now()
    upsert('updated_at', {
        'data_type': 'timestamp',
        'length': None,
        'numeric_precision': None,
        'numeric_scale': None,
        'is_nullable': False,
        'is_unique': False,
        'is_index': False,
        'is_primary_key': False,
        'is_auto_increment': False,
        'default_value': 'now()',
        'notes': 'Auto timestamp al actualizar',
    })

    # id_auth_user: integer not null
    upsert('id_auth_user', {
        'data_type': 'integer',
        'length': None,
        'numeric_precision': None,
        'numeric_scale': None,
        'is_nullable': False,
        'is_unique': False,
        'is_index': True,
        'is_primary_key': False,
        'is_auto_increment': False,
        'default_value': '',
        'notes': 'Usuario autenticado',
    })


class Migration(migrations.Migration):
    dependencies = [
        ('sapy', '0009_uicolumn_uifield'),
    ]

    operations = [
        migrations.RunPython(seed_more_templates, migrations.RunPython.noop),
    ]



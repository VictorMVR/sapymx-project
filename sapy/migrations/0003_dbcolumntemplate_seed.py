from django.db import migrations


def seed_column_templates(apps, schema_editor):
    DbColumnTemplate = apps.get_model('sapy', 'DbColumnTemplate')

    # id: PK entero autoincremental
    DbColumnTemplate.objects.update_or_create(
        name='id',
        defaults={
            'data_type': 'integer',
            'length': None,
            'numeric_precision': None,
            'numeric_scale': None,
            'is_nullable': False,
            'is_unique': True,
            'is_index': True,
            'is_primary_key': True,
            'is_auto_increment': True,
            'default_value': '',
            'notes': 'Columna primaria estándar',
        }
    )

    # nombre: texto requerido para catálogos
    DbColumnTemplate.objects.update_or_create(
        name='nombre',
        defaults={
            'data_type': 'varchar',
            'length': 150,
            'numeric_precision': None,
            'numeric_scale': None,
            'is_nullable': False,
            'is_unique': False,
            'is_index': True,
            'is_primary_key': False,
            'is_auto_increment': False,
            'default_value': '',
            'notes': 'Nombre descriptivo para tablas de catálogo',
        }
    )


class Migration(migrations.Migration):
    dependencies = [
        ('sapy', '0004_dbcolumntemplate_alter_dbtable_options_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_column_templates, migrations.RunPython.noop),
    ]



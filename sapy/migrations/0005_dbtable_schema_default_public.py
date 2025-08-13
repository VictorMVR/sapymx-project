from django.db import migrations, models


def backfill_schema_public(apps, schema_editor):
    DbTable = apps.get_model('sapy', 'DbTable')
    DbTable.objects.filter(schema_name__isnull=True).update(schema_name='public')
    DbTable.objects.filter(schema_name='').update(schema_name='public')


class Migration(migrations.Migration):
    dependencies = [
        ('sapy', '0004_dbcolumntemplate_alter_dbtable_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dbtable',
            name='schema_name',
            field=models.CharField(blank=True, default='public', help_text='Nombre del esquema (opcional, ej: public)', max_length=100),
        ),
        migrations.RunPython(backfill_schema_public, migrations.RunPython.noop),
    ]




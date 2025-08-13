from django.db import migrations, models


def backfill_positions(apps, schema_editor):
    DbColumn = apps.get_model('sapy', 'DbColumn')
    # Normalizar posiciones a partir de 1 por cada tabla
    from collections import defaultdict
    by_table = defaultdict(list)
    for col in DbColumn.objects.all().order_by('table_id', 'position', 'id'):
        by_table[col.table_id].append(col)
    for cols in by_table.values():
        for idx, col in enumerate(cols, start=1):
            if col.position != idx:
                col.position = idx
                col.save(update_fields=['position'])


class Migration(migrations.Migration):
    dependencies = [
        ('sapy', '0006_merge_20250812_0213'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dbcolumn',
            name='position',
            field=models.PositiveIntegerField(default=1, help_text='Orden de la columna (1..N)'),
        ),
        migrations.RunPython(backfill_positions, migrations.RunPython.noop),
    ]




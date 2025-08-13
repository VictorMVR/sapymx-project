from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sapy', '0020_page_table_title_and_column_alignment'),
    ]

    operations = [
        migrations.AddField(
            model_name='modal',
            name='external_template_path',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='modal',
            name='form_mode',
            field=models.CharField(choices=[('none', 'Sin formulario'), ('auto', 'Formulario automático'), ('external', 'Formulario externo')], default='auto', max_length=10),
        ),
    ]



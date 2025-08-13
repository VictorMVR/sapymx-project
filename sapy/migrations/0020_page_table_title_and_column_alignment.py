from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sapy', '0019_pages_and_modals'),
    ]

    operations = [
        migrations.AddField(
            model_name='pagetable',
            name='title',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='pagetablecolumnoverride',
            name='alignment',
            field=models.CharField(blank=True, choices=[('left', 'left'), ('center', 'center'), ('right', 'right')], max_length=10, null=True),
        ),
    ]



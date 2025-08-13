# Generated manually to update width_fraction format

from django.db import migrations

def convert_width_fraction_format(apps, schema_editor):
    """Convierte el formato de width_fraction de 1/1 a 1-1"""
    ModalFormFieldOverride = apps.get_model('sapy', 'ModalFormFieldOverride')
    
    # Mapeo de formato antiguo a nuevo
    format_mapping = {
        '1/1': '1-1',
        '1/2': '1-2', 
        '1/3': '1-3',
        '2/3': '2-3',
        '1/4': '1-4',
        '3/4': '3-4'
    }
    
    # Actualizar todos los registros existentes
    for override in ModalFormFieldOverride.objects.all():
        if override.width_fraction in format_mapping:
            override.width_fraction = format_mapping[override.width_fraction]
            override.save()

def reverse_convert_width_fraction_format(apps, schema_editor):
    """Revierte el formato de width_fraction de 1-1 a 1/1"""
    ModalFormFieldOverride = apps.get_model('sapy', 'ModalFormFieldOverride')
    
    # Mapeo inverso
    format_mapping = {
        '1-1': '1/1',
        '1-2': '1/2',
        '1-3': '1/3', 
        '2-3': '2/3',
        '1-4': '1/4',
        '3-4': '3/4'
    }
    
    # Actualizar todos los registros
    for override in ModalFormFieldOverride.objects.all():
        if override.width_fraction in format_mapping:
            override.width_fraction = format_mapping[override.width_fraction]
            override.save()

class Migration(migrations.Migration):

    dependencies = [
        ('sapy', '0021_modal_form_mode'),
    ]

    operations = [
        migrations.RunPython(convert_width_fraction_format, reverse_convert_width_fraction_format),
    ]

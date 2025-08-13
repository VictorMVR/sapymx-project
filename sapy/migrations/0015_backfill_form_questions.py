# Generated migration for backfilling FormQuestion

from django.db import migrations

def create_form_questions_for_existing_columns(apps, schema_editor):
    """Crear FormQuestion para todas las DbColumn existentes que no las tengan."""
    DbColumn = apps.get_model('sapy', 'DbColumn')
    FormQuestion = apps.get_model('sapy', 'FormQuestion')
    
    # Importar las funciones necesarias desde models
    from sapy.models import _derive_form_question_defaults, _title_from_name
    
    # Procesar todas las columnas existentes
    for db_column in DbColumn.objects.all():
        # Verificar si ya tiene FormQuestion
        if not FormQuestion.objects.filter(db_column=db_column).exists():
            # Evitar columnas técnicas
            if db_column.name in ['created_at', 'updated_at', 'id_auth_user']:
                continue
                
            try:
                # Usar la función de defaults pero adaptada para la migración
                name = db_column.name
                label = _title_from_name(name)
                
                # Valores por defecto simplificados para la migración
                question_defaults = {
                    'db_column': db_column,
                    'name': name,
                    'question_text': label + ':',
                    'help_text': '',
                    'input_type': 'text',  # Default simple
                    'required': not db_column.is_nullable,
                    'validation_rule': 'none',
                    'validation_value': '',
                    'options_source': 'none',
                    'options_custom': '',
                    'fk_table': None,
                    'fk_value_field': 'id',
                    'fk_label_field': 'nombre',
                    'css_class': 'col-md-6',
                    'placeholder': f'Ingrese {label.lower()}',
                    'default_value': db_column.default_value or '',
                    'order': db_column.position or 1,
                    'section': '',
                    'is_active': True,
                }
                
                # Ajustar según tipo de dato
                if db_column.data_type in ['integer', 'bigint', 'smallint', 'numeric']:
                    question_defaults['input_type'] = 'number'
                    if db_column.is_primary_key:
                        question_defaults['input_type'] = 'hidden'
                        question_defaults['is_active'] = False
                elif db_column.data_type == 'text':
                    question_defaults['input_type'] = 'textarea'
                    question_defaults['css_class'] = 'col-md-12'
                elif db_column.data_type == 'boolean':
                    question_defaults['input_type'] = 'checkbox'
                    question_defaults['css_class'] = 'col-md-3'
                    question_defaults['placeholder'] = ''
                elif db_column.data_type == 'date':
                    question_defaults['input_type'] = 'date'
                    question_defaults['css_class'] = 'col-md-4'
                    question_defaults['placeholder'] = ''
                elif db_column.data_type == 'timestamp':
                    question_defaults['input_type'] = 'datetime-local'
                    question_defaults['css_class'] = 'col-md-6'
                    question_defaults['placeholder'] = ''
                
                # Casos especiales
                if name == 'activo':
                    question_defaults['input_type'] = 'checkbox'
                    question_defaults['css_class'] = 'col-md-3'
                    question_defaults['placeholder'] = ''
                elif 'email' in name:
                    question_defaults['input_type'] = 'email'
                    question_defaults['validation_rule'] = 'email'
                elif 'password' in name or 'contrasena' in name:
                    question_defaults['input_type'] = 'password'
                    question_defaults['validation_rule'] = 'min_length'
                    question_defaults['validation_value'] = '8'
                elif name.startswith('id_') and name != 'id':
                    question_defaults['input_type'] = 'select'
                    question_defaults['options_source'] = 'fk'
                    question_defaults['placeholder'] = f'Seleccione {label.lower()}'
                
                FormQuestion.objects.create(**question_defaults)
                
            except Exception as e:
                # No fallar la migración por errores individuales
                print(f"Error creando FormQuestion para {db_column.name}: {e}")
                continue

def reverse_create_form_questions(apps, schema_editor):
    """Eliminar FormQuestion creadas por esta migración."""
    FormQuestion = apps.get_model('sapy', 'FormQuestion')
    FormQuestion.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('sapy', '0014_add_form_question'),
    ]

    operations = [
        migrations.RunPython(
            create_form_questions_for_existing_columns,
            reverse_create_form_questions
        ),
    ]






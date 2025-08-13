# forms.py
from django import forms
from django.db import models
from django.core.exceptions import ValidationError
from .models import Application, ApplicationDependency, ApplicationEnvironment, DbTable, DbColumn, DbTableColumn
import re
import secrets

class ApplicationForm(forms.ModelForm):
    """Formulario principal para crear/editar aplicaciones"""
    
    # Dependencias básicas que se agregarán por defecto
    add_default_dependencies = forms.BooleanField(
        required=False,
        initial=True,
        label='Agregar dependencias básicas',
        help_text='Django, psycopg2, gunicorn, python-decouple, etc.'
    )
    
    # Campo para confirmar la contraseña de la BD
    db_password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirmar contraseña',
            'autocomplete': 'new-password'
        }),
        label='Confirmar contraseña BD',
        required=False
    )
    
    class Meta:
        model = Application
        fields = [
            'name', 'display_name', 'description',
            'domain', 'subdomain', 'port',
            'db_engine', 'db_name', 'db_user', 'db_password',
            'db_host', 'db_port',
            'base_path', 'virtualenv_path',
            'python_version', 'django_version',
            'django_debug', 'django_allowed_hosts'
        ]
        
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ej: sistema_ventas',
                'pattern': '^[a-z][a-z0-9_]*$'
            }),
            'display_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ej: Sistema de Ventas'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción de la aplicación...'
            }),
            'domain': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ej: ventas.miempresa.com'
            }),
            'subdomain': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Opcional'
            }),
            'port': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1024,
                'max': 65535
            }),
            'db_engine': forms.Select(attrs={
                'class': 'form-control'
            }),
            'db_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ej: app_bd'
            }),
            'db_user': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ej: app_admin',
                'autocomplete': 'off',
                'autocapitalize': 'none',
                'autocorrect': 'off',
                'spellcheck': 'false'
            }),
            'db_password': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Contraseña segura',
                'autocomplete': 'new-password'
            }),
            'db_host': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'db_port': forms.NumberInput(attrs={
                'class': 'form-control'
            }),
            'base_path': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '/srv/'
            }),
            'virtualenv_path': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Dejar vacío para usar default'
            }),
            'python_version': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '3.11'
            }),
            'django_version': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '5.0'
            }),
            'django_debug': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'django_allowed_hosts': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'localhost, 127.0.0.1, midominio.com'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Default puerto DO Postgres
        if not self.instance.pk:
            self.fields['db_port'].initial = 25060
        
        # Generar secret key automáticamente si es nueva aplicación
        if not self.instance.pk:
            self.fields['django_secret_key'] = forms.CharField(
                widget=forms.HiddenInput(),
                initial=secrets.token_urlsafe(50),
                required=False
            )
            
            # Sugerencias db_name y db_user basadas en el nombre de la app
            name_val = ''
            if 'name' in self.data and self.data['name']:
                name_val = self.data['name']
            elif getattr(self.instance, 'name', None):
                name_val = self.instance.name
            if name_val:
                self.fields['db_name'].initial = f"{name_val}_bd"
                self.fields['db_user'].initial = f"{name_val}_admin"
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            # Validar formato
            if not re.match(r'^[a-z][a-z0-9_]*$', name):
                raise ValidationError(
                    'El nombre debe empezar con letra minúscula y solo contener letras, números y guiones bajos'
                )
            # Validar unicidad (excepto para la misma instancia)
            qs = Application.objects.filter(name=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError('Ya existe una aplicación con este nombre')
        return name
    
    def clean_db_name(self):
        db_name = self.cleaned_data.get('db_name')
        if db_name:
            if not re.match(r'^[a-z][a-z0-9_]*$', db_name):
                raise ValidationError(
                    'El nombre de BD debe empezar con letra minúscula y solo contener letras, números y guiones bajos'
                )
        return db_name
    
    def clean_domain(self):
        domain = self.cleaned_data.get('domain')
        if domain:
            # Quitar http:// o https:// si lo incluyen
            domain = re.sub(r'^https?://', '', domain)
            # Validar formato básico de dominio
            if not re.match(r'^[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,}$', domain, re.IGNORECASE):
                raise ValidationError('Formato de dominio inválido')
        return domain
    
    def clean_base_path(self):
        base_path = self.cleaned_data.get('base_path')
        if base_path:
            # Asegurar que termine con /
            if not base_path.endswith('/'):
                base_path += '/'
        return base_path
    
    def clean(self):
        cleaned_data = super().clean()
        db_password = cleaned_data.get('db_password')
        db_password_confirm = cleaned_data.get('db_password_confirm')
        
        # Solo validar confirmación si es nueva aplicación o si se cambió la contraseña
        if not self.instance.pk or db_password:
            if db_password != db_password_confirm:
                raise ValidationError({
                    'db_password_confirm': 'Las contraseñas no coinciden'
                })
        
        # Ajustar puerto de BD según el motor
        db_engine = cleaned_data.get('db_engine')
        if db_engine == 'postgresql' and not self.data.get('db_port'):
            cleaned_data['db_port'] = 5432
        elif db_engine == 'mysql' and not self.data.get('db_port'):
            cleaned_data['db_port'] = 3306
        
        return cleaned_data
    
    def save(self, commit=True):
        application = super().save(commit=False)
        
        # Generar secret key si no existe
        if not application.django_secret_key:
            application.django_secret_key = secrets.token_urlsafe(50)
        
        if commit:
            application.save()
            
            # Agregar dependencias por defecto si se solicitó
            if self.cleaned_data.get('add_default_dependencies'):
                self.add_default_dependencies(application)
        
        return application
    
    def add_default_dependencies(self, application):
        """Agrega las dependencias básicas de Django"""
        default_deps = [
            ('Django', self.cleaned_data.get('django_version', '5.0')),
            ('psycopg2-binary', ''),
            ('gunicorn', ''),
            ('python-decouple', ''),
            ('Pillow', ''),
            ('django-crispy-forms', ''),
            ('crispy-bootstrap5', ''),
            ('django-environ', ''),
            ('whitenoise', ''),
            ('celery', ''),
            ('redis', ''),
        ]
        
        for package, version in default_deps:
            ApplicationDependency.objects.get_or_create(
                application=application,
                package_name=package,
                defaults={'version': version}
            )


class DependencyFormSet(forms.BaseModelFormSet):
    """FormSet para manejar múltiples dependencias"""
    
    def clean(self):
        if any(self.errors):
            return
        
        packages = []
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                package = form.cleaned_data.get('package_name')
                if package:
                    if package in packages:
                        raise ValidationError(f'Paquete duplicado: {package}')
                    packages.append(package)


class QuickDeployForm(forms.Form):
    """Formulario simple para despliegue rápido"""
    
    confirm = forms.BooleanField(
        required=True,
        label='Confirmo que quiero instalar esta aplicación',
        help_text='Este proceso creará carpetas, base de datos y configurará el servidor'
    )
    create_superuser = forms.BooleanField(
        required=False,
        initial=True,
        label='Crear superusuario admin',
        help_text='Usuario: admin, Contraseña: admin123 (cambiar después)'
    )
    run_migrations = forms.BooleanField(
        required=False,
        initial=True,
        label='Ejecutar migraciones',
        help_text='Crear tablas en la base de datos'
    )
    install_sample_data = forms.BooleanField(
        required=False,
        initial=False,
        label='Instalar datos de ejemplo',
        help_text='Cargar datos de prueba en la aplicación'
    )


# ==== Formularios para DB schema ====

class DbTableForm(forms.ModelForm):
    def clean_name(self):
        name = self.cleaned_data.get('name', '')
        return (name or '').strip().lower()

    def clean_alias(self):
        alias = self.cleaned_data.get('alias', '')
        return (alias or '').strip().lower()

    def clean_schema_name(self):
        schema = self.cleaned_data.get('schema_name', '')
        schema = (schema or 'public').strip().lower()
        if not schema:
            schema = 'public'
        return schema

    class Meta:
        model = DbTable
        fields = ['name', 'alias', 'description', 'schema_name', 'table_kind']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'alias': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'schema_name': forms.TextInput(attrs={'class': 'form-control'}),
            'table_kind': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and not self.initial.get('schema_name'):
            self.fields['schema_name'].initial = 'public'


class DbColumnForm(forms.ModelForm):
    """Formulario para crear y editar columnas globales."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limpia valores por defecto para no prellenar como 'id'
        if not self.instance or not self.instance.pk:
            for field in ['name', 'length', 'numeric_precision', 'numeric_scale', 'default_value', 'notes']:
                if field in self.fields:
                    self.fields[field].initial = None
            # Desmarcar flags
            for field in ['is_nullable', 'is_unique', 'is_index', 'is_primary_key', 'is_auto_increment']:
                if field in self.fields:
                    self.fields[field].initial = False

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip().lower()
        return name

    def clean(self):
        cleaned = super().clean()
        name = cleaned.get('name') or ''
        # Si es FK por convención id_<tabla>
        if name.startswith('id_'):
            cleaned['data_type'] = 'integer'
        return cleaned

    class Meta:
        model = DbColumn
        fields = [
            'name', 'data_type', 'length', 'numeric_precision', 'numeric_scale',
            'is_nullable', 'is_unique', 'is_index', 'is_primary_key', 'is_auto_increment',
            'default_value', 'notes'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'data_type': forms.Select(attrs={'class': 'form-select'}),
            'length': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'numeric_precision': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'numeric_scale': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'is_nullable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_index': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_primary_key': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_auto_increment': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'default_value': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


# Nota: DbColumnFormSet ya no se usa porque DbColumn ya no tiene relación directa con DbTable
# Ahora se usa DbTableColumn para las relaciones tabla-columna

class DbTableColumnForm(forms.ModelForm):
    """Formulario para asignar columnas a tablas."""
    
    class Meta:
        model = DbTableColumn
        fields = [
            'column', 'position', 'is_nullable', 'is_unique', 'is_index', 
            'is_primary_key', 'is_auto_increment', 'default_value', 
            'references_table', 'on_delete', 'notes'
        ]
        widgets = {
            'column': forms.Select(attrs={'class': 'form-select'}),
            'position': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'is_nullable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_unique': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_index': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_primary_key': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_auto_increment': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'default_value': forms.TextInput(attrs={'class': 'form-control'}),
            'references_table': forms.Select(attrs={'class': 'form-select'}),
            'on_delete': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


# DbColumnTemplateForm eliminado - ya no es necesario

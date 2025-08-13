# models.py
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import uuid
from django.urls import reverse

class Application(models.Model):
    """Modelo principal para registrar aplicaciones ERP generadas"""
    
    STATUS_CHOICES = [
        ('draft', 'En Diseño'),
        ('generating', 'Generando'),
        ('generated', 'Generada'),
        ('installing', 'Instalando'),
        ('deployed', 'Desplegada'),
        ('error', 'Error'),
        ('maintenance', 'Mantenimiento'),
    ]
    
    DATABASE_CHOICES = [
        ('postgresql', 'PostgreSQL'),
        ('mysql', 'MySQL'),
        ('sqlite3', 'SQLite3'),
    ]
    
    # Identificación básica
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(
        max_length=100, 
        unique=True,
        validators=[RegexValidator(
            regex='^[a-z][a-z0-9_]*$',
            message='El nombre debe empezar con letra minúscula, solo letras, números y guiones bajos'
        )],
        help_text='Nombre técnico de la aplicación (sin espacios, ej: sistema_ventas)'
    )
    display_name = models.CharField(
        max_length=200,
        help_text='Nombre visible de la aplicación (ej: Sistema de Ventas)'
    )
    description = models.TextField(blank=True)
    
    # Configuración del dominio
    domain = models.CharField(
        max_length=255,
        unique=True,
        help_text='Dominio completo (ej: ventas.miempresa.com)'
    )
    subdomain = models.CharField(
        max_length=100,
        blank=True,
        help_text='Subdomain solo si aplica'
    )
    port = models.IntegerField(
        default=8000,
        validators=[MinValueValidator(1024), MaxValueValidator(65535)],
        help_text='Puerto para el servidor de desarrollo'
    )
    
    # Configuración de base de datos
    db_engine = models.CharField(
        max_length=20,
        choices=DATABASE_CHOICES,
        default='postgresql'
    )
    db_name = models.CharField(
        max_length=100,
        validators=[RegexValidator(
            regex='^[a-z][a-z0-9_]*$',
            message='Nombre de BD: solo minúsculas, números y guiones bajos'
        )]
    )
    db_user = models.CharField(max_length=100)
    db_password = models.CharField(max_length=255)
    db_host = models.CharField(max_length=255, default='localhost')
    db_port = models.IntegerField(default=5432)
    
    # Rutas del sistema
    base_path = models.CharField(
        max_length=500,
        help_text='Ruta base donde se instalará (ej: /home/usuario/apps/)'
    )
    virtualenv_path = models.CharField(
        max_length=500,
        blank=True,
        help_text='Ruta del entorno virtual (se genera automáticamente si está vacío)'
    )
    
    # Configuración Django
    django_secret_key = models.CharField(
        max_length=255,
        blank=True,
        help_text='Se genera automáticamente si está vacío'
    )
    django_debug = models.BooleanField(default=True)
    django_allowed_hosts = models.TextField(
        default='*',
        help_text='Hosts permitidos separados por comas'
    )
    
    # Estado y metadata
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='applications_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    installed_at = models.DateTimeField(null=True, blank=True)
    
    # Información adicional
    python_version = models.CharField(
        max_length=20,
        default='3.11',
        help_text='Versión de Python a usar'
    )
    django_version = models.CharField(
        max_length=20,
        default='5.0',
        help_text='Versión de Django a instalar'
    )
    
    class Meta:
        db_table = 'app_generator_applications'
        ordering = ['-created_at']
        verbose_name = 'Aplicación'
        verbose_name_plural = 'Aplicaciones'
    
    def __str__(self):
        return self.display_name or self.name

    def get_absolute_url(self):
        return reverse('sapy:application_detail', kwargs={'pk': self.pk})

    def get_deployment_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, 'Desconocido')

    def get_database_display(self):
        return dict(self.DATABASE_CHOICES).get(self.db_engine, 'Desconocido')


class ApplicationDependency(models.Model):
    """Dependencias Python/pip para cada aplicación"""
    
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='dependencies'
    )
    package_name = models.CharField(max_length=100)
    version = models.CharField(
        max_length=50,
        blank=True,
        help_text='Versión específica o dejar vacío para la última'
    )
    is_required = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'app_generator_dependencies'
        unique_together = ['application', 'package_name']
        ordering = ['package_name']
    
    def __str__(self):
        if self.version:
            return f"{self.package_name}=={self.version}"
        return self.package_name


class ApplicationEnvironment(models.Model):
    """Variables de entorno para cada aplicación"""
    
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='environment_vars'
    )
    key = models.CharField(max_length=100)
    value = models.TextField()
    is_secret = models.BooleanField(
        default=False,
        help_text='Marcar si contiene información sensible'
    )
    
    class Meta:
        db_table = 'app_generator_environment'
        unique_together = ['application', 'key']
        ordering = ['key']
    
    def __str__(self):
        if self.is_secret:
            return f"{self.key}=***"
        return f"{self.key}={self.value}"


class DeploymentLog(models.Model):
    """Registro de instalaciones y despliegues"""
    
    LOG_TYPES = [
        ('install', 'Instalación'),
        ('update', 'Actualización'),
        ('migration', 'Migración'),
        ('restart', 'Reinicio'),
        ('backup', 'Respaldo'),
        ('error', 'Error'),
    ]
    
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='deployment_logs'
    )
    log_type = models.CharField(max_length=20, choices=LOG_TYPES)
    command = models.TextField(help_text='Comando ejecutado')
    output = models.TextField(blank=True, help_text='Salida del comando')
    error_output = models.TextField(blank=True, help_text='Errores si los hay')
    success = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    executed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )
    
    class Meta:
        db_table = 'app_generator_deployment_logs'
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.application.name} - {self.log_type} - {self.started_at}"
    
    def duration(self):
        """Calcula la duración del proceso"""
        if self.completed_at and self.started_at:
            return self.completed_at - self.started_at
        return None


# ==== Esquema de Base de Datos (metadata para generación de tablas) ====

class DbTable(models.Model):
    """Tabla lógica de base de datos perteneciente a una `Application`.

    Nota de nomenclatura para evitar confusiones con tablas/columnas HTML:
    - Entidades de base de datos: usar prefijo Db (DbTable, DbColumn)
    - Entidades de UI HTML: más adelante usar prefijo Ui (UiTable, UiColumn)
    """

    class TableKinds(models.TextChoices):
        CATALOG = 'catalog', 'Catálogo'
        TRANSACTION = 'transaction', 'Transacción'
    name = models.CharField(max_length=100, help_text='Nombre técnico (ej: productos)')
    alias = models.CharField(
        max_length=150,
        help_text='Nombre amigable/alias (ej: Productos)'
    )
    description = models.TextField(blank=True)
    schema_name = models.CharField(
        max_length=100,
        blank=True,
        default='public',
        help_text='Nombre del esquema (opcional, ej: public)'
    )
    table_kind = models.CharField(
        max_length=20,
        choices=TableKinds.choices,
        default=TableKinds.CATALOG,
        help_text='Tipo de tabla: Catálogo o Transacción'
    )
    # Activación lógica del registro (0/1). En BD se puede almacenar como smallint/tinyint
    activo = models.SmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'app_generator_db_tables'
        unique_together = [('schema_name', 'name')]
        ordering = ['schema_name', 'name']
        verbose_name = 'Tabla BD'
        verbose_name_plural = 'Tablas BD'

    def __str__(self):
        schema = self.schema_name or 'public'
        return f"{schema}.{self.name}"

    def clean(self):
        from django.core.exceptions import ValidationError
        import re

        # Normalizar a minúsculas
        if self.name:
            self.name = self.name.strip().lower()
        if self.alias:
            self.alias = self.alias.strip().lower()
        if self.schema_name:
            self.schema_name = self.schema_name.strip().lower()

        # Validar nombre técnico (solo minúsculas, números y guion bajo, inicia con letra)
        if self.name and not re.match(r'^[a-z][a-z0-9_]*$', self.name):
            raise ValidationError({'name': 'Nombre técnico inválido. Use minúsculas, números y guiones bajos; debe iniciar con letra.'})

    def save(self, *args, **kwargs):  # pragma: no cover
        # Asegurar normalización/validación siempre
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def columns(self):
        """Acceso a las columnas de la tabla a través de la relación intermedia."""
        return self.table_columns.all().order_by('position')

    def get_column_count(self):
        """Obtiene el número de columnas en la tabla."""
        return self.table_columns.count()

    def assign_default_columns(self):
        """Asigna columnas básicas según el tipo de tabla."""
        from .models import DbColumn, DbTableColumn
        
        # Obtener o crear columnas básicas
        id_column, created = DbColumn.objects.get_or_create(
            name='id',
            defaults={
                'data_type': 'integer',
                'is_primary_key': True,
                'is_nullable': False,
                'is_auto_increment': True,
                'notes': 'Clave primaria automática'
            }
        )
        
        # Asignar columna ID a esta tabla
        DbTableColumn.objects.get_or_create(
            table=self,
            column=id_column,
            defaults={
                'position': 1,
                'is_primary_key': True,
                'is_nullable': False,
                'is_auto_increment': True
            }
        )
        
        # Si es tabla CATÁLOGO, agregar columna 'nombre'
        if self.table_kind == self.TableKinds.CATALOG:
            nombre_column, created = DbColumn.objects.get_or_create(
                name='nombre',
                defaults={
                    'data_type': 'varchar',
                    'length': 100,
                    'is_nullable': False,
                    'is_unique': True,
                    'notes': 'Nombre único del catálogo'
                }
            )
            
            # Asignar columna nombre a esta tabla
            DbTableColumn.objects.get_or_create(
                table=self,
                column=nombre_column,
                defaults={
                    'position': 2,
                    'is_nullable': False,
                    'is_unique': True
                }
            )
        
        # Si es tabla TRANSACCIÓN, agregar columnas de auditoría
        elif self.table_kind == self.TableKinds.TRANSACTION:
            # Columna activo
            activo_column, created = DbColumn.objects.get_or_create(
                name='activo',
                defaults={
                    'data_type': 'boolean',
                    'is_nullable': False,
                    'default_value': 'true',
                    'notes': 'Estado activo/inactivo del registro'
                }
            )
            
            DbTableColumn.objects.get_or_create(
                table=self,
                column=activo_column,
                defaults={
                    'position': 2,
                    'is_nullable': False,
                    'default_value': 'true'
                }
            )
            
            # Columna created_at
            created_at_column, created = DbColumn.objects.get_or_create(
                name='created_at',
                defaults={
                    'data_type': 'timestamp',
                    'is_nullable': False,
                    'default_value': 'CURRENT_TIMESTAMP',
                    'notes': 'Fecha de creación del registro'
                }
            )
            
            DbTableColumn.objects.get_or_create(
                table=self,
                column=created_at_column,
                defaults={
                    'position': 3,
                    'is_nullable': False,
                    'default_value': 'CURRENT_TIMESTAMP'
                }
            )
            
            # Columna updated_at
            updated_at_column, created = DbColumn.objects.get_or_create(
                name='updated_at',
                defaults={
                    'data_type': 'timestamp',
                    'is_nullable': False,
                    'default_value': 'CURRENT_TIMESTAMP',
                    'notes': 'Fecha de última actualización'
                }
            )
            
            DbTableColumn.objects.get_or_create(
                table=self,
                column=updated_at_column,
                defaults={
                    'position': 4,
                    'is_nullable': False,
                    'default_value': 'CURRENT_TIMESTAMP'
                }
            )
            
            # Columna id_auth_user
            id_auth_user_column, created = DbColumn.objects.get_or_create(
                name='id_auth_user',
                defaults={
                    'data_type': 'integer',
                    'is_nullable': False,
                    'notes': 'Usuario que creó/actualizó el registro'
                }
            )
            
            DbTableColumn.objects.get_or_create(
                table=self,
                column=id_auth_user_column,
                defaults={
                    'position': 5,
                    'is_nullable': False
                }
            )


class DbColumn(models.Model):
    """Definición única global de columna con metadatos para generar migraciones/SQL."""

    class DataTypes(models.TextChoices):
        INTEGER = 'integer', 'INTEGER'
        BIGINT = 'bigint', 'BIGINT'
        SMALLINT = 'smallint', 'SMALLINT'
        SERIAL = 'serial', 'SERIAL'
        BIGSERIAL = 'bigserial', 'BIGSERIAL'
        VARCHAR = 'varchar', 'VARCHAR'
        TEXT = 'text', 'TEXT'
        BOOLEAN = 'boolean', 'BOOLEAN'
        DATE = 'date', 'DATE'
        TIMESTAMP = 'timestamp', 'TIMESTAMP'
        NUMERIC = 'numeric', 'NUMERIC'

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text='Nombre único de la columna (ej: id, nombre, id_familias)'
    )
    data_type = models.CharField(
        max_length=20,
        choices=DataTypes.choices,
        help_text='Tipo de dato SQL'
    )
    length = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Longitud (solo aplica a VARCHAR)'
    )
    numeric_precision = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Precisión (solo NUMERIC)'
    )
    numeric_scale = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Escala (solo NUMERIC)'
    )
    is_nullable = models.BooleanField(default=True)
    is_unique = models.BooleanField(default=False)
    is_index = models.BooleanField(default=False)
    is_primary_key = models.BooleanField(default=False)
    is_auto_increment = models.BooleanField(
        default=False,
        help_text='Solo aplica a tipos serial o PK integer'
    )
    default_value = models.CharField(
        max_length=255,
        blank=True,
        help_text='Valor por defecto (literal SQL)'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'app_generator_db_columns'
        ordering = ['name']
        verbose_name = 'Columna BD'
        verbose_name_plural = 'Columnas BD'

    def __str__(self):
        return self.name

    def clean(self):
        from django.core.exceptions import ValidationError
        import re

        # Validar nombre de columna
        if not re.match(r'^[a-z][a-z0-9_]*$', self.name or ''):
            raise ValidationError({'name': 'Nombre inválido. Use minúsculas, números y guiones bajos.'})

        # Validaciones de longitud/precisión segun tipo
        if self.data_type == self.DataTypes.VARCHAR and not self.length:
            raise ValidationError({'length': 'Debe indicar longitud para VARCHAR.'})
        if self.data_type != self.DataTypes.VARCHAR and self.length:
            raise ValidationError({'length': 'Longitud solo aplica a VARCHAR.'})
        if self.data_type == self.DataTypes.NUMERIC and not self.numeric_precision:
            raise ValidationError({'numeric_precision': 'Debe indicar precisión para NUMERIC.'})
        if self.data_type != self.DataTypes.NUMERIC and (self.numeric_precision or self.numeric_scale):
            raise ValidationError('Precisión/Escala solo aplican a NUMERIC.')

        # Coherencia PK/NULL/UNIQUE
        if self.is_primary_key:
            if self.is_nullable:
                raise ValidationError({'is_nullable': 'Una PK no puede ser NULL.'})
            if self.is_unique is False:
                # PK es implícitamente única; no exigimos marcarla, pero no permitir marcar False explícito
                pass


class DbTableColumn(models.Model):
    """Relación entre tabla y columna con metadatos específicos de la implementación."""

    class OnDelete(models.TextChoices):
        CASCADE = 'CASCADE', 'CASCADE'
        RESTRICT = 'RESTRICT', 'RESTRICT'
        SET_NULL = 'SET NULL', 'SET NULL'
        NO_ACTION = 'NO ACTION', 'NO ACTION'

    table = models.ForeignKey(
        DbTable,
        on_delete=models.CASCADE,
        related_name='table_columns'
    )
    column = models.ForeignKey(
        DbColumn,
        on_delete=models.CASCADE,
        related_name='table_implementations'
    )
    position = models.PositiveIntegerField(
        default=1,
        help_text='Orden de la columna en la tabla (1..N)'
    )
    
    # Metadatos específicos de la implementación (pueden sobrescribir los de DbColumn)
    is_nullable = models.BooleanField(null=True, blank=True, help_text='Sobrescribe el valor de DbColumn')
    is_unique = models.BooleanField(null=True, blank=True, help_text='Sobrescribe el valor de DbColumn')
    is_index = models.BooleanField(null=True, blank=True, help_text='Sobrescribe el valor de DbColumn')
    is_primary_key = models.BooleanField(null=True, blank=True, help_text='Sobrescribe el valor de DbColumn')
    is_auto_increment = models.BooleanField(null=True, blank=True, help_text='Sobrescribe el valor de DbColumn')
    default_value = models.CharField(
        max_length=255,
        blank=True,
        help_text='Sobrescribe el valor por defecto de DbColumn'
    )

    # Llave foránea
    references_table = models.ForeignKey(
        DbTable,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='referenced_by_table_columns',
        help_text='Tabla de referencia si es FK'
    )
    on_delete = models.CharField(
        max_length=10,
        choices=OnDelete.choices,
        default=OnDelete.CASCADE,
        help_text='Comportamiento ON DELETE para la FK'
    )

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'app_generator_table_columns'
        unique_together = [('table', 'column')]
        ordering = ['table__name', 'position', 'column__name']
        verbose_name = 'Columna de Tabla'
        verbose_name_plural = 'Columnas de Tablas'

    def __str__(self):
        return f"{self.table.name}.{self.column.name}"

    def fk_constraint_name(self) -> str | None:
        if self.references_table_id:
            return f"FK_{self.table.name}_con_{self.references_table.name}"
        return None

    def get_effective_value(self, field_name):
        """Obtiene el valor efectivo: primero del override, luego del DbColumn."""
        override_value = getattr(self, field_name)
        if override_value is not None:
            return override_value
        return getattr(self.column, field_name)

    def clean(self):
        from django.core.exceptions import ValidationError
        
        # Validar FK: si hay tabla referenciada, nombre debe ser id_<tabla>
        if self.references_table_id:
            expected = f"id_{self.references_table.name}"
            if self.column.name != expected:
                raise ValidationError({'column': f'Nombre de FK debe ser "{expected}".'})
            # Tipo de dato recomendado entero
            if self.column.data_type not in [self.column.DataTypes.INTEGER, self.column.DataTypes.BIGINT, self.column.DataTypes.SMALLINT]:
                raise ValidationError({'column': 'La FK debe ser de tipo entero (integer/smallint/bigint).'})


# DbColumnTemplate eliminado - ya no es necesario


# ==== UI Defaults generados a partir de columnas de BD ====

class UiColumn(models.Model):
    class Alignment(models.TextChoices):
        LEFT = 'left', 'Izquierda'
        CENTER = 'center', 'Centro'
        RIGHT = 'right', 'Derecha'

    db_column = models.OneToOneField(DbColumn, on_delete=models.CASCADE, related_name='ui_column')
    label = models.CharField(max_length=150)
    alignment = models.CharField(max_length=10, choices=Alignment.choices, default=Alignment.LEFT)
    format = models.CharField(max_length=100, blank=True)
    visible_in_lists = models.BooleanField(default=True)
    is_toggle = models.BooleanField(default=False, help_text='Renderizar como interruptor en listas')
    width = models.PositiveIntegerField(null=True, blank=True, help_text='Ancho en px opcional')

    class Meta:
        db_table = 'app_generator_ui_columns'
        verbose_name = 'Columna UI'
        verbose_name_plural = 'Columnas UI'

    def __str__(self) -> str:  # pragma: no cover
        return self.label


class UiField(models.Model):
    class InputType(models.TextChoices):
        TEXT = 'text', 'Texto'
        TEXTAREA = 'textarea', 'Área de texto'
        NUMBER = 'number', 'Número'
        CHECKBOX = 'checkbox', 'Checkbox'
        DATE = 'date', 'Fecha'
        DATETIME = 'datetime-local', 'Fecha/Hora'
        SELECT = 'select', 'Selector'

    class OptionsSource(models.TextChoices):
        NONE = 'none', 'Ninguna'
        FK = 'fk', 'Llave foránea'

    db_column = models.OneToOneField(DbColumn, on_delete=models.CASCADE, related_name='ui_field')
    label = models.CharField(max_length=150)
    input_type = models.CharField(max_length=20, choices=InputType.choices)
    required = models.BooleanField(default=False)
    step = models.CharField(max_length=20, blank=True)
    min_value = models.CharField(max_length=50, blank=True)
    max_value = models.CharField(max_length=50, blank=True)
    pattern = models.CharField(max_length=120, blank=True)
    placeholder = models.CharField(max_length=150, blank=True)
    options_source = models.CharField(max_length=10, choices=OptionsSource.choices, default=OptionsSource.NONE)
    fk_table = models.ForeignKey(DbTable, null=True, blank=True, on_delete=models.SET_NULL)
    fk_label_field = models.CharField(max_length=100, blank=True, default='nombre')
    order = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = 'app_generator_ui_fields'
        verbose_name = 'Campo UI'
        verbose_name_plural = 'Campos UI'

    def __str__(self) -> str:  # pragma: no cover
        return self.label


class FormQuestion(models.Model):
    """Pregunta/campo para formularios dinámicos basada en columnas de BD."""
    
    class InputType(models.TextChoices):
        TEXT = 'text', 'Texto'
        TEXTAREA = 'textarea', 'Área de texto'
        NUMBER = 'number', 'Número'
        CHECKBOX = 'checkbox', 'Checkbox'
        RADIO = 'radio', 'Radio buttons'
        SELECT = 'select', 'Selector'
        DATE = 'date', 'Fecha'
        DATETIME = 'datetime-local', 'Fecha/Hora'
        EMAIL = 'email', 'Email'
        PASSWORD = 'password', 'Contraseña'
        FILE = 'file', 'Archivo'
        HIDDEN = 'hidden', 'Campo oculto'

    class OptionsSource(models.TextChoices):
        NONE = 'none', 'Ninguna'
        FK = 'fk', 'Llave foránea'
        CUSTOM = 'custom', 'Opciones personalizadas'

    class ValidationRule(models.TextChoices):
        NONE = 'none', 'Ninguna'
        REQUIRED = 'required', 'Requerido'
        EMAIL = 'email', 'Email válido'
        URL = 'url', 'URL válida'
        MIN_LENGTH = 'min_length', 'Longitud mínima'
        MAX_LENGTH = 'max_length', 'Longitud máxima'
        PATTERN = 'pattern', 'Patrón regex'
        MIN_VALUE = 'min_value', 'Valor mínimo'
        MAX_VALUE = 'max_value', 'Valor máximo'

    # Relación con columna de BD (opcional, puede ser independiente)
    db_column = models.OneToOneField(
        DbColumn, 
        on_delete=models.CASCADE, 
        related_name='form_question',
        null=True, blank=True
    )
    
    # Identificación
    name = models.CharField(
        max_length=100,
        help_text='Nombre técnico del campo (ej: descripcion, email_usuario)'
    )
    question_text = models.CharField(
        max_length=200,
        help_text='Texto de la pregunta que ve el usuario (ej: "Descripción del producto:")'
    )
    help_text = models.CharField(
        max_length=300, 
        blank=True,
        help_text='Texto de ayuda opcional'
    )
    
    # Tipo y comportamiento
    input_type = models.CharField(
        max_length=20, 
        choices=InputType.choices,
        default=InputType.TEXT
    )
    required = models.BooleanField(
        default=False,
        help_text='¿Es obligatorio responder esta pregunta?'
    )
    
    # Validación
    validation_rule = models.CharField(
        max_length=20,
        choices=ValidationRule.choices,
        default=ValidationRule.NONE
    )
    validation_value = models.CharField(
        max_length=100,
        blank=True,
        help_text='Valor para la validación (ej: longitud min/max, patrón regex)'
    )
    
    # Opciones para select/radio
    options_source = models.CharField(
        max_length=10,
        choices=OptionsSource.choices,
        default=OptionsSource.NONE
    )
    options_custom = models.TextField(
        blank=True,
        help_text='Opciones separadas por líneas (ej: "Opción 1\\nOpción 2")'
    )
    fk_table = models.ForeignKey(
        DbTable, 
        null=True, blank=True, 
        on_delete=models.SET_NULL,
        help_text='Tabla de origen para opciones FK'
    )
    fk_value_field = models.CharField(
        max_length=100, 
        blank=True, 
        default='id',
        help_text='Campo que se guarda como valor'
    )
    fk_label_field = models.CharField(
        max_length=100, 
        blank=True, 
        default='nombre',
        help_text='Campo que se muestra al usuario'
    )
    
    # Estilo y presentación
    css_class = models.CharField(
        max_length=100,
        blank=True,
        default='col-md-6',
        help_text='Clases CSS (ej: col-md-6, col-md-12)'
    )
    placeholder = models.CharField(
        max_length=150,
        blank=True,
        help_text='Placeholder para el campo'
    )
    default_value = models.CharField(
        max_length=255,
        blank=True,
        help_text='Valor por defecto'
    )
    
    # Orden y agrupación
    order = models.PositiveIntegerField(
        default=1,
        help_text='Orden de aparición en el formulario'
    )
    section = models.CharField(
        max_length=100,
        blank=True,
        help_text='Sección del formulario (opcional)'
    )
    
    # Control
    is_active = models.BooleanField(
        default=True,
        help_text='¿Está activa esta pregunta?'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'app_generator_form_questions'
        verbose_name = 'Pregunta de Formulario'
        verbose_name_plural = 'Preguntas de Formularios'
        ordering = ['order', 'name']

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.question_text} ({self.name})"

    def get_options_list(self):
        """Devuelve lista de opciones según el tipo de origen."""
        if self.options_source == self.OptionsSource.CUSTOM and self.options_custom:
            return [line.strip() for line in self.options_custom.split('\n') if line.strip()]
        elif self.options_source == self.OptionsSource.FK and self.fk_table:
            # Esto se implementaría con queries dinámicas al renderizar
            return []
        return []


def _title_from_name(name: str) -> str:
    base = (name or '').replace('_', ' ').strip()
    return base.capitalize()


def _derive_ui_defaults(db_col: DbColumn) -> tuple[dict, dict]:
    """Devuelve (ui_column_defaults, ui_field_defaults) desde una DbColumn."""
    name = db_col.name
    label = _title_from_name(name)
    alignment = UiColumn.Alignment.LEFT
    fmt = ''
    input_type = UiField.InputType.TEXT
    step = ''
    required = not db_col.is_nullable
    options_source = UiField.OptionsSource.NONE
    fk_table = None

    dt = db_col.data_type
    # Mapeo por tipo
    if dt in [DbColumn.DataTypes.INTEGER, DbColumn.DataTypes.SMALLINT, DbColumn.DataTypes.BIGINT]:
        alignment = UiColumn.Alignment.RIGHT
        input_type = UiField.InputType.NUMBER
        step = '1'
    elif dt == DbColumn.DataTypes.NUMERIC:
        alignment = UiColumn.Alignment.RIGHT
        input_type = UiField.InputType.NUMBER
        # step por escala
        try:
            scale = int(db_col.numeric_scale or 0)
        except Exception:
            scale = 0
        step = '0.' + ('0' * (scale - 1)) + '1' if scale > 0 else '1'
        fmt = f'number:{scale}' if scale > 0 else ''
    elif dt in [DbColumn.DataTypes.VARCHAR, DbColumn.DataTypes.TEXT]:
        alignment = UiColumn.Alignment.LEFT
        input_type = UiField.InputType.TEXTAREA if dt == DbColumn.DataTypes.TEXT else UiField.InputType.TEXT
        if dt == DbColumn.DataTypes.TEXT:
            fmt = 'truncate:80'
    elif dt == DbColumn.DataTypes.BOOLEAN:
        alignment = UiColumn.Alignment.CENTER
        input_type = UiField.InputType.CHECKBOX
    elif dt == DbColumn.DataTypes.DATE:
        alignment = UiColumn.Alignment.CENTER
        input_type = UiField.InputType.DATE
        fmt = 'date:YYYY-MM-DD'
    elif dt == DbColumn.DataTypes.TIMESTAMP:
        alignment = UiColumn.Alignment.CENTER
        input_type = UiField.InputType.DATETIME
        fmt = 'datetime:YYYY-MM-DD HH:mm'

    # Llave foránea por convención id_<tabla>
    if name.startswith('id_'):
        # Para DbColumn no existe references_table; resolvemos por nombre
        try:
            from .models import DbTable  # import local para evitar ciclos
            ref_name = name[3:]
            fk_table = DbTable.objects.filter(name=ref_name).first()
            if fk_table:
                input_type = UiField.InputType.SELECT
                options_source = UiField.OptionsSource.FK
        except Exception:
            pass

    # Etiqueta para columna UI: mantener literal id_* si aplica
    if name.startswith('id_'):
        label = name

    ui_col = dict(
        label=label,
        alignment=alignment,
        format=fmt,
        visible_in_lists=True,
        width=None,
        is_toggle=(name == 'activo'),
    )
    ui_field = None
    # No crear campo de formulario para PK
    if not db_col.is_primary_key:
        ui_field = dict(
            label=label,
            input_type=input_type,
            required=required,
            step=step,
            min_value='',
            max_value='',
            pattern='',
            placeholder='',
            options_source=options_source,
            fk_table=fk_table,
            fk_label_field='nombre',
            order=db_col.position or 1,
        )
    return ui_col, ui_field


def _derive_form_question_defaults(db_col: DbColumn, page_title: str = None) -> dict:
    """Devuelve form_question_defaults desde una DbColumn.
    
    Args:
        db_col: La columna de base de datos
        page_title: Título de la página (opcional, para personalizar labels)
    """
    name = db_col.name
    
    # Lógica especial para el campo "nombre" cuando se tiene el título de la página
    if name == 'nombre' and page_title:
        label = page_title
    else:
        label = _title_from_name(name)
    
    # Mapear tipos de datos a tipos de input para formularios
    input_type = FormQuestion.InputType.TEXT
    validation_rule = FormQuestion.ValidationRule.NONE
    validation_value = ''
    width_fraction = '1-1'  # Campo completo por defecto
    placeholder = f'Ingrese {label.lower()}'
    required = not db_col.is_nullable
    options_source = FormQuestion.OptionsSource.NONE
    fk_table = None
    
    dt = db_col.data_type
    
    if dt in [DbColumn.DataTypes.INTEGER, DbColumn.DataTypes.SMALLINT, DbColumn.DataTypes.BIGINT]:
        input_type = FormQuestion.InputType.NUMBER
        placeholder = f'Ingrese {label.lower()}'
        if db_col.is_primary_key:
            input_type = FormQuestion.InputType.HIDDEN
            placeholder = ''
            width_fraction = '1-1'
    elif dt == DbColumn.DataTypes.NUMERIC:
        input_type = FormQuestion.InputType.NUMBER
        placeholder = f'Ingrese {label.lower()}'
    elif dt == DbColumn.DataTypes.VARCHAR:
        input_type = FormQuestion.InputType.TEXT
        if db_col.length and db_col.length <= 50:
            width_fraction = '1-4'
        elif db_col.length and db_col.length <= 100:
            width_fraction = '1-2'
        else:
            width_fraction = '2-3'
        if db_col.length:
            validation_rule = FormQuestion.ValidationRule.MAX_LENGTH
            validation_value = str(db_col.length)
    elif dt == DbColumn.DataTypes.TEXT:
        input_type = FormQuestion.InputType.TEXTAREA
        width_fraction = '1-1'
        placeholder = f'Ingrese {label.lower()}'
    elif dt == DbColumn.DataTypes.BOOLEAN:
        input_type = FormQuestion.InputType.CHECKBOX
        width_fraction = '1-4'
        placeholder = ''
    elif dt == DbColumn.DataTypes.DATE:
        input_type = FormQuestion.InputType.DATE
        width_fraction = '1-4'
        placeholder = ''
    elif dt == DbColumn.DataTypes.TIMESTAMP:
        input_type = FormQuestion.InputType.DATETIME
        width_fraction = '1-2'
        placeholder = ''

    # Llave foránea por convención id_<tabla>
    if name.startswith('id_') and name != 'id':
        table_name = name[3:]  # remover 'id_'
        try:
            fk_table = DbTable.objects.filter(name=table_name).first()
            if fk_table:
                input_type = FormQuestion.InputType.SELECT
                options_source = FormQuestion.OptionsSource.FK
                # Ajustar label y placeholder para selects
                select_label = _title_from_name(table_name)
                label = f'Seleccionar {select_label}'
                placeholder = f'Seleccione {select_label.lower()}'
                width_fraction = '1-2'
        except Exception:
            pass

    # Casos especiales por nombre
    if name == 'activo':
        input_type = FormQuestion.InputType.CHECKBOX
        width_fraction = '1-4'
        placeholder = ''
    elif name == 'email' or 'password' in name or 'contrasena' in name:
        input_type = FormQuestion.InputType.EMAIL
        validation_rule = FormQuestion.ValidationRule.MIN_LENGTH
        validation_value = '8'
        width_fraction = '1-2'
    elif name in ['archivo', 'imagen']:
        input_type = FormQuestion.InputType.FILE
        width_fraction = '1-2'
        placeholder = f'Seleccione {label.lower()}'

    form_question_defaults = {
        'name': name,
        'question_text': label + ':',
        'help_text': '',
        'input_type': input_type,
        'required': required,
        'validation_rule': validation_rule,
        'validation_value': validation_value,
        'options_source': options_source,
        'options_custom': '',
        'fk_table': fk_table,
        'fk_value_field': 'id',
        'fk_label_field': 'nombre',
        'width_fraction': width_fraction,
        'placeholder': placeholder,
        'default_value': db_col.default_value or '',
        'order': db_col.position or 1,
        'section': '',
        'is_active': True,
    }
    
    return form_question_defaults


@receiver(post_save, sender=DbColumn)
def create_ui_defaults_for_dbcolumn(sender, instance: DbColumn, created: bool, **kwargs):
    if not created:
        return
    try:
        # No generar UI para columnas técnicas de auditoría y control
        if instance.name in ['created_at', 'updated_at', 'id_auth_user']:
            return
        # Crear UiColumn si no existe
        if not hasattr(instance, 'ui_column'):
            col_defaults, field_defaults = _derive_ui_defaults(instance)
            UiColumn.objects.create(db_column=instance, **col_defaults)
            if field_defaults is not None:
                UiField.objects.create(db_column=instance, **field_defaults)
        
        # Crear FormQuestion si no existe
        if not hasattr(instance, 'form_question'):
            question_defaults = _derive_form_question_defaults(instance)
            FormQuestion.objects.create(db_column=instance, **question_defaults)
    except Exception:
        # No romper la creación de columnas por errores de UI
        pass


@receiver(post_delete, sender=DbColumn)
def cleanup_ui_for_dbcolumn(sender, instance: DbColumn, **kwargs):
    # La relación es CASCADE por OneToOne, pero dejamos el receiver por claridad
    pass


class ApplicationTable(models.Model):
    """Relación entre aplicación y tabla de base de datos."""
    
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='assigned_tables'
    )
    table = models.ForeignKey(
        DbTable,
        on_delete=models.CASCADE,
        related_name='assigned_applications'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, help_text='Notas sobre el uso de esta tabla en la aplicación')
    
    class Meta:
        db_table = 'app_generator_application_tables'
        unique_together = [('application', 'table')]
        verbose_name = 'Tabla de Aplicación'
        verbose_name_plural = 'Tablas de Aplicaciones'
        ordering = ['application__name', 'table__name']
    
    def __str__(self):
        return f"{self.application.name} - {self.table.name}"


class ApplicationPage(models.Model):
    """Relación entre aplicación y página generada/gestionada por SAPY.
    Permite decidir qué páginas vivirán en una aplicación, independientemente de las tablas BD.
    """

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='assigned_pages'
    )
    page = models.ForeignKey(
        'Page',
        on_delete=models.CASCADE,
        related_name='assigned_applications'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, help_text='Notas sobre el uso de esta página en la aplicación')

    class Meta:
        db_table = 'app_generator_application_pages'
        unique_together = [('application', 'page')]
        verbose_name = 'Página de Aplicación'
        verbose_name_plural = 'Páginas de Aplicaciones'
        ordering = ['application__name', 'page__slug']

    def __str__(self):
        return f"{self.application.name} - {self.page.slug}"


# ==== Gestión de Páginas y Componentes (Pages/Modals/Forms/Table Overrides) ====


class Menu(models.Model):
    """Menú navegable que agrupa páginas en secciones y orden."""

    name = models.SlugField(
        max_length=100,
        unique=True,
        help_text='Identificador único en minúsculas (ej: usuarios)'
    )
    title = models.CharField(max_length=150, help_text='Título visible en el menú')
    icon = models.CharField(max_length=100, blank=True, help_text='Clase de icono (ej: bi bi-people, fas fa-user)')
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'app_generator_menus'
        ordering = ['name']
        verbose_name = 'Menú'
        verbose_name_plural = 'Menús'

    def __str__(self) -> str:  # pragma: no cover
        return self.title or self.name


class MenuPage(models.Model):
    """Asignación de páginas a un menú, con sección y orden."""

    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name='menu_pages')
    page = models.ForeignKey('Page', on_delete=models.CASCADE, related_name='menu_assignments')
    section = models.CharField(max_length=100, blank=True, help_text='Etiqueta de sección para agrupar opciones')
    order_index = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'app_generator_menu_pages'
        unique_together = [('menu', 'page')]
        ordering = ['menu__name', 'section', 'order_index']
        verbose_name = 'Página de Menú'
        verbose_name_plural = 'Páginas de Menú'

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.menu.name} → {self.page.slug}"


class ApplicationMenu(models.Model):
    """Relación entre aplicación y menú. Un menú agrupa varias páginas reutilizables."""

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='assigned_menus'
    )
    menu = models.ForeignKey(
        Menu,
        on_delete=models.CASCADE,
        related_name='assigned_applications'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'app_generator_application_menus'
        unique_together = [('application', 'menu')]
        ordering = ['application__name', 'menu__name']
        verbose_name = 'Menú de Aplicación'
        verbose_name_plural = 'Menús de Aplicaciones'

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.application.name} - {self.menu.name}"


class Icon(models.Model):
    class Provider(models.TextChoices):
        BOOTSTRAP = 'bi', 'Bootstrap Icons'
        FONTAWESOME = 'fa', 'Font Awesome Free'

    provider = models.CharField(max_length=10, choices=Provider.choices, default=Provider.BOOTSTRAP)
    class_name = models.CharField(max_length=120, unique=True, help_text='Clase CSS completa, ej: "bi bi-people" o "fas fa-user"')
    label = models.CharField(max_length=150, blank=True, help_text='Etiqueta legible (opcional)')
    tags = models.TextField(blank=True, help_text='Palabras clave separadas por espacio/coma (opcional)')

    # Campos extendidos para sincronización desde catálogos
    library = models.CharField(max_length=32, blank=True, help_text='bootstrap-icons | fontawesome6')
    version = models.CharField(max_length=24, blank=True)
    name = models.CharField(max_length=128, blank=True)
    style = models.CharField(max_length=16, blank=True)
    unicode = models.CharField(max_length=8, blank=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'app_generator_icons'
        ordering = ['provider', 'class_name']
        verbose_name = 'Ícono'
        verbose_name_plural = 'Íconos'

    def __str__(self) -> str:  # pragma: no cover
        return self.class_name


class Page(models.Model):
    class SourceType(models.TextChoices):
        DBTABLE = 'dbtable', 'Desde tabla BD'
        CUSTOM = 'custom', 'Personalizada'

    slug = models.SlugField(max_length=150, unique=True, help_text='Identificador URL, ej: productos')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    source_type = models.CharField(max_length=20, choices=SourceType.choices, default=SourceType.DBTABLE)
    db_table = models.ForeignKey(DbTable, null=True, blank=True, on_delete=models.SET_NULL)
    icon = models.CharField(max_length=100, blank=True)
    layout = models.CharField(max_length=100, blank=True)
    route_path = models.CharField(max_length=200, unique=True, help_text='Ruta relativa ej: /productos/')
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'app_generator_pages'
        ordering = ['slug']
        verbose_name = 'Página'
        verbose_name_plural = 'Páginas'

    def __str__(self):  # pragma: no cover
        return self.title or self.slug


class PageTable(models.Model):
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='page_tables')
    db_table = models.ForeignKey(DbTable, on_delete=models.CASCADE)
    title = models.CharField(max_length=200, blank=True, default='')
    searchable = models.BooleanField(default=True)
    export_csv = models.BooleanField(default=True)
    export_xlsx = models.BooleanField(default=True)
    export_pdf = models.BooleanField(default=True)
    page_size = models.PositiveIntegerField(default=25)
    default_sort = models.JSONField(default=dict, help_text='Ej: {"by":"id","dir":"desc"}')
    show_inactive = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'app_generator_page_tables'
        unique_together = [('page', 'db_table')]
        verbose_name = 'Tabla de Página'
        verbose_name_plural = 'Tablas de Página'

    def __str__(self):  # pragma: no cover
        return f"{self.page.slug} → {self.db_table.name}"


class PageTableColumnOverride(models.Model):
    class ColumnFormat(models.TextChoices):
        TEXT = 'text', 'Texto'
        CURRENCY = 'currency', 'Moneda'
        DECIMAL = 'decimal', 'Decimal'
        PERCENT = 'percent', 'Porcentaje'
        DATE = 'date', 'Fecha'
        DATETIME = 'datetime', 'Fecha/Hora'
        BUTTON = 'button', 'Botón'
        BADGE = 'badge', 'Insignia'
        LINK = 'link', 'Enlace'

    class ActionType(models.TextChoices):
        EDIT = 'edit', 'Editar'
        DELETE = 'delete', 'Eliminar'
        TOGGLE_ACTIVE = 'toggle_active', 'Alternar Activo'
        CUSTOM = 'custom', 'Personalizada'

    page_table = models.ForeignKey(PageTable, on_delete=models.CASCADE, related_name='column_overrides')
    ui_column = models.ForeignKey('UiColumn', null=True, blank=True, on_delete=models.CASCADE)
    form_question = models.ForeignKey('FormQuestion', null=True, blank=True, on_delete=models.CASCADE)
    db_column = models.ForeignKey('DbColumn', null=True, blank=True, on_delete=models.CASCADE)
    order_index = models.IntegerField(null=True, blank=True)
    width_px = models.IntegerField(null=True, blank=True)
    title_override = models.CharField(max_length=200, null=True, blank=True)
    alignment = models.CharField(max_length=10, choices=(('left','left'),('center','center'),('right','right')), null=True, blank=True)
    format = models.CharField(max_length=20, choices=ColumnFormat.choices, null=True, blank=True)
    visible = models.BooleanField(default=True)
    is_action_button = models.BooleanField(default=False)
    action_type = models.CharField(max_length=20, choices=ActionType.choices, null=True, blank=True)
    link_url_template = models.TextField(null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'app_generator_page_table_col_overrides'
        verbose_name = 'Override de Columna de Tabla'
        verbose_name_plural = 'Overrides de Columnas de Tabla'

    def clean(self):  # pragma: no cover
        from django.core.exceptions import ValidationError
        refs = [self.ui_column_id, self.form_question_id, self.db_column_id]
        filled = sum(1 for v in refs if v is not None)
        if filled != 1:
            raise ValidationError('Debe especificar exactamente una referencia: ui_column, form_question o db_column')


class Modal(models.Model):
    class Purpose(models.TextChoices):
        CREATE_EDIT = 'create_edit', 'Crear/Editar'
        CUSTOM = 'custom', 'Personalizado'

    class Size(models.TextChoices):
        SM = 'sm', 'Pequeño'
        MD = 'md', 'Mediano'
        LG = 'lg', 'Grande'
        XL = 'xl', 'Extra grande'
        FULL = 'full', 'Pantalla completa'

    purpose = models.CharField(max_length=20, choices=Purpose.choices, default=Purpose.CREATE_EDIT)
    title = models.CharField(max_length=200)
    size = models.CharField(max_length=10, choices=Size.choices, default=Size.LG)
    icon = models.CharField(max_length=100, blank=True)
    close_on_backdrop = models.BooleanField(default=True)
    close_on_escape = models.BooleanField(default=True)
    prevent_close_on_enter = models.BooleanField(default=False)
    prevent_close_on_space = models.BooleanField(default=False)
    submit_button_label = models.CharField(max_length=100, default='Guardar')
    submit_button_icon = models.CharField(max_length=100, blank=True)
    cancel_button_label = models.CharField(max_length=100, default='Cancelar')
    # Form modes: none (0), auto (1), external (2)
    class FormMode(models.TextChoices):
        NONE = 'none', 'Sin formulario'
        AUTO = 'auto', 'Formulario automático'
        EXTERNAL = 'external', 'Formulario externo'
    form_mode = models.CharField(max_length=10, choices=FormMode.choices, default=FormMode.AUTO)
    external_template_path = models.CharField(max_length=255, blank=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'app_generator_modals'
        verbose_name = 'Modal'
        verbose_name_plural = 'Modales'

    def __str__(self):  # pragma: no cover
        return self.title


class PageModal(models.Model):
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='page_modals')
    modal = models.ForeignKey(Modal, on_delete=models.PROTECT, related_name='pages')
    order_index = models.IntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'app_generator_pages_modals'
        unique_together = [('page', 'modal')]
        verbose_name = 'Modal de Página'
        verbose_name_plural = 'Modales de Página'


class ModalForm(models.Model):
    modal = models.OneToOneField(Modal, on_delete=models.CASCADE, related_name='form')
    db_table = models.ForeignKey(DbTable, null=True, blank=True, on_delete=models.SET_NULL)
    layout_columns_per_row = models.PositiveIntegerField(default=2)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'app_generator_modal_forms'
        verbose_name = 'Formulario de Modal'
        verbose_name_plural = 'Formularios de Modales'


class ModalFormFieldOverride(models.Model):
    class WidthFraction(models.TextChoices):
        W1 = '1-1', '1/1 (100%)'
        W2 = '1-2', '1/2 (50%)'
        W3 = '1-3', '1/3 (33%)'
        W23 = '2-3', '2/3 (67%)'
        W4 = '1-4', '1/4 (25%)'
        W34 = '3-4', '3/4 (75%)'
        W6 = '1-6', '1/6 (17%)'
        W56 = '5-6', '5/6 (83%)'

    modal_form = models.ForeignKey(ModalForm, on_delete=models.CASCADE, related_name='field_overrides')
    form_question = models.ForeignKey('FormQuestion', null=True, blank=True, on_delete=models.CASCADE)
    db_column = models.ForeignKey('DbColumn', null=True, blank=True, on_delete=models.CASCADE)
    order_index = models.IntegerField(null=True, blank=True)
    label_override = models.CharField(max_length=200, null=True, blank=True)
    placeholder = models.CharField(max_length=200, null=True, blank=True)
    width_fraction = models.CharField(max_length=10, choices=WidthFraction.choices, default=WidthFraction.W1)
    required_override = models.BooleanField(null=True, blank=True)
    help_text = models.CharField(max_length=300, null=True, blank=True)
    visible = models.BooleanField(default=True)
    default_value = models.JSONField(null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'app_generator_modal_form_field_overrides'
        verbose_name = 'Override de Campo de Formulario'
        verbose_name_plural = 'Overrides de Campos de Formulario'

    def clean(self):  # pragma: no cover
        from django.core.exceptions import ValidationError
        if not (self.form_question_id or self.db_column_id):
            raise ValidationError('Debe indicar form_question o db_column')


class PageShortcut(models.Model):
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='shortcuts')
    target_page = models.ForeignKey(Page, on_delete=models.PROTECT, related_name='incoming_shortcuts')
    label = models.CharField(max_length=150)
    icon = models.CharField(max_length=100, blank=True)
    order_index = models.IntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'app_generator_page_shortcuts'
        verbose_name = 'Acceso Directo de Página'
        verbose_name_plural = 'Accesos Directos de Página'


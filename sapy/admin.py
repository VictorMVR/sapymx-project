# admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Application, ApplicationDependency, ApplicationEnvironment, DeploymentLog

class ApplicationDependencyInline(admin.TabularInline):
    """Inline para gestionar dependencias"""
    model = ApplicationDependency
    extra = 1
    fields = ('package_name', 'version', 'is_required')

class ApplicationEnvironmentInline(admin.TabularInline):
    """Inline para gestionar variables de entorno"""
    model = ApplicationEnvironment
    extra = 1
    fields = ('key', 'value', 'is_secret')
    
    def get_readonly_fields(self, request, obj=None):
        """Ocultar valores secretos en modo lectura"""
        if obj:  # Editando objeto existente
            return ['value'] if obj.is_secret else []
        return []

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    """Admin para Application"""
    
    list_display = [
        'display_name', 
        'name', 
        'domain_link', 
        'status_badge', 
        'db_info',
        'created_at',
        'quick_actions'
    ]
    
    list_filter = [
        'status', 
        'db_engine', 
        'django_version',
        'created_at'
    ]
    
    search_fields = [
        'name', 
        'display_name', 
        'domain', 
        'description'
    ]
    
    readonly_fields = [
        'uuid', 
        'created_at', 
        'updated_at', 
        'installed_at',
        'created_by',
        'status_info',
        'access_urls'
    ]
    
    fieldsets = (
        ('Información Básica', {
            'fields': (
                'uuid',
                'name', 
                'display_name', 
                'description',
                'status',
                'created_by',
                'created_at',
                'updated_at',
                'installed_at'
            )
        }),
        ('Configuración de Dominio', {
            'fields': (
                'domain', 
                'subdomain', 
                'port',
                'access_urls'
            )
        }),
        ('Base de Datos', {
            'fields': (
                'db_engine',
                'db_name',
                'db_user',
                'db_password',
                'db_host',
                'db_port'
            ),
            'classes': ('collapse',)
        }),
        ('Configuración del Sistema', {
            'fields': (
                'base_path',
                'virtualenv_path',
                'python_version',
                'django_version'
            ),
            'classes': ('collapse',)
        }),
        ('Configuración Django', {
            'fields': (
                'django_secret_key',
                'django_debug',
                'django_allowed_hosts'
            ),
            'classes': ('collapse',)
        })
    )
    
    inlines = [ApplicationDependencyInline, ApplicationEnvironmentInline]
    
    def domain_link(self, obj):
        """Mostrar dominio como link"""
        url = f"http://{obj.domain}:{obj.port}"
        return format_html(
            '<a href="{}" target="_blank">{} <small>↗</small></a>',
            url, obj.domain
        )
    domain_link.short_description = 'Dominio'
    
    def status_badge(self, obj):
        """Mostrar estado con badge de color"""
        colors = {
            'draft': 'gray',
            'generating': 'blue',
            'generated': 'cyan',
            'installing': 'yellow',
            'deployed': 'green',
            'error': 'red',
            'maintenance': 'orange'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Estado'
    
    def db_info(self, obj):
        """Mostrar información de BD"""
        return format_html(
            '<small><b>{}</b><br>{}</small>',
            obj.db_engine.upper(),
            obj.db_name
        )
    db_info.short_description = 'Base de Datos'
    
    def quick_actions(self, obj):
        """Botones de acción rápida"""
        buttons = []
        
        # Botón Ver
        view_url = reverse('app_generator:application_detail', args=[obj.pk])
        buttons.append(f'<a href="{view_url}" class="button small">Ver</a>')
        
        # Botón Admin (si está desplegada)
        if obj.status == 'deployed':
            admin_url = f"http://{obj.domain}:{obj.port}/admin/"
            buttons.append(f'<a href="{admin_url}" target="_blank" class="button small">Admin</a>')
        
        # Botón Instalar (si está en draft o error)
        if obj.status in ['draft', 'error']:
            deploy_url = reverse('app_generator:application_detail', args=[obj.pk])
            buttons.append(f'<a href="{deploy_url}" class="button small default">Instalar</a>')
        
        return format_html(' '.join(buttons))
    quick_actions.short_description = 'Acciones'
    
    def status_info(self, obj):
        """Información detallada del estado"""
        info = f"<strong>Estado actual:</strong> {obj.get_status_display()}<br>"
        
        if obj.installed_at:
            info += f"<strong>Instalada:</strong> {obj.installed_at.strftime('%d/%m/%Y %H:%M')}<br>"
        
        # Último log
        last_log = obj.deployment_logs.first()
        if last_log:
            info += f"<strong>Última acción:</strong> {last_log.get_log_type_display()} "
            info += f"({last_log.started_at.strftime('%d/%m/%Y %H:%M')})<br>"
            if last_log.success:
                info += '<span style="color: green;">✓ Exitoso</span>'
            else:
                info += '<span style="color: red;">✗ Error</span>'
        
        return mark_safe(info)
    status_info.short_description = 'Información de Estado'
    
    def access_urls(self, obj):
        """URLs de acceso a la aplicación"""
        if obj.status != 'deployed':
            return "La aplicación debe estar desplegada para ver las URLs de acceso"
        
        urls = f"""
        <strong>Aplicación:</strong> <a href="http://{obj.domain}:{obj.port}" target="_blank">
            http://{obj.domain}:{obj.port}
        </a><br>
        <strong>Admin Django:</strong> <a href="http://{obj.domain}:{obj.port}/admin/" target="_blank">
            http://{obj.domain}:{obj.port}/admin/
        </a><br>
        <strong>Path en servidor:</strong> <code>{obj.get_full_path()}</code><br>
        <strong>Entorno virtual:</strong> <code>{obj.get_venv_path()}</code>
        """
        return mark_safe(urls)
    access_urls.short_description = 'URLs de Acceso'
    
    def save_model(self, request, obj, form, change):
        """Asignar usuario creador si es nuevo"""
        if not change:  # Nuevo objeto
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }


@admin.register(DeploymentLog)
class DeploymentLogAdmin(admin.ModelAdmin):
    """Admin para logs de deployment"""
    
    list_display = [
        'application',
        'log_type',
        'success_indicator',
        'started_at',
        'duration_display',
        'executed_by'
    ]
    
    list_filter = [
        'success',
        'log_type',
        'started_at',
        'application'
    ]
    
    search_fields = [
        'application__name',
        'application__display_name',
        'command',
        'output',
        'error_output'
    ]
    
    readonly_fields = [
        'application',
        'log_type',
        'command',
        'started_at',
        'completed_at',
        'duration_display',
        'executed_by',
        'formatted_output',
        'formatted_error'
    ]
    
    fieldsets = (
        ('Información General', {
            'fields': (
                'application',
                'log_type',
                'success',
                'executed_by'
            )
        }),
        ('Tiempos', {
            'fields': (
                'started_at',
                'completed_at',
                'duration_display'
            )
        }),
        ('Comando', {
            'fields': ('command',)
        }),
        ('Salida', {
            'fields': ('formatted_output',),
            'classes': ('collapse',)
        }),
        ('Errores', {
            'fields': ('formatted_error',),
            'classes': ('collapse',)
        })
    )
    
    def success_indicator(self, obj):
        """Indicador visual de éxito"""
        if obj.success:
            return format_html(
                '<span style="color: green; font-size: 16px;">✓</span>'
            )
        return format_html(
            '<span style="color: red; font-size: 16px;">✗</span>'
        )
    success_indicator.short_description = 'Estado'
    
    def duration_display(self, obj):
        """Mostrar duración formateada"""
        duration = obj.duration()
        if duration:
            total_seconds = int(duration.total_seconds())
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}m {seconds}s"
        return "-"
    duration_display.short_description = 'Duración'
    
    def formatted_output(self, obj):
        """Salida formateada con HTML"""
        if obj.output:
            return format_html(
                '<pre style="background: #f4f4f4; padding: 10px; '
                'border-radius: 4px; overflow-x: auto;">{}</pre>',
                obj.output
            )
        return "Sin salida"
    formatted_output.short_description = 'Salida del Comando'
    
    def formatted_error(self, obj):
        """Errores formateados con HTML"""
        if obj.error_output:
            return format_html(
                '<pre style="background: #fee; padding: 10px; '
                'border-radius: 4px; overflow-x: auto; color: #c00;">{}</pre>',
                obj.error_output
            )
        return "Sin errores"
    formatted_error.short_description = 'Errores'
    
    def has_add_permission(self, request):
        """No permitir agregar logs manualmente"""
        return False
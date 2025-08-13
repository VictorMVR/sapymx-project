# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
import os
import shutil
from django.db import transaction
from django.utils import timezone
from .models import Application, ApplicationDependency, DeploymentLog, DbTable, DbColumn, DbTableColumn, Page, PageTable, Modal, PageModal, ModalForm, Menu, MenuPage, ApplicationMenu, Role, RoleMenu, Icon, _derive_form_question_defaults
from .forms import ApplicationForm, QuickDeployForm, DbTableForm, DbColumnForm, DbTableColumnForm
from django.db import models
import subprocess
import os
import json
from datetime import datetime
import threading
import re

# ==== FUNCIONES DE CONVERSIÓN DE TIPOS ====

def get_ui_input_type_for_db_type(db_data_type, is_primary_key=False, is_auto_increment=False, column_name: str | None = None):
    """Convierte tipo de dato de BD a tipo de input de UI."""
    if is_primary_key and is_auto_increment:
        return 'hidden'  # PK auto-increment no se muestra en formularios
    
    type_mapping = {
        'integer': 'number',
        'bigint': 'number', 
        'smallint': 'number',
        'serial': 'hidden',  # Serial es auto-increment
        'bigserial': 'hidden',  # BigSerial es auto-increment
        'varchar': 'text',
        'text': 'textarea',
        'boolean': 'checkbox',
        'date': 'date',
        'timestamp': 'datetime-local',
        'numeric': 'number',
    }
    
    # Detectar FKs por convención id_*
    try:
        if column_name and column_name.startswith('id_') and not (is_primary_key and is_auto_increment):
            return 'select'
    except Exception:
        pass
    return type_mapping.get(db_data_type, 'text')

def get_ui_label_for_column(column_name, data_type):
    """Genera etiqueta de UI basada en nombre de columna y tipo de dato."""
    # Convertir snake_case a Title Case
    label = column_name.replace('_', ' ').replace('-', ' ').title()
    
    # Ajustes específicos por tipo de dato
    if data_type in ['date', 'timestamp']:
        if 'fecha' not in label.lower():
            label = f"Fecha de {label}"
    elif data_type == 'boolean':
        if not any(word in label.lower() for word in ['activo', 'habilitado', 'visible', 'estado']):
            label = f"¿{label}?"
    # Si es id_* (FK) mantener literal id_* para UiColumn
    if column_name.startswith('id_'):
        label = column_name
    
    return label

def get_ui_validation_rules(column, data_type):
    """Genera reglas de validación de UI basadas en propiedades de la columna."""
    rules = []
    
    if not column.is_nullable:
        rules.append('required')
    
    if data_type in ['varchar', 'text']:
        if column.length:
            rules.append(f'max_length:{column.length}')
        if column.length and column.length > 0:
            rules.append(f'min_length:1')
    
    if data_type == 'numeric':
        if column.numeric_precision:
            rules.append(f'max_value:{10**column.numeric_precision - 1}')
    
    if data_type == 'email':
        rules.append('email')
    
    return rules

def create_ui_components_for_column(column):
    """Crea automáticamente UiColumn, UiField y FormQuestion para una DbColumn."""
    from .models import UiColumn, UiField, FormQuestion
    
    try:
        # Crear UiColumn
        ui_column = UiColumn.objects.create(
            db_column=column,
            label=get_ui_label_for_column(column.name, column.data_type),
            alignment='left',
            format='',
            visible_in_lists=True,
            is_toggle=column.data_type == 'boolean',
            width=None
        )
        print(f"DEBUG: UiColumn creada para {column.name}")
        
        # Crear UiField
        input_type = get_ui_input_type_for_db_type(
            column.data_type,
            column.is_primary_key,
            column.is_auto_increment,
            column.name
        )
        
        # Detectar FK y preparar opciones
        options_source = 'none'
        fk_table = None
        fk_label_field = 'nombre'
        try:
            if column.name.startswith('id_') and not (column.is_primary_key and column.is_auto_increment):
                from .models import DbTable
                ref_name = column.name[3:]
                fk_table = DbTable.objects.filter(name=ref_name).first()
                if fk_table:
                    options_source = 'fk'
        except Exception:
            pass

        ui_field = UiField.objects.create(
            db_column=column,
            label=get_ui_label_for_column(column.name, column.data_type),
            input_type=input_type,
            required=not column.is_nullable,
            step='' if column.data_type != 'numeric' else '0.01',
            min_value='',
            max_value='',
            pattern='',
            placeholder=f"Ingrese {get_ui_label_for_column(column.name, column.data_type).lower()}",
            options_source=options_source,
            fk_table=fk_table,
            fk_label_field=fk_label_field,
            order=1
        )
        print(f"DEBUG: UiField creado para {column.name}")
        
        # Crear FormQuestion solo si no es PK auto-increment
        if not (column.is_primary_key and column.is_auto_increment):
            # Determinar regla de validación
            validation_rule = 'none'
            validation_value = ''
            
            if not column.is_nullable:
                validation_rule = 'required'
            elif column.data_type == 'varchar' and column.length:
                validation_rule = 'max_length'
                validation_value = str(column.length)
            elif column.data_type == 'email':
                validation_rule = 'email'
            
            # Preparar label y tipo para FKs
            fq_input_type = input_type
            fq_question_text = get_ui_label_for_column(column.name, column.data_type)
            fq_options_source = 'none'
            fq_fk_table = None
            if column.name.startswith('id_'):
                try:
                    from .models import DbTable
                    ref_name = column.name[3:]
                    fq_fk_table = DbTable.objects.filter(name=ref_name).first()
                    if fq_fk_table:
                        select_label = ref_name.replace('_', ' ').title()
                        fq_question_text = f"Seleccionar {select_label}"
                        fq_input_type = 'select'
                        fq_options_source = 'fk'
                except Exception:
                    pass

            form_question = FormQuestion.objects.create(
                db_column=column,
                name=column.name,
                question_text=fq_question_text,
                help_text=column.notes or '',
                input_type=fq_input_type,
                required=not column.is_nullable,
                validation_rule=validation_rule,
                validation_value=validation_value,
                options_source=fq_options_source,
                options_custom='',
                fk_table=fq_fk_table,
                fk_value_field='id',
                fk_label_field='nombre',
                order=1,
                is_active=True
            )
            print(f"DEBUG: FormQuestion creada para {column.name}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: No se pudo crear componentes UI para {column.name}: {e}")
        import traceback
        traceback.print_exc()
        return False

def update_ui_components_for_column(column):
    """Actualiza los componentes de UI existentes (UiColumn, UiField, FormQuestion)
    si la columna ya tiene instancias asociadas."""
    from .models import UiColumn, UiField, FormQuestion
    
    try:
        ui_column = UiColumn.objects.filter(db_column=column).first()
        if ui_column:
            ui_column.label = get_ui_label_for_column(column.name, column.data_type)
            ui_column.save()
            print(f"DEBUG: UiColumn actualizada para {column.name}")

        ui_field = UiField.objects.filter(db_column=column).first()
        if ui_field:
            input_type = get_ui_input_type_for_db_type(
                column.data_type, 
                column.is_primary_key, 
                column.is_auto_increment
            )
            ui_field.label = get_ui_label_for_column(column.name, column.data_type)
            ui_field.input_type = input_type
            ui_field.required = not column.is_nullable
            ui_field.step = '' if column.data_type != 'numeric' else '0.01'
            ui_field.save()
            print(f"DEBUG: UiField actualizada para {column.name}")

        form_question = FormQuestion.objects.filter(db_column=column).first()
        if form_question:
            input_type = get_ui_input_type_for_db_type(
                column.data_type, 
                column.is_primary_key, 
                column.is_auto_increment
            )
            validation_rule = 'none'
            validation_value = ''
            
            if not column.is_nullable:
                validation_rule = 'required'
            elif column.data_type == 'varchar' and column.length:
                validation_rule = 'max_length'
                validation_value = str(column.length)
            elif column.data_type == 'email':
                validation_rule = 'email'
            
            form_question.question_text = get_ui_label_for_column(column.name, column.data_type)
            form_question.input_type = input_type
            form_question.required = not column.is_nullable
            form_question.validation_rule = validation_rule
            form_question.validation_value = validation_value
            form_question.save()
            print(f"DEBUG: FormQuestion actualizada para {column.name}")

    except Exception as e:
        print(f"WARNING: Error actualizando componentes UI para {column.name}: {e}")
        # No fallar la edición por problemas de UI

def migrate_existing_columns_to_ui():
    """Migra todas las columnas existentes que no tengan componentes de UI."""
    from .models import DbColumn, UiColumn, UiField, FormQuestion
    
    migrated_count = 0
    error_count = 0
    
    # Obtener todas las columnas que no tengan componentes de UI
    columns_without_ui = DbColumn.objects.filter(
        ~models.Q(ui_column__isnull=False) |
        ~models.Q(ui_field__isnull=False) |
        ~models.Q(form_question__isnull=False)
    ).distinct()
    
    print(f"DEBUG: Encontradas {columns_without_ui.count()} columnas sin componentes de UI")
    
    for column in columns_without_ui:
        try:
            # Crear componentes de UI
            ui_created = create_ui_components_for_column(column)
            if ui_created:
                migrated_count += 1
                print(f"DEBUG: Migrada columna {column.name}")
            else:
                error_count += 1
                print(f"ERROR: No se pudo migrar columna {column.name}")
        except Exception as e:
            error_count += 1
            print(f"ERROR: Excepción migrando columna {column.name}: {e}")
    
    return {
        'total_columns': columns_without_ui.count(),
        'migrated_count': migrated_count,
        'error_count': error_count
    }

@login_required
def migrate_columns_ui(request):
    """Vista para migrar columnas existentes a componentes de UI."""
    if request.method == 'POST':
        try:
            result = migrate_existing_columns_to_ui()
            if result['error_count'] == 0:
                messages.success(request, f'Migración completada: {result["migrated_count"]} columnas migradas exitosamente.')
            else:
                messages.warning(request, f'Migración completada con advertencias: {result["migrated_count"]} migradas, {result["error_count"]} errores.')
        except Exception as e:
            messages.error(request, f'Error durante la migración: {e}')
        
        return redirect('sapy:db_column_list')
    
    # Mostrar información de migración
    from .models import DbColumn, UiColumn, UiField, FormQuestion
    
    total_columns = DbColumn.objects.count()
    columns_with_ui = DbColumn.objects.filter(
        models.Q(ui_column__isnull=False) &
        models.Q(ui_field__isnull=False) &
        models.Q(form_question__isnull=False)
    ).count()
    
    context = {
        'total_columns': total_columns,
        'columns_with_ui': columns_with_ui,
        'columns_without_ui': total_columns - columns_with_ui,
        'title': 'Migrar Columnas a UI',
    }
    
    return render(request, 'migrate_columns_ui.html', context)

@login_required
def application_list(request):
    """Lista todas las aplicaciones registradas"""
    applications = Application.objects.all().order_by('-created_at')
    context = {
        'applications': applications,
        'title': 'Gestión de Aplicaciones ERP'
    }
    return render(request, 'application_list.html', context)


@login_required
def application_create(request):
    """Crear nueva aplicación"""
    if request.method == 'POST':
        form = ApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            application.created_by = request.user
            application.save()
            form.save_m2m()  # Para relaciones many-to-many si las hay
            
            messages.success(
                request, 
                f'Aplicación "{application.display_name}" creada exitosamente.'
            )
            return redirect('sapy:application_detail', pk=application.pk)
    else:
        form = ApplicationForm()
    
    context = {
        'form': form,
        'title': 'Nueva Aplicación',
        'submit_text': 'Crear Aplicación'
    }
    return render(request, 'application_form.html', context)


@login_required
def application_edit(request, pk):
    """Editar aplicación existente"""
    application = get_object_or_404(Application, pk=pk)
    
    if request.method == 'POST':
        form = ApplicationForm(request.POST, instance=application)
        if form.is_valid():
            application = form.save()
            messages.success(
                request, 
                f'Aplicación "{application.display_name}" actualizada exitosamente.'
            )
            return redirect('sapy:application_detail', pk=application.pk)
    else:
        form = ApplicationForm(instance=application)
    
    context = {
        'form': form,
        'application': application,
        'title': f'Editar: {application.display_name}',
        'submit_text': 'Guardar Cambios'
    }
    return render(request, 'application_form.html', context)


@login_required
def application_detail(request, pk):
    """Ver detalles de una aplicación"""
    application = get_object_or_404(
        Application.objects.prefetch_related(
            'dependencies', 
            'environment_vars',
            'deployment_logs'
        ), 
        pk=pk
    )
    
    # Obtener últimos logs de deployment
    recent_logs = application.deployment_logs.all()[:5]

    # Log activo (instalación en curso)
    active_log = application.deployment_logs.filter(log_type='install', completed_at__isnull=True).first()
    
    # Obtener tablas asignadas a esta aplicación
    assigned_tables = application.assigned_tables.select_related('table').all()[:5]  # Solo las primeras 5
    
    # Form para deploy rápido (no se usan campos, pero mantenemos la variable)
    deploy_form = QuickDeployForm()
    
    context = {
        'application': application,
        'recent_logs': recent_logs,
        'active_log': active_log,
        'assigned_tables': assigned_tables,
        'deploy_form': deploy_form,
        'title': application.display_name
    }
    return render(request, 'application_detail.html', context)


@login_required
@require_POST
def application_delete(request, pk):
    """Eliminar aplicación de manera segura (soft delete por estado)."""
    application = get_object_or_404(Application, pk=pk)
    confirm = request.POST.get('confirm')
    if confirm == 'yes':
        app_name = application.display_name
        application.status = 'deleted'
        application.save(update_fields=['status', 'updated_at'])
        messages.success(request, f'Aplicación "{app_name}" eliminada.')
        return redirect('sapy:application_list')
    # Si no hay confirmación explícita, volver al detalle
    messages.info(request, 'Acción cancelada.')
    return redirect('sapy:application_detail', pk=pk)


def _run_install_job(application_id: int, deployment_log_id: int) -> None:
    """Ejecuta el script de instalación en background y actualiza estado/logs."""
    from django.db import connection
    try:
        application = Application.objects.get(pk=application_id)
        deployment_log = DeploymentLog.objects.get(pk=deployment_log_id)
        script_path = '/srv/scripts/install_application_noninteractive.sh'
        args = [
            script_path,
            '--name', application.name,
            '--domain', application.domain,
            '--db-pass', application.db_password or '',
        ]
        # Captura incremental combinando stdout+stderr
        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        try:
            for line in process.stdout:  # type: ignore
                deployment_log.output = (deployment_log.output or '') + line
                deployment_log.save(update_fields=['output'])
        finally:
            ret = process.wait(timeout=5*60*60)  # hasta 5 horas
        # Guardar estado final
        if ret == 0:
            application.status = 'deployed'
            application.installed_at = timezone.now()
            deployment_log.success = True
        else:
            application.status = 'error'
            deployment_log.success = False
        deployment_log.completed_at = timezone.now()
        application.save()
        deployment_log.save()
    except Exception as e:
        try:
            application = Application.objects.get(pk=application_id)
            deployment_log = DeploymentLog.objects.get(pk=deployment_log_id)
            application.status = 'error'
            application.save()
            prev = deployment_log.error_output or ''
            deployment_log.error_output = prev + f"\nUnexpected error: {e}"
            deployment_log.success = False
            deployment_log.completed_at = timezone.now()
            deployment_log.save()
        except Exception:
            pass
    finally:
        # Cerrar conexiones en hilo background
        try:
            connection.close()
        except Exception:
            pass


@login_required
@require_POST
def application_deploy(request, pk):
    """Inicia instalación en background usando el script no interactivo."""
    application = get_object_or_404(Application, pk=pk)

    # Crear log y marcar estado
    deployment_log = DeploymentLog.objects.create(
        application=application,
        log_type='install',
        command='/srv/scripts/install_application_noninteractive.sh',
        executed_by=request.user
    )

    application.status = 'installing'
    application.save()

    # Lanzar en background
    t = threading.Thread(target=_run_install_job, args=(application.pk, deployment_log.pk), daemon=True)
    t.start()

    messages.info(request, 'Instalación iniciada. Puedes permanecer en esta página; actualiza el estado arriba.')
    return redirect('sapy:application_detail', pk=application.pk)


@login_required
def deployment_log_detail(request, pk, log_pk):
    """Ver detalles de un log de deployment"""
    application = get_object_or_404(Application, pk=pk)
    log = get_object_or_404(DeploymentLog, pk=log_pk, application=application)
    
    context = {
        'application': application,
        'log': log,
        'title': f'Log de Deployment - {log.started_at}'
    }
    return render(request, 'deployment_log_detail.html', context)


@login_required
def deployment_log_stream(request, pk, log_pk):
    """Devuelve el log en JSON para consumo en tiempo real."""
    application = get_object_or_404(Application, pk=pk)
    log = get_object_or_404(DeploymentLog, pk=log_pk, application=application)
    return JsonResponse({
        'output': log.output or '',
        'error_output': log.error_output or '',
        'success': log.success,
        'completed_at': log.completed_at.isoformat() if log.completed_at else None,
    })


@login_required
def application_status(request, pk):
    """Endpoint AJAX para verificar el estado de una aplicación"""
    application = get_object_or_404(Application, pk=pk)
    
    return JsonResponse({
        'status': application.status,
        'status_display': application.get_status_display(),
        'last_updated': application.updated_at.isoformat(),
        'installed': application.installed_at.isoformat() if application.installed_at else None
    })


@login_required
def test_script_connection(request):
    """Probar que el script de instalación existe y es ejecutable"""
    script_path = '/srv/scripts/install_application_noninteractive.sh'
    
    if os.path.exists(script_path):
        if os.access(script_path, os.X_OK):
            return JsonResponse({
                'success': True,
                'message': 'Script encontrado y ejecutable'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Script encontrado pero no es ejecutable'
            })
    else:
        return JsonResponse({
            'success': False,
            'message': 'Script no encontrado en la ruta especificada'
        })


# ==== Vistas para DB schema (tablas y columnas) ====

@login_required
def db_table_list(request):
    tables = DbTable.objects.order_by('schema_name', 'name')
    return render(request, 'db_table_list.html', {
        'tables': tables,
        'title': 'Tablas de Base de Datos',
    })


@login_required
@require_POST
def db_table_toggle_active(request, pk):
    table = get_object_or_404(DbTable, pk=pk)
    table.activo = 0 if table.activo else 1
    table.save(update_fields=['activo'])
    return redirect('sapy:db_table_list')


@login_required
def db_table_create(request):
    if request.method == 'POST':
        form = DbTableForm(request.POST)
        if form.is_valid():
            table = form.save()
            
            # Asignar columnas automáticamente según el tipo de tabla
            table.assign_default_columns()
            
            messages.success(request, f'Tabla "{table.name}" creada exitosamente con columnas básicas asignadas automáticamente.')
            return redirect('sapy:db_table_detail', pk=table.pk)
    else:
        form = DbTableForm()
    
    context = {
        'form': form,
        'title': 'Nueva Tabla BD',
        'submit_text': 'Crear Tabla',
    }
    
    return render(request, 'db_table_form.html', context)


@login_required
def db_table_edit(request, pk):
    table = get_object_or_404(DbTable, pk=pk)
    if request.method == 'POST':
        form = DbTableForm(request.POST, instance=table)
        if form.is_valid():
            form.save()
            messages.success(request, f'Tabla BD "{table.name}" guardada.')
            return redirect('sapy:db_table_detail', pk=table.pk)
    else:
        form = DbTableForm(instance=table)

    return render(request, 'db_table_form.html', {
        'form': form,
        'table': table,
        'title': f'Editar Tabla BD: {table.name}',
        'submit_text': 'Guardar',
    })


@login_required
def db_table_detail(request, pk):
    try:
        table = get_object_or_404(DbTable, pk=pk)
        # Obtener columnas asignadas a esta tabla a través de DbTableColumn
        table_columns = table.table_columns.all().order_by('position')
        
        # Obtener columnas disponibles para asignar (que no estén ya asignadas a esta tabla)
        assigned_column_ids = set(table_columns.values_list('column_id', flat=True))
        available_columns = DbColumn.objects.exclude(id__in=assigned_column_ids).order_by('name')
        
        return render(request, 'db_table_detail.html', {
            'table': table,
            'table_columns': table_columns,  # DbTableColumn objects
            'available_columns': available_columns,  # DbColumn objects
            'existing_columns': available_columns,  # Para el JavaScript de búsqueda
            'title': f'Tabla BD: {table.name}',
        })
    except Exception as exc:
        messages.error(request, f'No se pudo abrir el detalle de la tabla: {exc}')
        return redirect('sapy:db_table_list')


@login_required
@require_POST
def db_table_column_inline_update(request, pk):
    """Actualiza en línea campos override de DbTableColumn: is_nullable, is_unique, is_index, default_value."""
    table_column = get_object_or_404(DbTableColumn, pk=pk)
    field = request.POST.get('field')
    value = request.POST.get('value')
    if field not in ['is_nullable', 'is_unique', 'is_index', 'default_value']:
        return JsonResponse({'success': False, 'message': 'Campo no permitido'}, status=400)
    try:
        if field == 'default_value':
            table_column.default_value = value or ''
        else:
            # toggle Sí/No o boolean textual
            v = (str(value).lower() in ['true','1','si','sí','yes','on'])
            setattr(table_column, field, v)
        table_column.save(update_fields=[field])
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
def db_column_create(request, pk):
    table = get_object_or_404(DbTable, pk=pk)
    column = DbColumn()
    if request.method == 'POST':
        # Forzar que el hidden table se establezca por si el navegador no envía el input oculto
        post_data = request.POST.copy()
        post_data['table'] = str(table.pk)
        
        # Manejar copia desde columna existente por nombre
        copy_from_name = request.POST.get('copy_from_name')
        if copy_from_name:
            try:
                # Buscar cualquier columna con ese nombre (tomar la primera como referencia)
                source_column = DbColumn.objects.filter(name=copy_from_name).first()
                if not source_column:
                    messages.error(request, f'No se encontró una columna con el nombre "{copy_from_name}".')
                    return redirect('sapy:db_table_detail', pk=table.pk)
                
                # Verificar que no esté ya asignada a esta tabla
                if table.table_columns.filter(column=source_column).exists():
                    messages.error(request, f'La columna "{copy_from_name}" ya está asignada a esta tabla.')
                    return redirect('sapy:db_table_detail', pk=table.pk)
                
                # Crear relación tabla-columna usando DbTableColumn
                from django.db import models
                max_pos = table.table_columns.aggregate(max_pos=models.Max('position'))['max_pos'] or 0
                
                # Crear la relación tabla-columna
                table_column = DbTableColumn.objects.create(
                    table=table,
                    column=source_column,
                    position=max_pos + 1,
                    # Copiar propiedades específicas de la implementación
                    is_nullable=source_column.is_nullable,
                    is_unique=source_column.is_unique,
                    is_index=source_column.is_index,
                    is_primary_key=source_column.is_primary_key,
                    is_auto_increment=source_column.is_auto_increment,
                    default_value=source_column.default_value,
                    notes=source_column.notes
                )
                messages.success(request, f'Columna "{source_column.name}" asignada a la tabla.')
                return redirect('sapy:db_table_detail', pk=table.pk)
            except Exception as e:
                messages.error(request, f'Error al asignar la columna: {str(e)}')
                return redirect('sapy:db_table_detail', pk=table.pk)
        
        form = DbColumnForm(post_data, instance=column)
        if form.is_valid():
            new_col: DbColumn = form.save(commit=False)
            # Validaciones mínimas si faltan campos no obligatorios
            if not new_col.data_type:
                messages.error(request, 'Selecciona el tipo de dato de la columna.')
            else:
                # Guardar la columna global
                new_col.save()
                
                # Crear automáticamente los componentes de UI
                ui_created = create_ui_components_for_column(new_col)
                if ui_created:
                    print(f"DEBUG: Componentes UI creados automáticamente para {new_col.name}")
                else:
                    print(f"WARNING: No se pudieron crear componentes UI para {new_col.name}")
                
                # Crear la relación tabla-columna
                from django.db import models
                max_pos = table.table_columns.aggregate(max_pos=models.Max('position'))['max_pos'] or 0
                
                table_column = DbTableColumn.objects.create(
                    table=table,
                    column=new_col,
                    position=max_pos + 1,
                    # Copiar propiedades específicas de la implementación
                    is_nullable=new_col.is_nullable,
                    is_unique=new_col.is_unique,
                    is_index=new_col.is_index,
                    is_primary_key=new_col.is_primary_key,
                    is_auto_increment=new_col.is_auto_increment,
                    default_value=new_col.default_value,
                    notes=new_col.notes
                )
                
                messages.success(request, 'Columna creada y asignada a la tabla.')
                return redirect('sapy:db_table_detail', pk=table.pk)
        else:
            messages.error(request, 'Revisa los campos obligatorios del formulario.')
    else:
        form = DbColumnForm(instance=column)
    return render(request, 'db_column_form.html', {
        'form': form,
        'table': table,
        'title': f'Nueva Columna en {table.name}',
        'submit_text': 'Crear Columna',
    })


@login_required
def db_column_edit(request, col_pk):
    # Edición de columnas deshabilitada en esta sección por requerimiento.
    column = get_object_or_404(DbColumn, pk=col_pk)
    messages.info(request, 'Edición de columna no disponible aquí. Solo reordenar o desasignar.')
    return redirect('sapy:db_table_detail', pk=column.table_id)


@login_required
@require_POST
def db_column_delete(request, col_pk):
    column = get_object_or_404(DbColumn, pk=col_pk)
    table_pk = column.table_id
    name = column.name
    column.delete()
    messages.success(request, f'Columna "{name}" desasignada de la tabla.')
    return redirect('sapy:db_table_detail', pk=table_pk)


# ==== Vista de datos y toggle de activo (beta) ====

def _quote_ident(identifier: str) -> str:
    # Nuestros nombres están validados: ^[a-z][a-z0-9_]*$
    # Aún así, encapsulamos en comillas dobles por seguridad básica
    return '"' + identifier.replace('"', '') + '"'


@login_required
def db_table_data_list(request, pk):
    """Lista datos de una tabla física (hasta 100 filas) con soporte de toggle en 'activo'."""
    table = get_object_or_404(DbTable, pk=pk)
    schema = table.schema_name or 'public'
    # Columnas visibles según UI (si existen); fallback a columnas BD
    db_columns = list(table.columns.all().order_by('position', 'name'))
    # Intentar usar metadatos UI si existen
    visible_cols = []
    has_activo = False
    for c in db_columns:
        label = c.name.replace('_', ' ').capitalize()
        is_toggle = False
        try:
            if hasattr(c, 'ui_column'):
                label = c.ui_column.label or label
                is_toggle = getattr(c.ui_column, 'is_toggle', False)
        except Exception:
            pass
        if c.name == 'activo':
            has_activo = True
        visible_cols.append({'name': c.name, 'label': label, 'is_toggle': is_toggle})

    # Build SELECT: siempre incluir id para acciones
    select_list = ['"id"']
    select_list += [
        _quote_ident(c['name']) for c in visible_cols if c['name'] != 'id'
    ]
    select_cols = ', '.join(select_list)
    sql = f'SELECT {select_cols} FROM {_quote_ident(schema)}.{_quote_ident(table.name)} ORDER BY "id" DESC LIMIT 100'
    rows = []
    try:
        from django.db import connection
        with connection.cursor() as cur:
            cur.execute(sql)
            colnames = [desc[0] for desc in cur.description]
            for r in cur.fetchall():
                rows.append(dict(zip(colnames, r)))
    except Exception as exc:
        messages.error(request, f'No se pudieron leer los datos: {exc}')
        rows = []

    return render(request, 'db_table_data_list.html', {
        'table': table,
        'columns': visible_cols,
        'rows': rows,
        'has_activo': has_activo,
        'title': f"Datos: {table.name}",
    })


@login_required
@require_POST
def db_table_toggle_activo(request, pk, row_id: int):
    table = get_object_or_404(DbTable, pk=pk)
    # Verificar que exista columna 'activo'
    if not table.columns.filter(name='activo').exists():
        return JsonResponse({'success': False, 'message': 'La tabla no tiene columna activo'}, status=400)
    schema = table.schema_name or 'public'
    sql = f'UPDATE {_quote_ident(schema)}.{_quote_ident(table.name)} SET "activo" = NOT "activo" WHERE "id" = %s RETURNING "activo"'
    try:
        from django.db import connection
        with connection.cursor() as cur:
            cur.execute(sql, [row_id])
            res = cur.fetchone()
        if not res:
            return JsonResponse({'success': False, 'message': 'Registro no encontrado'}, status=404)
        return JsonResponse({'success': True, 'activo': bool(res[0])})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=500)


@login_required
@require_POST
def db_table_reorder(request, pk):
    """Reordena columnas de una tabla según el arreglo de IDs recibido."""
    table = get_object_or_404(DbTable, pk=pk)
    try:
        import json
        payload = json.loads(request.body.decode('utf-8'))
        order: list[int] = payload.get('order', [])
        if not isinstance(order, list) or not order:
            return JsonResponse({'success': False, 'message': 'Formato inválido'}, status=400)

        # Validar pertenencia
        valid_ids = set(table.columns.filter(id__in=order).values_list('id', flat=True))
        if len(valid_ids) != len(order):
            return JsonResponse({'success': False, 'message': 'IDs no válidos'}, status=400)

        # Actualizar posiciones 0..N según el orden recibido
        with transaction.atomic():
            update_objs: list[DbTableColumn] = []
            for index, col_id in enumerate(order, start=1):
                col = DbTableColumn.objects.get(id=col_id)
                col.position = index
                update_objs.append(col)
            DbTableColumn.objects.bulk_update(update_objs, ['position'])

        return JsonResponse({'success': True})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=500)


@login_required
def db_table_delete(request, pk):
    table = get_object_or_404(DbTable, pk=pk)
    if request.method != 'POST':
        messages.info(request, 'Para eliminar una tabla usa el botón Eliminar del listado.')
        return redirect('sapy:db_table_list')
    name = table.name
    try:
        table.delete()
        messages.success(request, f'Tabla BD "{name}" eliminada.')
    except Exception as exc:
        messages.error(request, f'No se pudo eliminar la tabla "{name}": {exc}')
    return redirect('sapy:db_table_list')


# ==== Gestión de Todas las Columnas BD ====

@login_required
def db_column_list(request):
    """Lista todas las columnas del sistema (en uso y disponibles)."""
    try:
        # Manejar eliminación de columnas si es POST
        if request.method == 'POST':
            action = request.POST.get('action')
            column_id = request.POST.get('column_id')
            
            if action == 'delete' and column_id:
                try:
                    column = get_object_or_404(DbColumn, pk=column_id)
                    column_name = column.name
                    
                    print(f"DEBUG: Intentando eliminar columna {column_name} (ID: {column_id})")
                    
                    # Verificar si está en uso
                    implementations_count = column.table_implementations.count()
                    print(f"DEBUG: Implementaciones encontradas: {implementations_count}")
                    
                    if implementations_count > 0:
                        messages.error(request, f'No se puede eliminar la columna "{column_name}" porque está asignada a tablas.')
                    else:
                        # Verificar relaciones adicionales antes de eliminar
                        can_delete = True
                        delete_reason = ""
                        
                        try:
                            # Verificar si hay UiColumn relacionada
                            if hasattr(column, 'ui_column') and column.ui_column:
                                can_delete = False
                                delete_reason = "configuraciones de UI"
                        except Exception as e:
                            print(f"DEBUG: Error verificando UiColumn: {e}")
                        
                        try:
                            # Verificar si hay UiField relacionada
                            if hasattr(column, 'ui_field') and column.ui_field:
                                can_delete = False
                                delete_reason = "configuraciones de campo UI"
                        except Exception as e:
                            print(f"DEBUG: Error verificando UiField: {e}")
                        
                        try:
                            # Verificar si hay FormQuestion relacionada
                            if hasattr(column, 'form_question') and column.form_question:
                                can_delete = False
                                delete_reason = "preguntas de formulario"
                        except Exception as e:
                            print(f"DEBUG: Error verificando FormQuestion: {e}")
                        
                        if can_delete:
                            # Eliminar la columna usando transacción
                            with transaction.atomic():
                                print(f"DEBUG: Iniciando transacción para eliminar columna {column_name}")
                                
                                # Verificar una vez más que no esté en uso
                                final_check = DbTableColumn.objects.filter(column=column).count()
                                if final_check > 0:
                                    raise Exception(f"La columna {column_name} está siendo usada por {final_check} tablas")
                                
                                # Eliminar la columna
                                print(f"DEBUG: Eliminando columna {column_name}")
                                column.delete()
                                print(f"DEBUG: Columna {column_name} eliminada exitosamente")
                            
                            messages.success(request, f'Columna "{column_name}" eliminada del sistema.')
                        else:
                            messages.error(request, f'No se puede eliminar la columna "{column_name}" porque tiene {delete_reason}.')
                            
                except Exception as exc:
                    print(f"DEBUG: Error eliminando columna: {exc}")
                    import traceback
                    traceback.print_exc()
                    messages.error(request, f'Error al eliminar la columna: {exc}')
                
                # Redirigir a la misma página para refrescar
                return redirect('sapy:db_column_list')
        
        # Código original para GET
        search_query = request.GET.get('search', '')
        data_type_filter = request.GET.get('data_type', '')
        
        # Obtener todas las columnas globales
        columns = DbColumn.objects.all().order_by('name')
        
        # Aplicar filtros
        if search_query:
            columns = columns.filter(name__icontains=search_query)
        
        if data_type_filter:
            columns = columns.filter(data_type=data_type_filter)
        
        # Obtener filtros disponibles
        data_types = DbColumn.objects.values_list('data_type', flat=True).distinct().order_by('data_type')
        
        # Para cada columna, obtener información de uso
        columns_data = []
        for column in columns:
            try:
                # Obtener todas las tablas donde aparece esta columna
                tables_using = list(DbTableColumn.objects.filter(column=column).values_list('table__name', flat=True).distinct())
                total_usage = len(tables_using)
                
                # Crear objeto con información completa
                column_info = {
                    'name': column.name,
                    'data_type': column.data_type,
                    'total_usage': total_usage,
                    'tables_using': tables_using,
                    'first_instance': column,
                    'can_delete': total_usage == 0,  # Solo se puede eliminar si no está en uso
                    'is_in_use': total_usage > 0,
                    'is_template': False,
                }
                columns_data.append(column_info)
            except Exception as e:
                print(f"DEBUG: Error procesando columna {column.name}: {e}")
                # Continuar con la siguiente columna
                continue
        
        context = {
            'columns': columns_data,
            'search_query': search_query,
            'data_type_filter': data_type_filter,
            'data_types': data_types,
            'total_count': len(columns_data),
            'filtered_count': len(columns_data),
        }
        
        return render(request, 'db_column_list.html', context)
    except Exception as e:
        import traceback
        print(f"Error en db_column_list: {e}")
        traceback.print_exc()
        # Retornar una respuesta de error simple
        from django.http import HttpResponse
        return HttpResponse(f"Error: {e}", status=500)


@login_required
def db_column_edit_standalone(request, pk):
    """Editar columna específica."""
    column = get_object_or_404(DbColumn, pk=pk)
    
    if request.method == 'POST':
        form = DbColumnForm(request.POST, instance=column)
        if form.is_valid():
            # Guardar la columna
            column = form.save()
            
            # Actualizar o crear componentes de UI si es necesario
            try:
                # Verificar si ya existen componentes de UI
                has_ui_column = hasattr(column, 'ui_column') and column.ui_column
                has_ui_field = hasattr(column, 'ui_field') and column.ui_field
                has_form_question = hasattr(column, 'form_question') and column.form_question
                
                if not (has_ui_column and has_ui_field and has_form_question):
                    # Crear componentes de UI faltantes
                    ui_created = create_ui_components_for_column(column)
                    if ui_created:
                        print(f"DEBUG: Componentes UI creados/actualizados para {column.name}")
                    else:
                        print(f"WARNING: No se pudieron crear componentes UI para {column.name}")
                else:
                    # Actualizar componentes existentes
                    update_ui_components_for_column(column)
                    print(f"DEBUG: Componentes UI actualizados para {column.name}")
                    
            except Exception as e:
                print(f"WARNING: Error actualizando componentes UI para {column.name}: {e}")
                # No fallar la edición por problemas de UI
            
            messages.success(request, f'Columna "{column.name}" actualizada exitosamente.')
            return redirect('sapy:db_column_list')
    else:
        form = DbColumnForm(instance=column)
    
    context = {
        'form': form,
        'column': column,
        'title': f'Editar Columna: {column.name}',
        'submit_text': 'Actualizar Columna',
        'is_required': True,
    }
    
    return render(request, 'db_column_form.html', context)


@login_required
@require_POST
def db_column_delete_standalone(request, pk):
    """Eliminar columna global (solo si no está en uso)."""
    try:
        column = get_object_or_404(DbColumn, pk=pk)
        column_name = column.name
        
        print(f"DEBUG: Intentando eliminar columna {column_name} (ID: {pk})")
        
        # Verificar si está en uso
        implementations_count = column.table_implementations.count()
        print(f"DEBUG: Implementaciones encontradas: {implementations_count}")
        
        if implementations_count > 0:
            messages.error(request, f'No se puede eliminar la columna "{column_name}" porque está asignada a tablas.')
            return redirect('sapy:db_column_list')
        
        # Verificar relaciones adicionales antes de eliminar
        try:
            # Verificar si hay UiColumn relacionada
            ui_column_count = getattr(column, 'ui_column', None)
            if ui_column_count:
                print(f"DEBUG: UiColumn encontrada para columna {column_name}")
                messages.error(request, f'No se puede eliminar la columna "{column_name}" porque tiene configuraciones de UI.')
                return redirect('sapy:db_column_list')
        except Exception as e:
            print(f"DEBUG: Error verificando UiColumn: {e}")
        
        try:
            # Verificar si hay UiField relacionada
            ui_field_count = getattr(column, 'ui_field', None)
            if ui_field_count:
                print(f"DEBUG: UiField encontrada para columna {column_name}")
                messages.error(request, f'No se puede eliminar la columna "{column_name}" porque tiene configuraciones de campo UI.')
                return redirect('sapy:db_column_list')
        except Exception as e:
            print(f"DEBUG: Error verificando UiField: {e}")
        
        try:
            # Verificar si hay FormQuestion relacionada
            form_question_count = getattr(column, 'form_question', None)
            if form_question_count:
                print(f"DEBUG: FormQuestion encontrada para columna {column_name}")
                messages.error(request, f'No se puede eliminar la columna "{column_name}" porque tiene preguntas de formulario.')
                return redirect('sapy:db_column_list')
        except Exception as e:
            print(f"DEBUG: Error verificando FormQuestion: {e}")
        
        # Eliminar la columna usando transacción
        with transaction.atomic():
            print(f"DEBUG: Iniciando transacción para eliminar columna {column_name}")
            
            # Verificar una vez más que no esté en uso
            final_check = DbTableColumn.objects.filter(column=column).count()
            if final_check > 0:
                raise Exception(f"La columna {column_name} está siendo usada por {final_check} tablas")
            
            # Eliminar la columna
            print(f"DEBUG: Eliminando columna {column_name}")
            column.delete()
            print(f"DEBUG: Columna {column_name} eliminada exitosamente")
        
        messages.success(request, f'Columna "{column_name}" eliminada del sistema.')
        return redirect('sapy:db_column_list')
        
    except Exception as exc:
        print(f"DEBUG: Error en db_column_delete_standalone: {exc}")
        import traceback
        traceback.print_exc()
        
        # Retornar una respuesta de error simple
        from django.http import HttpResponse
        return HttpResponse(f"Error al eliminar columna: {exc}", status=500)


@login_required
@require_POST
def db_table_column_delete(request, pk):
    """Desvincular columna de una tabla específica."""
    table_column = get_object_or_404(DbTableColumn, pk=pk)
    column_name = table_column.column.name
    table_name = table_column.table.name
    
    try:
        table_column.delete()
        messages.success(request, f'Columna "{column_name}" desvinculada de la tabla "{table_name}". La definición sigue disponible.')
    except Exception as exc:
        messages.error(request, f'Error al desvincular la columna "{column_name}": {exc}')
    
    return redirect('sapy:db_table_detail', pk=table_column.table.pk)


# ==== Gestión de Plantillas de Columnas BD ====

# Vista db_column_template_list eliminada


# Vista db_column_template_create eliminada


# Vista db_column_template_edit eliminada


# Vista db_column_template_delete eliminada


# Vista db_column_template_detail eliminada


# ==== GESTIÓN DE TABLAS ASIGNADAS A APLICACIONES ====

@login_required
def application_tables(request, pk):
    """Gestionar tablas asignadas a una aplicación específica."""
    application = get_object_or_404(Application, pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        table_id = request.POST.get('table_id')
        
        if action == 'assign' and table_id:
            try:
                table = get_object_or_404(DbTable, pk=table_id)
                
                # Verificar que no esté ya asignada
                if application.assigned_tables.filter(table=table).exists():
                    messages.warning(request, f'La tabla "{table.name}" ya está asignada a esta aplicación.')
                else:
                    # Crear la asignación
                    from .models import ApplicationTable
                    ApplicationTable.objects.create(
                        application=application,
                        table=table,
                        notes=f"Tabla asignada automáticamente el {timezone.now().strftime('%d/%m/%Y')}"
                    )
                    messages.success(request, f'Tabla "{table.name}" asignada a la aplicación "{application.display_name}".')
                
            except Exception as e:
                messages.error(request, f'Error al asignar la tabla: {e}')
        
        elif action == 'unassign' and table_id:
            try:
                # Buscar la asignación
                assignment = application.assigned_tables.filter(table_id=table_id).first()
                if assignment:
                    table_name = assignment.table.name
                    assignment.delete()
                    messages.success(request, f'Tabla "{table_name}" desasignada de la aplicación.')
                else:
                    messages.error(request, 'No se encontró la asignación de tabla.')
                    
            except Exception as e:
                messages.error(request, f'Error al desasignar la tabla: {e}')
        
        elif action == 'generate_model' and table_id:
            try:
                table = get_object_or_404(DbTable, pk=table_id)
                # Analizar dependencias de la tabla (id_*)
                dep_status = analyze_dependency_status(application, table)
                msgs = []
                if dep_status['missing_catalog']:
                    msgs.append(f"No existen en catálogo: {', '.join(dep_status['missing_catalog'])}")
                if dep_status['not_assigned']:
                    msgs.append(f"No asignadas a esta app: {', '.join(dep_status['not_assigned'])}")
                if dep_status['not_generated']:
                    msgs.append(f"No implementadas aún: {', '.join(dep_status['not_generated'])}")
                if msgs:
                    messages.warning(request, f"Antes de generar '{table.name}', resuelve dependencias → " + ' | '.join(msgs))
                else:
                    # Todas las dependencias están listas; generar solo esta tabla
                    result = generate_django_model_for_table(application, table)
                    if result.get('success'):
                        messages.success(request, f"Tabla '{table.name}' generada correctamente.")
                    else:
                        messages.error(request, f"Error generando '{table.name}': {result.get('error')}")
            except Exception as e:
                messages.error(request, f'Error al generar modelo: {e}')
        
        return redirect('sapy:application_tables', pk=application.pk)
    
    # Obtener tablas asignadas
    assigned_tables = application.assigned_tables.select_related('table').all()
    
    # Para cada tabla asignada, verificar si ya fue generada y contar registros
    for assignment in assigned_tables:
        assignment.is_generated = check_table_exists_in_app(application, assignment.table)
        if assignment.is_generated:
            assignment.record_count = get_table_record_count(application, assignment.table)
        else:
            assignment.record_count = None
    
    # Obtener tablas disponibles para asignar (excluyendo las ya asignadas)
    assigned_table_ids = assigned_tables.values_list('table_id', flat=True)
    available_tables = DbTable.objects.exclude(id__in=assigned_table_ids).filter(activo=True).order_by('name')
    
    # Búsqueda de tablas disponibles
    search_query = request.GET.get('search', '')
    if search_query:
        available_tables = available_tables.filter(name__icontains=search_query)
    
    context = {
        'application': application,
        'assigned_tables': assigned_tables,
        'available_tables': available_tables,
        'search_query': search_query,
        'title': f'Tablas de {application.display_name}',
    }
    
    return render(request, 'application_tables.html', context)


@login_required
def application_table_detail(request, app_pk, table_pk):
    """Ver detalles de una tabla específica asignada a una aplicación."""
    application = get_object_or_404(Application, pk=app_pk)
    table = get_object_or_404(DbTable, pk=table_pk)
    
    # Verificar que la tabla esté asignada a esta aplicación
    assignment = application.assigned_tables.filter(table=table).first()
    if not assignment:
        messages.error(request, 'Esta tabla no está asignada a la aplicación especificada.')
        return redirect('sapy:application_tables', pk=application.pk)
    
    # Obtener columnas de la tabla
    table_columns = table.table_columns.select_related('column').order_by('position')
    
    context = {
        'application': application,
        'table': table,
        'assignment': assignment,
        'table_columns': table_columns,
        'title': f'{table.name} en {application.display_name}',
    }
    
    return render(request, 'application_table_detail.html', context)


@login_required
def application_tables_search(request, pk):
	"""Devuelve JSON con tablas disponibles filtradas por 'q' para asignar a la app dada."""
	application = get_object_or_404(Application, pk=pk)
	q = (request.GET.get('q') or '').strip()
	assigned_ids = application.assigned_tables.values_list('table_id', flat=True)
	qs = DbTable.objects.filter(activo=True).exclude(id__in=assigned_ids)
	if q:
		qs = qs.filter(name__icontains=q)
	qs = qs.order_by('name')[:20]
	data = [
		{
			'id': t.id,
			'name': t.name,
			'columns_count': t.table_columns.count(),
			'description': (t.description or '')[:80]
		}
		for t in qs
	]
	return JsonResponse({'results': data})




@login_required
def application_menus(request, pk):
    application = get_object_or_404(Application, pk=pk)
    # Gestión de asignación/desasignación
    if request.method == 'POST':
        action = request.POST.get('action')
        menu_id = request.POST.get('menu_id')
        if action == 'assign' and menu_id:
            try:
                menu = get_object_or_404(Menu, pk=menu_id)
                if application.assigned_menus.filter(menu=menu).exists():
                    messages.warning(request, f'El menú "{menu.title}" ya está asignado a esta aplicación.')
                else:
                    ApplicationMenu.objects.create(application=application, menu=menu)
                    messages.success(request, f'Menú "{menu.title}" asignado a la aplicación.')
            except Exception as e:
                messages.error(request, f'Error al asignar el menú: {e}')
        elif action == 'unassign' and menu_id:
            try:
                am = application.assigned_menus.filter(menu_id=menu_id).first()
                if am:
                    title = am.menu.title
                    am.delete()
                    messages.success(request, f'Menú "{title}" desasignado de la aplicación.')
            except Exception as e:
                messages.error(request, f'Error al desasignar el menú: {e}')
        return redirect('sapy:application_menus', pk=application.pk)

    assigned = application.assigned_menus.select_related('menu').all()
    # Menús disponibles
    assigned_ids = assigned.values_list('menu_id', flat=True)
    available = Menu.objects.exclude(id__in=assigned_ids).filter(activo=True).order_by('name')
    # Búsqueda
    search_query = request.GET.get('search', '')
    if search_query:
        available = available.filter(models.Q(name__icontains=search_query) | models.Q(title__icontains=search_query))

    # Para cada menú asignado, construir detalles de sus páginas y checks por página
    details = []
    for am in assigned:
        pages = am.menu.menu_pages.select_related('page').order_by('section', 'order_index')
        page_infos = []
        for mp in pages:
            p = mp.page
            # Existe ruta en app destino? Reutilizamos route_path de Page
            # Para este generador, tratamos ruta como declarativa; marcamos 'exists' si el proyecto destino está desplegado y la ruta responde 200 (opcional). Por ahora indicamos N/D.
            route_exists = None  # N/D
            # Si es página basada en tabla, verificar registros
            records = 'N/D'
            if p.source_type == 'dbtable' and p.db_table_id:
                # Verificar existencia tabla y contar registros
                exists = check_table_exists_in_app(application, p.db_table)
                if exists:
                    cnt = get_table_record_count(application, p.db_table)
                    records = str(cnt if cnt is not None else '0')
                else:
                    records = 'N/D'
            page_infos.append({
                'title': p.title,
                'slug': p.slug,
                'icon': p.icon,
                'route_path': p.route_path,
                'section': mp.section or '1',
                'order_index': mp.order_index,
                'route_exists': route_exists,
                'records': records,
            })
        details.append({
            'menu': am.menu,
            'pages': page_infos,
        })

    context = {
        'application': application,
        'assigned_menus': details,
        'available_menus': available,
        'search_query': search_query,
        'title': f'Menús de {application.display_name}',
    }
    return render(request, 'application_menus.html', context)


@login_required
def application_menus_search(request, pk):
    application = get_object_or_404(Application, pk=pk)
    q = (request.GET.get('q') or '').strip()
    assigned_ids = application.assigned_menus.values_list('menu_id', flat=True)
    qs = Menu.objects.filter(activo=True).exclude(id__in=assigned_ids)
    if q:
        qs = qs.filter(models.Q(name__icontains=q) | models.Q(title__icontains=q))
    qs = qs.order_by('name')[:20]
    data = [
        {
            'id': m.id,
            'name': m.name,
            'title': m.title,
            'icon': m.icon,
        }
        for m in qs
    ]
    return JsonResponse({'results': data})

# ==== PAGES: generación desde DbTable y lectura de configuración efectiva ====

@login_required
@require_POST
def page_generate_from_dbtable(request):
    """Genera una Page con componentes por defecto a partir de una DbTable.
    Body: {"dbtable_id": int, "title"?: str, "slug"?: str}
    """
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'success': False, 'message': 'JSON inválido'}, status=400)

    dbtable_id = payload.get('dbtable_id')
    if not dbtable_id:
        return JsonResponse({'success': False, 'message': 'dbtable_id requerido'}, status=400)

    table = get_object_or_404(DbTable, pk=dbtable_id)

    # Defaults
    slug = (payload.get('slug') or table.name).strip().lower()
    base_title = table.alias or table.name
    try:
        if table.alias and len((table.alias or '').strip()) <= 1:
            base_title = table.name
    except Exception:
        base_title = table.name
    title = payload.get('title') or base_title.replace('_', ' ').capitalize()
    route_path = f"/{slug}/"

    with transaction.atomic():
        # Reusar si ya existe página para esta DbTable
        page = Page.objects.filter(source_type='dbtable', db_table=table).first()
        if page is None:
            # Evitar colisiones por slug/ruta
            existing_slug = Page.objects.filter(slug=slug).exists()
            if existing_slug:
                slug = f"{slug}-1"
                route_path = f"/{slug}/"
            page = Page.objects.create(
                slug=slug,
                title=title,
                description=table.description or '',
                source_type='dbtable',
                db_table=table,
                icon='',
                layout='',
                route_path=route_path,
                activo=True,
            )

        # Tabla principal con defaults (crear si falta)
        page_table = page.page_tables.filter(db_table=table).first()
        if page_table is None:
            page_table = PageTable.objects.create(
                page=page,
                db_table=table,
                title=title,
                searchable=True,
                export_csv=True,
                export_xlsx=True,
                export_pdf=True,
                page_size=25,
                default_sort={'by': 'id', 'dir': 'desc'},
                show_inactive=False,
                activo=True,
            )

        # Modal CRUD por defecto + formulario (crear si falta)
        pm = page.page_modals.select_related('modal').order_by('order_index').first()
        if pm is None:
            modal = Modal.objects.create(
                purpose='create_edit',
                title=f"Gestionar {title}",
                size='lg',
                icon='',
                close_on_backdrop=True,
                close_on_escape=True,
                prevent_close_on_enter=False,
                prevent_close_on_space=False,
                submit_button_label='Guardar',
                submit_button_icon='',
                cancel_button_label='Cancelar',
                activo=True,
            )
            PageModal.objects.create(page=page, modal=modal, order_index=0, activo=True)
            mf = ModalForm.objects.create(modal=modal, db_table=table, layout_columns_per_row=2, activo=True)
        else:
            modal = pm.modal
            mf = getattr(modal, 'form', None)
            if mf is None:
                mf = ModalForm.objects.create(modal=modal, db_table=table, layout_columns_per_row=2, activo=True)

        # Asegurar preguntas de formulario para columnas de la tabla (excepto PK autoincrement y técnicas)
        from .models import FormQuestion
        db_columns = table.table_columns.select_related('column').order_by('position')
        for tc in db_columns:
            col = tc.column
            if col.name in ['created_at', 'updated_at', 'id_auth_user']:
                continue
            if col.is_primary_key and col.is_auto_increment:
                continue
            fq = getattr(col, 'form_question', None)
            if not fq:
                try:
                    defaults = _derive_form_question_defaults(col, title)
                    FormQuestion.objects.create(db_column=col, **defaults)
                except Exception:
                    pass

    return JsonResponse({'success': True, 'page_id': page.id, 'slug': page.slug, 'route_path': page.route_path})


@login_required
def page_effective_config(request, page_id: int):
    """Devuelve la configuración efectiva de la página fusionando overrides con defaults.
    No crea overrides; solo calcula.
    """
    page = get_object_or_404(Page.objects.select_related('db_table'), pk=page_id)

    # Tabla efectiva (única en 95% de casos): usar la primera si hay varias
    pt = page.page_tables.select_related('db_table').first()
    table_cfg = None
    columns_cfg = []
    if pt:
        table_cfg = {
            'dbtable': pt.db_table.name,
            'searchable': pt.searchable,
            'export_csv': pt.export_csv,
            'export_xlsx': pt.export_xlsx,
            'export_pdf': pt.export_pdf,
            'page_size': pt.page_size,
            'default_sort': pt.default_sort,
            'show_inactive': pt.show_inactive,
        }

        # Defaults desde UiColumn si existen; si no, desde DbColumn
        db_columns = pt.db_table.table_columns.select_related('column').order_by('position')
        for tc in db_columns:
            col = tc.column
            base_title = col.name.replace('_', ' ').capitalize()
            try:
                if hasattr(col, 'ui_column') and col.ui_column:
                    base_title = col.ui_column.label or base_title
            except Exception:
                pass
            columns_cfg.append({
                'name': col.name,
                'title': base_title,
                'visible': True,
            })

        # Aplicar overrides si existen
        for ov in pt.column_overrides.all():
            # Resolver nombre de columna objetivo
            target_name = None
            if ov.ui_column_id and ov.ui_column and ov.ui_column.db_column_id:
                target_name = ov.ui_column.db_column.name
            elif ov.form_question_id and ov.form_question and ov.form_question.db_column_id:
                target_name = ov.form_question.db_column.name
            elif ov.db_column_id and ov.db_column:
                target_name = ov.db_column.name
            if not target_name:
                continue
            for c in columns_cfg:
                if c['name'] == target_name:
                    if ov.title_override:
                        c['title'] = ov.title_override
                    if ov.visible is not None:
                        c['visible'] = ov.visible
                    break

    # Modales y formularios (pueden ser varios; reusables)
    modals_cfg = []
    for pm in page.page_modals.select_related('modal').order_by('order_index'):
        m = pm.modal
        mf = getattr(m, 'form', None)
        form_cfg = None
        if mf:
            # Campos desde FormQuestion de la DbTable por defecto (si no hay, se derivan)
            fields = []
            if mf.db_table_id:
                db_columns = mf.db_table.table_columns.select_related('column').order_by('position')
                for tc in db_columns:
                    col = tc.column
                    if col.name in ['created_at', 'updated_at', 'id_auth_user']:
                        continue
                    fq = getattr(col, 'form_question', None)
                    if not fq:
                        # Derivar on-the-fly para visualización (sin persistir si falla)
                        try:
                            d = _derive_form_question_defaults(col)
                            # Construir opciones para selects FK
                            options = []
                            try:
                                if (d.get('input_type') == 'select' and d.get('options_source') == 'fk' and d.get('fk_table')):
                                    fk_tbl = d.get('fk_table')
                                    value_field = d.get('fk_value_field', 'id')
                                    label_field = d.get('fk_label_field', 'nombre')
                                    from django.db import connection
                                    table_ident = _quote_ident(getattr(fk_tbl, 'schema_name', 'public')) + '.' + _quote_ident(fk_tbl.name)
                                    sql1 = f'SELECT {_quote_ident(value_field)} as v, {_quote_ident(label_field)} as l FROM {table_ident} WHERE "activo" = true ORDER BY {_quote_ident(label_field)} LIMIT 200'
                                    sql2 = f'SELECT {_quote_ident(value_field)} as v, {_quote_ident(label_field)} as l FROM {table_ident} ORDER BY {_quote_ident(label_field)} LIMIT 200'
                                    try:
                                        with connection.cursor() as cur:
                                            cur.execute(sql1)
                                            options = [{'value': r[0], 'label': str(r[1])} for r in cur.fetchall()]
                                    except Exception:
                                        try:
                                            with connection.cursor() as cur:
                                                cur.execute(sql2)
                                                options = [{'value': r[0], 'label': str(r[1])} for r in cur.fetchall()]
                                        except Exception:
                                            options = []
                            except Exception:
                                options = []
                            # Metadatos para archivo/imagen
                            accept = None
                            preview = False
                            if d.get('input_type') == 'file':
                                if col.name == 'imagen':
                                    accept = 'image/*'
                                    preview = True
                                else:
                                    accept = '*/*'
                            fields.append({
                                'name': d['name'],
                                'label': d['question_text'].rstrip(':'),
                                'required': d['required'],
                                'placeholder': d['placeholder'],
                                'css_class': d['css_class'],
                                'input_type': d.get('input_type', 'text'),
                                'options': options,
                                'accept': accept,
                                'preview': preview,
                            })
                            continue
                        except Exception:
                            pass
                    if fq:
                        # Construir opciones para selects FK desde FormQuestion
                        options = []
                        try:
                            if (fq.input_type == 'select' and fq.options_source == fq.OptionsSource.FK and fq.fk_table_id):
                                from django.db import connection
                                value_field = fq.fk_value_field or 'id'
                                label_field = fq.fk_label_field or 'nombre'
                                fk_tbl = fq.fk_table
                                table_ident = _quote_ident(getattr(fk_tbl, 'schema_name', 'public')) + '.' + _quote_ident(fk_tbl.name)
                                sql1 = f'SELECT {_quote_ident(value_field)} as v, {_quote_ident(label_field)} as l FROM {table_ident} WHERE "activo" = true ORDER BY {_quote_ident(label_field)} LIMIT 200'
                                sql2 = f'SELECT {_quote_ident(value_field)} as v, {_quote_ident(label_field)} as l FROM {table_ident} ORDER BY {_quote_ident(label_field)} LIMIT 200'
                                try:
                                    with connection.cursor() as cur:
                                        cur.execute(sql1)
                                        options = [{'value': r[0], 'label': str(r[1])} for r in cur.fetchall()]
                                except Exception:
                                    try:
                                        with connection.cursor() as cur:
                                            cur.execute(sql2)
                                            options = [{'value': r[0], 'label': str(r[1])} for r in cur.fetchall()]
                                    except Exception:
                                        options = []
                        except Exception:
                            options = []
                        # Metadatos para archivo/imagen
                        accept = None
                        preview = False
                        if fq.input_type == 'file':
                            if col.name == 'imagen':
                                accept = 'image/*'
                                preview = True
                            else:
                                accept = '*/*'
                        fields.append({
                            'name': fq.name,
                            'label': fq.question_text.rstrip(':'),
                            'required': fq.required,
                            'placeholder': fq.placeholder,
                            'css_class': fq.css_class,
                            'input_type': fq.input_type,
                            'options': options,
                            'accept': accept,
                            'preview': preview,
                        })
            form_cfg = {
                'layout_columns_per_row': mf.layout_columns_per_row,
                'fields': fields,
            }
        modals_cfg.append({
            'title': m.title,
            'purpose': m.purpose,
            'size': m.size,
            'submit_button_label': m.submit_button_label,
            'cancel_button_label': m.cancel_button_label,
            'behavior': {
                'close_on_backdrop': m.close_on_backdrop,
                'close_on_escape': m.close_on_escape,
                'prevent_close_on_enter': m.prevent_close_on_enter,
                'prevent_close_on_space': m.prevent_close_on_space,
            },
            'form': form_cfg,
        })

    # Accesos directos
    shortcuts = [
        {
            'label': s.label,
            'icon': s.icon,
            'target_slug': s.target_page.slug,
        }
        for s in page.shortcuts.select_related('target_page').order_by('order_index')
    ]

    data = {
        'page': {
            'slug': page.slug,
            'title': page.title,
            'route_path': page.route_path,
            'source_type': page.source_type,
        },
        'table': table_cfg,
        'columns': columns_cfg,
        'modals': modals_cfg,
        'shortcuts': shortcuts,
    }
    return JsonResponse(data)


# ==== Gestión de Páginas (lista, detalle simple) ====

@login_required
def pages_list(request):
    pages = Page.objects.all().order_by('slug')
    return render(request, 'pages_list.html', {
        'pages': pages,
        'title': 'Gestión de Páginas',
    })


@login_required
def menus_list(request):
    menus = Menu.objects.all().order_by('name')
    return render(request, 'menus_list.html', {
        'menus': menus,
        'title': 'Menús de Navegación',
    })


@login_required
def menu_create(request):
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip().lower()
        title = (request.POST.get('title') or '').strip()
        icon = (request.POST.get('icon') or '').strip()
        if not name or not title:
            messages.error(request, 'Nombre y Título son obligatorios')
        else:
            try:
                m = Menu.objects.create(name=name, title=title, icon=icon)
                messages.success(request, f'Menú "{m.title}" creado.')
                return redirect('sapy:menu_detail', menu_id=m.id)
            except Exception as e:
                messages.error(request, f'Error creando menú: {e}')
    return render(request, 'menu_form.html', {'title': 'Nuevo Menú'})


@login_required
def roles_list(request):
    roles = Role.objects.all().order_by('name')
    return render(request, 'roles_list.html', {'roles': roles, 'title': 'Roles'})


@login_required
def role_create(request):
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip().lower()
        title = (request.POST.get('title') or '').strip()
        description = (request.POST.get('description') or '').strip()
        if not name or not title:
            messages.error(request, 'Nombre y Título son obligatorios')
        else:
            try:
                r = Role.objects.create(name=name, title=title, description=description)
                messages.success(request, f'Rol "{r.title}" creado')
                return redirect('sapy:role_detail', role_id=r.id)
            except Exception as e:
                messages.error(request, f'Error creando rol: {e}')
    return render(request, 'role_form.html', {'title': 'Nuevo Rol'})


@login_required
def role_detail(request, role_id: int):
    role = get_object_or_404(Role, pk=role_id)
    assigned = role.menus.select_related('menu').all()
    assigned_ids = assigned.values_list('menu_id', flat=True)
    available = Menu.objects.exclude(id__in=assigned_ids).filter(activo=True).order_by('name')
    # Asignar/desasignar
    if request.method == 'POST':
        action = request.POST.get('action')
        menu_id = request.POST.get('menu_id')
        if action == 'assign' and menu_id:
            try:
                m = get_object_or_404(Menu, pk=menu_id)
                RoleMenu.objects.get_or_create(role=role, menu=m)
                messages.success(request, f'Menú "{m.title}" asignado al rol')
            except Exception as e:
                messages.error(request, f'Error al asignar menú: {e}')
        elif action == 'unassign' and menu_id:
            try:
                rm = role.menus.filter(menu_id=menu_id).first()
                if rm:
                    t = rm.menu.title
                    rm.delete()
                    messages.success(request, f'Menú "{t}" desasignado del rol')
            except Exception as e:
                messages.error(request, f'Error al desasignar menú: {e}')
        return redirect('sapy:role_detail', role_id=role.id)
    return render(request, 'role_detail.html', {'role': role, 'assigned': assigned, 'available': available, 'title': f'Rol: {role.title}'})


@login_required
@require_POST
def role_update(request, role_id: int):
    role = get_object_or_404(Role, pk=role_id)
    role.title = (request.POST.get('title') or role.title).strip()
    role.description = (request.POST.get('description') or role.description).strip()
    activo = request.POST.get('activo')
    if activo is not None:
        role.activo = (activo.lower() == 'true')
    role.save()
    messages.success(request, 'Rol actualizado')
    return redirect('sapy:role_detail', role_id=role.id)


@login_required
def role_menus_search(request, role_id: int):
    role = get_object_or_404(Role, pk=role_id)
    q = (request.GET.get('q') or '').strip()
    assigned_ids = role.menus.values_list('menu_id', flat=True)
    qs = Menu.objects.exclude(id__in=assigned_ids).filter(activo=True)
    if q:
        qs = qs.filter(models.Q(name__icontains=q) | models.Q(title__icontains=q))
    qs = qs.order_by('name')[:20]
    data = [{ 'id': m.id, 'name': m.name, 'title': m.title, 'icon': m.icon } for m in qs]
    return JsonResponse({'results': data})


@login_required
def menu_detail(request, menu_id: int):
    menu = get_object_or_404(Menu, pk=menu_id)
    assigned = menu.menu_pages.select_related('page').order_by('section', 'order_index', 'page__slug')
    # Páginas disponibles (excluyendo las ya asignadas)
    assigned_ids = assigned.values_list('page_id', flat=True)
    available = Page.objects.exclude(id__in=assigned_ids).order_by('slug')
    search_query = request.GET.get('search', '')
    if search_query:
        q = search_query.strip()
        available = available.filter(models.Q(slug__icontains=q) | models.Q(title__icontains=q))
    return render(request, 'menu_detail.html', {
        'menu': menu,
        'assigned': assigned,
        'available': available,
        'search_query': search_query,
        'title': f'Menú: {menu.title}',
    })


@login_required
@require_POST
def menu_update(request, menu_id: int):
    menu = get_object_or_404(Menu, pk=menu_id)
    menu.title = (request.POST.get('title') or menu.title).strip()
    menu.icon = (request.POST.get('icon') or menu.icon).strip()
    activo = request.POST.get('activo')
    if activo is not None:
        menu.activo = (activo.lower() == 'true')
    menu.save()
    messages.success(request, 'Menú actualizado')
    return redirect('sapy:menu_detail', menu_id=menu.id)


@login_required
@require_POST
def menu_assign_page(request, menu_id: int):
    menu = get_object_or_404(Menu, pk=menu_id)
    page_id = request.POST.get('page_id')
    section = (request.POST.get('section') or '1').strip()
    try:
        pg = get_object_or_404(Page, pk=int(page_id))
        # Calcular order_index siguiente dentro de la sección
        max_order = menu.menu_pages.filter(section=section).aggregate(m=models.Max('order_index'))['m'] or 0
        MenuPage.objects.create(menu=menu, page=pg, section=section, order_index=max_order + 1)
        messages.success(request, f'Página "{pg.title}" asignada al menú.')
    except Exception as e:
        messages.error(request, f'Error al asignar página: {e}')
    return redirect('sapy:menu_detail', menu_id=menu.id)


@login_required
@require_POST
def menu_unassign_page(request, menu_id: int):
    menu = get_object_or_404(Menu, pk=menu_id)
    page_id = request.POST.get('page_id')
    try:
        mp = menu.menu_pages.filter(page_id=page_id).first()
        if mp:
            mp.delete()
            messages.success(request, 'Página desasignada del menú.')
    except Exception as e:
        messages.error(request, f'Error al desasignar página: {e}')
    return redirect('sapy:menu_detail', menu_id=menu.id)


@login_required
@require_POST
def menu_page_update(request, menu_id: int):
    """Actualiza sección u orden de una página asignada individualmente."""
    menu = get_object_or_404(Menu, pk=menu_id)
    page_id = request.POST.get('page_id')
    new_section = (request.POST.get('section') or '').strip()
    new_order = request.POST.get('order_index')
    mp = menu.menu_pages.filter(page_id=page_id).first()
    if not mp:
        return JsonResponse({'success': False, 'message': 'Asignación no encontrada'}, status=404)
    updated = False
    if new_section is not None:
        mp.section = new_section or '1'
        updated = True
    try:
        if new_order is not None:
            mp.order_index = int(new_order)
            updated = True
    except Exception:
        pass
    if updated:
        mp.save(update_fields=['section', 'order_index', 'updated_at'])
    return JsonResponse({'success': True})


@login_required
@require_POST
def menu_pages_reorder(request, menu_id: int):
    """Reordena todas las páginas asignadas: recibe lista de ids y su orden y opcionalmente sección."""
    import json
    menu = get_object_or_404(Menu, pk=menu_id)
    try:
        payload = json.loads(request.body.decode('utf-8'))
        items = payload.get('items') or []  # [{page_id, order_index, section?}]
        if not isinstance(items, list):
            return JsonResponse({'success': False, 'message': 'Formato inválido'}, status=400)
        updated = []
        for it in items:
            pid = it.get('page_id')
            order_i = it.get('order_index')
            section = it.get('section')
            mp = menu.menu_pages.filter(page_id=pid).first()
            if not mp:
                continue
            if section is not None:
                mp.section = (str(section) or '1')
            try:
                if order_i is not None:
                    mp.order_index = int(order_i)
            except Exception:
                pass
            updated.append(mp)
        if updated:
            MenuPage.objects.bulk_update(updated, ['section', 'order_index'])
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
def menu_pages_search(request, menu_id: int):
    menu = get_object_or_404(Menu, pk=menu_id)
    q = (request.GET.get('q') or '').strip()
    assigned_ids = menu.menu_pages.values_list('page_id', flat=True)
    qs = Page.objects.exclude(id__in=assigned_ids)
    if q:
        qs = qs.filter(models.Q(slug__icontains=q) | models.Q(title__icontains=q))
    qs = qs.order_by('slug')[:30]
    data = [
        {'id': p.id, 'slug': p.slug, 'title': p.title, 'route_path': p.route_path, 'icon': p.icon}
        for p in qs
    ]
    return JsonResponse({'results': data})


@login_required
def icons_search(request):
    """Busca íconos en BD por proveedor/clase/etiquetas. Retorna JSON para el picker."""
    q = (request.GET.get('q') or '').strip().lower()
    provider = (request.GET.get('provider') or '').strip()
    qs = Icon.objects.filter(activo=True)
    if provider in ['bi', 'fa']:
        qs = qs.filter(provider=provider)
    if q:
        qs = qs.filter(
            models.Q(class_name__icontains=q) |
            models.Q(name__icontains=q) |
            models.Q(label__icontains=q) |
            models.Q(tags__icontains=q)
        )
    limit = 400
    try:
        limit = max(50, min(800, int(request.GET.get('limit') or limit)))
    except Exception:
        limit = 400
    qs = qs.order_by('provider', 'class_name')[:limit]
    data = [
        {
            'class_name': ic.class_name,
            'label': ic.label,
            'tags': ic.tags,
            'name': ic.name,
            'provider': ic.provider,
            'style': ic.style,
            'library': ic.library,
        }
        for ic in qs
    ]
    return JsonResponse({'results': data})


@login_required
def icons_list(request):
    q = (request.GET.get('q') or '').strip()
    provider = (request.GET.get('provider') or '').strip()
    qs = Icon.objects.all().order_by('provider', 'class_name')
    if provider in ['bi','fa']:
        qs = qs.filter(provider=provider)
    if q:
        qs = qs.filter(models.Q(class_name__icontains=q) | models.Q(label__icontains=q) | models.Q(tags__icontains=q))
    return render(request, 'icons_list.html', {
        'icons': qs[:500],
        'q': q,
        'provider': provider,
        'title': 'Catálogo de Íconos',
    })


@login_required
def icons_import(request):
    """Importa íconos en bloque desde texto pegado (una clase por línea) u opcionalmente con prefijo de proveedor.
    Formatos aceptados por línea:
      - bi bi-people
      - fas fa-user
      - fa|fas fa-user (provider explícito al inicio separado por '|')
    """
    if request.method == 'POST':
        raw = (request.POST.get('payload') or '').strip()
        default_provider = (request.POST.get('provider') or '').strip()
        count = 0
        errors = 0
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            prov = default_provider if default_provider in ['bi','fa'] else ''
            cls = line
            # Permitir indicar provider al inicio: fa|fas fa-user
            if '|' in line:
                head, _, rest = line.partition('|')
                head = head.strip().lower()
                rest = rest.strip()
                if head in ['fa','bi']:
                    prov = head
                    cls = rest
            # Inferir provider por prefijo de clase
            if not prov:
                prov = 'fa' if cls.startswith('fa') else ('bi' if cls.startswith('bi') else 'bi')
            try:
                Icon.objects.get_or_create(class_name=cls, defaults={'provider': prov})
                count += 1
            except Exception:
                errors += 1
        messages.success(request, f'Importación finalizada. Agregados/existentes: {count}. Errores: {errors}.')
        return redirect('sapy:icons_list')
    return render(request, 'icons_import.html', {'title': 'Importar Íconos'})


@login_required
def page_detail(request, page_id: int):
    page = get_object_or_404(Page, pk=page_id)
    # Cargar componentes relacionados para la gestión
    page_table = page.page_tables.select_related('db_table').first()
    db_columns = []
    if page_table:
        db_columns = list(page_table.db_table.table_columns.select_related('column').order_by('position'))
    modals = list(page.page_modals.select_related('modal').order_by('order_index'))
    # Enriquecer con campos del formulario (config efectiva)
    for pm in modals:
        try:
            m = pm.modal
            mf = getattr(m, 'form', None)
            fields = []
            if mf and getattr(mf, 'db_table_id', None) and getattr(m, 'form_mode', 'auto') != 'none':
                overrides_map = {}
                try:
                    for ov in mf.field_overrides.all():
                        key = (ov.form_question_id or 0, ov.db_column_id or 0)
                        overrides_map[key] = ov
                except Exception:
                    overrides_map = {}
                db_cols = mf.db_table.table_columns.select_related('column').order_by('position')
                for tc in db_cols:
                    col = tc.column
                    if (col.name or '') in ['created_at','updated_at','id_auth_user']:
                        continue
                    fq = getattr(col, 'form_question', None)
                    if not fq:
                        try:
                            d = _derive_form_question_defaults(col)
                            base_label = d.get('question_text','').rstrip(':')
                            base_placeholder = d.get('placeholder','')
                            base_required = bool(d.get('required', False))
                            fq_id = 0
                        except Exception:
                            continue
                    else:
                        base_label = (fq.question_text or '').rstrip(':')
                        base_placeholder = fq.placeholder or ''
                        base_required = bool(fq.required)
                        fq_id = fq.id or 0
                    ov = overrides_map.get((fq_id, 0)) or overrides_map.get((0, col.id or 0))
                    label = (ov.label_override if (ov and ov.label_override) else base_label)
                    placeholder = (ov.placeholder if (ov and ov.placeholder) else base_placeholder)
                    width_fraction = getattr(ov, 'width_fraction', None) or '1/1'
                    required = (ov.required_override if (ov and ov.required_override is not None) else base_required)
                    visible = (ov.visible if ov is not None else True)
                    order_idx = (ov.order_index if (ov and ov.order_index is not None) else (getattr(fq, 'order', 1) if fq else (tc.position or 1)))
                    fields.append({
                        'fq_id': fq_id,
                        'db_col_id': col.id,
                        'name': getattr(fq, 'name', None) or col.name,
                        'label': label,
                        'placeholder': placeholder,
                        'width_fraction': width_fraction,
                        'required': required,
                        'visible': visible,
                        'order_index': int(order_idx or 1),
                    })
                fields.sort(key=lambda x: x.get('order_index', 1))
            pm.computed_fields = fields
        except Exception:
            pm.computed_fields = []
    return render(request, 'page_detail.html', {
        'page': page,
        'page_table': page_table,
        'db_columns': db_columns,
        'modals': modals,
        'title': f'Página: {page.title}',
    })


@login_required
@require_POST
def page_update(request, page_id: int):
    """Actualiza propiedades básicas de la página (por ahora solo título)."""
    page = get_object_or_404(Page, pk=page_id)
    new_title = (request.POST.get('title') or '').strip()
    new_icon = (request.POST.get('icon') or '').strip()
    table_title = (request.POST.get('table_title') or '').strip()
    updated_fields = []
    if new_title:
        page.title = new_title
        updated_fields.append('title')
    # Permitir limpiar icono enviando cadena vacía explícita
    if request.POST.get('icon') is not None:
        page.icon = new_icon
        updated_fields.append('icon')
    if updated_fields:
        updated_fields.append('updated_at')
        page.save(update_fields=updated_fields)
        messages.success(request, 'Página actualizada')
    # Guardar título de la tabla si existe PageTable
    if table_title and hasattr(page, 'page_tables'):
        pt = page.page_tables.first()
        if pt:
            pt.title = table_title
            pt.save(update_fields=['title'])
            messages.success(request, 'Título de la tabla actualizado')
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    return redirect('sapy:page_detail', page_id=page.id)


@login_required
@require_POST
def page_table_column_override_save(request, page_table_id: int):
    """Crea/actualiza overrides de columnas de tabla en página."""
    page_table = get_object_or_404(PageTable, pk=page_table_id)
    db_column_id = request.POST.get('db_column_id')
    title_override = request.POST.get('title_override')
    visible_str = request.POST.get('visible')
    try:
        visible = None if visible_str is None else (visible_str.lower() == 'true')
    except Exception:
        visible = None
    alignment = request.POST.get('alignment')
    fmt = request.POST.get('format')

    if not db_column_id:
        return JsonResponse({'success': False, 'message': 'db_column_id requerido'}, status=400)

    from .models import DbColumn, PageTableColumnOverride
    db_col = get_object_or_404(DbColumn, pk=int(db_column_id))
    ov, _ = PageTableColumnOverride.objects.get_or_create(
        page_table=page_table,
        db_column=db_col,
        defaults={}
    )
    if title_override is not None:
        ov.title_override = title_override or None
    if visible is not None:
        ov.visible = bool(visible)
    if alignment in ['left','center','right','',None]:
        ov.alignment = alignment or None
    if fmt in ['text','currency','decimal','percent','date','datetime','button','badge','link','',None]:
        ov.format = fmt or None
    ov.save()
    return JsonResponse({'success': True})


@login_required
@require_POST
def modal_update(request, modal_id: int):
    """Actualiza propiedades del modal (título, tamaño, comportamiento, labels)."""
    modal = get_object_or_404(Modal, pk=modal_id)
    fields_map = {
        'title': 'title',
        'size': 'size',
        'close_on_backdrop': 'close_on_backdrop',
        'close_on_escape': 'close_on_escape',
        'prevent_close_on_enter': 'prevent_close_on_enter',
        'prevent_close_on_space': 'prevent_close_on_space',
        'submit_button_label': 'submit_button_label',
        'cancel_button_label': 'cancel_button_label',
        'form_mode': 'form_mode',
        'external_template_path': 'external_template_path',
    }
    for key, attr in fields_map.items():
        if key in request.POST:
            val = request.POST.get(key)
            if attr in ['close_on_backdrop','close_on_escape','prevent_close_on_enter','prevent_close_on_space']:
                setattr(modal, attr, val.lower() == 'true')
            else:
                setattr(modal, attr, val)
    modal.save()
    messages.success(request, 'Modal actualizado')
    return redirect('sapy:page_detail', page_id=modal.pages.first().page_id if modal.pages.exists() else request.POST.get('page_id'))


@login_required
@require_POST
def modal_form_field_override_save(request, modal_id: int):
    """Crea/actualiza overrides de campos del formulario del modal."""
    modal = get_object_or_404(Modal, pk=modal_id)
    mf = getattr(modal, 'form', None)
    if mf is None:
        return JsonResponse({'success': False, 'message': 'Modal sin formulario'}, status=400)
    form_question_id = request.POST.get('form_question_id')
    db_column_id = request.POST.get('db_column_id')
    label_override = request.POST.get('label_override')
    placeholder = request.POST.get('placeholder')
    width_fraction = request.POST.get('width_fraction')
    required_override = request.POST.get('required_override')
    visible_str = request.POST.get('visible')
    order_index = request.POST.get('order_index')
    
    # Debug: mostrar en consola qué se está recibiendo
    print(f"DEBUG: width_fraction recibido: '{width_fraction}'")
    print(f"DEBUG: label_override recibido: '{label_override}'")
    print(f"DEBUG: placeholder recibido: '{placeholder}'")

    required_val = None
    if required_override is not None:
        if required_override.lower() in ['true','false']:
            required_val = (required_override.lower() == 'true')

    visible_val = None if visible_str is None else (visible_str.lower() == 'true')

    from .models import FormQuestion, DbColumn, ModalFormFieldOverride
    kwargs_key = {}
    if form_question_id:
        fq = get_object_or_404(FormQuestion, pk=int(form_question_id))
        kwargs_key['form_question'] = fq
    elif db_column_id:
        db_col = get_object_or_404(DbColumn, pk=int(db_column_id))
        kwargs_key['db_column'] = db_col
    else:
        return JsonResponse({'success': False, 'message': 'form_question_id o db_column_id requerido'}, status=400)

    ov, _ = ModalFormFieldOverride.objects.get_or_create(
        modal_form=mf,
        **kwargs_key
    )
    if label_override is not None:
        ov.label_override = label_override or None
    if placeholder is not None:
        ov.placeholder = placeholder or None
    if width_fraction in ['1-1','1-2','1-3','2-3','1-4','3-4','1-6','5-6']:
        ov.width_fraction = width_fraction
    if required_val is not None:
        ov.required_override = required_val
    if visible_str is not None:
        ov.visible = bool(visible_val)
    try:
        if order_index is not None:
            ov.order_index = int(order_index)
    except Exception:
        pass
    ov.save()
    return JsonResponse({'success': True})


# ==== FUNCIONES AUXILIARES PARA GENERACIÓN DE MODELOS ====

def check_table_exists_in_app(application, table):
	"""Verifica si una tabla ya existe en la aplicación destino."""
	try:
		import psycopg2
		from psycopg2 import sql
		# Probar múltiples configuraciones
		for params in _get_app_db_connect_params(application):
			try:
				conn = psycopg2.connect(**params)
				with conn.cursor() as cursor:
					query = sql.SQL("""
						SELECT EXISTS (
							SELECT FROM information_schema.tables 
							WHERE table_schema = 'public' 
							AND table_name = %s
						);
					""")
					cursor.execute(query, (table.name,))
					exists = cursor.fetchone()[0]
				conn.close()
				return bool(exists)
			except Exception as e:
				print(f"WARNING: conexión fallida {params.get('host')}:{params.get('port')} → {e}")
		return False
	except Exception as e:
		print(f"ERROR verificando existencia de tabla {table.name}: {e}")
		return False


def get_table_record_count(application, table):
	"""Obtiene el número de registros en una tabla de la aplicación destino."""
	try:
		import psycopg2
		from psycopg2 import sql
		for params in _get_app_db_connect_params(application):
			try:
				conn = psycopg2.connect(**params)
				with conn.cursor() as cursor:
					query = sql.SQL("SELECT COUNT(*) FROM {};" ).format(sql.Identifier(table.name))
					cursor.execute(query)
					count = cursor.fetchone()[0]
				conn.close()
				return int(count)
			except Exception as e:
				print(f"WARNING: conteo fallido {params.get('host')}:{params.get('port')} → {e}")
		return None
	except Exception as e:
		print(f"ERROR contando registros de tabla {table.name}: {e}")
		return None


def _ensure_directory_writable(path: str, web_user: str = 'www-data') -> tuple[bool, str | None]:
    """Intenta dejar un directorio existente o creado como escribible para el proceso web.
    - Crea el directorio si no existe
    - Aplica chown y chmod (mejor esfuerzo, sin depender de binarios externos)
    - Revalida acceso de escritura
    Retorna (ok, error_msg).
    """
    try:
        os.makedirs(path, mode=0o775, exist_ok=True)
    except Exception as e:
        return False, f'No se pudo crear directorio: {path} → {e}'
    try:
        try:
            shutil.chown(path, user=web_user, group=web_user)
        except Exception:
            pass
        try:
            os.chmod(path, 0o775)
        except Exception:
            pass
        if not os.access(path, os.W_OK):
            return False, f'No hay permisos de escritura en: {path}'
        return True, None
    except Exception as e:
        return False, f'Error corrigiendo/verificando permisos del directorio: {e}'


def generate_django_model_for_table(application, table):
    """Genera un modelo Django para una tabla específica en la aplicación destino."""
    try:
        # Obtener las columnas de la tabla usando DbTableColumn
        table_columns = table.table_columns.select_related('column').order_by('position')
        
        if not table_columns.exists():
            return {'success': False, 'error': 'La tabla no tiene columnas definidas'}
        
        # Generar el código del modelo
        model_code = generate_model_code(application, table, table_columns)
        
        # Construir ruta del archivo de modelos
        base_path = application.base_path.rstrip('/')
        app_name = application.name
        model_file_path = f"{base_path}/{app_name}/{app_name}/models.py"
        
        print(f"DEBUG: Ruta del archivo de modelos: {model_file_path}")
        
        # Crear toda la estructura de directorios necesaria
        import pwd
        
        # Asegurar permisos en app_base_dir y app_django_dir (no tocamos permisos de base_path del sistema)
        app_base_dir = f"{base_path}/{app_name}"
        app_django_dir = f"{app_base_dir}/{app_name}"
        # 1) base_path: solo validar existencia y permisos básicos, sin corregir
        if not os.path.isdir(base_path):
            return {'success': False, 'error': f'Directorio base_path no existe: {base_path}'}
        if not os.access(base_path, os.W_OK | os.X_OK):
            return {'success': False, 'error': f'base_path no es escribible/ejecutable: {base_path}'}
        # 2) app_base_dir
        ok, err = _ensure_directory_writable(app_base_dir)
        if not ok:
            return {'success': False, 'error': err}
        # 3) app_django_dir
        ok, err = _ensure_directory_writable(app_django_dir)
        if not ok:
            return {'success': False, 'error': err}
        print(f"DEBUG: Directorios verificados: base={base_path} app_base={app_base_dir} app_django={app_django_dir}")
        
        # Crear archivo __init__.py si no existe
        init_file = f"{app_django_dir}/__init__.py"
        if not os.path.exists(init_file):
            try:
                with open(init_file, 'w') as f:
                    f.write("# Django app initialization\n")
                print(f"DEBUG: Archivo __init__.py creado: {init_file}")
            except Exception as e:
                print(f"WARNING: No se pudo crear __init__.py: {e}")
        
        # Crear archivo models.py si no existe
        if not os.path.exists(model_file_path):
            try:
                with open(model_file_path, 'w') as f:
                    f.write("# Django models\n")
                print(f"DEBUG: Archivo models.py creado: {model_file_path}")
            except Exception as e:
                print(f"WARNING: No se pudo crear models.py: {e}")
        
        # Verificar permisos del archivo models.py
        if os.path.exists(model_file_path):
            if not os.access(model_file_path, os.W_OK):
                try:
                    try:
                        shutil.chown(model_file_path, user='www-data', group='www-data')
                    except Exception:
                        pass
                    try:
                        os.chmod(model_file_path, 0o664)
                    except Exception:
                        pass
                    if not os.access(model_file_path, os.W_OK):
                        return {'success': False, 'error': f'No hay permisos de escritura en: {model_file_path}'}
                    print("DEBUG: Permisos de models.py verificados/corregidos (Python)")
                except Exception as e:
                    return {'success': False, 'error': f'Error corrigiendo/verificando permisos de archivo: {e}'}
        
        # Escribir o actualizar el archivo de modelos
        try:
            write_model_to_file(model_file_path, table.name, model_code)
            print(f"DEBUG: Modelo escrito en: {model_file_path}")
        except PermissionError:
            return {'success': False, 'error': f'No hay permisos para escribir en: {model_file_path}'}
        except Exception as e:
            return {'success': False, 'error': f'Error escribiendo archivo: {e}'}
        
        # Ejecutar migraciones en la aplicación destino
        migration_result = run_migrations_in_app(application, table.name)
        
        if migration_result['success']:
            return {'success': True, 'message': f'Modelo generado y migraciones ejecutadas para {table.name}'}
        else:
            return {'success': False, 'error': f'Error en migraciones: {migration_result["error"]}'}
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


def generate_model_code(application, table, table_columns):
    """Genera el código Python del modelo Django."""
    model_lines = []
    
    # Imports
    model_lines.append("from django.db import models")
    model_lines.append("from django.utils import timezone")
    model_lines.append("")
    
    # Clase del modelo
    model_lines.append(f"class {table.name.title()}(models.Model):")
    model_lines.append(f'    """Modelo para la tabla {table.name}"""')
    model_lines.append("")
    
    # Campos del modelo
    for table_column in table_columns:
        column = table_column.column
        field_definition = generate_field_definition(table_column, column)
        model_lines.append(f"    {field_definition}")
    
    # Meta class
    model_lines.append("")
    model_lines.append("    class Meta:")
    model_lines.append(f'        db_table = "{table.name}"')
    if table.description:
        model_lines.append(f'        verbose_name = "{table.description}"')
    model_lines.append("")
    
    # String representation
    model_lines.append("    def __str__(self):")
    # Buscar un campo que parezca ser el nombre principal
    name_field = find_name_field(table_columns)
    if name_field:
        model_lines.append(f"        return str(self.{name_field})")
    else:
        model_lines.append(f"        return f'{table.name.title()}({{self.id}})'")
    
    return "\n".join(model_lines)


def generate_field_definition(table_column, column):
    """Genera la definición de un campo Django basado en DbTableColumn y DbColumn."""
    field_name = column.name
    field_type = get_django_field_type(column.data_type, column.length, column.numeric_precision, column.numeric_scale)
    
    # Propiedades del campo
    properties = []
    
    if not table_column.is_nullable:
        properties.append("null=False")
    else:
        properties.append("null=True")
    
    if table_column.is_unique:
        properties.append("unique=True")
    
    if table_column.is_index:
        properties.append("db_index=True")
    
    if table_column.is_primary_key:
        properties.append("primary_key=True")
    
    if table_column.is_auto_increment:
        properties.append("auto_created=True")
    
    # Valores específicos según el tipo
    if column.data_type == 'varchar' and column.length:
        properties.append(f"max_length={column.length}")
    
    if column.data_type == 'numeric':
        if column.numeric_precision:
            properties.append(f"max_digits={column.numeric_scale + column.numeric_precision}")
        if column.numeric_scale:
            properties.append(f"decimal_places={column.numeric_scale}")
    
    # Valor por defecto
    if table_column.default_value:
        if column.data_type == 'boolean':
            properties.append(f"default={table_column.default_value.lower()}")
        elif column.data_type in ['integer', 'bigint', 'smallint']:
            properties.append(f"default={table_column.default_value}")
        else:
            properties.append(f'default="{table_column.default_value}"')
    
    # Llave foránea
    if field_name.startswith('id_') and len(field_name.split('_')) > 1:
        referenced_table = field_name[3:]  # Remover 'id_'
        properties.append(f"on_delete=models.CASCADE")
        properties.append(f'related_name="{table_column.table.name}_set"')
        field_type = f"models.ForeignKey('{referenced_table.title()}', {', '.join(properties)})"
    else:
        field_type = f"{field_type}({', '.join(properties)})"
    
    # Comentario si hay notas
    if column.notes:
        return f"{field_name} = {field_type}  # {column.notes}"
    else:
        return f"{field_name} = {field_type}"


def get_django_field_type(db_type, length=None, precision=None, scale=None):
    """Convierte tipo de dato de BD a tipo de campo Django."""
    type_mapping = {
        'integer': 'models.IntegerField',
        'bigint': 'models.BigIntegerField',
        'smallint': 'models.SmallIntegerField',
        'serial': 'models.AutoField',
        'bigserial': 'models.BigAutoField',
        'varchar': 'models.CharField',
        'text': 'models.TextField',
        'boolean': 'models.BooleanField',
        'date': 'models.DateField',
        'timestamp': 'models.DateTimeField',
        'numeric': 'models.DecimalField',
    }
    
    return type_mapping.get(db_type, 'models.CharField')


def find_name_field(table_columns):
    """Busca un campo que parezca ser el nombre principal de la entidad."""
    name_patterns = ['nombre', 'name', 'titulo', 'title', 'descripcion', 'description']
    
    for table_column in table_columns:
        column_name = table_column.column.name.lower()
        if any(pattern in column_name for pattern in name_patterns):
            return table_column.column.name
    
    return None


def write_model_to_file(file_path, table_name, model_code):
	"""Escribe o reemplaza de forma segura el modelo en models.py.
	- Reemplaza el bloque completo `class {Model}(models.Model): ...` si existe
	- Agrega imports una sola vez al inicio del archivo
	"""
	import os, re
	model_class = f"{table_name.title()}"
	class_header = f"class {model_class}(models.Model):"

	existing_content = ""
	if os.path.exists(file_path):
		with open(file_path, 'r', encoding='utf-8') as f:
			existing_content = f.read()
	else:
		existing_content = ""

	# Asegurar imports únicos al inicio
	header_imports = "from django.db import models\nfrom django.utils import timezone\n\n"
	content = existing_content or ""
	if 'from django.db import models' not in content:
		content = header_imports + content

	# Reemplazar bloque de clase existente usando regex multiline
	pattern = rf"^class\s+{re.escape(model_class)}\(models\.Model\):[\s\S]*?(?=^class\s+|\Z)"
	re_flags = re.MULTILINE
	if re.search(pattern, content, flags=re_flags):
		content = re.sub(pattern, model_code + "\n", content, flags=re_flags)
	else:
		# Agregar al final con dos saltos de línea
		if not content.endswith('\n'):
			content += '\n'
		content += '\n' + model_code + '\n'

	with open(file_path, 'w', encoding='utf-8') as f:
		f.write(content)


def run_migrations_in_app(application, table_name):
    """Ejecuta migraciones en la aplicación destino."""
    try:
        import subprocess
        import os
        
        # Cambiar al directorio de la aplicación
        app_dir = f"{application.base_path}/{application.name}"
        if not os.path.exists(app_dir):
            return {'success': False, 'error': f'Directorio de aplicación no existe: {app_dir}'}
        
        # Verificar si existe entorno virtual
        venv_python = f"{app_dir}/venv/bin/python"
        if os.path.exists(venv_python):
            python_cmd = venv_python
            print(f"DEBUG: Usando entorno virtual: {venv_python}")
        else:
            python_cmd = 'python'
            print(f"DEBUG: Usando Python del sistema")
        
        # Asegurar que no heredamos DJANGO_SETTINGS_MODULE de SAPY
        env = os.environ.copy()
        env['DJANGO_SETTINGS_MODULE'] = f"{application.name}.settings"
        
        # Ejecutar makemigrations
        print(f"DEBUG: Ejecutando makemigrations en {app_dir}")
        result = subprocess.run(
            [python_cmd, 'manage.py', 'makemigrations'],
            cwd=app_dir,
            capture_output=True,
            text=True,
            timeout=60,
            env=env
        )
        
        if result.returncode != 0:
            error_msg = result.stderr if result.stderr else result.stdout
            return {'success': False, 'error': f'Error en makemigrations: {error_msg}'}
        
        print(f"DEBUG: makemigrations exitoso")
        
        # Ejecutar migrate
        print(f"DEBUG: Ejecutando migrate en {app_dir}")
        result = subprocess.run(
            [python_cmd, 'manage.py', 'migrate'],
            cwd=app_dir,
            capture_output=True,
            text=True,
            timeout=120,
            env=env
        )
        
        if result.returncode != 0:
            error_msg = result.stderr if result.stderr else result.stdout
            return {'success': False, 'error': f'Error en migrate: {error_msg}'}
        
        print(f"DEBUG: migrate exitoso")
        return {'success': True, 'message': 'Migraciones ejecutadas exitosamente'}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}

# ==== FUNCIONES AUXILIARES PARA DEPENDENCIAS DE TABLAS ====

def get_table_dependencies(root_table: DbTable) -> list[DbTable]:
	"""Devuelve las tablas (DbTable) de las que depende root_table vía columnas id_*. No incluye root_table.
	Resuelve por nombre: id_familias -> DbTable(name='familias').
	"""
	deps: list[DbTable] = []
	seen_names: set[str] = set()
	for tc in root_table.table_columns.select_related('column').all():
		col_name = tc.column.name or ''
		if col_name.startswith('id_') and len(col_name) > 3:
			ref_name = col_name[3:]
			# Excepción: auth_user es tabla base de Django, no exigirla en catálogo
			if ref_name == 'auth_user':
				continue
			if ref_name and ref_name not in seen_names:
				dep = DbTable.objects.filter(name=ref_name).first()
				if dep:
					deps.append(dep)
					seen_names.add(ref_name)
	return deps


def analyze_dependency_status(application: Application, root_table: DbTable) -> dict:
	"""Analiza dependencias por columnas id_* y clasifica faltantes sin inventar tablas.
	Devuelve dict con listas: missing_catalog (nombres), not_assigned (nombres), not_generated (nombres).
	"""
	status = {'missing_catalog': [], 'not_assigned': [], 'not_generated': []}
	seen_names: set[str] = set()
	for tc in root_table.table_columns.select_related('column').all():
		col_name = (tc.column.name or '').strip()
		if not (col_name.startswith('id_') and len(col_name) > 3):
			continue
		ref_name = col_name[3:]
		if not ref_name or ref_name in seen_names:
			continue
		# Excepción: auth_user existe por defecto en la app Django
		if ref_name == 'auth_user':
			seen_names.add(ref_name)
			continue
		seen_names.add(ref_name)
		dep = DbTable.objects.filter(name=ref_name).first()
		if not dep:
			status['missing_catalog'].append(ref_name)
			continue
		# Debe estar asignada a la app
		if not application.assigned_tables.filter(table=dep).exists():
			status['not_assigned'].append(dep.name)
			continue
		# Debe existir físicamente en la BD de la app
		if not check_table_exists_in_app(application, dep):
			status['not_generated'].append(dep.name)
	return status


def get_generation_order_for_table(root_table: DbTable) -> list[DbTable]:
	"""Calcula un orden de generación (topológico) simple: dependencias primero, luego root_table.
	Evita ciclos simples mediante conjunto de visitados.
	"""
	order: list[DbTable] = []
	visited: set[int] = set()
	stack: set[int] = set()

	def dfs(t: DbTable):
		if t.id in visited:
			return
		if t.id in stack:
			return  # ciclo: no continuar para evitar loop
		stack.add(t.id)
		for dep in get_table_dependencies(t):
			dfs(dep)
		order.append(t)
		stack.remove(t.id)
		visited.add(t.id)

	dfs(root_table)
	# El resultado contiene root_table al final; remover duplicados preservando orden
	seen: set[int] = set()
	unique_order: list[DbTable] = []
	for t in order:
		if t.id not in seen:
			unique_order.append(t)
			seen.add(t.id)
	return unique_order


def generate_table_with_dependencies(application: Application, root_table: DbTable) -> dict:
	"""Genera modelos y migra en orden de dependencias. Asigna automáticamente tablas faltantes a la app.
	Retorna dict con success y mensajes/resumen.
	"""
	from .models import ApplicationTable
	generated: list[str] = []
	assigned_now: list[str] = []
	order = get_generation_order_for_table(root_table)
	for table in order:
		# Asegurar asignación a la app
		if not application.assigned_tables.filter(table=table).exists():
			ApplicationTable.objects.create(
				application=application,
				table=table,
				notes=f"Asignada automáticamente por dependencia de {root_table.name}"
			)
			assigned_now.append(table.name)
		# Saltar si ya existe físicamente en la app
		if check_table_exists_in_app(application, table):
			continue
		res = generate_django_model_for_table(application, table)
		if not res.get('success'):
			return {
				'success': False,
				'error': f"Error generando '{table.name}': {res.get('error')}",
				'assigned_auto': assigned_now,
				'generated': generated,
			}
		generated.append(table.name)
	return {'success': True, 'generated': generated, 'assigned_auto': assigned_now}

# ==== Helpers de conexión a BD de aplicación destino ====

def _parse_database_url(db_url: str) -> dict:
	"""Parsea DATABASE_URL estilo dj_database_url y retorna dict para psycopg2.connect."""
	from urllib.parse import urlparse, unquote
	result = {}
	try:
		url = urlparse(db_url)
		result['host'] = url.hostname or 'localhost'
		if url.port:
			result['port'] = url.port
		result['database'] = (url.path or '/')[1:]
		if url.username:
			result['user'] = unquote(url.username)
		if url.password:
			result['password'] = unquote(url.password)
		# Buscar sslmode en query
		if url.query:
			for pair in url.query.split('&'):
				k, _, v = pair.partition('=')
				if k == 'sslmode' and v:
					result['sslmode'] = v
	except Exception:
		pass
	return result


def _get_app_db_connect_params(application: Application) -> list[dict]:
	"""Genera una lista de configuraciones de conexión a probar, en orden de preferencia.
	1) Campos del modelo Application
	2) DATABASE_URL del .env de la app destino (si existe)
	"""
	params_list: list[dict] = []
	# 1) Desde Application
	base = {
		'host': application.db_host or 'localhost',
		'port': application.db_port or 5432,
		'database': application.db_name,
		'user': application.db_user,
		'password': application.db_password or '',
	}
	if hasattr(application, 'db_sslmode') and application.db_sslmode:
		base['sslmode'] = application.db_sslmode
	params_list.append(base)
	# 2) Desde .env
	try:
		import os
		base_path = (application.base_path or '').rstrip('/')
		candidate_envs = []
		if base_path:
			candidate_envs.append(f"{base_path}/.env")
			if application.name:
				candidate_envs.append(f"{base_path}/{application.name}/.env")
		for env_path in candidate_envs:
			if not os.path.exists(env_path):
				continue
			content = ''
			with open(env_path, 'r') as f:
				content = f.read()
			for line in content.splitlines():
				line = line.strip()
				if not line or line.startswith('#'):
					continue
				if line.startswith('DATABASE_URL'):
					_, _, value = line.partition('=')
					value = value.strip().strip('"').strip("'")
					parsed = _parse_database_url(value)
					if parsed:
						params_list.append(parsed)
					break
	except Exception:
		pass
	return params_list
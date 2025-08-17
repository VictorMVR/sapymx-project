import os
import subprocess
from pathlib import Path
from typing import List, Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from sapy.models import Application, DbTable, ApplicationTable, Page, PageTable, Menu, ApplicationMenu, MenuPage


LIST_TEMPLATE = """{{% extends 'base.html' %}}
{{% load static %}}
{{% load utils %}}
{{% block content %}}
<!-- [sapy-auto:{table_name}:list start] -->
<div class=\"page page-{page_slug}\">
  <h1 class=\"page-title\">{page_title}</h1>

  {{% if shortcuts %}}
  <hr class=\"section-sep\" />
  <section class=\"shortcuts-section\">
    <ul class=\"shortcuts-list\">
      {{% for s in shortcuts %}}
      <li class=\"shortcut-item\">
        <i class=\"shortcut-icon {{{{ s.icon }}}}\"></i>
        <a class=\"shortcut-label\" href=\"{{{{ s.url }}}}\">{{{{ s.label }}}}</a>
      </li>
      {{% endfor %}}
    </ul>
  </section>
  {{% endif %}}

  <hr class=\"section-sep\" />
  <div class=\"modal-cta text-center\">
    <button type=\"button\" class=\"btn btn-primary modal-cta-btn\" data-bs-toggle=\"modal\" data-bs-target=\"#modal-{table_name}-form\">
      <i class=\"fas fa-plus\"></i>
      <span class=\"d-none d-sm-inline\">{{{{ modal_btn_title|default:'Agregar' }}}}</span>
    </button>
  </div>

  <hr class=\"section-sep\" />
  <section class=\"data-table-wrap\">
    <div class=\"table-toolbar d-flex justify-content-between align-items-center gap-2\">
      <div class=\"table-filters\"><!-- filtros --></div>
      <div class=\"d-flex align-items-center gap-2 ms-auto\">
        <div class=\"table-search\"><!-- búsqueda --></div>
        <div class=\"table-exports d-flex align-items-center gap-1\">
          <a class=\"btn btn-sm btn-outline-secondary export-csv\" href=\"/{table_name}/export/csv/\" title=\"Exportar CSV\">
            <i class=\"fas fa-file-csv\"></i>
          </a>
          <a class=\"btn btn-sm btn-outline-secondary export-xlsx\" href=\"/{table_name}/export/xlsx/\" title=\"Exportar Excel\">
            <i class=\"fas fa-file-excel\"></i>
          </a>
          <a class=\"btn btn-sm btn-outline-secondary export-pdf\" href=\"/{table_name}/export/pdf/\" title=\"Exportar PDF\">
            <i class=\"fas fa-file-pdf\"></i>
          </a>
        </div>
      </div>
    </div>

  <table class=\"table table-striped data-table\">
    <thead class=\"table-head\">
      <tr>
        {{% for col in columns %}}
        <th>{{{{ col.label }}}}</th>
        {{% endfor %}}
        <th class=\"text-end\">Acciones</th>
      </tr>
    </thead>
    <tbody class=\"table-body\">
      {{% if rows %}}
      {{% for row in rows %}}
      <tr>
        {{% for col in columns %}}
        <td>{{{{ row|get_item:col.name }}}}</td>
        {{% endfor %}}
        <td class=\"row-actions text-end\"><!-- acciones por fila --></td>
      </tr>
      {{% endfor %}}
      {{% else %}}
      <tr>
        <td class=\"text-center text-muted py-4\" colspan=\"{{{{ columns|length|add:1 }}}}\">Sin registros</td>
      </tr>
      {{% endif %}}
    </tbody>
  </table>
  </section>

  {{% include '{app_name}/modals/{table_name}_form_modal.html' %}}
{{% endblock %}}
"""


MODAL_TEMPLATE = """<!-- [sapy-auto:{table_name}:modal start] -->
<div class=\"modal fade\" id=\"modal-{table_name}-form\" tabindex=\"-1\" aria-hidden=\"true\">\n  <div class=\"modal-dialog modal-lg\">\n    <div class=\"modal-content\">\n      <div class=\"modal-header\">\n        <h5 class=\"modal-title\">{{{{ modal_title|default:'Nuevo registro' }}}}</h5>\n        <button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"modal\" aria-label=\"Close\"></button>\n      </div>\n      <div class=\"modal-body\">\n        <form id=\"form-{table_name}\" class=\"modal-form\" method=\"post\" action=\"{{% url '{table_name}_create' %}}\" enctype=\"multipart/form-data\">\n          {{% csrf_token %}}\n          <div class=\"row g-3\">\n            {{% for f in modal_fields %}}\n            <div class=\"col-12\">\n              <label class=\"form-label\">{{{{ f.label }}}}</label>\n              <input type=\"text\" name=\"{{{{ f.name }}}}\" class=\"form-control\" placeholder=\"{{{{ f.placeholder }}}}\" {{% if f.required %}}required{{% endif %}} />\n            </div>\n            {{% endfor %}}\n          </div>\n        </form>\n      </div>\n      <div class=\"modal-footer\">\n        <button type=\"button\" class=\"btn btn-secondary\" data-bs-dismiss=\"modal\">Cerrar</button>\n        <button type=\"submit\" class=\"btn btn-primary\" form=\"form-{table_name}\">Guardar</button>\n      </div>\n    </div>\n  </div>\n</div>\n<!-- [sapy-auto:{table_name}:modal end] -->\n"""


class Command(BaseCommand):
    help = "Genera páginas CRUD y modales para una Application destino (plantillas y hooks CSS)"

    def add_arguments(self, parser):
        parser.add_argument('--app', required=True, help='Nombre de la app destino (ej: facxy)')
        parser.add_argument('--tables', help='Lista de tablas (separadas por coma); omitir para --all-assigned')
        parser.add_argument('--all-assigned', action='store_true', help='Usar todas las tablas asignadas a la app')
        parser.add_argument('--btn-title', help='Título por defecto del botón para abrir modal')
        parser.add_argument('--with-modals', action='store_true', default=True, help='Generar modales (default: sí)')
        parser.add_argument('--menu', help='Slug de menú donde integrar las páginas (opcional)')
        parser.add_argument('--overwrite', action='store_true', help='Reescribir bloques sapy-auto si existen')
        parser.add_argument('--reload', action='store_true', help='Intentar recargar el servicio tras generar (systemd)')
        parser.add_argument('--reload-service', help='Nombre explícito de servicio systemd a recargar/reiniciar (ej: gunicorn@admischool)')

    @transaction.atomic
    def handle(self, *args, **options):
        app_name: str = options['app']
        btn_title: Optional[str] = options.get('btn_title')
        overwrite: bool = options.get('overwrite') or False
        with_modals: bool = bool(options.get('with_modals'))
        menu_slug: Optional[str] = options.get('menu')
        do_reload: bool = bool(options.get('reload'))
        reload_service: Optional[str] = options.get('reload_service')

        application = Application.objects.filter(name=app_name).first()
        if not application:
            raise CommandError(f"Application '{app_name}' no encontrada")

        if options.get('all-assigned'):
            qs = application.assigned_tables.select_related('table').all()
            tables = [at.table for at in qs]
        else:
            tables_arg = options.get('tables')
            if not tables_arg:
                raise CommandError('Debe indicar --tables o --all-assigned')
            names = [t.strip() for t in tables_arg.split(',') if t.strip()]
            tables = list(DbTable.objects.filter(name__in=names))

        base_path = Path(application.base_path.rstrip('/')) / app_name
        app_pkg_dir = base_path / app_name
        urls_path = app_pkg_dir / 'urls.py'
        views_path = app_pkg_dir / 'views.py'
        tpl_dir = base_path / 'templates' / app_name
        modal_dir = tpl_dir / 'modals'
        tpl_dir.mkdir(parents=True, exist_ok=True)
        modal_dir.mkdir(parents=True, exist_ok=True)

        # Asegurar librería de filtros en la app destino (para get_item)
        _ensure_template_tags(app_pkg_dir)

        created_files: List[str] = []
        updated_files: List[str] = []

        for table in tables:
            # Asegurar título legible; evitar alias demasiado cortos (p.ej. "ne")
            base_title = (getattr(table, 'alias', None) or table.name or '').strip()
            if len(base_title) < 3:
                base_title = table.name
            page_title = base_title.replace('_', ' ').title()
            page_slug = table.name
            list_content = LIST_TEMPLATE.format(
                table_name=table.name,
                page_title=page_title,
                page_slug=page_slug,
                app_name=app_name,
                modal_btn_title=btn_title,
            )
            modal_content = MODAL_TEMPLATE.format(table_name=table.name)

            list_path = tpl_dir / f"{table.name}_list.html"
            modal_path = modal_dir / f"{table.name}_form_modal.html"
            form_path = tpl_dir / f"{table.name}_form.html"
            confirm_path = tpl_dir / f"{table.name}_confirm_delete.html"

            def _ensure_parent_dir_writable(p: Path):
                try:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        # Intento best-effort de permisos
                        os.chmod(p.parent, 0o775)
                    except Exception:
                        pass
                except Exception:
                    pass

            def write_block(path: Path, content: str, block_key: str):
                _ensure_parent_dir_writable(path)
                if path.exists():
                    old = path.read_text(encoding='utf-8')
                    start = f"[sapy-auto:{block_key} start]"
                    end = f"[sapy-auto:{block_key} end]"
                    if start in old and end in old:
                        if overwrite:
                            # Para listas, reescribir archivo completo para garantizar extends/base y blocks
                            if block_key.endswith(':list') and path.suffix == '.html':
                                try:
                                    path.write_text(content, encoding='utf-8')
                                except PermissionError as e:
                                    raise CommandError(f"Permisos insuficientes para escribir {path}. Sugerencia: chown -R www-data:www-data {base_path} && chmod -R 775 {base_path}") from e
                                updated_files.append(str(path))
                            else:
                                # Reemplazar solo el bloque
                                new = _replace_block(old, content, start, end)
                                try:
                                    path.write_text(new, encoding='utf-8')
                                except PermissionError as e:
                                    raise CommandError(f"Permisos insuficientes para escribir {path}. Sugerencia: chown -R www-data:www-data {base_path} && chmod -R 775 {base_path}") from e
                                updated_files.append(str(path))
                        else:
                            # Conservar, no sobrescribir
                            pass
                    else:
                        if overwrite:
                            # Si es lista HTML y no hay marcadores, reescribir completo para garantizar layout
                            if block_key.endswith(':list') and path.suffix == '.html':
                                try:
                                    path.write_text(content, encoding='utf-8')
                                except PermissionError as e:
                                    raise CommandError(f"Permisos insuficientes para escribir {path}. Sugerencia: chown -R www-data:www-data {base_path} && chmod -R 775 {base_path}") from e
                                updated_files.append(str(path))
                            else:
                                # Anexar al final de archivo para no sobreescribir contenido del usuario
                                try:
                                    with open(path, 'a', encoding='utf-8') as fh:
                                        fh.write("\n" + content)
                                except PermissionError as e:
                                    raise CommandError(f"Permisos insuficientes para escribir {path}. Sugerencia: chown -R www-data:www-data {base_path} && chmod -R 775 {base_path}") from e
                                updated_files.append(str(path))
                else:
                    try:
                        path.write_text(content, encoding='utf-8')
                    except PermissionError as e:
                        raise CommandError(f"Permisos insuficientes para crear {path}. Sugerencia: chown -R www-data:www-data {base_path} && chmod -R 775 {base_path}") from e
                    created_files.append(str(path))

            write_block(list_path, list_content, f"{table.name}:list")
            if with_modals:
                write_block(modal_path, modal_content, f"{table.name}:modal")

            # Formularios básicos y confirmación de borrado (plantillas simples)
            form_tpl = (
                f"{{% extends 'base.html' %}}\n{{% block content %}}\n"
                f"<div class=\"page page-{table.name}\">\n"
                f"  <h1 class=\"page-title\">Formulario {page_title}</h1>\n"
                f"  <form method=\"post\" enctype=\"multipart/form-data\">{{% csrf_token %}}\n"
                f"    {{% for field in form %}}\n"
                f"    <div class=\"field field-1-1\">\n"
                f"      <label>{{{{ field.label }}}}</label> {{{{ field }}}}\n"
                f"      {{{{ field.errors }}}}\n"
                f"    </div>\n"
                f"    {{% endfor %}}\n"
                f"    <div class=\"text-end\"><button class=\"btn btn-primary\" type=\"submit\">Guardar</button></div>\n"
                f"  </form>\n"
                f"</div>\n{{% endblock %}}\n"
            )
            confirm_tpl = (
                f"{{% extends 'base.html' %}}\n{{% block content %}}\n"
                f"<div class=\"page page-{table.name}\">\n"
                f"  <h1 class=\"page-title\">Confirmar eliminación</h1>\n"
                f"  <p>¿Desea eliminar este registro?</p>\n"
                f"  <form method=\"post\">{{% csrf_token %}}\n"
                f"    <a class=\"btn btn-secondary\" href=\"{{% url '{table.name}_list' %}}\">Cancelar</a>\n"
                f"    <button class=\"btn btn-danger\" type=\"submit\">Eliminar</button>\n"
                f"  </form>\n"
                f"</div>\n{{% endblock %}}\n"
            )
            write_block(form_path, form_tpl, f"{table.name}:form")
            write_block(confirm_path, confirm_tpl, f"{table.name}:confirm_delete")

            # URLs y Views: insertar bloques por tabla
            urls_block = _build_urls_block(app_name, table.name)
            write_block(urls_path, urls_block, f"{table.name}:urls")

            views_block = _build_views_block(app_name, table.name, btn_title)
            write_block(views_path, views_block, f"{table.name}:views")

            # Crear/actualizar Page y PageTable
            page, _ = Page.objects.get_or_create(
                slug=table.name,
                defaults={
                    'title': page_title,
                    'db_table': table,
                    'route_path': f"/{table.name}/",
                }
            )
            PageTable.objects.get_or_create(page=page, db_table=table, defaults={'title': page_title})

            # Integración a menú si se pidió
            if menu_slug:
                menu, _ = Menu.objects.get_or_create(name=menu_slug, defaults={'title': menu_slug.title()})
                ApplicationMenu.objects.get_or_create(application=application, menu=menu)
                MenuPage.objects.get_or_create(menu=menu, page=page, defaults={'order_index': 1})

        self.stdout.write(self.style.SUCCESS('Generación completada.'))
        if created_files:
            self.stdout.write('Archivos creados:')
            for f in created_files:
                self.stdout.write(f" - {f}")
        if updated_files:
            self.stdout.write('Archivos actualizados:')
            for f in updated_files:
                self.stdout.write(f" - {f}")

        # Recarga best-effort
        if do_reload or reload_service:
            self._best_effort_reload(app_name, reload_service)
        else:
            # Intento prudente por defecto para que se reflejen cambios sin intervención
            self._best_effort_reload(app_name, None)

    def _best_effort_reload(self, app_name: str, explicit_service: Optional[str]) -> None:
        candidates: List[str] = []
        if explicit_service:
            candidates.append(explicit_service)
        # Variantes comunes de gunicorn
        candidates.extend([
            f'gunicorn@{app_name}',
            f'gunicorn@{app_name}.service',
            f'gunicorn-{app_name}.service',
            'gunicorn@default',
            'gunicorn.service',
            'gunicorn',
        ])
        for svc in candidates:
            try:
                res = subprocess.run(['systemctl', 'reload', svc], capture_output=True, text=True)
                if res.returncode == 0:
                    self.stdout.write(self.style.SUCCESS(f"Recargado: {svc}"))
                    return
                # Intentar restart si reload falla
                res2 = subprocess.run(['systemctl', 'restart', svc], capture_output=True, text=True)
                if res2.returncode == 0:
                    self.stdout.write(self.style.SUCCESS(f"Reiniciado: {svc}"))
                    return
                # Log corto del error
                err_tail = (res.stderr or res2.stderr or '')[-200:]
                self.stdout.write(f"No se pudo recargar/reiniciar {svc}: {err_tail}")
            except Exception as exc:
                self.stdout.write(f"Error al manejar servicio {svc}: {exc}")
        self.stdout.write("No se encontró servicio systemd adecuado para recargar.")


def _replace_block(text: str, whole_content: str, start_marker: str, end_marker: str) -> str:
    """Reemplaza seguro a nivel de líneas el bloque delimitado por start_marker/end_marker.

    - Localiza la línea que contiene start_marker y la que contiene end_marker
    - Sustituye desde el inicio de la línea de start_marker hasta el final de la línea de end_marker
    - No intenta abarcar llaves/comentarios especiales para evitar recortes indebidos
    """
    sm_idx = text.find(start_marker)
    em_idx = text.find(end_marker)
    if sm_idx == -1 or em_idx == -1:
        # Si no están ambos marcadores, no tocar el archivo aquí; el caller decidirá anexar
        return text
    # Inicio de línea del start
    line_start = text.rfind('\n', 0, sm_idx)
    line_start = 0 if line_start == -1 else line_start + 1
    # Fin de línea del end
    line_end = text.find('\n', em_idx)
    if line_end == -1:
        line_end = len(text)
    else:
        line_end = line_end + 1
    return text[:line_start] + whole_content + text[line_end:]


def _ensure_template_tags(app_pkg_dir: Path) -> None:
    """Garantiza que exista app/templatetags con un filtro 'get_item'. Idempotente."""
    tt_dir = app_pkg_dir / 'templatetags'
    try:
        tt_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        return
    init_py = tt_dir / '__init__.py'
    utils_py = tt_dir / 'utils.py'
    try:
        if not init_py.exists():
            init_py.write_text("# templatetags package\n", encoding='utf-8')
    except Exception:
        pass
    if not utils_py.exists():
        try:
            utils_py.write_text(
                "from django import template\n\n"
                "register = template.Library()\n\n"
                "@register.filter(name='get_item')\n"
                "def get_item(value, key):\n"
                "    if value is None:\n"
                "        return ''\n"
                "    try:\n"
                "        if isinstance(value, dict):\n"
                "            return value.get(key, '')\n"
                "        return getattr(value, key, '')\n"
                "    except Exception:\n"
                "        return ''\n",
                encoding='utf-8',
            )
        except Exception:
            pass


def _build_urls_block(app_name: str, table_name: str) -> str:
    """Construye bloque de urls para una tabla específica."""
    return (
        f"# [sapy-auto:{table_name}:urls start]\n"
        f"from django.urls import path\n"
        f"from . import views\n"
        f"try:\n    urlpatterns\nexcept NameError:\n    urlpatterns = []\n\n"
        f"urlpatterns += [\n"
        f"    path('{table_name}/', views.list_{table_name}, name='{table_name}_list'),\n"
        f"    path('{table_name}/create/', views.create_{table_name}, name='{table_name}_create'),\n"
        f"    path('{table_name}/<int:pk>/update/', views.update_{table_name}, name='{table_name}_update'),\n"
        f"    path('{table_name}/<int:pk>/delete/', views.delete_{table_name}, name='{table_name}_delete'),\n"
        f"    path('ajax/fk/<str:model>/', views.ajax_fk_options, name='ajax_fk_options'),\n"
        f"    path('{table_name}/export/csv/', views.export_{table_name}_csv, name='{table_name}_export_csv'),\n"
        f"    path('{table_name}/export/xlsx/', views.export_{table_name}_xlsx, name='{table_name}_export_xlsx'),\n"
        f"    path('{table_name}/export/pdf/', views.export_{table_name}_pdf, name='{table_name}_export_pdf'),\n"
        f"]\n"
        f"# [sapy-auto:{table_name}:urls end]\n"
    )


def _build_views_block(app_name: str, table_name: str, btn_title: Optional[str]) -> str:
    """Construye bloque de vista lista por tabla, usando apps.get_model para resolver el modelo."""
    model_class = table_name.title()
    btn_title_literal = repr(btn_title) if btn_title else 'None'
    return (
        f"# [sapy-auto:{table_name}:views start]\n"
        f"from django.apps import apps\n"
        f"from django.contrib.auth.decorators import login_required\n"
        f"from django.shortcuts import render, get_object_or_404, redirect\n"
        f"from django.forms import modelform_factory\n"
        f"from django.http import JsonResponse, HttpResponse\n"
        f"import csv\n\n"
        f"@login_required\n"
        f"def list_{table_name}(request):\n"
        f"    Model = apps.get_model('{app_name}', '{model_class}')\n"
        f"    # Campos simples\n"
        f"    field_names = [f.name for f in Model._meta.fields if f.name != 'id']\n"
        f"    rows = list(Model.objects.values(*field_names)[:200])\n"
        f"    columns = [\n"
        f"        {{'name': f, 'label': f.replace('_',' ').title()}} for f in field_names\n"
        f"    ]\n"
        f"    # Leer configuración efectiva de la página para construir campos/columnas\n"
        f"    modal_fields = []\n"
        f"    try:\n"
        f"        from django.urls import reverse\n"
        f"        from django.test import RequestFactory\n"
        f"        rf = RequestFactory()\n"
        f"        # page_effective_config espera page_id; nuestro slug coincide con la tabla\n"
        f"        from sapy.models import Page\n"
        f"        pg = Page.objects.filter(slug='{table_name}').first()\n"
        f"        if pg:\n"
        f"            from sapy.views import page_effective_config\n"
        f"            fake = rf.get('/_internal/')\n"
        f"            fake.user = request.user\n"
        f"            resp = page_effective_config(fake, pg.id)\n"
        f"            import json\n"
        f"            data = json.loads(resp.content.decode('utf-8'))\n"
        f"            modals = data.get('modals') or []\n"
        f"            if modals and modals[0].get('form'):\n"
        f"                for fld in (modals[0]['form'].get('fields') or []):\n"
        f"                    if fld.get('name') in ['id','activo','created_at','updated_at','id_auth_user']:\n"
        f"                        continue\n"
        f"                    modal_fields.append({{'name': fld.get('name'), 'label': fld.get('label'), 'placeholder': fld.get('placeholder'), 'required': bool(fld.get('required'))}})\n"
        f"    except Exception:\n"
        f"        modal_fields = []\n"
        f"    ctx = {{\n"
        f"        'columns': columns,\n"
        f"        'rows': rows,\n"
        f"        'modal_fields': modal_fields,\n"
        f"        'modal_btn_title': {btn_title_literal},\n"
        f"    }}\n"
        f"    return render(request, '{app_name}/{table_name}_list.html', ctx)\n\n"
        f"@login_required\n"
        f"def create_{table_name}(request):\n"
        f"    Model = apps.get_model('{app_name}', '{model_class}')\n"
        f"    Form = modelform_factory(Model, fields='__all__')\n"
        f"    if request.method == 'POST':\n"
        f"        form = Form(request.POST, request.FILES)\n"
        f"        if form.is_valid():\n"
        f"            form.save()\n"
        f"            return redirect('{table_name}_list')\n"
        f"    else:\n"
        f"        form = Form()\n"
        f"    return render(request, '{app_name}/{table_name}_form.html', {{'form': form}})\n\n"
        f"@login_required\n"
        f"def update_{table_name}(request, pk: int):\n"
        f"    Model = apps.get_model('{app_name}', '{model_class}')\n"
        f"    obj = get_object_or_404(Model, pk=pk)\n"
        f"    Form = modelform_factory(Model, fields='__all__')\n"
        f"    if request.method == 'POST':\n"
        f"        form = Form(request.POST, request.FILES, instance=obj)\n"
        f"        if form.is_valid():\n"
        f"            form.save()\n"
        f"            return redirect('{table_name}_list')\n"
        f"    else:\n"
        f"        form = Form(instance=obj)\n"
        f"    return render(request, '{app_name}/{table_name}_form.html', {{'form': form}})\n\n"
        f"@login_required\n"
        f"def delete_{table_name}(request, pk: int):\n"
        f"    Model = apps.get_model('{app_name}', '{model_class}')\n"
        f"    obj = get_object_or_404(Model, pk=pk)\n"
        f"    if request.method == 'POST':\n"
        f"        obj.delete()\n"
        f"        return redirect('{table_name}_list')\n"
        f"    return render(request, '{app_name}/{table_name}_confirm_delete.html', {{'object': obj}})\n"
        f"\n"
        f"@login_required\n"
        f"def ajax_fk_options(request, model: str):\n"
        f"    label_field = request.GET.get('label', 'nombre')\n"
        f"    q = request.GET.get('q', '').strip()\n"
        f"    try:\n"
        f"        Model = apps.get_model('{app_name}', model.title())\n"
        f"    except LookupError:\n"
        f"        return JsonResponse({{'results': []}})\n"
        f"    qs = Model.objects.all()\n"
        f"    if q:\n"
        f"        try:\n"
        f"            key = f\"{{label_field}}__icontains\"\n"
        f"            qs = qs.filter(**{{key: q}})\n"
        f"        except Exception:\n"
        f"            pass\n"
        f"    data = []\n"
        f"    for obj in qs[:20]:\n"
        f"        try:\n"
        f"            label = getattr(obj, label_field)\n"
        f"        except Exception:\n"
        f"            label = str(obj)\n"
        f"        data.append({{'id': getattr(obj, 'id', None), 'label': label}})\n"
        f"    return JsonResponse({{'results': data}})\n"
        f"\n"
        f"@login_required\n"
        f"def export_{table_name}_csv(request):\n"
        f"    Model = apps.get_model('{app_name}', '{model_class}')\n"
        f"    field_names = [f.name for f in Model._meta.fields]\n"
        f"    response = HttpResponse(content_type='text/csv')\n"
        f"    response['Content-Disposition'] = 'attachment; filename={table_name}.csv'\n"
        f"    writer = csv.writer(response)\n"
        f"    writer.writerow(field_names)\n"
        f"    for row in Model.objects.values_list(*field_names):\n"
        f"        writer.writerow(row)\n"
        f"    return response\n"
        f"\n"
        f"@login_required\n"
        f"def export_{table_name}_xlsx(request):\n"
        f"    Model = apps.get_model('{app_name}', '{model_class}')\n"
        f"    field_names = [f.name for f in Model._meta.fields]\n"
        f"    try:\n"
        f"        import io\n"
        f"        from openpyxl import Workbook\n"
        f"        wb = Workbook()\n"
        f"        ws = wb.active\n"
        f"        ws.append(field_names)\n"
        f"        for row in Model.objects.values_list(*field_names):\n"
        f"            ws.append(list(row))\n"
        f"        bio = io.BytesIO()\n"
        f"        wb.save(bio)\n"
        f"        bio.seek(0)\n"
        f"        response = HttpResponse(bio.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')\n"
        f"        response['Content-Disposition'] = 'attachment; filename={table_name}.xlsx'\n"
        f"        return response\n"
        f"    except Exception:\n"
        f"        # Fallback: CSV si no está disponible openpyxl\n"
        f"        response = HttpResponse(content_type='text/csv')\n"
        f"        response['Content-Disposition'] = 'attachment; filename={table_name}.csv'\n"
        f"        writer = csv.writer(response)\n"
        f"        writer.writerow(field_names)\n"
        f"        for row in Model.objects.values_list(*field_names):\n"
        f"            writer.writerow(row)\n"
        f"        return response\n"
        f"\n"
        f"@login_required\n"
        f"def export_{table_name}_pdf(request):\n"
        f"    Model = apps.get_model('{app_name}', '{model_class}')\n"
        f"    field_names = [f.name for f in Model._meta.fields]\n"
        f"    try:\n"
        f"        import io\n"
        f"        from reportlab.lib.pagesizes import letter\n"
        f"        from reportlab.pdfgen import canvas\n"
        f"        buffer = io.BytesIO()\n"
        f"        c = canvas.Canvas(buffer, pagesize=letter)\n"
        f"        textobject = c.beginText(40, 770)\n"
        f"        textobject.textLine(', '.join(field_names))\n"
        f"        for row in Model.objects.values_list(*field_names)[:1000]:\n"
        f"            textobject.textLine(', '.join([str(v) for v in row]))\n"
        f"            if textobject.getY() < 40:\n"
        f"                c.drawText(textobject); c.showPage(); textobject = c.beginText(40, 770)\n"
        f"        c.drawText(textobject)\n"
        f"        c.save()\n"
        f"        pdf = buffer.getvalue()\n"
        f"        buffer.close()\n"
        f"        response = HttpResponse(pdf, content_type='application/pdf')\n"
        f"        response['Content-Disposition'] = 'attachment; filename={table_name}.pdf'\n"
        f"        return response\n"
        f"    except Exception:\n"
        f"        # Fallback simple: entregar CSV si no hay backend PDF\n"
        f"        response = HttpResponse(content_type='text/csv')\n"
        f"        response['Content-Disposition'] = 'attachment; filename={table_name}.csv'\n"
        f"        writer = csv.writer(response)\n"
        f"        writer.writerow(field_names)\n"
        f"        for row in Model.objects.values_list(*field_names):\n"
        f"            writer.writerow(row)\n"
        f"        return response\n"
        f"# [sapy-auto:{table_name}:views end]\n"
    )



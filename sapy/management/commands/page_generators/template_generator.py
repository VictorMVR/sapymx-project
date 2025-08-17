"""
Template generator that uses real page configuration to generate Django templates.
"""
import json
from pathlib import Path
from typing import Dict, Any, List
from django.template import Template, Context
from django.template.loader import get_template

from .config_loader import PageConfig


class TemplateGenerator:
    """Generates Django templates using real page configuration."""
    
    def __init__(self, app_name: str, base_path: Path):
        self.app_name = app_name
        self.base_path = base_path
        self.templates_dir = Path(__file__).parent / 'templates'
    
    def generate_list_template(self, table_name: str, config: PageConfig) -> str:
        """Generate the list template using real configuration."""
        page_title = config.page_title
        page_slug = config.page_slug
        
        # Generate column headers and data display
        columns_html = ""
        for col in config.get_visible_columns():
            col_name = col.get('name', '')
            col_title = col.get('title', col_name.replace('_', ' ').title())
            alignment = col.get('alignment', '')
            align_class = f' class="text-{alignment}"' if alignment else ''
            columns_html += f'        <th{align_class}>{col_title}</th>\n'
        
        # Generate column data display with formatting
        column_data_html = ""
        for col in config.get_visible_columns():
            col_name = col.get('name', '')
            alignment = col.get('alignment', '')
            format_type = col.get('format', '')
            align_class = f' class="text-{alignment}"' if alignment else ''
            
            if format_type == 'currency':
                data_display = f"${{{{ row.{col_name}|floatformat:2 }}}}"
            elif format_type == 'decimal':
                data_display = f"{{{{ row.{col_name}|floatformat:2 }}}}"
            elif format_type == 'percent':
                data_display = f"{{{{ row.{col_name}|floatformat:1 }}}}%"
            elif format_type == 'date':
                data_display = f"{{{{ row.{col_name}|date:'Y-m-d' }}}}"
            elif format_type == 'datetime':
                data_display = f"{{{{ row.{col_name}|date:'Y-m-d H:i' }}}}"
            elif format_type == 'badge':
                data_display = f'<span class="badge bg-secondary">{{{{ row.{col_name} }}}}</span>'
            else:
                data_display = f"{{{{ row.{col_name} }}}}"
            
            column_data_html += f'        <td{align_class}>{data_display}</td>\n'
        
        # Build template using string concatenation to avoid f-string issues
        template = (
            f"<!-- [sapy-auto:{table_name}:list start] -->\n"
            "{% extends 'base.html' %}\n"
            "{% load static %}\n"
            "{% block content %}\n"
            f"<div class=\"page page-{page_slug}\">\n"
            f"  <h1 class=\"page-title\">{page_title}</h1>\n\n"
            "  <hr class=\"section-sep\" />\n"
            "  <div class=\"modal-cta text-center\">\n"
            f"    <button type=\"button\" class=\"btn btn-primary modal-cta-btn\" data-bs-toggle=\"modal\" data-bs-target=\"#modal-{table_name}-form\">\n"
            "      <i class=\"fas fa-plus\"></i>\n"
            "      <span class=\"d-none d-sm-inline\">Agregar</span>\n"
            "    </button>\n"
            "  </div>\n\n"
            "  <hr class=\"section-sep\" />\n"
            "  <section class=\"data-table-wrap\">\n"
            "    <div class=\"table-toolbar d-flex justify-content-between align-items-center gap-2\">\n"
            "      <div class=\"table-filters\"><!-- filtros --></div>\n"
            "      <div class=\"d-flex align-items-center gap-2 ms-auto\">\n"
            "        <div class=\"table-search\"><!-- búsqueda --></div>\n"
            "        <div class=\"table-exports d-flex align-items-center gap-1\">\n"
            f"          <a class=\"btn btn-sm btn-outline-secondary export-csv\" href=\"/{table_name}/export/csv/\" title=\"Exportar CSV\">\n"
            "            <i class=\"fas fa-file-csv\"></i>\n"
            "          </a>\n"
            f"          <a class=\"btn btn-sm btn-outline-secondary export-xlsx\" href=\"/{table_name}/export/xlsx/\" title=\"Exportar Excel\">\n"
            "            <i class=\"fas fa-file-excel\"></i>\n"
            "          </a>\n"
            f"          <a class=\"btn btn-sm btn-outline-secondary export-pdf\" href=\"/{table_name}/export/pdf/\" title=\"Exportar PDF\">\n"
            "            <i class=\"fas fa-file-pdf\"></i>\n"
            "          </a>\n"
            "        </div>\n"
            "      </div>\n"
            "    </div>\n\n"
            "    <table class=\"table table-striped data-table\">\n"
            "      <thead class=\"table-head\">\n"
            "        <tr>\n"
            f"{columns_html}"
            "          <th class=\"text-end\">Acciones</th>\n"
            "        </tr>\n"
            "      </thead>\n"
            "      <tbody class=\"table-body\">\n"
            "        {% if rows %}\n"
            "        {% for row in rows %}\n"
            "        <tr>\n"
            f"{column_data_html}"
            "          <td class=\"row-actions text-end\">\n"
            "            <div class=\"btn-group btn-group-sm\">\n"
            "              <button type=\"button\" class=\"btn btn-outline-primary btn-edit\" \n"
            "                      data-bs-toggle=\"modal\" \n"
            f"                      data-bs-target=\"#modal-{table_name}-form\"\n"
            "                      data-id=\"{{ row.id }}\"\n"
            "                      title=\"Editar\">\n"
            "                <i class=\"fas fa-edit\"></i>\n"
            "              </button>\n"
            "              <a class=\"btn btn-outline-danger\" \n"
            f"                 href=\"{{% url '{table_name}_delete' row.id %}}\"\n"
            "                 title=\"Eliminar\">\n"
            "                <i class=\"fas fa-trash\"></i>\n"
            "              </a>\n"
            "            </div>\n"
            "          </td>\n"
            "        </tr>\n"
            "        {% endfor %}\n"
            "        {% else %}\n"
            "        <tr>\n"
            f"          <td class=\"text-center text-muted py-4\" colspan=\"{len(config.get_visible_columns()) + 1}\">Sin registros</td>\n"
            "        </tr>\n"
            "        {% endif %}\n"
            "      </tbody>\n"
            "    </table>\n"
            "  </section>\n\n"
            f"  {{% include '{self.app_name}/modals/{table_name}_form_modal.html' %}}\n"
            "</div>\n"
            "{% endblock %}\n"
            f"<!-- [sapy-auto:{table_name}:list end] -->\n"
        )
        
        return template
    
    def generate_modal_template(self, table_name: str, config: PageConfig) -> str:
        """Generate the modal template using real configuration."""
        modal_config = config.get_modal_config()
        page_title = config.page_title
        
        # Generate form fields HTML
        form_fields_html = ""
        for field in config.get_form_fields():
            if not field.get('visible', True):
                continue
                
            field_name = field.get('name', '')
            field_label = field.get('label', '')
            field_placeholder = field.get('placeholder', '')
            field_type = field.get('input_type', 'text')
            required = field.get('required', False)
            width_fraction = field.get('width_fraction', '1-1')
            
            required_attr = ' required' if required else ''
            required_class = ' required' if required else ''
            
            # Generate input field based on type
            if field_type == 'textarea':
                field_input = f"""<textarea name="{field_name}" class="form-control" placeholder="{field_placeholder}"{required_attr}></textarea>"""
            elif field_type == 'select':
                field_input = f"""<select name="{field_name}" class="form-select"{required_attr}>
                  <option value="">{field_placeholder or 'Seleccione...'}</option>
                </select>"""
            elif field_type == 'checkbox':
                field_input = f"""<div class="form-check">
                  <input type="checkbox" name="{field_name}" class="form-check-input" id="field-{field_name}" value="1" />
                  <label class="form-check-label" for="field-{field_name}">
                    {field_placeholder or 'Activar'}
                  </label>
                </div>"""
            else:
                field_input = f"""<input type="{field_type}" name="{field_name}" class="form-control" placeholder="{field_placeholder}"{required_attr} />"""
            
            form_fields_html += f"""            <div class="field field-{width_fraction}{required_class}">
              <label class="form-label{required_class}">{field_label}</label>
              {field_input}
            </div>
"""
        
        modal_size_class = ""
        if modal_config['size'] == 'sm':
            modal_size_class = " modal-sm"
        elif modal_config['size'] == 'lg':
            modal_size_class = " modal-lg"
        elif modal_config['size'] == 'xl':
            modal_size_class = " modal-xl"
        elif modal_config['size'] == 'full':
            modal_size_class = " modal-fullscreen"
        
        backdrop_attr = ""
        keyboard_attr = ""
        if not modal_config.get('close_on_backdrop', True):
            backdrop_attr = ' data-bs-backdrop="static"'
        if not modal_config.get('close_on_escape', True):
            keyboard_attr = ' data-bs-keyboard="false"'
        
        return f"""<!-- [sapy-auto:{table_name}:modal start] -->
<div class="modal fade" id="modal-{table_name}-form" tabindex="-1" aria-hidden="true"{backdrop_attr}{keyboard_attr}>
  <div class="modal-dialog{modal_size_class}">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">{modal_config['title']}</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <div class="modal-body">
        <form id="form-{table_name}" class="modal-form" method="post" action="{{% url '{table_name}_create' %}}" enctype="multipart/form-data">
          {{% csrf_token %}}
          <input type="hidden" name="id" id="field-id" />
          
          <div class="form-grid">
{form_fields_html}          </div>
        </form>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">{modal_config['cancel_button_label']}</button>
        <button type="submit" class="btn btn-primary" form="form-{table_name}">{modal_config['submit_button_label']}</button>
      </div>
    </div>
  </div>
</div>
<!-- [sapy-auto:{table_name}:modal end] -->"""
    
    def generate_form_template(self, table_name: str, config: PageConfig) -> str:
        """Generate the standalone form template."""
        page_title = config.page_title
        
        return (
            "{% extends 'base.html' %}\n"
            "{% block content %}\n"
            f"<div class=\"page page-{table_name}\">\n"
            f"  <h1 class=\"page-title\">Formulario {page_title}</h1>\n"
            "  \n"
            "  <form method=\"post\" enctype=\"multipart/form-data\">\n"
            "    {% csrf_token %}\n"
            "    \n"
            "    <div class=\"form-grid\">\n"
            "      {% for field in form %}\n"
            "      <div class=\"field field-1-1\">\n"
            "        <label class=\"form-label\">{{ field.label }}</label>\n"
            "        {{ field }}\n"
            "        {% if field.errors %}\n"
            "        <div class=\"text-danger\">{{ field.errors }}</div>\n"
            "        {% endif %}\n"
            "        {% if field.help_text %}\n"
            "        <div class=\"form-text\">{{ field.help_text }}</div>\n"
            "        {% endif %}\n"
            "      </div>\n"
            "      {% endfor %}\n"
            "    </div>\n"
            "    \n"
            "    <div class=\"text-end mt-3\">\n"
            f"      <a class=\"btn btn-secondary me-2\" href=\"{{% url '{table_name}_list' %}}\">Cancelar</a>\n"
            "      <button class=\"btn btn-primary\" type=\"submit\">Guardar</button>\n"
            "    </div>\n"
            "  </form>\n"
            "</div>\n"
            "{% endblock %}\n"
        )
    
    def generate_confirm_delete_template(self, table_name: str, config: PageConfig) -> str:
        """Generate the confirm delete template."""
        page_title = config.page_title
        
        return (
            "{% extends 'base.html' %}\n"
            "{% block content %}\n"
            f"<div class=\"page page-{table_name}\">\n"
            "  <h1 class=\"page-title\">Confirmar eliminación</h1>\n"
            "  \n"
            "  <div class=\"alert alert-warning\">\n"
            "    <h5><i class=\"fas fa-exclamation-triangle\"></i> ¿Está seguro?</h5>\n"
            f"    <p>Esta acción eliminará permanentemente este registro de {page_title}.</p>\n"
            "    <p><strong>Esta acción no se puede deshacer.</strong></p>\n"
            "  </div>\n"
            "  \n"
            "  <form method=\"post\">\n"
            "    {% csrf_token %}\n"
            "    <div class=\"d-flex gap-2\">\n"
            f"      <a class=\"btn btn-secondary\" href=\"{{% url '{table_name}_list' %}}\">Cancelar</a>\n"
            "      <button class=\"btn btn-danger\" type=\"submit\">\n"
            "        <i class=\"fas fa-trash\"></i> Confirmar eliminación\n"
            "      </button>\n"
            "    </div>\n"
            "  </form>\n"
            "</div>\n"
            "{% endblock %}\n"
        )
    
    def generate_views_block(self, table_name: str, config: PageConfig) -> str:
        """Generate the views code block using real configuration."""
        template_path = self.templates_dir / 'views_template.py'
        template_content = template_path.read_text(encoding='utf-8')
        
        # Prepare columns configuration as Python code
        columns = []
        for col in config.get_visible_columns():
            columns.append({
                'name': col.get('name', ''),
                'title': col.get('title', col.get('name', '').replace('_', ' ').title()),
                'alignment': col.get('alignment', ''),
                'format': col.get('format', ''),
            })
        
        # Prepare form fields configuration as Python code
        form_fields = []
        for field in config.get_form_fields():
            if field.get('visible', True):
                form_fields.append({
                    'name': field.get('name', ''),
                    'label': field.get('label', ''),
                    'placeholder': field.get('placeholder', ''),
                    'input_type': field.get('input_type', 'text'),
                    'required': field.get('required', False),
                    'visible': field.get('visible', True),
                    'width_fraction': field.get('width_fraction', '1-1'),
                })
        
        model_class = table_name.title()
        modal_config = config.get_modal_config()
        
        # Convert JSON to Python-compatible format
        def json_to_python(data):
            """Convert JSON data to Python-compatible string representation."""
            import json
            json_str = json.dumps(data, indent=4)
            # Replace JavaScript booleans with Python booleans
            json_str = json_str.replace('true', 'True').replace('false', 'False')
            return json_str
        
        context = {
            'table_name': table_name,
            'app_name': self.app_name,
            'model_class': model_class,
            'page_title': config.page_title,
            'columns_config': json_to_python(columns),
            'form_fields_config': json_to_python(form_fields),
            'modal_config': json_to_python(modal_config),
        }
        
        template = Template(template_content)
        return template.render(Context(context))
    
    def generate_urls_block(self, table_name: str) -> str:
        """Generate the URLs block for a table."""
        return (
            f"    path('{table_name}/', views.list_{table_name}, name='{table_name}_list'),\n"
            f"    path('{table_name}/create/', views.create_{table_name}, name='{table_name}_create'),\n"
            f"    path('{table_name}/<int:pk>/update/', views.update_{table_name}, name='{table_name}_update'),\n"
            f"    path('{table_name}/<int:pk>/delete/', views.delete_{table_name}, name='{table_name}_delete'),\n"
            f"    path('{table_name}/<int:pk>/json/', views.{table_name}_json, name='{table_name}_json'),\n"
            f"    path('ajax/fk/<str:model>/', views.ajax_fk_options, name='ajax_fk_options'),\n"
            f"    path('{table_name}/export/csv/', views.export_{table_name}_csv, name='{table_name}_export_csv'),\n"
            f"    path('{table_name}/export/xlsx/', views.export_{table_name}_xlsx, name='{table_name}_export_xlsx'),\n"
            f"    path('{table_name}/export/pdf/', views.export_{table_name}_pdf, name='{table_name}_export_pdf'),\n"
        )
    
    def create_template_tags_utils(self) -> str:
        """Create template tags utils - not needed as ui_extras already exists."""
        # No longer needed as we use existing ui_extras templatetag
        return ""
from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.forms import modelform_factory
from django.http import JsonResponse, HttpResponse
import csv

@login_required
def list_{{ table_name }}(request):
    Model = apps.get_model('{{ app_name }}', '{{ model_class }}')
    
    # Get visible columns from configuration
    columns = {{ columns_config|safe }}
    field_names = [col['name'] for col in columns]
    
    # Get data with only visible fields
    rows = list(Model.objects.values(*field_names)[:200])
    
    ctx = {
        'columns': columns,
        'rows': rows,
        'form_fields': {{ form_fields_config|safe }},
        'modal_config': {{ modal_config|safe }},
        'page_title': '{{ page_title }}',
        'table_name': '{{ table_name }}',
        'app_name': '{{ app_name }}',
    }
    return render(request, '{{ app_name }}/{{ table_name }}_list.html', ctx)

@login_required
def create_{{ table_name }}(request):
    Model = apps.get_model('{{ app_name }}', '{{ model_class }}')
    
    # Create form with only the fields that should be editable
    editable_fields = [f['name'] for f in {{ form_fields_config|safe }} if f.get('visible', True)]
    Form = modelform_factory(Model, fields=editable_fields)
    
    if request.method == 'POST':
        form = Form(request.POST, request.FILES)
        if form.is_valid():
            instance = form.save(commit=False)
            # Set audit fields if they exist
            if hasattr(instance, 'id_auth_user'):
                instance.id_auth_user = request.user
            instance.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'id': instance.pk})
            return redirect('{{ table_name }}_list')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = Form()
    
    return render(request, '{{ app_name }}/{{ table_name }}_form.html', {
        'form': form,
        'page_title': '{{ page_title }}',
        'table_name': '{{ table_name }}'
    })

@login_required
def update_{{ table_name }}(request, pk: int):
    Model = apps.get_model('{{ app_name }}', '{{ model_class }}')
    obj = get_object_or_404(Model, pk=pk)
    
    # Create form with only the fields that should be editable
    editable_fields = [f['name'] for f in {{ form_fields_config|safe }} if f.get('visible', True)]
    Form = modelform_factory(Model, fields=editable_fields)
    
    if request.method == 'POST':
        form = Form(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            instance = form.save(commit=False)
            # Update audit fields if they exist
            if hasattr(instance, 'id_auth_user'):
                instance.id_auth_user = request.user
            instance.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'id': instance.pk})
            return redirect('{{ table_name }}_list')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = Form(instance=obj)
    
    return render(request, '{{ app_name }}/{{ table_name }}_form.html', {
        'form': form,
        'object': obj,
        'page_title': '{{ page_title }}',
        'table_name': '{{ table_name }}'
    })

@login_required
def delete_{{ table_name }}(request, pk: int):
    Model = apps.get_model('{{ app_name }}', '{{ model_class }}')
    obj = get_object_or_404(Model, pk=pk)
    
    if request.method == 'POST':
        obj.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return redirect('{{ table_name }}_list')
    
    return render(request, '{{ app_name }}/{{ table_name }}_confirm_delete.html', {
        'object': obj,
        'page_title': '{{ page_title }}',
        'table_name': '{{ table_name }}'
    })

@login_required
def {{ table_name }}_json(request, pk: int):
    """Return object data as JSON for AJAX editing."""
    Model = apps.get_model('{{ app_name }}', '{{ model_class }}')
    obj = get_object_or_404(Model, pk=pk)
    
    # Get only the fields that are in the form configuration
    form_field_names = [f['name'] for f in {{ form_fields_config|safe }}]
    data = {}
    
    for field_name in form_field_names:
        try:
            value = getattr(obj, field_name)
            # Handle special field types
            if hasattr(value, 'isoformat'):  # datetime/date objects
                data[field_name] = value.isoformat()
            elif value is None:
                data[field_name] = ''
            else:
                data[field_name] = str(value)
        except AttributeError:
            data[field_name] = ''
    
    return JsonResponse(data)

@login_required
def ajax_fk_options(request, model: str):
    """Return FK options for select fields."""
    label_field = request.GET.get('label', 'nombre')
    q = request.GET.get('q', '').strip()
    try:
        Model = apps.get_model('{{ app_name }}', model.title())
    except LookupError:
        return JsonResponse({'results': []})
    
    qs = Model.objects.all()
    if q:
        try:
            key = f"{label_field}__icontains"
            qs = qs.filter(**{key: q})
        except Exception:
            pass
    
    data = []
    for obj in qs[:20]:
        try:
            label = getattr(obj, label_field)
        except Exception:
            label = str(obj)
        data.append({'id': getattr(obj, 'id', None), 'label': label})
    
    return JsonResponse({'results': data})

@login_required
def export_{{ table_name }}_csv(request):
    Model = apps.get_model('{{ app_name }}', '{{ model_class }}')
    
    # Use configured visible columns
    columns = {{ columns_config|safe }}
    field_names = [col['name'] for col in columns]
    headers = [col['title'] for col in columns]
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename={{ table_name }}.csv'
    writer = csv.writer(response)
    writer.writerow(headers)
    
    for row in Model.objects.values_list(*field_names):
        writer.writerow(row)
    
    return response

@login_required
def export_{{ table_name }}_xlsx(request):
    Model = apps.get_model('{{ app_name }}', '{{ model_class }}')
    
    # Use configured visible columns
    columns = {{ columns_config|safe }}
    field_names = [col['name'] for col in columns]
    headers = [col['title'] for col in columns]
    
    try:
        import io
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(headers)
        
        for row in Model.objects.values_list(*field_names):
            ws.append(list(row))
        
        bio = io.BytesIO()
        wb.save(bio)
        bio.seek(0)
        response = HttpResponse(bio.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename={{ table_name }}.xlsx'
        return response
    except Exception:
        # Fallback to CSV if openpyxl is not available
        return export_{{ table_name }}_csv(request)

@login_required
def export_{{ table_name }}_pdf(request):
    Model = apps.get_model('{{ app_name }}', '{{ model_class }}')
    
    # Use configured visible columns
    columns = {{ columns_config|safe }}
    field_names = [col['name'] for col in columns]
    headers = [col['title'] for col in columns]
    
    try:
        import io
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        textobject = c.beginText(40, 770)
        textobject.textLine(', '.join(headers))
        
        for row in Model.objects.values_list(*field_names)[:1000]:
            textobject.textLine(', '.join([str(v) for v in row]))
            if textobject.getY() < 40:
                c.drawText(textobject)
                c.showPage()
                textobject = c.beginText(40, 770)
        
        c.drawText(textobject)
        c.save()
        pdf = buffer.getvalue()
        buffer.close()
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename={{ table_name }}.pdf'
        return response
    except Exception:
        # Fallback to CSV if reportlab is not available
        return export_{{ table_name }}_csv(request)

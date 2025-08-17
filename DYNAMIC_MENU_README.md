# 🚀 Sistema de Menú Dinámico para Aplicaciones Django

## 📋 Descripción General

El sistema de menú dinámico permite que cada aplicación Django generada por `sapy` tenga un menú de navegación que se actualiza automáticamente desde la base de datos central (`sapy_bd`). Esto elimina la necesidad de modificar manualmente el dashboard de cada aplicación cuando se agregan o quitan menús y páginas.

## 🏗️ Arquitectura del Sistema

### Componentes Principales

1. **Endpoint API en `sapy`** (`/sapy/api/menu/<app_name>/`)
   - Sirve la configuración del menú para cada aplicación
   - Consulta la base de datos `sapy_bd` para obtener menús y páginas activas

2. **Plantilla de Carga** (`dynamic_menu_loader.html`)
   - Se incluye en cada aplicación destino
   - Carga el menú dinámicamente desde `sapy`
   - Maneja errores y muestra menú de fallback

3. **Script de Bootstrap Modificado** (`bootstrap_django_app.sh`)
   - Genera aplicaciones con el menú dinámico integrado
   - Incluye Bootstrap y Font Awesome para un diseño moderno

## 🔧 Implementación

### 1. Endpoint API en `sapy`

```python
# sapy/views.py
def application_dynamic_menu(request, app_name):
    """Endpoint para servir la configuración del menú dinámico"""
    # Busca la aplicación por nombre
    # Obtiene menús activos y páginas asociadas
    # Retorna JSON con estructura del menú
```

**URL**: `/sapy/api/menu/<app_name>/`

**Respuesta JSON**:
```json
{
  "app_name": "facxy",
  "app_title": "Facxy - Gestión Empresarial",
  "menus": [
    {
      "id": 1,
      "name": "Gestión Empresarial",
      "slug": "gestion-empresarial",
      "pages": [
        {
          "id": 1,
          "name": "Empresas",
          "slug": "empresas",
          "url": "/empresas/",
          "table_name": "empresas",
          "orden": 1,
          "seccion": "General"
        }
      ]
    }
  ],
  "standard_options": [
    {"name": "Inicio", "url": "/", "icon": "fas fa-home"},
    {"name": "Dashboard", "url": "/dashboard/", "icon": "fas fa-tachometer-alt"},
    {"name": "Admin", "url": "/admin/", "icon": "fas fa-cog"},
    {"name": "Cerrar sesión", "url": "/logout/", "icon": "fas fa-sign-out-alt"}
  ]
}
```

### 2. Plantilla de Carga

La plantilla `dynamic_menu_loader.html` se incluye en el `base.html` de cada aplicación:

```html
<!-- En base.html -->
{% include 'dynamic_menu_loader.html' %}

<div class="main-content">
  {% block content %}{% endblock %}
</div>
```

### 3. Características del Menú

- **Sidebar fijo izquierdo** con ancho de 280px
- **Colapsable** (doble clic en header para colapsar a 70px)
- **Responsive** con botón hamburguesa en móvil
- **Overlay** para móvil que se cierra al tocar
- **Scrollbar personalizado** para menús largos
- **Iconos Font Awesome** para cada opción
- **Indicador de página activa** con borde rojo

## 🎨 Diseño y UX

### Estilo Visual

- **Tema oscuro** estilo YouTube/Spotify
- **Colores**: Fondo #1a1a1a, hover #2d2d2d
- **Acentos**: Rojo (#ff0000) para elementos activos
- **Tipografía**: Sans-serif moderna y legible
- **Iconos**: Font Awesome 6.4.0

### Interacciones

- **Hover**: Cambio de color de fondo y borde izquierdo rojo
- **Activo**: Página actual marcada con borde rojo
- **Colapsado**: Solo iconos visibles (doble clic en header)
- **Móvil**: Sidebar deslizable con overlay

### Responsividad

- **Desktop**: Sidebar fijo, contenido ajustado
- **Tablet**: Sidebar colapsable
- **Móvil**: Sidebar deslizable, overlay de fondo

## 🚀 Uso y Configuración

### 1. Generar Nueva Aplicación

```bash
# El script de bootstrap ya incluye el menú dinámico
cd /srv
./bootstrap_django_app.sh
```

### 2. Configurar Menús en `sapy`

1. Ir a la interfaz de `sapy`
2. Crear/editar menús en "Menús"
3. Asignar menús a la aplicación en "Aplicaciones > Menús"
4. Crear páginas y vincularlas a tablas
5. El menú se actualiza automáticamente

### 3. Personalizar en Aplicación Destino

```html
<!-- Para personalizar colores, editar CSS variables en dynamic_menu_loader.html -->
:root {
    --sidebar-bg: #tu-color;
    --sidebar-hover: #tu-color-hover;
    --sidebar-text: #tu-color-texto;
}
```

## 🔍 Pruebas y Debugging

### Script de Prueba

```bash
# Instalar requests si no está disponible
pip install requests

# Ejecutar prueba
python test_dynamic_menu.py
```

### Verificar Endpoint

```bash
# Probar directamente
curl http://localhost:8000/sapy/api/menu/facxy/
```

### Logs de Django

```bash
# Ver logs de sapy
tail -f /var/log/sapy.log

# Ver logs de la app destino
tail -f /var/log/facxy.log
```

## 🛠️ Mantenimiento

### Actualizar Menú

1. **En `sapy`**: Modificar menús, páginas o asignaciones
2. **Automático**: El menú se actualiza en la próxima carga de página
3. **Sin reinicios**: No requiere reiniciar servicios

### Agregar Nuevas Opciones

1. **Opciones estándar**: Editar `application_dynamic_menu` en `sapy/views.py`
2. **Iconos**: Usar clases de Font Awesome disponibles
3. **URLs**: Asegurar que las rutas existan en la app destino

### Resolver Problemas

#### Menú no carga
- Verificar que `sapy` esté corriendo
- Revisar logs de la consola del navegador
- Confirmar que la app esté registrada en `sapy_bd`

#### Menú vacío
- Verificar que existan menús asignados a la aplicación
- Confirmar que las páginas estén activas
- Revisar permisos de usuario

#### Errores de CSS
- Verificar que Bootstrap y Font Awesome se carguen
- Revisar que las variables CSS estén definidas
- Confirmar que no haya conflictos de estilos

## 🔒 Seguridad

### Consideraciones

- **Sin autenticación**: El endpoint es público (las apps están en el mismo servidor)
- **Rate limiting**: Considerar implementar si hay muchas apps
- **Validación**: Los datos se validan antes de servir

### Mejoras Futuras

- **Autenticación**: Tokens de API por aplicación
- **Cache**: Redis para mejorar rendimiento
- **Compresión**: Gzip para respuestas JSON

## 📈 Rendimiento

### Optimizaciones Actuales

- **Consultas eficientes**: Uso de `select_related` y `prefetch_related`
- **JSON ligero**: Solo datos necesarios en la respuesta
- **Cache del navegador**: Headers apropiados para recursos estáticos

### Métricas Esperadas

- **Tiempo de respuesta**: < 100ms para menús típicos
- **Tamaño de respuesta**: < 5KB para menús con 10-20 páginas
- **Uso de memoria**: Mínimo impacto en `sapy`

## 🔮 Roadmap

### Próximas Funcionalidades

1. **Menús anidados** con submenús
2. **Permisos por usuario** en menús
3. **Temas personalizables** por aplicación
4. **Notificaciones** en elementos del menú
5. **Búsqueda** en menús largos

### Integraciones

1. **Webhooks** para actualizaciones en tiempo real
2. **API REST** completa para gestión de menús
3. **CLI** para gestión desde terminal
4. **Docker** para despliegue simplificado

## 📚 Referencias

- **Django**: Framework web principal
- **Bootstrap 5**: Framework CSS para diseño responsive
- **Font Awesome**: Iconos vectoriales
- **CSS Variables**: Personalización dinámica de estilos
- **Fetch API**: Carga asíncrona de datos

## 🤝 Contribución

### Reportar Bugs

1. Describir el problema claramente
2. Incluir pasos para reproducir
3. Adjuntar logs y capturas de pantalla
4. Especificar versión de Django y navegador

### Sugerencias

1. Crear issue en el repositorio
2. Describir la funcionalidad deseada
3. Explicar el caso de uso
4. Proponer implementación si es posible

---

**Desarrollado para el proyecto `sapy` - Generador de Aplicaciones Django**

*Última actualización: $(date)*

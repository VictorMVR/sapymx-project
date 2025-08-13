# SapyMX

Aplicación web para gestión de páginas con modales y formularios dinámicos para Django.

## Características

- **Generación automática** de páginas desde tablas de base de datos
- **Sistema de modales** configurables para formularios CRUD
- **Formularios dinámicos** con campos personalizables
- **Gestión de columnas** con drag & drop para reordenamiento
- **Sistema de grid** flexible para layouts de formularios
- **Exportación** a Excel, PDF y CSV
- **Interfaz responsiva** para dispositivos móviles

## Tecnologías

- Django 4.x
- PostgreSQL
- Bootstrap 5
- SweetAlert2
- CSS Grid personalizado

## Instalación

1. Clonar el repositorio
2. Crear entorno virtual: `python -m venv venv`
3. Activar entorno: `source venv/bin/activate`
4. Instalar dependencias: `pip install -r requirements.txt`
5. Configurar base de datos PostgreSQL
6. Ejecutar migraciones: `python manage.py migrate`
7. Crear superusuario: `python manage.py createsuperuser`
8. Ejecutar servidor: `python manage.py runserver`

## Uso

1. Crear tablas de base de datos
2. Generar páginas automáticamente desde las tablas
3. Personalizar modales, formularios y columnas
4. Configurar accesos directos entre páginas

## Estructura del Proyecto

```
sapy/
├── sapy/           # Aplicación principal
│   ├── models.py   # Modelos de base de datos
│   ├── views.py    # Vistas y lógica de negocio
│   └── urls.py     # Configuración de URLs
├── templates/      # Plantillas HTML
├── static/         # Archivos estáticos (CSS, JS)
└── migrations/     # Migraciones de base de datos
```

## Licencia

MIT License

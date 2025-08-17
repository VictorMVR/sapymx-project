# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Setup and Installation
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# or venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Configure database connection (create .env file with DATABASE_URL)
# Example: DATABASE_URL=postgresql://user:password@localhost:5432/dbname

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver

# Collect static files (for production)
python manage.py collectstatic
```

### Database Operations
```bash
# Make migrations after model changes
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Run custom management commands
python manage.py add_activo_all  # Adds 'activo' field to all tables
python manage.py generate_pages --app <app_name> --tables <table_list> --overwrite  # Generates pages from database schemas
python manage.py sync_icons     # Syncs icon catalogs
```

### Page Generation Commands
```bash
# Generate pages for specific tables
python manage.py generate_pages --app admischool --tables niveles_educativos,escuelas --overwrite

# Generate all assigned tables for an application
python manage.py generate_pages --app admischool --all-assigned --overwrite

# Add custom button title and menu
python manage.py generate_pages --app admischool --tables niveles_educativos --btn-title "Nuevo Nivel" --menu main_menu
```

### Testing and Validation
```bash
# Check for issues (no tests configured yet)
python manage.py check

# Validate models
python manage.py validate
```

## Architecture Overview

SapyMX is a Django web application for dynamic page generation from database schemas with configurable modals and forms. The system follows a metadata-driven architecture where database table schemas are used to automatically generate UI components.

### Core Architecture Components

**Database Schema Management (`models.py`)**
- `DbTable`: Represents logical database tables with metadata (name, alias, type, schema)
- `DbColumn`: Global column definitions with SQL data types and constraints
- `DbTableColumn`: Junction table linking tables to columns with position and override capabilities
- Support for table types: CATALOG (simple lookups) and TRANSACTION (full audit trail)

**UI Component Generation**
- `UiColumn`: Display metadata for table columns (alignment, format, visibility)
- `UiField`: Form field definitions with input types and validation
- `FormQuestion`: Dynamic form field configuration with custom validation rules
- Automatic UI component generation from database column metadata via Django signals

**Page and Modal System**
- `Page`: Top-level page definitions with routing and table associations
- `PageTable`: Configuration for tables displayed within pages
- `Modal`: Reusable modal dialogs with configurable forms
- `ModalForm`: Form configurations within modals with layout control
- Override systems for customizing column display and form field behavior

**Application Management**
- `Application`: ERP application definitions with deployment configuration
- `ApplicationTable`: Links applications to database tables
- `DeploymentLog`: Tracks deployment history and status

**Dynamic Menu System**
- `Menu`: Menu navigation structure with icons and ordering
- `MenuPage`: Assignments of pages to menus with sections
- `ApplicationMenu`: Links applications to menus for multi-app navigation
- `Role`/`RoleMenu`: Role-based access control for menu visibility

### Key Design Patterns

**Metadata-Driven UI Generation**
- Database columns automatically generate corresponding UI components
- Override patterns allow customization without losing base definitions
- Signal-based creation ensures UI components stay in sync with schema changes

**Flexible Grid Layout System**
- CSS Grid-based form layouts with fractional width specifications (1-1, 1-2, 1-3, etc.)
- Responsive design that collapses to single column on mobile
- Custom CSS classes: `field-1-1` (100%), `field-1-2` (50%), `field-1-4` (25%), etc.

**Convention-Based Foreign Keys**
- Foreign key columns follow `id_<table_name>` naming convention
- Automatic detection and SELECT input generation for FK relationships
- Support for custom label and value fields in dropdown options

### Directory Structure

```
sapy/
├── sapy/                    # Main Django app
│   ├── models.py           # Core data models and metadata
│   ├── views.py            # Business logic and view controllers
│   ├── forms.py            # Django form definitions
│   ├── urls.py             # Main URL configuration
│   ├── app_urls.py         # App-specific URL patterns
│   ├── settings.py         # Django settings
│   ├── migrations/         # Database migration files
│   └── management/         # Custom Django management commands
│       └── commands/
│           ├── add_activo_all.py      # Adds activo field to tables
│           ├── generate_pages.py      # Main page generation command
│           ├── sync_icons.py          # Syncs icon libraries
│           └── page_generators/       # Modular page generation system
│               ├── config_loader.py   # Loads real page configuration
│               ├── template_generator.py # Generates Django templates
│               ├── file_manager.py    # Handles file operations
│               ├── service_manager.py # Manages service reloads
│               └── templates/         # Template files for generation
│                   └── views_template.py # Django views template
├── templates/              # HTML templates
│   ├── base.html          # Base template with Bootstrap 5 and grid CSS
│   ├── dashboard.html     # Main dashboard
│   ├── dynamic_menu.html  # Dynamic menu system
│   └── [various page templates]
├── static/                 # Static assets
│   ├── css/
│   │   ├── form-grid.css  # Grid layout system for dynamic forms
│   │   ├── sapy-theme.css # Main theme and variables
│   │   └── sapy-components.css # Advanced UI components
│   ├── js/
│   │   └── sapy-common.js # Shared JavaScript utilities
│   └── icons/             # Icon library JSON catalogs
└── requirements.txt       # Python dependencies
```

### Environment Configuration

The application uses python-decouple and dotenv for environment variable management:
- `SECRET_KEY`: Django secret key
- `DEBUG`: Development mode flag
- `DATABASE_URL`: PostgreSQL connection string
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts

### Dependencies and Technology Stack

- **Django 4.x+**: Web framework
- **PostgreSQL**: Primary database with psycopg2-binary driver
- **Bootstrap 5**: Frontend framework via CDN
- **SweetAlert2**: Modal dialogs and notifications
- **python-decouple**: Environment variable management
- **dj-database-url**: Database URL parsing
- **django-crispy-forms**: Form rendering enhancement
- **crispy-bootstrap5**: Bootstrap 5 form templates
- **Pillow**: Image processing capabilities
- **gunicorn**: WSGI HTTP server for production
- **whitenoise**: Static file serving

### CSS Framework and UI Standards

SapyMX includes a comprehensive CSS framework that extends Bootstrap 5 with application-specific components:

**CSS Architecture:**
- `form-grid.css`: Dynamic form layout system with fractional widths
- `sapy-theme.css`: Core theme, variables, and main UI components
- `sapy-components.css`: Advanced components (filters, dropdowns, animations)
- `sapy-common.js`: Shared JavaScript utilities and interactions

**Standardized UI Components:**
- `.sapy-table-container`: Unified table headers with actions
- `.sapy-mobile-card`: Responsive mobile view cards  
- `.sapy-badge-*`: Consistent status and type indicators
- `.sapy-btn-icon`: Buttons with icons following design system
- `.sapy-empty-state`: Consistent empty states across views
- `.sapy-filter-section`: Standardized search and filter forms

**Responsive Strategy:**
- Mobile-first design with automatic table-to-card conversion
- Consistent spacing using CSS custom properties
- Unified hover effects and transitions

### Dynamic Menu System

The application features a sophisticated dynamic menu system that allows generated applications to receive menu configurations from the central SapyMX system:

**Components:**
- **API Endpoint**: `/sapy/api/menu/<app_name>/` serves menu configuration as JSON
- **Dynamic Loading**: Apps load menus dynamically without hardcoding navigation
- **Responsive Design**: Collapsible sidebar with mobile overlay support
- **Role-Based Access**: Menu visibility controlled by user roles

**Features:**
- Dark theme sidebar (YouTube/Spotify style)
- Font Awesome icons integration
- Active page highlighting
- Smooth animations and hover effects
- Bootstrap Icons and Font Awesome support

### Page Configuration System

The system features a sophisticated page configuration interface accessible at `/sapy/pages/<id>/` where administrators define exactly how pages should appear and behave:

**Page Detail Interface Components:**
- **Page Metadata**: Title, icon, routing, and basic configuration
- **Table Configuration**: Define which columns show in lists, their titles, alignment, formats, and visibility
- **Modal Configuration**: Complete control over modal dialogs including size, behavior, and form fields
- **Form Field Management**: Control field labels, placeholders, widths, requirement status, and visibility
- **Live Preview**: Real-time preview of how modals will appear when generated

**Critical Form Field Rules:**
- **Primary Key (ID)**: Always excluded from user forms (handled as hidden field for edits only)
- **Audit Fields**: `created_at`, `updated_at`, `id_auth_user` are never shown in forms
- **Active Status**: `activo` field is managed through table actions, not form inputs
- **Field Visibility**: Each field can be individually shown/hidden in forms
- **Width Control**: Fractional width system (1-1, 1-2, 1-3, etc.) for responsive layouts

### Development Workflow

1. **Schema Definition**: Create DbTable and DbColumn instances to define database structure
2. **UI Generation**: UiColumn, UiField, and FormQuestion objects are automatically created via signals
3. **Page Creation**: Generate Page objects from tables using the interface or API
4. **Page Configuration**: Use the detailed configuration interface at `/sapy/pages/<id>/` to:
   - Configure table columns (titles, alignment, formats, visibility)
   - Set up modals (size, behavior, form mode)
   - Customize form fields (labels, placeholders, widths, requirements)
   - Preview the final result in real-time
5. **Override Management**: System stores overrides in PageTableColumnOverride and ModalFormFieldOverride
6. **Effective Configuration**: Use `page_effective_config` endpoint to get final merged configuration
7. **Code Generation**: Generate complete Django applications based on stored configurations

### Signal-Based Automation

The system uses Django signals extensively for automation:
- **post_save on DbColumn**: Automatically creates UiColumn, UiField, and FormQuestion
- **post_delete on DbColumn**: Cleans up related UI components
- Convention-based field type detection and UI component generation

### Important Conventions

- Database table names: lowercase with underscores (e.g., `productos`, `categorias_productos`)
- Foreign key columns: `id_<table_name>` format (e.g., `id_categoria` references `categoria` table)
- Audit columns for transaction tables: `activo`, `created_at`, `updated_at`, `id_auth_user`
- CSS classes for form fields: `field-{numerator}-{denominator}` for fractional widths
- All UI components include an `activo` field for soft deletion/activation control
- Icon naming: Use Bootstrap Icons (`bi bi-*`) or Font Awesome (`fas fa-*`) classes

### Form Field Filtering Rules

The system applies strict rules about which database columns appear in user forms:

**Excluded Fields (Never in Forms):**
- Primary key fields with auto-increment (`id` column)
- Audit timestamp fields: `created_at`, `updated_at`
- User tracking field: `id_auth_user`

**Special Handling:**
- `activo` field: Managed via table toggle actions, not form inputs
- Foreign keys (`id_*`): Rendered as SELECT dropdowns with related table data
- Primary keys (for editing): Included as hidden fields to maintain record identity

**Override System:**
- Use `PageTableColumnOverride` for table display customization
- Use `ModalFormFieldOverride` for form field customization
- Each override can modify: visibility, labels, placeholders, widths, requirements
- Overrides are merged with defaults via the `page_effective_config` system

### Code Generation Features

The system can generate complete Django applications with:
- Database models based on DbTable/DbColumn definitions
- Views with CRUD operations
- Templates with responsive design
- URL configurations
- Static files and CSS frameworks
- Dynamic menu integration

### Configuration Management

**Page Effective Configuration System:**
- Access via `/sapy/pages/<id>/effective-config/` endpoint
- Merges base column/field definitions with custom overrides
- Returns JSON configuration used by code generation
- Handles all filtering rules (excludes ID, audit fields, etc.)
- Used by the page generation system to create accurate code

**Page Detail Interface:**
- Comprehensive configuration at `/sapy/pages/<id>/`
- Real-time form preview with current settings
- Column management with drag-and-drop reordering
- Field-level control over visibility, labels, and layout
- Modal preview showing exact appearance

### Testing and Quality Assurance

- Database table validation scripts
- Icon synchronization from external catalogs
- Dynamic menu endpoint testing utilities
- Migration verification tools
- Page configuration validation and preview system

### Security Considerations

- Environment-based configuration management
- Secure database connection handling
- CSRF protection for forms
- SQL injection prevention through ORM usage
- Role-based access control for menus and pages
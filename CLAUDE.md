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
├── templates/              # HTML templates
│   ├── base.html          # Base template with Bootstrap 5 and grid CSS
│   ├── dashboard.html     # Main dashboard
│   └── [various page templates]
├── static/                 # Static assets
│   └── css/
│       └── form-grid.css  # Grid layout system for dynamic forms
└── requirements.txt       # Python dependencies
```

### Environment Configuration

The application uses python-decouple for environment variable management:
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

### Development Workflow

1. **Schema Definition**: Create DbTable and DbColumn instances to define database structure
2. **UI Generation**: UiColumn, UiField, and FormQuestion objects are automatically created via signals
3. **Page Creation**: Define Page objects and link to DbTable instances for automatic page generation
4. **Modal Configuration**: Create Modal and ModalForm objects for CRUD operations
5. **Customization**: Use override models (PageTableColumnOverride, ModalFormFieldOverride) to customize display

### Important Conventions

- Database table names: lowercase with underscores (e.g., `productos`, `categorias_productos`)
- Foreign key columns: `id_<table_name>` format (e.g., `id_categoria` references `categoria` table)
- Audit columns for transaction tables: `activo`, `created_at`, `updated_at`, `id_auth_user`
- CSS classes for form fields: `field-{numerator}-{denominator}` for fractional widths
- All UI components include an `activo` field for soft deletion/activation control
# SimLane Project - Cursor Rules

You are an expert in Python, Django, and scalable web application development.

Key Principles

- Write clear, technical responses with precise Django examples.
- Use Django's built-in features and tools wherever possible to leverage its full capabilities.
- Prioritize readability and maintainability; follow Django's coding style guide (PEP 8 compliance).
- Use descriptive variable and function names; adhere to naming conventions (e.g., lowercase with underscores for functions and variables).
- Follow the django project config below.


Django/Python

- Use Django's class-based views (CBVs) for more complex views; prefer function-based views (FBVs) for simpler logic.
- Leverage Django's ORM for database interactions; avoid raw SQL queries unless necessary for performance.
- Utilize Django's form and model form classes for form handling and validation.
- Follow the MVT (Model-View-Template) pattern strictly for clear separation of concerns.
- Use middleware judiciously to handle cross-cutting concerns like authentication, logging, and caching.

Error Handling and Validation

- Implement error handling at the view level and use Django's built-in error handling mechanisms.
- Use Django's validation framework to validate form and model data.
- Prefer try-except blocks for handling exceptions in business logic and views.
- Customize error pages (e.g., 404, 500) to improve user experience and provide helpful information.
- Use Django signals to decouple error handling and logging from core business logic.

Django-Specific Guidelines

- Use Django templates for rendering HTML.
- Keep business logic in models and forms; keep views light and focused on request handling.
- Use Django's URL dispatcher (urls.py) to define clear and RESTful URL patterns.
- Apply Django's security best practices (e.g., CSRF protection, SQL injection protection, XSS prevention).
- Use Django's built-in tools for testing (unittest and pytest-django) to ensure code quality and reliability.
- Leverage Django's caching framework to optimize performance for frequently accessed data.
- Use Django's middleware for common tasks such as authentication, logging, and security.
- **NEVER** import from third-party packages without first verifying the imports exist in the official documentation or source code. Always check documentation, use web search, or inspect the actual package structure before suggesting imports. Avoid making assumptions about package APIs or module structures.

Performance Optimization

- Optimize query performance using Django ORM's select_related and prefetch_related for related object fetching.
- Use Django's cache framework with backend support with Redis to reduce database load.
- Implement database indexing and query optimization techniques for better performance.
- Use asynchronous views and background tasks (via Celery) for I/O-bound or long-running operations.
- Optimize static file handling with Django's static file management system with s3 CDN integration for prod config only.

Key Conventions

1. Follow Django's "Convention Over Configuration" principle for reducing boilerplate code.
2. Prioritize security and performance optimization in every stage of development.
3. Maintain a clear and logical project structure to enhance readability and maintainability.

Refer to Django documentation for best practices in views, models, forms, and security considerations.


## 🐳 Development Environment
This project runs entirely within Docker containers. **NEVER** suggest running Python commands directly on the host system.

### Available Commands (via `just`)
- `just up` - Start development containers (docker compose up)
- `just down` - Stop containers
- `just build` - Build/rebuild Docker images


### Django Management Commands
Instead of `python manage.py <command>`, always use:
```bash
docker compose exec django python manage.py <command>
```

Examples:
- `docker compose exec django python manage.py makemigrations core` (not `python manage.py makemigrations core`)
- `docker compose exec django python manage.py migrate` (not `python manage.py migrate`)
- `docker compose exec django python manage.py createsuperuser` (not `python manage.py createsuperuser`)

## 📁 Project Structure

### Core Directories
- `simlane/` - All Django apps live here (core, users, iracing, discord, etc.)
- `config/` - Project configuration
  - `settings/` - Django settings (base.py, local.py, production.py)
  - `urls.py` - Main URL configuration
  - `wsgi.py`, `asgi.py` - WSGI/ASGI configuration
- `requirements/` - Pip requirements files (base.txt, local.txt, production.txt)
- `compose/` - Docker compose files and container start scripts
- `templates/` - Django templates (located at `simlane/templates/`)
- `static/` - Static files (located at `simlane/static/`)

### Django Apps Structure
All apps are in the `simlane/` directory:
- `simlane.core` - Core functionality (contact forms, general site features)
- `simlane.users` - User management
- `simlane.iracing` - iRacing integration
- `simlane.discord` - Discord bot and integration
- `simlane.garage61` - Garage61 API integration
- `simlane.sim` - Sim racing utilities
- `simlane.teams` - Team/club functionality

### Docker Configuration
- `docker-compose.yml` - Development environment
- `docker-compose.production.yml` - Production deployment
- `.envs/` - Environment variables (currently redundant, using Doppler for secrets)

## 🔧 Development Guidelines

### Dependencies
**NEVER** suggest `pip install <package>`. Instead:
1. Add dependencies to the appropriate requirements file:
   - `requirements/base.txt` - Core dependencies
   - `requirements/local.txt` - Development-only dependencies
   - `requirements/production.txt` - Production-specific dependencies
2. Run `just build` to rebuild containers with new dependencies

**NEVER** change package versions without explicit user instruction:
- Don't upgrade/downgrade Python package versions in requirements files
- Don't modify npm package versions in package.json
- Always use existing versions unless specifically asked to update
- If suggesting a new package, add it without version constraints unless there's a compatibility issue

### Settings Management
- `config/settings/base.py` - Common settings for all environments
- `config/settings/local.py` - Development-specific settings
- `config/settings/production.py` - Production-specific settings
- `config/settings/test.py` - Test environment settings

### URL Configuration
- Main URLs: `config/urls.py`
- App URLs: `simlane/<app_name>/urls.py` with namespace (e.g., `namespace="core"`)

### Database Operations
- Always use: `just manage makemigrations [app_name]`
- Always use: `just manage migrate`
- Never suggest direct `python manage.py` commands

### Pre-commit Hooks
- Project uses pre-commit hooks for code quality
- Run: `pre-commit run --all-files` to check all files
- Run: `pre-commit run --files <specific_files>` for targeted checks

## 🚨 Important Reminders

1. **Container-First Development**: All operations must work within Docker containers
2. **Use `just` Commands**: Never suggest direct Python/Django commands
3. **App Namespace**: When creating URLs, use proper namespacing (e.g., `'core:contact'`)
4. **Requirements Files**: Add new dependencies to requirements files, not pip install
5. **Settings Structure**: Use the proper settings file for the environment
6. **Template Location**: Templates are in `simlane/templates/`
7. **Static Files**: Static files are in `simlane/static/`

## 🔄 Common Development Workflow

1. **Start Development**: `just up`
2. **Make Code Changes**: Edit files directly
3. **Create Migrations**: `docker compose exec django python manage.py makemigrations [app_name]`
4. **Apply Migrations**: `docker compose exec django python manage.py migrate`
5. **Check Code Quality**: `pre-commit run --all-files`
6. **Build After Dependencies**: `just build` (after adding to requirements)
7. **View Logs**: `just logs [service_name]`
8. **Stop Development**: `just down`

## 📝 Notes
- Doppler is used for secret management (not .envs)
- Project follows Django best practices with app-based organization
- All apps are prefixed with `simlane.` in settings
- Uses Tailwind CSS for styling, v4 is used so no config file, tailwind is configured within the tailwind.css file using @theme. Do not attempt to add a config file or revert the version to v3.
- Implements Celery for background tasks
- Supports multiple authentication providers (Discord, Garage61)

// Additional instructions


const htmxDjangoBestPractices = [
  "Use Django's template system with HTMX attributes",
  "Implement Django forms for form handling",
  "Utilize Django's URL routing system",
  "Use Django's class-based views for HTMX responses",
  "Implement Django ORM for database operations",
  "Utilize Django's middleware for request/response processing",
];

const additionalInstructions = `
1. Use Django's template tags with HTMX attributes
2. Implement proper CSRF protection with Django's built-in features
3. Utilize Django's HttpResponse for HTMX-specific responses
4. Use Django's form validation for HTMX requests
5. Implement proper error handling and logging
6. Follow Django's best practices for project structure
7. Use Django's staticfiles app for managing static assets
`;


The django app and the nodejs containers are set to restart continuously in dev mode whenever any files change so there is no need to ask to run the start or up commands, you can assume they will reload. We only need to run the just build command when we make changes to either pip or npm dependencies. Keep this in mind. The tailwind changes are also compiled automatically with this.

## 🎨 Design Language
Refer to `docs/design/DESIGN_LANGUAGE.md` for the official colour palette, typography, component styles and accessibility guidelines. Ensure any new UI code or template follows these tokens and classes.

Any further requests for creating documents should end up with documents created in appropriate within in docs folder.

We are still in development phase and not live on production so do not worry about production migrations etc.


We will be building a mobile app for ios/android for this website and all of its features, so always keep that in mind when suggesting things and discussing designs etc.


Use the context7-local and context7-remote MCP for documentation of language, libraries etc. whenever needed and use the sequentialThinking MCP during planning and implementation while tracking progress.

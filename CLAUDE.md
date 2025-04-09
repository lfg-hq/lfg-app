# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Django Project Commands
- **Run server**: `python manage.py runserver 9000`
- **Migrations**: `python manage.py makemigrations` and `python manage.py migrate`
- **Tests**: `python manage.py test` or `python manage.py test app_name.tests.TestClassName.test_name`
- **Shell**: `python manage.py shell`

## Code Style Guidelines
- Follow PEP 8 conventions for Python code
- Group imports: standard library, third-party packages, local app imports
- Use Django class-based views where appropriate
- Include docstrings for functions/methods with complex logic
- Model fields should specify null/blank constraints explicitly
- Use descriptive variable names in snake_case
- Place related_name on ForeignKey fields for reverse relationships
- Always use login_required decorator for authenticated views
- Prefer get_object_or_404 for retrieving models by primary key
- Handle form validation errors explicitly with appropriate response

## Error Handling
- Use try/except blocks for external service calls (API requests)
- Return appropriate HTTP status codes with error messages
- Log exceptions in production environments
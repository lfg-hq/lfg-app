from django.shortcuts import render
from django.http import JsonResponse
from django.db import connection
from django.conf import settings
import datetime

# Create your views here.

def landing_page(request):
    """Render the marketing landing page."""
    return render(request, 'marketing/landing.html')

def health_check(request):
    """
    Health check endpoint to verify the application is running correctly.
    Checks database connectivity and returns detailed status information.
    """
    status = "healthy"
    database_status = "connected"
    errors = []
    
    # Check database connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as e:
        database_status = "disconnected"
        status = "unhealthy"
        errors.append(f"Database error: {str(e)}")
    
    # Build response data
    data = {
        "status": status,
        "timestamp": datetime.datetime.now().isoformat(),
        "environment": "production" if not settings.DEBUG else "development",
        "services": {
            "database": database_status
        }
    }
    
    if errors:
        data["errors"] = errors
    
    return JsonResponse(data)

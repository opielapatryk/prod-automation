from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

def api_endpoint(methods):
    """
    Combines common decorators for API endpoints:
    1. csrf_exempt - disables CSRF protection
    2. api_view - specifies allowed HTTP methods
    3. permission_classes with AllowAny - allows unauthenticated access
    """
    def decorator(func):
        # Apply decorators in reverse order
        decorated_func = permission_classes([AllowAny])(func)
        decorated_func = api_view(methods)(decorated_func)
        decorated_func = csrf_exempt(decorated_func)
        return decorated_func
    return decorator

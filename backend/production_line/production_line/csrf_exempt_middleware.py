from django.middleware.csrf import CsrfViewMiddleware

class CsrfExemptMiddleware(CsrfViewMiddleware):
    def process_view(self, request, callback, callback_args, callback_kwargs):
        # Skip CSRF validation for API endpoints
        if request.path.startswith('/api/'):
            return None
        # Otherwise, perform normal CSRF validation
        return super().process_view(request, callback, callback_args, callback_kwargs)

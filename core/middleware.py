# core/middleware.py
from django.utils.deprecation import MiddlewareMixin

class CSPMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        # Remove any strict CSP headers
        csp_headers = [
            'Content-Security-Policy',
            'Content-Security-Policy-Report-Only',
            'X-Content-Security-Policy',
            'X-WebKit-CSP'
        ]
        
        for header in csp_headers:
            if header in response:
                del response[header]
        
        # Add a more permissive CSP for development
        if request.path.startswith('/admin/'):
            # Keep stricter for admin
            response['Content-Security-Policy'] = "default-src 'self'"
        else:
            # Allow everything for your app
            response['Content-Security-Policy'] = (
                "default-src 'self' https://cdn.jsdelivr.net https://code.jquery.com https://cdn.datatables.net; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://code.jquery.com https://cdn.datatables.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdn.datatables.net https://cdnjs.cloudflare.com; "
                "font-src 'self' https://cdnjs.cloudflare.com; "
                "img-src 'self' data: https: http:;"
            )
        
        return response
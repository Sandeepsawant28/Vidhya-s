from django.shortcuts import redirect
from django.contrib.auth.models import User
from django.urls import reverse

class FirstRunSetupMiddleware:
    """
    Detects if the application is being launched for the very first time.
    If no users exist in the database, automatically forces navigation to
    the first-run setup wizard (/setup/) to safely configure the store and owner.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        # Allow static files, service worker, manifest, and setup page itself
        if (path.startswith('/static/') or 
            path.startswith('/manifest.json') or 
            path.startswith('/sw.js') or 
            path.startswith('/setup/')):
            return self.get_response(request)

        # Check if database has any user configured
        try:
            if not User.objects.exists():
                return redirect('setup_wizard')
        except Exception:
            # During initial migration or table creation, ignore
            pass

        return self.get_response(request)

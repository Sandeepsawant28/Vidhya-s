from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied

def is_owner_user(user):
    """Returns True if the user has Owner privileges or is superuser."""
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name='Owner').exists()

def owner_required(view_func):
    """Restricts access strictly to shop owners (blocks Cashiers from reports, cost prices, cancellations)."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not is_owner_user(request.user):
            messages.error(request, "Access Restricted: This section is available only to the Shop Owner.")
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

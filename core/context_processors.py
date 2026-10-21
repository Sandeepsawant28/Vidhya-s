from .models import ShopSettings
from .decorators import is_owner_user
from .utils import get_local_ip

def shop_context(request):
    """Provides common store configuration and permission checks to all templates."""
    try:
        settings_obj = ShopSettings.get_settings()
    except Exception:
        settings_obj = None

    is_owner = is_owner_user(request.user) if request.user.is_authenticated else False
    
    return {
        'shop_settings': settings_obj,
        'is_owner': is_owner,
        'local_ip': get_local_ip(),
    }

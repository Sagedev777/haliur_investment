# core/context_processors.py
from django.conf import settings
import sys

# Add system directory to path for importing navigation
sys.path.append(str(settings.BASE_DIR))

try:
    from system.navigation import NAVIGATION_CONFIG
except ImportError:
    # Fallback if navigation config doesn't exist yet
    NAVIGATION_CONFIG = {}

def navigation_context(request):
    """
    Build navigation context for the entire system.
    This is the single source of truth for navigation state.
    """
    if not request.user.is_authenticated:
        return {}
    
    # Determine user role
    if request.user.is_superuser:
        user_role = "admin"
    elif request.user.is_staff:
        user_role = "staff"
    else:
        user_role = None
    
    # Get active app/nav from view context
    active_app = getattr(request, 'active_app', 'dashboard')
    active_nav = getattr(request, 'active_nav', 'overview')
    
    # Store in session for persistence
    request.session['active_app'] = active_app
    request.session['active_nav'] = active_nav
    
    # Filter navigation based on user permissions
    filtered_nav = {}
    for app_id, app_config in NAVIGATION_CONFIG.items():
        if user_role not in app_config.get('permissions', []):
            continue
        
        # Filter subnav based on permissions
        filtered_subnav = []
        for subnav in app_config.get('subnav', []):
            subnav_permissions = subnav.get('permissions', ['admin', 'staff'])
            if user_role in subnav_permissions:
                filtered_subnav.append(subnav)
        
        if filtered_subnav:
            app_config_copy = app_config.copy()
            app_config_copy['subnav'] = filtered_subnav
            app_config_copy['is_active'] = (app_id == active_app)
            filtered_nav[app_id] = app_config_copy
    
    # Sort apps by order
    sorted_nav = dict(sorted(filtered_nav.items(), key=lambda x: x[1].get('order', 0)))
    
    # Mark active subnav
    if active_app in sorted_nav:
        for subnav in sorted_nav[active_app]['subnav']:
            subnav['is_active'] = (subnav['id'] == active_nav)
    
    return {
        'navigation': sorted_nav,
        'active_app': active_app,
        'active_nav': active_nav,
        'user_role': user_role,
    }
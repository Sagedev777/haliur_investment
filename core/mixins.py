# core/mixins.py
class NavigationMixin:
    """
    Mixin to set navigation context for any view.
    Inherit this in all views that should set navigation state.
    """
    active_app = None
    active_nav = None
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_app'] = self.active_app
        context['active_nav'] = self.active_nav
        
        # Store in request for context processor
        self.request.active_app = self.active_app
        self.request.active_nav = self.active_nav
        
        return context
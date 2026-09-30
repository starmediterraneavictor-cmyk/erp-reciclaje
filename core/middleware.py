from django.contrib.auth.views import redirect_to_login
from django.urls import resolve, Resolver404


class LoginRequiredMiddleware:
    """Exige login en todas las vistas excepto las públicas."""
    
    PUBLIC_URLS = [
        '/admin/login/',
        '/admin/logout/',
        '/accounts/login/',
        '/accounts/logout/',
        '/static/',
        '/media/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Si ya está autenticado, dejamos pasar
        if request.user.is_authenticated:
            return self.get_response(request)
        
        # Si la URL es pública, dejamos pasar
        path = request.path
        for public in self.PUBLIC_URLS:
            if path.startswith(public):
                return self.get_response(request)
        
        # Resto: redirigimos al login
        return redirect_to_login(path)
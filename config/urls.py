from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core import views
from django.contrib.auth import views as auth_views
from core import views as core_views
from django.conf.urls.i18n import i18n_patterns


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.dashboard, name='dashboard'),
    path('pedidos/', include('pedidos.urls')),
    path('clientes/', include('clientes.urls')),
    path('proveedores/', include('proveedores.urls')),
    path('inventario/', include('inventario.urls')),
    path('finanzas/', include('finanzas.urls')),
    path('analisis/', include('analisis.urls')),
    path('crm/', include('crm.urls')),
    path('logout/', auth_views.LogoutView.as_view(next_page='/admin/login/'), name='logout'),
    path('manual/', core_views.manual_usuario, name='manual_usuario'),
    path('i18n/', include('django.conf.urls.i18n')),
]


# Servir archivos media (logos, PDFs) en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
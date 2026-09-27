from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_proveedores, name='lista_proveedores'),
    path('nuevo/', views.nuevo_proveedor, name='nuevo_proveedor'),
    path('<int:proveedor_id>/editar/', views.editar_proveedor, name='editar_proveedor'),
    path('<int:proveedor_id>/eliminar/', views.confirmar_eliminar_proveedor, name='confirmar_eliminar_proveedor'),
    path('<int:proveedor_id>/eliminar/confirmar/', views.eliminar_proveedor, name='eliminar_proveedor'),
]
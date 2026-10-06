from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_clientes, name='lista_clientes'),
    path('nuevo/', views.nuevo_cliente, name='nuevo_cliente'),
    path('<int:cliente_id>/editar/', views.editar_cliente, name='editar_cliente'),
    path('<int:cliente_id>/eliminar/', views.confirmar_eliminar_cliente, name='confirmar_eliminar_cliente'),
    path('<int:cliente_id>/eliminar/confirmar/', views.eliminar_cliente, name='eliminar_cliente'),
    path('exportar/', views.exportar_clientes_excel, name='exportar_clientes_excel'),
]
from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_inventario, name='lista_inventario'),
    path('nuevo/', views.nuevo_material, name='nuevo_material'),
    path('<int:material_id>/', views.detalle_material, name='detalle_material'),
    path('subgrupos/<int:tipo_id>/', views.subgrupos_por_tipo, name='subgrupos_por_tipo'),
    path('<int:material_id>/editar/', views.editar_material, name='editar_material'),
    path('<int:material_id>/eliminar/', views.confirmar_eliminar_material, name='confirmar_eliminar_material'),
    path('<int:material_id>/eliminar/confirmar/', views.eliminar_material, name='eliminar_material'),
    
]

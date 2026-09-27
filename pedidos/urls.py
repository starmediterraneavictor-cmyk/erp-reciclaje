from django.urls import path
from . import views

urlpatterns = [
    # Pedidos normales
    path('', views.lista_pedidos, name='lista_pedidos'),
    path('nuevo/', views.nuevo_pedido, name='nuevo_pedido'),
    path('<int:pedido_id>/', views.detalle_pedido, name='detalle_pedido'),
    path('<int:pedido_id>/editar/', views.editar_pedido, name='editar_pedido'),
    path('<int:pedido_id>/eliminar/', views.confirmar_eliminar_pedido, name='confirmar_eliminar_pedido'),
    path('<int:pedido_id>/eliminar/confirmar/', views.eliminar_pedido, name='eliminar_pedido'),

    # Generar factura desde pedido
    path('<int:pedido_id>/generar-factura/', views.generar_factura_desde_pedido, name='generar_factura_desde_pedido'),

    
    # Pedidos internacionales y nacionales
    path('internacional/', views.seguimiento_internacional, name='seguimiento_internacional'),
    path('internacional/<int:int_id>/', views.detalle_pedido_internacional, name='detalle_pedido_internacional'),
    path('internacional/<int:int_id>/editar/', views.editar_pedido_internacional, name='editar_pedido_internacional'),
    path('internacional/pago/<int:pago_id>/eliminar/', views.eliminar_pago_internacional, name='eliminar_pago_internacional'),
]
from django.urls import path
from . import views

urlpatterns = [
    # Facturas
    path('', views.lista_facturas, name='lista_facturas'),
    path('nueva/', views.nueva_factura, name='nueva_factura'),
    path('<int:factura_id>/editar/', views.editar_factura, name='editar_factura'),
    path('<int:factura_id>/eliminar/', views.confirmar_eliminar_factura, name='confirmar_eliminar_factura'),
    path('<int:factura_id>/eliminar/confirmar/', views.eliminar_factura, name='eliminar_factura'),
    path('<int:factura_id>/pdf/', views.factura_pdf, name='factura_pdf'),

    # Exportar Excel
    path('exportar/facturas/', views.exportar_facturas_excel, name='exportar_facturas_excel'),
    
    # Regristrar cobro/pago desde factura
    path('factura/<int:factura_id>/registrar-cobro-pago/', views.registrar_cobro_pago_factura, name='registrar_cobro_pago_factura'),

        # Eliminar cuentas por pagar
    path('pagar/<int:cuenta_id>/eliminar/', views.confirmar_eliminar_cuenta_por_pagar, name='confirmar_eliminar_cuenta_por_pagar'),
    path('pagar/<int:cuenta_id>/eliminar/confirmar/', views.eliminar_cuenta_por_pagar, name='eliminar_cuenta_por_pagar'),

    # Eliminar cuentas por cobrar
    path('cobrar/<int:cuenta_id>/eliminar/', views.confirmar_eliminar_cuenta_por_cobrar, name='confirmar_eliminar_cuenta_por_cobrar'),
    path('cobrar/<int:cuenta_id>/eliminar/confirmar/', views.eliminar_cuenta_por_cobrar, name='eliminar_cuenta_por_cobrar'),
    

    # Cuentas por pagar
    path('pagar/', views.cuentas_por_pagar, name='cuentas_por_pagar'),
    path('pagar/nueva/', views.nueva_cuenta_por_pagar, name='nueva_cuenta_por_pagar'),
    path('pagar/<int:cuenta_id>/pagar/', views.registrar_pago_cuenta, name='registrar_pago_cuenta'),
    
    
    # Cuentas por cobrar
    path('cobrar/', views.cuentas_por_cobrar, name='cuentas_por_cobrar'),
    path('cobrar/nueva/', views.nueva_cuenta_por_cobrar, name='nueva_cuenta_por_cobrar'),
    path('cobrar/<int:cuenta_id>/cobrar/', views.registrar_cobro_cuenta, name='registrar_cobro_cuenta'),
   
    
    # Dashboard financiero
    path('dashboard/', views.dashboard_financiero, name='dashboard_financiero'),

    # Libros de gastos ingresos
    path('libro/', views.libro_gastos_ingresos, name='libro_gastos_ingresos'),
    path('libro/exportar/', views.exportar_libro_excel, name='exportar_libro_excel'),

    

]

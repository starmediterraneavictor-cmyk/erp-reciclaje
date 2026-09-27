from django.contrib import admin
from .models import Pedido, DetallePedido, PedidoInternacional, PagoInternacional, CondicionPago


class DetalleInline(admin.TabularInline):
    model = DetallePedido
    extra = 1


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('numero_pedido', 'cliente', 'tipo', 'estado', 'fecha')
    list_filter = ('tipo', 'estado')
    search_fields = ('numero_pedido', 'cliente__nombre')
    inlines = [DetalleInline]


@admin.register(CondicionPago)
class CondicionPagoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'porcentaje_anticipo', 'dias_antes_llegada', 'activo')


class PagoInternacionalInline(admin.TabularInline):
    model = PagoInternacional
    extra = 1


@admin.register(PedidoInternacional)
class PedidoInternacionalAdmin(admin.ModelAdmin):
    list_display = (
        'pedido', 'estado', 'incoterm', 'puerto_destino',
        'fecha_eta', 'valor_total', 'porcentaje_pagado', 'alerta_cobro'
    )
    list_filter = ('estado', 'incoterm', 'condicion_pago', 'ambito')
    search_fields = ('pedido__numero_pedido', 'numero_contenedor', 'numero_bl', 'puerto_destino')
    inlines = [PagoInternacionalInline]
    readonly_fields = ('porcentaje_pagado', 'total_pagado', 'saldo_pendiente', 'dias_para_llegada')

    fieldsets = (
        ('Pedido', {
            'fields': ('pedido', 'estado', 'incoterm', 'condicion_pago')
        }),
        ('Ámbito', {
            'fields': ('ambito', 'provincia_destino')
        }),
        ('Datos logísticos', {
            'fields': (
                'numero_contenedor', 'numero_precinto', 'naviera',
                'numero_bl', 'buque', 'puerto_origen', 'puerto_destino'
            )
        }),
        ('Fechas', {
            'fields': ('fecha_carga', 'fecha_salida', 'fecha_eta', 'fecha_entrega_real')
        }),
        ('Datos económicos', {
            'fields': (
                'valor_total', 'coste_flete', 'peso_total_kg',
                'total_pagado', 'porcentaje_pagado', 'saldo_pendiente', 'dias_para_llegada'
            )
        }),
        ('Notas', {
            'fields': ('notas',)
        }),
    )
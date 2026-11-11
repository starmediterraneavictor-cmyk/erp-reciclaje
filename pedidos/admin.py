from django.contrib import admin
from .models import (
    Pedido, PesadaCamion, DetallePedido, 
    PedidoInternacional, PagoInternacional, 
    CondicionPago, OrigenVenta, Comercial, Comision
)

# ============================================
# INLINES (Secciones dentro del Pedido)
# ============================================

class DetalleInline(admin.TabularInline):
    model = DetallePedido
    extra = 1

class PesadaCamionInline(admin.TabularInline):
    model = PesadaCamion
    extra = 0
    

class ComisionInline(admin.TabularInline):
    model = Comision
    extra = 1


# ============================================
# ADMIN DE PEDIDOS
# ============================================

@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('numero_pedido', 'cliente', 'proveedor', 'tipo', 'estado', 'fecha')
    list_filter = ('tipo', 'estado')
    search_fields = ('numero_pedido', 'cliente__nombre', 'proveedor__nombre')
    
    # 🆕 Añadimos TODOS los inlines aquí
    inlines = [DetalleInline, PesadaCamionInline, ComisionInline]


# ============================================
# OTROS MODELOS
# ============================================

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


@admin.register(OrigenVenta)
class OrigenVentaAdmin(admin.ModelAdmin):
    list_display = ('pedido_venta', 'pedido_compra', 'cantidad_tn', 'fecha_asignacion')
    search_fields = ('pedido_venta__numero_pedido', 'pedido_compra__numero_pedido')
    list_filter = ('pedido_venta__tipo', 'pedido_compra__tipo')


@admin.register(Comercial)
class ComercialAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'telefono', 'email', 'activo')
    search_fields = ('nombre', 'email')
    list_filter = ('activo',)
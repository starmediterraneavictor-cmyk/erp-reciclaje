from django.contrib import admin
from .models import (
    Factura, CuentaPorPagar, PagoCuentaPorPagar,
    CuentaPorCobrar, CobroCuentaPorCobrar
)


@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = ('numero_factura', 'tipo', 'cliente','proveedor', 'fecha', 'total', 'estado_pago')
    list_filter = ('tipo', 'categoria', 'estado_pago', 'fecha')
    search_fields = ('numero_factura', 'cliente__nombre', 'proveedor__nombre')
    date_hierarchy = 'fecha'


class PagoInline(admin.TabularInline):
    model = PagoCuentaPorPagar
    extra = 1


@admin.register(CuentaPorPagar)
class CuentaPorPagarAdmin(admin.ModelAdmin):
    list_display = (
        'concepto', 'categoria', 'proveedor', 'importe_total', 
        'saldo_pendiente', 'fecha_vencimiento', 'estado', 'alerta'
    )
    list_filter = ('categoria', 'estado', 'fecha_vencimiento')
    search_fields = ('concepto', 'proveedor__nombre', 'numero_factura')
    inlines = [PagoInline]
    date_hierarchy = 'fecha_vencimiento'
    readonly_fields = ('saldo_pendiente', 'dias_para_vencer', 'esta_vencida')


class CobroInline(admin.TabularInline):
    model = CobroCuentaPorCobrar
    extra = 1


@admin.register(CuentaPorCobrar)
class CuentaPorCobrarAdmin(admin.ModelAdmin):
    list_display = (
        'concepto', 'cliente', 'importe_total', 
        'saldo_pendiente', 'fecha_vencimiento', 'estado', 'alerta'
    )
    list_filter = ('estado', 'fecha_vencimiento')
    search_fields = ('concepto', 'cliente__nombre', 'numero_factura')
    inlines = [CobroInline]
    date_hierarchy = 'fecha_vencimiento'
    readonly_fields = ('saldo_pendiente', 'dias_para_vencer')
"""
Script para reparar la sincronización entre Facturas y Cuentas.
Ejecutar una sola vez:
    python manage.py shell < reparar_estados.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from finanzas.models import CuentaPorPagar, CuentaPorCobrar, Factura

contador = 0

# Reparar Cuentas por Pagar
for c in CuentaPorPagar.objects.all():
    factura = Factura.objects.filter(numero_factura=c.numero_factura).first()
    if factura and factura.estado_pago != c.estado:
        if c.estado in ['PAGADO', 'PARCIAL', 'PENDIENTE']:
            factura.estado_pago = c.estado
            factura.save()
            contador += 1
            print(f"✅ PAGAR {factura.numero_factura}: {c.estado}")

# Reparar Cuentas por Cobrar
for c in CuentaPorCobrar.objects.all():
    factura = Factura.objects.filter(numero_factura=c.numero_factura).first()
    if factura and factura.estado_pago != c.estado:
        if c.estado == 'COBRADO':
            factura.estado_pago = 'PAGADO'
        elif c.estado in ['PENDIENTE', 'PARCIAL']:
            factura.estado_pago = c.estado
        factura.save()
        contador += 1
        print(f"✅ COBRAR {factura.numero_factura}: {factura.estado_pago}")

print(f"\n✅ Completado. {contador} facturas reparadas.")
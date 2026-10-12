"""
Script para diagnosticar la anulación de factura/cuenta.
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from finanzas.models import Factura, CuentaPorCobrar, CuentaPorPagar

print("=== FACTURAS ===")
for f in Factura.objects.all():
    print(f"Factura {f.numero_factura}: tipo={f.tipo}, estado={f.estado_pago}")

print("\n=== CUENTAS POR COBRAR ===")
for c in CuentaPorCobrar.objects.all():
    print(f"Cuenta: {c.concepto}")
    print(f"  num_factura: {c.numero_factura}")
    print(f"  estado: {c.estado}")
    print(f"  importe_total: {c.importe_total}")
    print(f"  importe_cobrado: {c.importe_cobrado}")
    print(f"  saldo_pendiente: {c.saldo_pendiente}")

print("\n=== CUENTAS POR PAGAR ===")
for c in CuentaPorPagar.objects.all():
    print(f"Cuenta: {c.concepto}")
    print(f"  num_factura: {c.numero_factura}")
    print(f"  estado: {c.estado}")
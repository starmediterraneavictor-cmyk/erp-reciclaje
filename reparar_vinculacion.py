"""
Script para vincular cuentas y facturas por pedido.
Ejecutar una sola vez:
    python manage.py shell < reparar_vinculacion.py
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from finanzas.models import CuentaPorPagar, Factura
from pedidos.models import Pedido

contador = 0

for c in CuentaPorPagar.objects.all():
    if not c.concepto.startswith('Pedido '):
        continue
    
    num_pedido = c.concepto.replace('Pedido ', '').strip()
    pedido = Pedido.objects.filter(numero_pedido=num_pedido).first()
    
    if not pedido:
        print(f"⚠️ Pedido no encontrado: {num_pedido}")
        continue
    
    factura = Factura.objects.filter(pedido=pedido).first()
    
    if not factura:
        print(f"⚠️ Factura no encontrada para pedido: {num_pedido}")
        continue
    
    # Vincular: actualizar el numero_factura de la cuenta con el de la factura
    if c.numero_factura != factura.numero_factura:
        c.numero_factura = factura.numero_factura
        c.save()
        print(f"🔗 Vinculada: {c.concepto} → {factura.numero_factura}")
        contador += 1
    
    # Sincronizar el estado de la factura
    if factura.estado_pago != c.estado:
        if c.estado in ['PAGADO', 'PARCIAL', 'PENDIENTE']:
            factura.estado_pago = c.estado
            factura.save()
            print(f"✅ {factura.numero_factura}: {c.estado}")
            contador += 1

print(f"\n✅ Completado. {contador} registros reparados.")
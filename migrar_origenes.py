"""
Script para migrar pedidos_origen a OrigenVenta.
Ejecutar una sola vez:
    python manage.py shell < migrar_origenes.py
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from pedidos.models import Pedido, OrigenVenta

contador = 0

for p in Pedido.objects.filter(pedido_origen__isnull=False, tipo='VENTA_MAT'):
    # Si ya tiene orígenes, saltar
    if p.origenes_venta.exists():
        continue
    
    # Crear el OrigenVenta con la cantidad total del pedido
    OrigenVenta.objects.create(
        pedido_venta=p,
        pedido_compra=p.pedido_origen,
        cantidad_tn=p.total_kg,
    )
    contador += 1
    print(f"✅ {p.numero_pedido} ← {p.pedido_origen.numero_pedido} ({p.total_kg} tn)")

print(f"\n✅ Completado. {contador} orígenes migrados.")
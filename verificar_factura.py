"""
Script para verificar la factura asociada al pedido 2026S0001.
Ejecutar: python manage.py shell < verificar_factura.py
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from pedidos.models import Pedido
from finanzas.models import Factura

p = Pedido.objects.get(numero_pedido='2026S0001')
print(f"Pedido: {p.numero_pedido}")
print(f"  total_kg: {p.total_kg}")
print(f"  total_importe: {p.total_importe}")
print(f"  origenes_venta: {p.origenes_venta.count()}")

f = Factura.objects.filter(pedido=p).first()
if f:
    print(f"Factura: {f.numero_factura}")
    print(f"  base: {f.base}")
    print(f"  total: {f.total}")
    print(f"  categoria: {f.categoria}")
else:
    print("Sin factura asociada")
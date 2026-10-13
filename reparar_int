"""
Script para sincronizar valor_total de PedidoInternacional.
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from pedidos.models import PedidoInternacional

for pi in PedidoInternacional.objects.all():
    if pi.pedido:
        valor_actual = pi.valor_total
        valor_nuevo = pi.pedido.total_importe
        if valor_actual != valor_nuevo:
            pi.valor_total = valor_nuevo
            pi.peso_total_kg = pi.pedido.total_kg
            pi.save()
            print(f"🔧 {pi.pedido.numero_pedido}: {valor_actual} → {valor_nuevo}")
        else:
            print(f"✅ {pi.pedido.numero_pedido}: {valor_actual} (OK)")

print("\n✅ Completado")
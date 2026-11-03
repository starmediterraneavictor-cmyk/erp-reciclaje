import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from finanzas.models import CuentaPorPagar, Factura

def ejecutar():
    actualizadas = 0
    print("Iniciando actualización de categorías...")

    # Recorremos TODAS las cuentas por pagar (sin filtrar por categoría)
    for cuenta in CuentaPorPagar.objects.all():
        # 1. Intentar buscar por factura
        if cuenta.numero_factura:
            factura = Factura.objects.filter(numero_factura=cuenta.numero_factura).first()
            if factura:
                cuenta.categoria = factura.categoria
                cuenta.save()
                actualizadas += 1
                continue # Si ya la actualizamos por factura, pasamos a la siguiente

        # 2. Si no tiene factura, mirar el proveedor
        if cuenta.proveedor:
            if cuenta.proveedor.tipo == 'COMERCIO_MATERIALES':
                cuenta.categoria = 'COMERCIO_MATERIALES'
            elif cuenta.proveedor.tipo == 'TRANSPORTE':
                cuenta.categoria = 'TRANSPORTE'
            elif cuenta.proveedor.tipo == 'SUMINISTROS':
                cuenta.categoria = 'SUMINISTROS'
            else:
                cuenta.categoria = 'OTROS' 
            cuenta.save()
            actualizadas += 1

    print(f"✅ {actualizadas} cuentas actualizadas en total.")

ejecutar()
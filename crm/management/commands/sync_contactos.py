from django.core.management.base import BaseCommand
from crm.models import Contacto, SectorContacto
from clientes.models import Cliente
from proveedores.models import Proveedor

class Command(BaseCommand):
    help = 'Sincroniza los Clientes y Proveedores existentes al CRM'

    def handle(self, *args, **kwargs):
        self.stdout.write("Iniciando sincronización...")

        sector_default, _ = SectorContacto.objects.get_or_create(
            nombre='GENERAL (Importado)',
            defaults={'tipo': 'AMBOS'}
        )

        creados = 0
        actualizados = 0

        for prov in Proveedor.objects.all():
            contacto, created = Contacto.objects.get_or_create(
                proveedor=prov,
                defaults={
                    'nombre': prov.nombre,
                    'tipo': 'PROVEEDOR',
                    'pais': prov.pais,
                    'email': prov.email,
                    'telefono': prov.telefono,
                    'ubicacion': prov.direccion,
                    'sector': sector_default,
                    'notas': 'Importado automáticamente desde el módulo de Proveedores.'
                }
            )
            if created:
                creados += 1
            else:
                actualizados += 1

        for cli in Cliente.objects.all():
            contacto, created = Contacto.objects.get_or_create(
                cliente=cli,
                defaults={
                    'nombre': cli.nombre,
                    'tipo': 'CLIENTE',
                    'pais': cli.pais,
                    'email': cli.email,
                    'telefono': cli.telefono,
                    'ubicacion': cli.direccion,
                    'sector': sector_default,
                    'notas': 'Importado automáticamente desde el módulo de Clientes.'
                }
            )
            if created:
                creados += 1
            else:
                actualizados += 1

        self.stdout.write(self.style.SUCCESS(
            f'✅ Sincronización completada. Creados: {creados}, Actualizados: {actualizados}'
        ))
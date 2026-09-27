from django.core.management.base import BaseCommand
from inventario.models import TipoMaterial, SubgrupoMaterial


class Command(BaseCommand):
    help = 'Crea los tipos y subgrupos de material por defecto'

    def handle(self, *args, **options):
        datos = {
            'Plástico': ['HDPE', 'PET', 'PP', 'PVC', 'PS', 'ABS', 'LDPE', 'PA', 'ABS-PC'],
            'Metal': ['Mix Metal','Cobre', 'Aluminio', 'Hierro', 'Acero', 'Latón', 'Zinc'],
            'Papel y Cartón': ['Cartón', 'Papel blanco', 'Papel mezclado', 'Periódico'],
            'Electrónica': ['Placas base', 'Cables', 'Componentes'],
            
        }

        tipos_creados = 0
        subgrupos_creados = 0

        for nombre_tipo, subgrupos in datos.items():
            tipo, creado = TipoMaterial.objects.get_or_create(
                nombre=nombre_tipo,
                defaults={'descripcion': f'Categoría {nombre_tipo}'}
            )
            if creado:
                tipos_creados += 1

            for nombre_sub in subgrupos:
                _, creado_sub = SubgrupoMaterial.objects.get_or_create(
                    tipo=tipo,
                    nombre=nombre_sub,
                    defaults={'descripcion': f'{nombre_sub} dentro de {nombre_tipo}'}
                )
                if creado_sub:
                    subgrupos_creados += 1

        self.stdout.write(self.style.SUCCESS(
            f'✅ {tipos_creados} tipos y {subgrupos_creados} subgrupos creados'
        ))
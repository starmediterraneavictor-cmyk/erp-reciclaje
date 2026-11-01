import pandas as pd
from django.core.management.base import BaseCommand
from crm.models import Contacto, SectorContacto, EstadoContacto, InteresMaterial

def limpiar(texto, limite=200):
    if pd.isna(texto) or str(texto).lower() == 'nan':
        return ''
    return str(texto).strip()[:limite]

class Command(BaseCommand):
    help = 'Importa los materiales desde el archivo Excel'

    def handle(self, *args, **kwargs):
        self.stdout.write("Iniciando importación de materiales...")
        
        # Leemos el excel SIN cabeceras (header=None)
        try:
            df = pd.read_excel('excel_data/consulta_mat.xlsx', sheet_name=0, header=None)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error leyendo el archivo: {e}"))
            return

        # Buscamos en qué fila están los nombres de los materiales (HDPE, LDPE, etc.)
        fila_cabecera = None
        for i, row in df.iterrows():
            if 'HDPE' in [str(x).strip() for x in row.values]:
                fila_cabecera = i
                break

        if fila_cabecera is None:
            self.stdout.write(self.style.ERROR("No se encontró la fila de materiales (HDPE)."))
            return

        # Asignamos esa fila como cabecera
        df.columns = df.iloc[fila_cabecera]
        df = df[fila_cabecera + 1:].reset_index(drop=True)

        # Filtramos las columnas que son materiales (desde HDPE en adelante)
        columnas_materiales = []
        encontrado_hdpe = False
        for col in df.columns:
            col_name = str(col).strip()
            if col_name == 'HDPE':
                encontrado_hdpe = True
            if encontrado_hdpe and col_name != 'nan':
                columnas_materiales.append(col)

        intereses_creados = 0
        empresas_encontradas = 0

        for index, row in df.iterrows():
            empresa_raw = row.get('EMPRESA')
            if pd.isna(empresa_raw):
                continue
                
            empresa = limpiar(empresa_raw, 200)
            accion_raw = str(row.get('ACCION', '')).strip().upper()

            accion = 'COMPRO' if 'COMPRO' in accion_raw else ('VENDEMOS' if 'VENDEMOS' in accion_raw else None)
            if not accion:
                continue

            contacto = Contacto.objects.filter(nombre__iexact=empresa).first()
            if not contacto:
                contacto = Contacto.objects.filter(nombre__icontains=empresa).first()

            if not contacto:
                contacto = Contacto.objects.create(
                    nombre=empresa,
                    pais=limpiar(row.get('PAIS', 'España'), 100).capitalize(),
                    tipo='PROSPECTO'
                )
            
            empresas_encontradas += 1

            for material in columnas_materiales:
                detalle = limpiar(row.get(material), 300)
                if detalle:
                    obj, created = InteresMaterial.objects.get_or_create(
                        contacto=contacto,
                        accion=accion,
                        tipo_material=limpiar(material, 100),
                        defaults={'detalle': detalle}
                    )
                    if created:
                        intereses_creados += 1

        self.stdout.write(self.style.SUCCESS(f"   -> {intereses_creados} intereses importados para {empresas_encontradas} empresas."))
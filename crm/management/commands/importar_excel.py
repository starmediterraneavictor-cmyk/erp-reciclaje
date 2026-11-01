import pandas as pd
from django.core.management.base import BaseCommand
from crm.models import Contacto, SectorContacto, EstadoContacto, InteresMaterial

def limpiar(texto, limite=200):
    if pd.isna(texto) or str(texto).lower() == 'nan':
        return ''
    return str(texto).strip()[:limite]

class Command(BaseCommand):
    help = 'Importa los contactos y materiales desde los archivos Excel'

    def handle(self, *args, **kwargs):
        self.stdout.write("Iniciando importación de Excel...")
        self.importar_todas_las_hojas()
        self.importar_matriz_materiales()
        self.stdout.write(self.style.SUCCESS("✅ Importación finalizada con éxito."))

    def importar_todas_las_hojas(self):
        self.stdout.write("-> Leyendo seguimiento.xlsx (Todas las hojas de clientes)...")
        
        estado_seg, _ = EstadoContacto.objects.get_or_create(nombre='SEGUIMIENTO', defaults={'color': 'info'})
        estado_pau, _ = EstadoContacto.objects.get_or_create(nombre='EN PAUSA', defaults={'color': 'warning'})
        estado_desc, _ = EstadoContacto.objects.get_or_create(nombre='DESCARTADO', defaults={'color': 'danger'})

        creados = 0
        try:
            xls = pd.ExcelFile('excel_data/seguimiento.xlsx')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error abriendo el archivo: {e}"))
            return

        for sheet_name in xls.sheet_names:
            if sheet_name in ['Listas', 'MAT TRADING', 'TRANSPORTES', 'BB']:
                continue

            self.stdout.write(f"   -> Procesando hoja: {sheet_name}")
            df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
            
            header_row = None
            for i, row in df.iterrows():
                if 'Nombre' in [str(x).strip() for x in row.values]:
                    header_row = i
                    break
            
            if header_row is None:
                continue

            df.columns = df.iloc[header_row]
            df = df[header_row + 1:].reset_index(drop=True)
            df = df.dropna(how='all')

            for index, row in df.iterrows():
                nombre = limpiar(row.get('Nombre'))
                if not nombre:
                    continue

                try:
                    est_nombre = str(row.get('Estado', 'SEGUIMIENTO')).strip().upper()
                    if 'PAUSA' in est_nombre: estado_obj = estado_pau
                    elif 'DESCART' in est_nombre: estado_obj = estado_desc
                    else: estado_obj = estado_seg

                    actividad = limpiar(row.get('ACTIVIDAD'), 100)
                    sector_obj = None
                    if actividad:
                        sector_obj, _ = SectorContacto.objects.get_or_create(nombre=actividad, defaults={'tipo': 'AMBOS'})

                    fecha_raw = row.get('Última fecha contactado')
                    fecha_contacto = None
                    if pd.notna(fecha_raw):
                        try: fecha_contacto = pd.to_datetime(fecha_raw).date()
                        except: pass

                    contacto, created = Contacto.objects.get_or_create(
                        nombre=nombre[:200],
                        defaults={
                            'pais': limpiar(row.get('País', 'España'), 100).capitalize(),
                            'ubicacion': limpiar(row.get('UBICACION')),
                            'provincia': limpiar(row.get('PROVINCIA'), 100),
                            'localidad': limpiar(row.get('LOCALIDAD'), 100),
                            'web': limpiar(row.get('Web')) if str(row.get('Web', '')).startswith('http') else '',
                            'persona_contacto': limpiar(row.get('Nombre contacto'), 150),
                            'email': limpiar(row.get('Email')),
                            'telefono': limpiar(row.get('Teléfono'), 50),
                            'movil': limpiar(row.get('Móvil'), 50),
                            'estado': estado_obj,
                            'sector': sector_obj,
                            'actividad': actividad,
                            'notas': limpiar(row.get('Notas'), 5000),
                            'ultima_fecha_contacto': fecha_contacto,
                            'codigo_gestor': limpiar(row.get('CÓDIGO DE GESTOR'), 50)
                        }
                    )
                    if created:
                        creados += 1
                except Exception as e:
                    pass

        self.stdout.write(self.style.SUCCESS(f"   -> {creados} contactos importados en total."))

    def importar_matriz_materiales(self):
        self.stdout.write("-> Leyendo consulta_mat.xlsx (Matriz de materiales)...")
        try:
            df = pd.read_excel('excel_data/consulta_mat.xlsx', sheet_name=0, header=None)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error leyendo el archivo: {e}"))
            return

        fila_cabecera = None
        for i, row in df.iterrows():
            if 'HDPE' in [str(x).strip() for x in row.values]:
                fila_cabecera = i
                break

        if fila_cabecera is None:
            return

        df.columns = df.iloc[fila_cabecera]
        df = df[fila_cabecera + 1:].reset_index(drop=True)

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
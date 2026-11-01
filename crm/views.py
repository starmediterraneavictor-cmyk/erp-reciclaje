from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils import timezone
from datetime import date
from .models import Contacto, Interaccion, SectorContacto, EstadoContacto
from clientes.models import Cliente
from proveedores.models import Proveedor

@login_required
def lista_contactos(request):
    # Filtros
    alerta = request.GET.get('alerta', '')
    buscar = request.GET.get('buscar', '').strip()
    sector_id = request.GET.get('sector', '')
    estado_id = request.GET.get('estado', '')

    contactos = Contacto.objects.all()

    if buscar:
        contactos = contactos.filter(
            Q(nombre__icontains=buscar) | 
            Q(email__icontains=buscar) | 
            Q(notas__icontains=buscar)
        )
    if sector_id:
        contactos = contactos.filter(sector_id=sector_id)
    if estado_id:
        contactos = contactos.filter(estado_id=estado_id)
    
    # Filtro especial de alerta
    if alerta == '1':
        # No podemos filtrar directamente por @property en la DB, 
        # así que lo hacemos en Python
        contactos = [c for c in contactos if c.alerta]
    else:
        contactos = list(contactos)

    # Ordenar: Primero los que tienen alerta urgente, luego por nombre
    def orden_alerta(c):
        niveles = {'urgente': 1, 'pronto': 2, 'ok': 3, None: 4}
        return (niveles.get(c.nivel_alerta, 5), c.nombre)
    
    contactos.sort(key=orden_alerta)

    context = {
        'contactos': contactos,
        'sectores': SectorContacto.objects.filter(activo=True),
        'estados': EstadoContacto.objects.filter(activo=True),
        'alerta_filtro': alerta,
        'buscar_filtro': buscar,
        'sector_filtro': sector_id,
        'estado_filtro': estado_id,
        'total': len(contactos),
        'num_alertas': len([c for c in contactos if c.alerta])
    }
    return render(request, 'crm/lista.html', context)


@login_required
def detalle_contacto(request, contacto_id):
    contacto = get_object_or_404(Contacto, id=contacto_id)
    
    if request.method == 'POST' and 'estado' in request.POST:
        # Cambio rápido de estado desde la ficha
        contacto.estado_id = request.POST.get('estado') or None
        contacto.save()
        messages.success(request, 'Estado actualizado.')
        return redirect('detalle_contacto', contacto_id=contacto.id)

    context = {
        'contacto': contacto,
        'interacciones': contacto.interacciones.all(),
        'intereses_compra': contacto.intereses_compra,
        'intereses_venta': contacto.intereses_venta,
        'estados': EstadoContacto.objects.filter(activo=True),
    }
    return render(request, 'crm/ficha.html', context)


@login_required
def editar_contacto(request, contacto_id=None):
    if contacto_id:
        contacto = get_object_or_404(Contacto, id=contacto_id)
    else:
        contacto = None

    if request.method == 'POST':
        # Procesar formulario manualmente (igual que en proveedores)
        if not contacto:
            contacto = Contacto()
            
        contacto.nombre = request.POST.get('nombre')
        contacto.tipo = request.POST.get('tipo', 'PROSPECTO')
        contacto.pais = request.POST.get('pais', '')
        contacto.ubicacion = request.POST.get('ubicacion', '')
        contacto.provincia = request.POST.get('provincia', '')
        contacto.localidad = request.POST.get('localidad', '')
        contacto.web = request.POST.get('web', '')
        contacto.persona_contacto = request.POST.get('persona_contacto', '')
        contacto.email = request.POST.get('email', '')
        contacto.telefono = request.POST.get('telefono', '')
        contacto.movil = request.POST.get('movil', '')
        contacto.sector_id = request.POST.get('sector') or None
        contacto.estado_id = request.POST.get('estado') or None
        contacto.actividad = request.POST.get('actividad', '')
        contacto.notas = request.POST.get('notas', '')
        contacto.dias_alerta = request.POST.get('dias_alerta', 9)
        contacto.save()
        
        messages.success(request, 'Contacto guardado correctamente.')
        return redirect('detalle_contacto', contacto_id=contacto.id)

    context = {
        'contacto': contacto,
        'tipos': Contacto.TIPO_CONTACTO,
        'sectores': SectorContacto.objects.filter(activo=True),
        'estados': EstadoContacto.objects.filter(activo=True),
    }
    return render(request, 'crm/formulario.html', context)


@login_required
def nueva_interaccion(request, contacto_id):
    contacto = get_object_or_404(Contacto, id=contacto_id)
    if request.method == 'POST':
        Interaccion.objects.create(
            contacto=contacto,
            tipo=request.POST.get('tipo'),
            resumen=request.POST.get('resumen'),
            fecha=request.POST.get('fecha') or timezone.now().date(),
            autor=request.user
        )
        messages.success(request, 'Interacción registrada.')
    return redirect('detalle_contacto', contacto_id=contacto.id)


@login_required
def convertir_contacto(request, contacto_id):
    """Convierte un prospecto en Cliente o Proveedor real."""
    contacto = get_object_or_404(Contacto, id=contacto_id)
    target = request.GET.get('target') # 'cliente' o 'proveedor'

    if target == 'proveedor' and not contacto.proveedor:
        nuevo_prov = Proveedor.objects.create(
            nombre=contacto.nombre,
            pais=contacto.pais or 'España',
            email=contacto.email,
            telefono=contacto.telefono or contacto.movil,
            direccion=contacto.ubicacion,
            tipo='COMERCIO_MATERIALES' # Por defecto
        )
        contacto.proveedor = nuevo_prov
        contacto.tipo = 'PROVEEDOR' if contacto.tipo == 'PROSPECTO' else 'AMBOS'
        contacto.save()
        messages.success(request, f'Creado Proveedor: {nuevo_prov.nombre}')
        
    elif target == 'cliente' and not contacto.cliente:
        nuevo_cli = Cliente.objects.create(
            nombre=contacto.nombre,
            pais=contacto.pais or 'España',
            email=contacto.email,
            telefono=contacto.telefono or contacto.movil,
            direccion=contacto.ubicacion
        )
        contacto.cliente = nuevo_cli
        contacto.tipo = 'CLIENTE' if contacto.tipo == 'PROSPECTO' else 'AMBOS'
        contacto.save()
        messages.success(request, f'Creado Cliente: {nuevo_cli.nombre}')

    return redirect('detalle_contacto', contacto_id=contacto.id)

@login_required
def matriz_materiales(request):
    # Filtro por material (opcional)
    material_filtro = request.GET.get('material', '')
    accion_filtro = request.GET.get('accion', '')

    # Obtenemos todos los intereses
    intereses = InteresMaterial.objects.select_related('contacto').all()

    if material_filtro:
        intereses = intereses.filter(tipo_material__iexact=material_filtro)
    if accion_filtro:
        intereses = intereses.filter(accion=accion_filtro)

    # Agrupamos por contacto para pintar la tabla
    contactos_dict = {}
    for i in intereses:
        if i.contacto not in contactos_dict:
            contactos_dict[i.contacto] = []
        contactos_dict[i.contacto].append(i)

    # Obtener la lista única de materiales para las cabeceras
    materiales_unicos = InteresMaterial.objects.values_list('tipo_material', flat=True).distinct().order_by('tipo_material')
    materiales_unicos = [m for m in materiales_unicos if m]

    context = {
        'contactos_dict': contactos_dict.items(),
        'materiales_unicos': materiales_unicos,
        'material_filtro': material_filtro,
        'accion_filtro': accion_filtro,
    }
    return render(request, 'crm/matriz.html', context)
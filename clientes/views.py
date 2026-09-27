from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Cliente
from django.db.models import Q


@login_required
def lista_clientes(request):
    clientes = Cliente.objects.all().order_by('nombre')

    # Buscador
    busqueda = request.GET.get('q', '')
    if busqueda:
        clientes = clientes.filter(
            Q(nombre__icontains=busqueda) |
            Q(email__icontains=busqueda) |
            Q(telefono__icontains=busqueda)
        )

    # Filtro por tipo
    tipo = request.GET.get('tipo', '')
    if tipo:
        clientes = clientes.filter(tipo=tipo)

    # Filtro por estado
    estado = request.GET.get('estado', '')
    if estado:
        clientes = clientes.filter(estado=estado)

    # Filtro por país (opcional)
    pais = request.GET.get('pais', '')
    if pais:
        clientes = clientes.filter(pais__icontains=pais)

    context = {
        'clientes': clientes,
        'total': clientes.count(),
        'tipos': Cliente.TIPO_CLIENTE,
        'estados': Cliente.ESTADO_CHOICES,
        'busqueda': busqueda,
        'tipo_filtro': tipo,
        'estado_filtro': estado,
        'pais_filtro': pais,
    }
    return render(request, 'clientes/lista.html', context)


@login_required
def confirmar_eliminar_cliente(request, cliente_id):
    """Muestra página de confirmación antes de borrar"""
    cliente = get_object_or_404(Cliente, id=cliente_id)
    context = {
        'cliente': cliente,
    }
    return render(request, 'clientes/confirmar_eliminar.html', context)


@login_required
def eliminar_cliente(request, cliente_id):
    """Elimina el cliente definitivamente"""
    cliente = get_object_or_404(Cliente, id=cliente_id)
    
    if request.method == 'POST':
        nombre = cliente.nombre
        try:
            cliente.delete()
            messages.success(request, f'✅ Cliente "{nombre}" eliminado correctamente')
        except Exception as e:
            messages.error(request, f'❌ No se puede eliminar: tiene pedidos o facturas asociadas')
        return redirect('lista_clientes')
    
    return redirect('confirmar_eliminar_cliente', cliente_id=cliente_id)
@login_required
def nuevo_cliente(request):
    """Formulario para crear un nuevo cliente"""
    if request.method == 'POST':
        try:
            cliente = Cliente.objects.create(
                nombre=request.POST.get('nombre'),
                pais=request.POST.get('pais', 'España'),
                email=request.POST.get('email', ''),
                telefono=request.POST.get('telefono', ''),
                tipo=request.POST.get('tipo', 'RECICLAJE'),
                estado=request.POST.get('estado', 'ACTIVO'),
                notas=request.POST.get('notas', ''),
            )
            messages.success(request, f'✅ Cliente "{cliente.nombre}" creado correctamente')
            return redirect('lista_clientes')
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')
    
    return render(request, 'clientes/nuevo_cliente.html')


@login_required
def editar_cliente(request, cliente_id):
    """Formulario para editar un cliente existente"""
    cliente = get_object_or_404(Cliente, id=cliente_id)
    
    if request.method == 'POST':
        cliente.nombre = request.POST.get('nombre')
        cliente.pais = request.POST.get('pais', 'España')
        cliente.email = request.POST.get('email', '')
        cliente.telefono = request.POST.get('telefono', '')
        cliente.tipo = request.POST.get('tipo', 'RECICLAJE')
        cliente.estado = request.POST.get('estado', 'ACTIVO')
        cliente.notas = request.POST.get('notas', '')
        cliente.save()
        
        messages.success(request, f'✅ Cliente "{cliente.nombre}" actualizado')
        return redirect('lista_clientes')
    
    context = {'cliente': cliente}
    return render(request, 'clientes/editar_cliente.html', context)
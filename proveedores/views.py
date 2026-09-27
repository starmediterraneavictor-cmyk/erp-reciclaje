from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError, Q

from .models import Proveedor


@login_required
def lista_proveedores(request):
    proveedores = Proveedor.objects.all().order_by('nombre')

    # Buscador
    busqueda = request.GET.get('q', '')
    if busqueda:
        proveedores = proveedores.filter(
            Q(nombre__icontains=busqueda) |
            Q(nif__icontains=busqueda) |
            Q(email__icontains=busqueda)
        )

    # Filtro por tipo
    tipo = request.GET.get('tipo', '')
    if tipo:
        proveedores = proveedores.filter(tipo=tipo)

    # Filtro por estado
    estado = request.GET.get('estado', '')
    if estado:
        proveedores = proveedores.filter(estado=estado)

    context = {
        'proveedores': proveedores,
        'total': proveedores.count(),
        'tipos': Proveedor.TIPO_PROVEEDOR,
        'estados': Proveedor.ESTADO_CHOICES,
        'busqueda': busqueda,
        'tipo_filtro': tipo,
        'estado_filtro': estado,
    }
    return render(request, 'proveedores/lista.html', context)


@login_required
def nuevo_proveedor(request):
    if request.method == 'POST':
        try:
            proveedor = Proveedor.objects.create(
                nombre=request.POST.get('nombre'),
                nif=request.POST.get('nif', ''),
                pais=request.POST.get('pais', 'España'),
                email=request.POST.get('email', ''),
                telefono=request.POST.get('telefono', ''),
                direccion=request.POST.get('direccion', ''),
                tipo=request.POST.get('tipo', 'MATERIAL'),
                estado=request.POST.get('estado', 'ACTIVO'),
                iban=request.POST.get('iban', ''),
                notas=request.POST.get('notas', ''),
            )
            messages.success(request, f'✅ Proveedor "{proveedor.nombre}" creado correctamente')
            return redirect('lista_proveedores')
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')

    context = {
        'tipos': Proveedor.TIPO_PROVEEDOR,
        'estados': Proveedor.ESTADO_CHOICES,
    }
    return render(request, 'proveedores/nuevo_proveedor.html', context)


@login_required
def editar_proveedor(request, proveedor_id):
    proveedor = get_object_or_404(Proveedor, id=proveedor_id)

    if request.method == 'POST':
        proveedor.nombre = request.POST.get('nombre')
        proveedor.nif = request.POST.get('nif', '')
        proveedor.pais = request.POST.get('pais', 'España')
        proveedor.email = request.POST.get('email', '')
        proveedor.telefono = request.POST.get('telefono', '')
        proveedor.direccion = request.POST.get('direccion', '')
        proveedor.tipo = request.POST.get('tipo', 'MATERIAL')
        proveedor.estado = request.POST.get('estado', 'ACTIVO')
        proveedor.iban = request.POST.get('iban', '')
        proveedor.notas = request.POST.get('notas', '')
        proveedor.save()

        messages.success(request, f'✅ Proveedor "{proveedor.nombre}" actualizado')
        return redirect('lista_proveedores')

    context = {
        'proveedor': proveedor,
        'tipos': Proveedor.TIPO_PROVEEDOR,
        'estados': Proveedor.ESTADO_CHOICES,
    }
    return render(request, 'proveedores/editar_proveedor.html', context)


@login_required
def confirmar_eliminar_proveedor(request, proveedor_id):
    proveedor = get_object_or_404(Proveedor, id=proveedor_id)
    context = {'proveedor': proveedor}
    return render(request, 'proveedores/confirmar_eliminar.html', context)


@login_required
def eliminar_proveedor(request, proveedor_id):
    proveedor = get_object_or_404(Proveedor, id=proveedor_id)

    if request.method == 'POST':
        nombre = proveedor.nombre
        try:
            proveedor.delete()
            messages.success(request, f'✅ Proveedor "{nombre}" eliminado correctamente')
        except ProtectedError:
            messages.error(request, f'❌ No se puede eliminar "{nombre}": tiene facturas asociadas')
        except Exception as e:
            messages.error(request, f'❌ Error inesperado: {str(e)}')
        return redirect('lista_proveedores')

    return redirect('confirmar_eliminar_proveedor', proveedor_id=proveedor_id)
from django.contrib import admin
from .models import Proveedor


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'nif', 'tipo', 'estado', 'pais')
    list_filter = ('tipo', 'estado', 'pais')
    search_fields = ('nombre', 'nif', 'email', 'codigo_nima', 'numero_gestor')
    fieldsets = (
        ('Datos básicos', {
            'fields': ('nombre', 'nif', 'pais', 'email', 'telefono', 'direccion')
        }),
        ('Datos de residuos', {                                  # ← NUEVO
            'fields': ('codigo_nima', 'numero_gestor')
        }),
        ('Clasificación', {
            'fields': ('tipo', 'estado', 'iban', 'notas')
        }),
    )
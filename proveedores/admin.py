from django.contrib import admin
from .models import Proveedor


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'nif', 'tipo', 'estado', 'pais')
    list_filter = ('tipo', 'estado', 'pais')
    search_fields = ('nombre', 'nif', 'email')
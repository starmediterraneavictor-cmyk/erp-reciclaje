from django.contrib import admin
from .models import Cliente


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'pais', 'tipo', 'estado')
    list_filter = ('tipo', 'estado', 'pais')
    search_fields = ('nombre', 'email', 'codigo_nima', 'numero_gestor')
    fieldsets = (
        ('Datos básicos', {
            'fields': ('nombre', 'pais', 'email', 'telefono')
        }),
        ('Datos de residuos', {                                  # ← NUEVO
            'fields': ('codigo_nima', 'numero_gestor')
        }),
        ('Clasificación', {
            'fields': ('tipo', 'estado', 'notas')
        }),
    )
from django.contrib import admin
from .models import DatosEmpresa


@admin.register(DatosEmpresa)
class DatosEmpresaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'nif', 'ciudad')
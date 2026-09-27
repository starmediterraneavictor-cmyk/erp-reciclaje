from django.contrib import admin
from .models import TipoMaterial, SubgrupoMaterial, Material, Inventario


@admin.register(TipoMaterial)
class TipoMaterialAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre',)


@admin.register(SubgrupoMaterial)
class SubgrupoMaterialAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'descripcion')
    list_filter = ('tipo',)
    search_fields = ('nombre',)


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'tipo', 'subgrupo', 'precio_compra', 'precio_venta')
    list_filter = ('tipo', 'subgrupo')
    search_fields = ('codigo', 'nombre')


@admin.register(Inventario)
class InventarioAdmin(admin.ModelAdmin):
    list_display = ('material', 'cantidad', 'fecha_actualizacion')
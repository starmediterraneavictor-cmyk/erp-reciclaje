from django.contrib import admin
from .models import Contacto, SectorContacto, EstadoContacto, InteresMaterial, Interaccion


class InteresMaterialInline(admin.TabularInline):
    model = InteresMaterial
    extra = 1


class InteraccionInline(admin.TabularInline):
    model = Interaccion
    extra = 0
    readonly_fields = ('fecha_creacion',)


@admin.register(Contacto)
class ContactoAdmin(admin.ModelAdmin):
    list_display = (
        'nombre', 'tipo', 'sector', 'estado', 'pais',
        'ultima_fecha_contacto', 'alerta_visual'
    )
    list_filter = ('tipo', 'sector', 'estado', 'pais')
    search_fields = ('nombre', 'email', 'telefono', 'movil', 'notas')
    inlines = [InteresMaterialInline, InteraccionInline]
    readonly_fields = ('fecha_alta', 'fecha_modificacion')

    fieldsets = (
        ('Vinculación', {
            'fields': ('cliente', 'proveedor', 'tipo')
        }),
        ('Datos básicos', {
            'fields': ('nombre', 'pais', 'ubicacion', 'provincia',
                       'localidad', 'web')
        }),
        ('Contacto', {
            'fields': ('persona_contacto', 'email', 'telefono', 'movil')
        }),
        ('CRM', {
            'fields': ('sector', 'estado', 'actividad',
                       'codigo_gestor', 'notas')
        }),
        ('Seguimiento', {
            'fields': ('ultima_fecha_contacto', 'dias_alerta')
        }),
        ('Auditoría', {
            'fields': ('fecha_alta', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )

    def alerta_visual(self, obj):
        nivel = obj.nivel_alerta
        if nivel == 'urgente':
            return '🔴 TOCA'
        if nivel == 'pronto':
            return '🟠 Pronto'
        if nivel == 'ok':
            return '🟢 OK'
        return '—'
    alerta_visual.short_description = 'Alerta'


@admin.register(SectorContacto)
class SectorContactoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'activo')
    list_filter = ('tipo', 'activo')


@admin.register(EstadoContacto)
class EstadoContactoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'orden', 'color', 'activo')
    list_editable = ('orden', 'color', 'activo')


@admin.register(Interaccion)
class InteraccionAdmin(admin.ModelAdmin):
    list_display = ('contacto', 'fecha', 'tipo', 'resumen_corto', 'autor')
    list_filter = ('tipo', 'fecha')
    search_fields = ('contacto__nombre', 'resumen')

    def resumen_corto(self, obj):
        return obj.resumen[:60] + ('...' if len(obj.resumen) > 60 else '')
    resumen_corto.short_description = 'Resumen'
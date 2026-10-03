from django.db import models


class Cliente(models.Model):
    TIPO_CLIENTE = [
        ('RECICLAJE', 'Rreciclaje'),
        ('SERVICIOS', 'Servicios (parking, alquiler...)'),
        
    ]
    
    ESTADO_CHOICES = [
        ('ACTIVO', 'Activo'),
        ('SEGUIMIENTO', 'En seguimiento'),
        ('EN_PAUSA', 'En pausa'),
        ('DESCARTADO', 'Descartado'),
    ]
    
    nombre = models.CharField(max_length=200)
    nif = models.CharField(max_length=20, blank=True)
    pais = models.CharField(max_length=100, default='España')
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=50, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CLIENTE, default='RECICLAJE')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='ACTIVO')
    notas = models.TextField(blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    codigo_nima = models.CharField(max_length=50, blank=True,verbose_name="Código NIMA")
    numero_gestor = models.CharField(max_length=50, blank=True,verbose_name="Nº Gestor de Residuos")
    
    def __str__(self):
        return self.nombre
    
    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['nombre']
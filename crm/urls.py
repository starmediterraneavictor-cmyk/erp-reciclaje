from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_contactos, name='lista_contactos'),
    path('<int:contacto_id>/', views.detalle_contacto, name='detalle_contacto'),
    path('nuevo/', views.editar_contacto, name='nuevo_contacto'),
    path('<int:contacto_id>/editar/', views.editar_contacto, name='editar_contacto'),
    path('<int:contacto_id>/interaccion/', views.nueva_interaccion, name='nueva_interaccion'),
    path('<int:contacto_id>/convertir/', views.convertir_contacto, name='convertir_contacto'),
]
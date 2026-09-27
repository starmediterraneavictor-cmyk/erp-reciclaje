from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_analisis, name='dashboard_analisis'),
]
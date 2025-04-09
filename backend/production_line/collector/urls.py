from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('map/', views.machine_map, name='machine_map'),
    path('machines/warnings/', views.get_machines_with_warnings, name='api_machines_warnings'),
    path('telemetry/receive/', views.receive_telemetry, name='api_receive_telemetry'),
]

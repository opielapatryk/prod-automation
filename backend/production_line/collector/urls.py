from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('map/', views.machine_map, name='machine_map'),
    path('routes/', views.routes, name='routes'),
    path('machines/', views.get_machines, name='api_get_machines'),
    path('machines/warnings/', views.get_machines_with_warnings, name='api_machines_warnings'),
    path('telemetry/receive/', views.receive_telemetry, name='api_receive_telemetry'),
    path('routes/<int:route_id>/', views.route_details, name='api_route_details'),   
    path('routes/optimize/', views.optimize_route, name='api_optimize_route'),   
    path('routes/create/', views.create_route, name='api_create_route'),
    path('routes/list/', views.routes_list, name='api_routes_list'),
]
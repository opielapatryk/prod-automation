from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from . import views

urlpatterns = [
    # Regular views
    path('dashboard/', views.dashboard, name='dashboard'),
    path('map/', views.machine_map, name='machine_map'),
    path('routes/', views.routes, name='routes'),
    
    # Apply csrf_exempt to ALL API endpoints
    path('machines/', csrf_exempt(views.get_machines), name='api_get_machines'),
    path('machines/warnings/', csrf_exempt(views.get_machines_with_warnings), name='api_machines_warnings'),
    path('telemetry/receive/', csrf_exempt(views.receive_telemetry), name='api_receive_telemetry'),
    path('routes/<int:route_id>/', csrf_exempt(views.route_details), name='api_route_details'),
    path('routes/optimize/', csrf_exempt(views.optimize_route), name='api_optimize_route'),
    path('routes/create/', csrf_exempt(views.create_route), name='api_create_route'),
    path('routes/list/', csrf_exempt(views.routes_list), name='api_routes_list'),
]
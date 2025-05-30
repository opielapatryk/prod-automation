from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
import json
from datetime import datetime, date, timedelta
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from django.contrib.auth.models import User

from .models import Machine, Location, Telemetry, Warning, WarningRule, ServiceRecord, Route, RouteStop
from .serializers import (MachineSerializer, LocationSerializer, TelemetrySerializer, 
                         WarningSerializer, TelemetryInputSerializer)

def dashboard(request):
    machines = Machine.objects.all()
    active_warnings = Warning.objects.filter(resolved_at=None)
    
    machine_warnings_count = {}
    for machine in machines:
        machine_warnings_count[machine.id] = machine.warnings.filter(resolved_at=None).count()
    
    context = {
        'machines': machines,
        'active_warnings': active_warnings,
        'machine_warnings_count': machine_warnings_count,
        'machines_with_warnings_count': Machine.objects.filter(status='warning').count(),
        'machines_critical_count': Machine.objects.filter(status='critical').count(),
    }
    
    return render(request, 'collector/dashboard.html', context)

def machine_map(request):
    machines = Machine.objects.select_related('location').all()
    
    context = {
        'machines': machines,
    }
    
    return render(request, 'collector/machine_map.html', context)

def routes(request):
    routes = Route.objects.all().order_by('date')
    
    technicians = User.objects.exclude(is_staff=True, is_superuser=True)
    if not technicians:
        technicians = User.objects.all()
    
    technician_id = request.GET.get('technician')
    if technician_id:
        routes = routes.filter(technician_id=technician_id)
    
    date_filter = request.GET.get('date')
    if date_filter:
        routes = routes.filter(date=date_filter)
    
    context = {
        'routes': routes,
        'technicians': technicians,
        'headquarters': "Warsaw, Poland (Basecamp)",
    }
    
    return render(request, 'collector/routes.html', context)

@swagger_auto_schema(
    method='post',
    operation_description="Optimize a route based on machine locations.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['machine_ids'],
        properties={
            'machine_ids': openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_INTEGER),
                description="List of machine IDs to include in the route"
            )
        }
    ),
    responses={
        200: openapi.Response(
            description="Successful optimization",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'headquarters': openapi.Schema(type=openapi.TYPE_OBJECT),
                    'is_delegation': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'total_distance': openapi.Schema(type=openapi.TYPE_NUMBER),
                    'total_duration': openapi.Schema(type=openapi.TYPE_NUMBER),
                    'formatted_duration': openapi.Schema(type=openapi.TYPE_STRING),
                    'optimized_machines': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT))
                }
            )
        ),
        400: "Bad request - missing machine IDs or invalid request",
        404: "Machine not found"
    }
)
@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def optimize_route(request):
    from math import radians, cos, sin, asin, sqrt
    import itertools
    
    machine_ids = request.data.get('machine_ids', [])
    
    if not machine_ids:
        return Response({'error': 'No machines specified'}, status=status.HTTP_400_BAD_REQUEST)
    
    machines = []
    for machine_id in machine_ids:
        try:
            machine = Machine.objects.select_related('location').get(id=machine_id)
            if not machine.location:
                return Response({'error': f'Machine {machine.name} has no location data'}, status=status.HTTP_400_BAD_REQUEST)
            
            machines.append(machine)
        except Machine.DoesNotExist:
            return Response({'error': f'Machine with ID {machine_id} not found'}, status=status.HTTP_404_NOT_FOUND)
    
    def calculate_distance(lat1, lon1, lat2, lon2):
        lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371  # Radius of earth in kilometers
        return c * r
    
    hq_lat, hq_lng = 52.2297, 21.0122
    
    num_locations = len(machines) + 1
    distance_matrix = [[0 for _ in range(num_locations)] for _ in range(num_locations)]
    
    for i, machine in enumerate(machines, 1):
        machine_lat = float(machine.location.latitude)
        machine_lng = float(machine.location.longitude)
        distance = calculate_distance(hq_lat, hq_lng, machine_lat, machine_lng)
        distance_matrix[0][i] = distance_matrix[i][0] = distance
    
    for i in range(1, num_locations):
        for j in range(i+1, num_locations):
            machine_i = machines[i-1]
            machine_j = machines[j-1]
            distance = calculate_distance(
                float(machine_i.location.latitude),
                float(machine_i.location.longitude),
                float(machine_j.location.latitude),
                float(machine_j.location.longitude)
            )
            distance_matrix[i][j] = distance_matrix[j][i] = distance
    
    best_distance = float('inf')
    best_order = None
    
    if len(machines) <= 8:
        all_permutations = list(itertools.permutations(range(1, num_locations)))
        
        for perm in all_permutations:
            route = (0,) + perm + (0,)
            total_distance = sum(distance_matrix[route[i]][route[i+1]] for i in range(len(route)-1))
            
            if total_distance < best_distance:
                best_distance = total_distance
                best_order = perm
    else:
        current_location = 0
        unvisited = set(range(1, num_locations))
        route = [current_location]
        total_distance = 0
        
        while unvisited:
            next_location = min(unvisited, key=lambda loc: distance_matrix[current_location][loc])
            total_distance += distance_matrix[current_location][next_location]
            
            route.append(next_location)
            unvisited.remove(next_location)
            current_location = next_location
        
        route.append(0)
        total_distance += distance_matrix[current_location][0]
        
        best_distance = total_distance
        best_order = tuple(route[1:-1])
    
    optimized_machines = []
    total_distance = 0
    avg_speeds = {
        'city': 30,
        'suburban': 70,
        'highway': 100
    }
    
    def estimate_travel_speed(distance):
        if distance < 5:
            return avg_speeds['city']
        elif distance < 30:
            return (avg_speeds['city'] * 0.2 + avg_speeds['suburban'] * 0.8)
        else:
            return (avg_speeds['highway'] * 0.7 + avg_speeds['suburban'] * 0.2 + avg_speeds['city'] * 0.1)
    
    previous_lat, previous_lng = hq_lat, hq_lng
    previous_location_name = "Headquarters"
    total_duration = 0
    
    for idx in best_order:
        machine = machines[idx-1]
        machine_lat = float(machine.location.latitude)
        machine_lng = float(machine.location.longitude)
        
        distance = calculate_distance(previous_lat, previous_lng, machine_lat, machine_lng)
        speed = estimate_travel_speed(distance)
        travel_time = distance / speed
        
        total_distance += distance
        total_duration += travel_time
        
        service_time = 1.0
        total_duration += service_time
        
        optimized_machines.append({
            'id': machine.id,
            'name': machine.name,
            'lat': machine_lat,
            'lng': machine_lng,
            'address': machine.location.address if machine.location.address else "Unknown",
            'travel_distance_from_previous': round(distance, 1),
            'travel_time_from_previous': round(travel_time, 1),
            'previous_location': previous_location_name,
            'service_time': service_time,
            'speed': round(speed, 1)
        })
        
        previous_lat, previous_lng = machine_lat, machine_lng
        previous_location_name = machine.name
    
    return_distance = calculate_distance(previous_lat, previous_lng, hq_lat, hq_lng)
    speed = estimate_travel_speed(return_distance)
    return_time = return_distance / speed
    
    total_distance += return_distance
    total_duration += return_time
    
    buffer_duration = total_duration * 0.15
    total_duration += buffer_duration
    
    hours = int(total_duration)
    minutes = int((total_duration - hours) * 60)
    
    result = {
        'headquarters': {
            'lat': hq_lat,
            'lng': hq_lng,
            'address': 'Warsaw, Poland (Basecamp)'
        },
        'is_delegation': total_duration > 8.0,
        'total_distance': round(total_distance, 1),
        'total_duration': round(total_duration, 2),
        'formatted_duration': f"{hours}h {minutes}min",
        'buffer_time': round(buffer_duration, 2),
        'optimized_machines': optimized_machines,
        'return_distance': round(return_distance, 1),
        'return_time': round(return_time, 1)
    }
    
    return Response(result)

@swagger_auto_schema(
    method='get',
    operation_description="Get detailed information about a specific route.",
    responses={
        200: openapi.Response(
            description="Route details", 
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'name': openapi.Schema(type=openapi.TYPE_STRING),
                    'technician': openapi.Schema(type=openapi.TYPE_OBJECT),
                    'date': openapi.Schema(type=openapi.TYPE_STRING, format='date'),
                    'status': openapi.Schema(type=openapi.TYPE_STRING),
                    'estimated_duration': openapi.Schema(type=openapi.TYPE_NUMBER),
                    'is_delegation': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'stops': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT))
                }
            )
        ),
        404: "Route not found"
    }
)
@csrf_exempt
@api_view(['GET'])
@permission_classes([AllowAny])
def route_details(request, route_id):
    try:
        route = Route.objects.get(id=route_id)
    except Route.DoesNotExist:
        return Response({'error': 'Route not found'}, status=status.HTTP_404_NOT_FOUND)
    
    stops = route.routestop_set.all().order_by('order')
    stops_data = []
    
    for stop in stops:
        machine = stop.machine
        warnings_count = machine.warnings.filter(resolved_at=None).count()
        
        stops_data.append({
            'order': stop.order,
            'machine_id': machine.id,
            'machine_name': machine.name,
            'status': machine.status,
            'model': machine.model,
            'address': machine.location.address if machine.location else None,
            'lat': float(machine.location.latitude) if machine.location else None,
            'lng': float(machine.location.longitude) if machine.location else None,
            'service_time': stop.estimated_service_time,
            'completed': stop.completed,
            'warnings_count': warnings_count
        })
    
    route_data = {
        'id': route.id,
        'name': route.name,
        'technician': {
            'id': route.technician.id,
            'name': f"{route.technician.first_name} {route.technician.last_name}".strip() or route.technician.username
        },
        'date': route.date,
        'status': route.status,
        'estimated_duration': route.estimated_duration,
        'is_delegation': route.is_delegation,
        'start_location': route.start_location,
        'stops': stops_data
    }
    
    return Response(route_data)

@swagger_auto_schema(
    method='get',
    operation_description="Get machines with active warnings",
    responses={
        200: openapi.Response(
            description="List of machines with warnings",
            schema=openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'name': openapi.Schema(type=openapi.TYPE_STRING),
                        'status': openapi.Schema(type=openapi.TYPE_STRING),
                        'serial_number': openapi.Schema(type=openapi.TYPE_STRING),
                        'warnings_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'latest_warning': openapi.Schema(type=openapi.TYPE_STRING, nullable=True),
                        'location': openapi.Schema(type=openapi.TYPE_OBJECT, nullable=True)
                    }
                )
            )
        )
    }
)
@csrf_exempt
@api_view(['GET'])
@permission_classes([AllowAny])
def get_machines_with_warnings(request):
    machines = Machine.objects.filter(status__in=['warning', 'critical'])
    data = []
    
    for machine in machines:
        active_warnings = machine.warnings.filter(resolved_at=None)
        data.append({
            'id': machine.id,
            'name': machine.name,
            'status': machine.status,
            'serial_number': machine.serial_number,
            'warnings_count': active_warnings.count(),
            'latest_warning': active_warnings.first().description if active_warnings.exists() else None,
            'location': {
                'lat': float(machine.location.latitude) if machine.location else None,
                'lng': float(machine.location.longitude) if machine.location else None,
                'address': machine.location.address if machine.location else None,
            } if machine.location else None
        })
    
    return Response(data)

@swagger_auto_schema(
    method='post',
    request_body=TelemetryInputSerializer,
    operation_description="Receive telemetry data from machines",
    responses={
        201: openapi.Response(
            description="Telemetry data saved successfully",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'telemetry_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'warnings_triggered': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_INTEGER))
                }
            )
        ),
        400: "Invalid input data",
        404: "Machine not found"
    }
)
@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def receive_telemetry(request):
    try:
        data = request.data
        serial_number = data.get('serial_number')
        parameter = data.get('parameter')
        value = data.get('value')
        
        try:
            machine = Machine.objects.get(serial_number=serial_number)
        except Machine.DoesNotExist:
            return Response({'error': f'Machine with serial {serial_number} not found'}, status=status.HTTP_404_NOT_FOUND)
        
        telemetry = Telemetry.objects.create(
            machine=machine,
            parameter=parameter,
            value=value
        )
        
        rules = WarningRule.objects.filter(parameter=parameter)
        triggered_warnings = []
        
        for rule in rules:
            is_triggered = False
            
            if rule.comparison_operator == '>':
                is_triggered = value > rule.threshold_value
            elif rule.comparison_operator == '>=':
                is_triggered = value >= rule.threshold_value
            elif rule.comparison_operator == '<':
                is_triggered = value < rule.threshold_value
            elif rule.comparison_operator == '<=':
                is_triggered = value <= rule.threshold_value
            elif rule.comparison_operator == '==':
                is_triggered = value == rule.threshold_value
            elif rule.comparison_operator == '!=':
                is_triggered = value != rule.threshold_value
                
            if is_triggered:
                warning = Warning.objects.create(
                    machine=machine,
                    rule=rule,
                    telemetry=telemetry,
                    description=f"Warning: {parameter} {rule.comparison_operator} {rule.threshold_value} (Actual: {value})"
                )
                triggered_warnings.append(warning.id)
                
                if rule.severity == 'critical' and machine.status != 'critical':
                    machine.status = 'critical'
                elif rule.severity in ['high', 'medium'] and machine.status not in ['critical']:
                    machine.status = 'warning'
                
                machine.save()
        
        return Response({
            'telemetry_id': telemetry.id,
            'warnings_triggered': triggered_warnings
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='get',
    operation_description="Get a filtered list of routes",
    manual_parameters=[
        openapi.Parameter('technician', openapi.IN_QUERY, description="Filter by technician ID", type=openapi.TYPE_INTEGER),
        openapi.Parameter('date', openapi.IN_QUERY, description="Filter by date (YYYY-MM-DD)", type=openapi.TYPE_STRING)
    ],
    responses={
        200: openapi.Response(
            description="List of routes",
            schema=openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'name': openapi.Schema(type=openapi.TYPE_STRING),
                        'date': openapi.Schema(type=openapi.TYPE_STRING, format='date'),
                        'technician': openapi.Schema(type=openapi.TYPE_OBJECT),
                        'status': openapi.Schema(type=openapi.TYPE_STRING),
                        'estimated_duration': openapi.Schema(type=openapi.TYPE_NUMBER),
                        'is_delegation': openapi.Schema(type=openapi.TYPE_BOOLEAN)
                    }
                )
            )
        )
    }
)
@csrf_exempt
@api_view(['GET'])
@permission_classes([AllowAny])
def routes_list(request):
    routes = Route.objects.select_related('technician').all().order_by('date')
    
    technician_id = request.GET.get('technician')
    if technician_id:
        routes = routes.filter(technician_id=technician_id)
    
    date_filter = request.GET.get('date')
    if date_filter:
        routes = routes.filter(date=date_filter)
    
    data = []
    for route in routes:
        data.append({
            'id': route.id,
            'name': route.name,
            'date': route.date,
            'technician': {
                'id': route.technician.id,
                'username': route.technician.username,
                'first_name': route.technician.first_name,
                'last_name': route.technician.last_name,
            },
            'status': route.status,
            'estimated_duration': route.estimated_duration,
            'is_delegation': route.is_delegation,
        })
    
    return Response(data)

@swagger_auto_schema(
    method='get',
    operation_description="Get all machines with their locations and status information",
    responses={
        200: openapi.Response(
            description="List of machines",
            schema=openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'name': openapi.Schema(type=openapi.TYPE_STRING),
                        'status': openapi.Schema(type=openapi.TYPE_STRING),
                        'serial_number': openapi.Schema(type=openapi.TYPE_STRING),
                        'model': openapi.Schema(type=openapi.TYPE_STRING),
                        'manufacturer': openapi.Schema(type=openapi.TYPE_STRING),
                        'active_warnings_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'location': openapi.Schema(type=openapi.TYPE_OBJECT, nullable=True),
                    }
                )
            )
        )
    }
)
@csrf_exempt
@api_view(['GET'])
@permission_classes([AllowAny])
def get_machines(request):
    machines = Machine.objects.select_related('location').all()
    data = []
    
    for machine in machines:
        active_warnings_count = machine.warnings.filter(resolved_at=None).count()
        data.append({
            'id': machine.id,
            'name': machine.name,
            'status': machine.status,
            'serial_number': machine.serial_number,
            'model': machine.model,
            'manufacturer': machine.manufacturer,
            'active_warnings_count': active_warnings_count,
            'location': {
                'lat': float(machine.location.latitude) if machine.location else None,
                'lng': float(machine.location.longitude) if machine.location else None,
                'address': machine.location.address if machine.location else None,
            } if machine.location else None
        })
    
    return Response(data)

@swagger_auto_schema(
    method='post',
    operation_description="Create a new service route from optimized data",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['name', 'date', 'technician_id', 'machines', 'estimated_duration'],
        properties={
            'name': openapi.Schema(type=openapi.TYPE_STRING, description="Route name"),
            'date': openapi.Schema(type=openapi.TYPE_STRING, format='date', description="Route date"),
            'technician_id': openapi.Schema(type=openapi.TYPE_INTEGER, description="Technician ID"),
            'estimated_duration': openapi.Schema(type=openapi.TYPE_NUMBER, description="Estimated duration in hours"),
            'start_location': openapi.Schema(type=openapi.TYPE_STRING, description="Starting location"),
            'machines': openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'machine_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'order': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'estimated_service_time': openapi.Schema(type=openapi.TYPE_NUMBER)
                    }
                )
            )
        }
    ),
    responses={
        201: openapi.Response(
            description="Route created successfully",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'name': openapi.Schema(type=openapi.TYPE_STRING),
                    'date': openapi.Schema(type=openapi.TYPE_STRING, format='date'),
                    'technician': openapi.Schema(type=openapi.TYPE_OBJECT),
                    'estimated_duration': openapi.Schema(type=openapi.TYPE_NUMBER),
                    'is_delegation': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'status': openapi.Schema(type=openapi.TYPE_STRING)
                }
            )
        ),
        400: "Bad request - missing required fields or invalid data",
        404: "Technician not found"
    }
)
@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def create_route(request):
    try:
        data = request.data
        
        required_fields = ['name', 'date', 'technician_id', 'machines', 'estimated_duration']
        for field in required_fields:
            if field not in data:
                return Response({'error': f'Missing required field: {field}'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            technician = User.objects.get(pk=data['technician_id'])
        except User.DoesNotExist:
            return Response({'error': 'Technician not found'}, status=status.HTTP_404_NOT_FOUND)
        
        route = Route.objects.create(
            name=data['name'],
            technician=technician,
            date=data['date'],
            estimated_duration=data['estimated_duration'],
            start_location=data.get('start_location', 'Warsaw, Poland'),
            status='planned',
            notes=data.get('notes', '')
        )
        
        for stop_data in data['machines']:
            try:
                machine = Machine.objects.get(pk=stop_data['machine_id'])
                RouteStop.objects.create(
                    route=route,
                    machine=machine,
                    order=stop_data['order'],
                    estimated_service_time=stop_data.get('estimated_service_time', 1.0),
                    completed=False
                )
            except Machine.DoesNotExist:
                continue
        
        return Response({
            'id': route.id,
            'name': route.name,
            'date': route.date,
            'technician': {
                'id': technician.id,
                'name': f"{technician.first_name} {technician.last_name}".strip() or technician.username
            },
            'estimated_duration': route.estimated_duration,
            'is_delegation': route.is_delegation,
            'status': route.status
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='post',
    operation_description="Refresh routes based on new warnings",
    responses={
        200: openapi.Response(
            description="Routes refresh summary",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'new_routes_created': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'routes_updated': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'message': openapi.Schema(type=openapi.TYPE_STRING),
                }
            )
        ),
        400: "Bad request"
    }
)
@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_routes(request):
    """
    Odświeża trasy na podstawie nowych ostrzeżeń. Sprawdza wszystkie 
    maszyny z ostrzeżeniami i dodaje je do istniejących tras lub tworzy nowe.
    """
    try:
        # Pobierz datę z parametru lub użyj następnego dnia roboczego
        target_date_str = request.data.get('date', None)
        if target_date_str:
            try:
                target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({'error': 'Niepoprawny format daty. Użyj YYYY-MM-DD'}, 
                               status=status.HTTP_400_BAD_REQUEST)
        else:
            # Użyj jutrzejszej daty
            today = date.today()
            target_date = today + timedelta(days=1)
            
            # Jeśli jutro weekend, przejdź do poniedziałku
            if target_date.weekday() == 5:  # Sobota
                target_date = target_date + timedelta(days=2)
            elif target_date.weekday() == 6:  # Niedziela
                target_date = target_date + timedelta(days=1)
        
        # 1. Pobierz maszyny z aktywnymi ostrzeżeniami
        machines_with_warnings = Machine.objects.filter(
            status__in=['warning', 'critical']
        ).exclude(location=None)
        
        # Sprawdzamy, czy istnieją trasy na docelowy dzień
        existing_routes = Route.objects.filter(
            date=target_date, 
            status='planned'
        )
        
        new_routes = 0
        updated_routes = 0
        
        # 2. Jeśli istnieją trasy na ten dzień, zaktualizuj je
        if existing_routes.exists():
            # Znajdź maszyny, które są już zaplanowane na istniejących trasach
            scheduled_machines = set()
            for route in existing_routes:
                route_stops = RouteStop.objects.filter(route=route)
                for stop in route_stops:
                    scheduled_machines.add(stop.machine.id)
            
            # Znajdź maszyny, które nie są jeszcze zaplanowane
            unscheduled_machines = [m for m in machines_with_warnings if m.id not in scheduled_machines]
            
            if unscheduled_machines:
                # Przypisz niezaplanowane maszyny do istniejących tras wg regionów
                for machine in unscheduled_machines:
                    assigned = False
                    nearest_route = None
                    min_distance = float('inf')
                    
                    # Znajdź najbliższą trasę dla maszyny
                    for route in existing_routes:
                        route_machines = Machine.objects.filter(routestop__route=route)
                        
                        if route_machines.exists():
                            # Oblicz średnią odległość od wszystkich maszyn na trasie
                            total_distance = 0
                            count = 0
                            
                            for rm in route_machines:
                                if rm.location and machine.location:
                                    # Oblicz odległość między maszynami (uproszczona metoda)
                                    lat1 = float(rm.location.latitude)
                                    lng1 = float(rm.location.longitude)
                                    lat2 = float(machine.location.latitude)
                                    lng2 = float(machine.location.longitude)
                                    
                                    # Proste obliczenie odległości (można zastąpić bardziej złożonym)
                                    dist = ((lat1-lat2)**2 + (lng1-lng2)**2)**0.5
                                    total_distance += dist
                                    count += 1
                            
                            if count > 0:
                                avg_distance = total_distance / count
                                if avg_distance < min_distance:
                                    min_distance = avg_distance
                                    nearest_route = route
                    
                    # Dodaj maszynę do najbliższej trasy
                    if nearest_route:
                        # Znajdź najwyższy numer przystanku i dodaj nowy
                        max_order = RouteStop.objects.filter(route=nearest_route).aggregate(
                            max_order=models.Max('order')
                        )['max_order'] or 0
                        
                        RouteStop.objects.create(
                            route=nearest_route,
                            machine=machine,
                            order=max_order + 1,
                            estimated_service_time=1.0,
                            completed=False
                        )
                        
                        # Przelicz szacowany czas trasy
                        nearest_route.calculate_estimated_duration()
                        updated_routes += 1
                        assigned = True
                    
                    # Jeśli nie udało się przypisać, utwórz nową trasę
                    if not assigned:
                        # Znajdź dostępnego serwisanta z najmniejszą liczbą zaplanowanych tras
                        technicians = User.objects.filter(is_active=True).exclude(
                            is_staff=True, is_superuser=True
                        )
                        
                        if not technicians:
                            technicians = User.objects.filter(username='admin')
                        
                        if technicians:
                            technician_routes = {}
                            for tech in technicians:
                                technician_routes[tech] = Route.objects.filter(
                                    technician=tech, date=target_date
                                ).count()
                            
                            # Wybierz serwisanta z najmniejszą liczbą tras
                            selected_technician = min(
                                technician_routes.items(), key=lambda x: x[1]
                            )[0]
                            
                            # Utwórz nową trasę
                            route = Route.objects.create(
                                name=f"Auto-{target_date}-{new_routes+1}",
                                technician=selected_technician,
                                date=target_date,
                                estimated_duration=2.0,  # Początkowa wartość
                                start_location='Warsaw, Poland',
                                status='planned',
                                notes=f"Trasa utworzona automatycznie podczas odświeżania"
                            )
                            
                            # Dodaj maszynę jako przystanek
                            RouteStop.objects.create(
                                route=route,
                                machine=machine,
                                order=1,
                                estimated_service_time=1.0,
                                completed=False
                            )
                            
                            route.calculate_estimated_duration()
                            new_routes += 1
            else:
                # Wszystkie maszyny z ostrzeżeniami są już zaplanowane
                pass
                
        # 3. Jeśli brak tras na ten dzień, utwórz nowe
        else:
            # Pogrupuj maszyny wg regionów
            machine_regions = {}
            
            for machine in machines_with_warnings:
                if not machine.location:
                    continue
                    
                # Prosta heurystyka grupująca wg współrzędnych
                lat = float(machine.location.latitude)
                lng = float(machine.location.longitude)
                
                # Regionalizacja (można zastąpić bardziej zaawansowaną)
                if lat > 54:
                    region = "Północ"
                elif lat > 52:
                    region = "Centrum"
                else:
                    region = "Południe"
                    
                if region not in machine_regions:
                    machine_regions[region] = []
                    
                machine_regions[region].append(machine)
            
            # Utwórz trasy dla każdego regionu
            technicians = User.objects.filter(is_active=True).exclude(
                is_staff=True, is_superuser=True
            )
            
            if not technicians:
                technicians = User.objects.filter(username='admin')
            
            if technicians:
                tech_index = 0
                
                for region, machines in machine_regions.items():
                    if not machines:
                        continue
                        
                    # Wybierz serwisanta rotacyjnie
                    technician = technicians[tech_index % len(technicians)]
                    tech_index += 1
                    
                    # Użyj API optymalizacji trasy
                    machine_ids = [machine.id for machine in machines]
                    
                    try:
                        # Bezpośrednie wywołanie funkcji to alternatywa dla zapytań HTTP
                        # w tym przypadku bezpieczniejsza, bo działamy w ramach tego samego procesu
                        from django.http import HttpRequest
                        request_data = {'machine_ids': machine_ids}
                        mock_request = HttpRequest()
                        mock_request._body = json.dumps(request_data).encode('utf-8')
                        mock_request.content_type = 'application/json'
                        
                        # Użyj istniejącej funkcji optymalizacji
                        route_data = optimize_route(mock_request).data
                        
                        if route_data:
                            # Utwórz trasę
                            route = Route.objects.create(
                                name=f"Auto-{region}-{target_date}",
                                technician=technician,
                                date=target_date,
                                estimated_duration=route_data.get('total_duration', 4.0),
                                start_location='Warsaw, Poland',
                                status='planned',
                                notes=f"Trasa utworzona automatycznie dla regionu {region}"
                            )
                            
                            # Dodaj przystanki w zoptymalizowanej kolejności
                            for idx, machine_data in enumerate(route_data.get('optimized_machines', []), 1):
                                try:
                                    machine = Machine.objects.get(pk=machine_data['id'])
                                    RouteStop.objects.create(
                                        route=route,
                                        machine=machine,
                                        order=idx,
                                        estimated_service_time=machine_data.get('service_time', 1.0),
                                        completed=False
                                    )
                                except Machine.DoesNotExist:
                                    continue
                            
                            new_routes += 1
                    except Exception as e:
                        print(f"Błąd podczas optymalizacji trasy: {str(e)}")
        
        # Zwróć podsumowanie
        return Response({
            'new_routes_created': new_routes,
            'routes_updated': updated_routes,
            'message': f'Zaktualizowano trasy na dzień {target_date}',
            'target_date': target_date.strftime('%Y-%m-%d')
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

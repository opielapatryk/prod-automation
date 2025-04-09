from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import json
from datetime import datetime
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from django.contrib.auth.models import User  # Make sure to import User model

from .models import Machine, Location, Telemetry, Warning, WarningRule, ServiceRecord, Route, RouteStop
from .serializers import (MachineSerializer, LocationSerializer, TelemetrySerializer, 
                         WarningSerializer, TelemetryInputSerializer)

def dashboard(request):
    """
    Dashboard view for service managers showing machine statuses and warnings.
    """
    machines = Machine.objects.all()
    active_warnings = Warning.objects.filter(resolved_at=None)
    
    # Create a dictionary to store active warnings count per machine
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
    """
    View to display machines on a map.
    """
    machines = Machine.objects.select_related('location').all()
    
    context = {
        'machines': machines,
    }
    
    return render(request, 'collector/machine_map.html', context)

def routes(request):
    """
    View to display and manage technician routes.
    """
    routes = Route.objects.all().order_by('date')
    technicians = User.objects.filter(routes__isnull=False).distinct()
    
    # Filter by technician if specified
    technician_id = request.GET.get('technician')
    if technician_id:
        routes = routes.filter(technician_id=technician_id)
    
    # Filter by date if specified
    date_filter = request.GET.get('date')
    if date_filter:
        routes = routes.filter(date=date_filter)
    
    context = {
        'routes': routes,
        'technicians': technicians,
        'headquarters': "Warsaw, Poland",
    }
    
    return render(request, 'collector/routes.html', context)

@api_view(['POST'])
def optimize_route(request):
    """
    API endpoint to optimize a route based on machine locations.
    Takes a list of machine IDs and calculates the shortest route.
    """
    from math import radians, cos, sin, asin, sqrt
    import itertools
    
    machine_ids = request.data.get('machine_ids', [])
    
    if not machine_ids:
        return Response({'error': 'No machines specified'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Get machine data with locations
    machines = []
    for machine_id in machine_ids:
        try:
            machine = Machine.objects.select_related('location').get(id=machine_id)
            if not machine.location:
                return Response({'error': f'Machine {machine.name} has no location data'}, status=status.HTTP_400_BAD_REQUEST)
            
            machines.append(machine)
        except Machine.DoesNotExist:
            return Response({'error': f'Machine with ID {machine_id} not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Helper function to calculate distance between coordinates (Haversine formula)
    def calculate_distance(lat1, lon1, lat2, lon2):
        """
        Calculate the great circle distance between two points 
        on the earth specified in decimal degrees
        """
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        
        # Haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371  # Radius of earth in kilometers
        return c * r
    
    # Warsaw coordinates (headquarters)
    hq_lat, hq_lng = 52.2297, 21.0122
    
    # For a small number of machines, we can try all permutations
    # For larger datasets, we'd need a more efficient algorithm like a heuristic
    if len(machines) <= 8:  # Beyond 8 machines, permutations become too computationally expensive
        # Create all possible routes
        all_permutations = list(itertools.permutations(range(len(machines))))
        best_distance = float('inf')
        best_order = None
        
        for perm in all_permutations:
            distance = 0
            
            # Distance from HQ to first machine
            first_machine = machines[perm[0]]
            distance += calculate_distance(
                hq_lat, hq_lng, 
                float(first_machine.location.latitude), 
                float(first_machine.location.longitude)
            )
            
            # Distances between consecutive machines
            for i in range(len(perm) - 1):
                current_machine = machines[perm[i]]
                next_machine = machines[perm[i + 1]]
                
                distance += calculate_distance(
                    float(current_machine.location.latitude), 
                    float(current_machine.location.longitude),
                    float(next_machine.location.latitude), 
                    float(next_machine.location.longitude)
                )
            
            # Distance from last machine back to HQ
            last_machine = machines[perm[-1]]
            distance += calculate_distance(
                float(last_machine.location.latitude), 
                float(last_machine.location.longitude),
                hq_lat, hq_lng
            )
            
            if distance < best_distance:
                best_distance = distance
                best_order = perm
    else:
        # For too many machines, use a simple greedy approach (nearest neighbor)
        remaining_machines = machines.copy()
        ordered_machines = []
        
        # Start from HQ and always choose the closest next machine
        current_lat, current_lng = hq_lat, hq_lng
        best_order = []
        
        while remaining_machines:
            best_distance = float('inf')
            best_machine_idx = -1
            
            for i, machine in enumerate(remaining_machines):
                dist = calculate_distance(
                    current_lat, current_lng,
                    float(machine.location.latitude), 
                    float(machine.location.longitude)
                )
                
                if dist < best_distance:
                    best_distance = dist
                    best_machine_idx = i
            
            best_machine = remaining_machines.pop(best_machine_idx)
            ordered_machines.append(best_machine)
            best_order.append(machine_ids.index(best_machine.id))
            
            current_lat = float(best_machine.location.latitude)
            current_lng = float(best_machine.location.longitude)
    
    # Create the result with the optimized order
    optimized_machines = []
    total_distance = 0
    avg_speed = 60  # km/h
    total_duration = 0
    
    # Get first machine
    current_lat, current_lng = hq_lat, hq_lng
    
    for idx in best_order:
        machine = machines[idx]
        
        # Calculate distance from previous point
        machine_lat = float(machine.location.latitude)
        machine_lng = float(machine.location.longitude)
        
        distance = calculate_distance(current_lat, current_lng, machine_lat, machine_lng)
        total_distance += distance
        
        # Calculate travel time in hours
        travel_time = distance / avg_speed
        
        # Add 1 hour service time per machine
        service_time = 1.0
        total_duration += travel_time + service_time
        
        optimized_machines.append({
            'id': machine.id,
            'name': machine.name,
            'lat': machine_lat,
            'lng': machine_lng,
            'address': machine.location.address if machine.location.address else "Unknown",
            'travel_distance_from_previous': round(distance, 1),
            'travel_time_from_previous': round(travel_time, 1),
            'service_time': service_time
        })
        
        current_lat, current_lng = machine_lat, machine_lng
    
    # Calculate return to HQ
    return_distance = calculate_distance(current_lat, current_lng, hq_lat, hq_lng)
    return_time = return_distance / avg_speed
    total_distance += return_distance
    total_duration += return_time
    
    # Add 15% buffer time
    total_duration *= 1.15
    
    result = {
        'headquarters': {
            'lat': hq_lat,
            'lng': hq_lng,
            'address': 'Warsaw, Poland'
        },
        'is_delegation': total_duration > 8.0,
        'total_distance': round(total_distance, 1),
        'total_duration': round(total_duration, 1),
        'optimized_machines': optimized_machines,
        'return_distance': round(return_distance, 1),
        'return_time': round(return_time, 1)
    }
    
    return Response(result)

@api_view(['GET'])
def route_details(request, route_id):
    """
    API endpoint to get detailed information about a route.
    """
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
    operation_description="Pobiera listę maszyn z aktywnymi ostrzeżeniami",
    responses={
        200: openapi.Response(
            description="Lista maszyn z ostrzeżeniami",
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
                        'location': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            nullable=True,
                            properties={
                                'lat': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'lng': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'address': openapi.Schema(type=openapi.TYPE_STRING, nullable=True)
                            }
                        )
                    }
                )
            )
        )
    }
)
@api_view(['GET'])
def get_machines_with_warnings(request):
    """
    API endpoint to get machines with active warnings.
    """
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
    operation_description="Odbiera dane telemetryczne z maszyn i sprawdza pod kątem warunków ostrzegawczych",
    responses={
        201: openapi.Response(
            description="Dane telemetryczne zapisane pomyślnie",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'telemetry_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'warnings_triggered': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(type=openapi.TYPE_INTEGER)
                    )
                }
            )
        ),
        400: "Niepoprawne dane wejściowe",
        404: "Maszyna o podanym numerze seryjnym nie znaleziona"
    }
)
@csrf_exempt
@api_view(['POST'])
def receive_telemetry(request):
    """
    API endpoint to receive telemetry data from machines and check against warning rules.
    """
    try:
        data = request.data
        serial_number = data.get('serial_number')
        parameter = data.get('parameter')
        value = data.get('value')
        
        # Find the machine
        try:
            machine = Machine.objects.get(serial_number=serial_number)
        except Machine.DoesNotExist:
            return Response({'error': f'Machine with serial {serial_number} not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Store telemetry
        telemetry = Telemetry.objects.create(
            machine=machine,
            parameter=parameter,
            value=value
        )
        
        # Check warning rules
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
                
                # Update machine status based on warning severity
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

@api_view(['GET'])
def routes_list(request):
    """
    API endpoint to get filtered list of routes for the refresh functionality.
    """
    routes = Route.objects.select_related('technician').all().order_by('date')
    
    # Filter by technician if specified
    technician_id = request.GET.get('technician')
    if technician_id:
        routes = routes.filter(technician_id=technician_id)
    
    # Filter by date if specified
    date_filter = request.GET.get('date')
    if date_filter:
        routes = routes.filter(date=date_filter)
    
    # Format response data
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

@api_view(['GET'])
def get_machines(request):
    """
    API endpoint to get all machines with their locations and status.
    """
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

@csrf_exempt
@api_view(['POST'])
def create_route(request):
    """
    API endpoint to create a new route from optimized data
    """
    try:
        data = request.data
        
        # Validate required fields
        required_fields = ['name', 'date', 'technician_id', 'machines', 'estimated_duration']
        for field in required_fields:
            if field not in data:
                return Response({'error': f'Missing required field: {field}'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate technician exists
        try:
            technician = User.objects.get(pk=data['technician_id'])
        except User.DoesNotExist:
            return Response({'error': 'Technician not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Create the route
        route = Route.objects.create(
            name=data['name'],
            technician=technician,
            date=data['date'],
            estimated_duration=data['estimated_duration'],
            start_location=data.get('start_location', 'Warsaw, Poland'),
            status='planned',
            notes=data.get('notes', '')
        )
        
        # Create route stops
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
                # Log error but continue with other machines
                print(f"Machine with ID {stop_data['machine_id']} not found")
                continue
        
        # Return the created route data
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

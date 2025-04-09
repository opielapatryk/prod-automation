from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
# Remove login_required import since we're not using it for now
# from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import json
from datetime import datetime
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Machine, Location, Telemetry, Warning, WarningRule, ServiceRecord
from .serializers import (MachineSerializer, LocationSerializer, TelemetrySerializer, 
                         WarningSerializer, TelemetryInputSerializer)

# Remove @login_required decorator
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

# Remove @login_required decorator
def machine_map(request):
    """
    View to display machines on a map.
    """
    machines = Machine.objects.select_related('location').all()
    
    context = {
        'machines': machines,
    }
    
    return render(request, 'collector/machine_map.html', context)

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

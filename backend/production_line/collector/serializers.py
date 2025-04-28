from rest_framework import serializers
from .models import Machine, Location, Telemetry, Warning, WarningRule, ServiceRecord

class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'latitude', 'longitude', 'address']

class MachineSerializer(serializers.ModelSerializer):
    location = LocationSerializer()
    
    class Meta:
        model = Machine
        fields = ['id', 'name', 'serial_number', 'model', 'manufacturer', 'status',
                  'location', 'installation_date', 'last_maintenance_date', 'next_maintenance_date']

class WarningRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = WarningRule
        fields = ['id', 'name', 'parameter', 'comparison_operator', 'threshold_value', 
                  'severity', 'created_at']

class TelemetrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Telemetry
        fields = ['id', 'machine', 'timestamp', 'parameter', 'value']

class WarningSerializer(serializers.ModelSerializer):
    machine = MachineSerializer(read_only=True)
    rule = WarningRuleSerializer(read_only=True)
    
    class Meta:
        model = Warning
        fields = ['id', 'machine', 'rule', 'created_at', 'resolved_at', 'description', 'is_active']

class ServiceRecordSerializer(serializers.ModelSerializer):
    resolved_warnings = WarningSerializer(many=True, read_only=True)
    
    class Meta:
        model = ServiceRecord
        fields = ['id', 'machine', 'technician', 'service_date', 'description', 'resolved_warnings']

class TelemetryInputSerializer(serializers.Serializer):
    serial_number = serializers.CharField(max_length=50, required=True, 
                                        help_text="Numer seryjny maszyny")
    parameter = serializers.CharField(max_length=50, required=True,
                                    help_text="Nazwa parametru telemetrii")
    value = serializers.FloatField(required=True,
                                help_text="Wartość parametru telemetrii")

from django.contrib import admin
from .models import Machine, Location, Telemetry, Warning, WarningRule, ServiceRecord

@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ('name', 'serial_number', 'model', 'status', 'installation_date')
    list_filter = ('status', 'model', 'manufacturer')
    search_fields = ('name', 'serial_number')

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('latitude', 'longitude', 'address')
    search_fields = ('address',)

@admin.register(WarningRule)
class WarningRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'parameter', 'comparison_operator', 'threshold_value', 'severity')
    list_filter = ('severity', 'created_by')
    search_fields = ('name', 'parameter')

@admin.register(Telemetry)
class TelemetryAdmin(admin.ModelAdmin):
    list_display = ('machine', 'parameter', 'value', 'timestamp')
    list_filter = ('parameter', 'machine')
    date_hierarchy = 'timestamp'

@admin.register(Warning)
class WarningAdmin(admin.ModelAdmin):
    list_display = ('machine', 'description', 'created_at', 'resolved_at', 'is_active')
    list_filter = ('created_at', 'resolved_at')
    search_fields = ('description', 'machine__name')

@admin.register(ServiceRecord)
class ServiceRecordAdmin(admin.ModelAdmin):
    list_display = ('machine', 'technician', 'service_date')
    list_filter = ('service_date', 'technician')
    filter_horizontal = ('resolved_warnings',)

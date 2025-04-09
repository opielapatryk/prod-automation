from django.db import models
from django.contrib.auth.models import User

class Location(models.Model):
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    address = models.CharField(max_length=255, blank=True, null=True)
    
    def __str__(self):
        return f"{self.latitude}, {self.longitude}"

class Machine(models.Model):
    STATUS_CHOICES = [
        ('operational', 'Operational'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
        ('offline', 'Offline'),
        ('maintenance', 'Under Maintenance'),
    ]

    name = models.CharField(max_length=100)
    serial_number = models.CharField(max_length=50, unique=True)
    model = models.CharField(max_length=100)
    manufacturer = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='operational')
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, related_name='machines')
    installation_date = models.DateField()
    last_maintenance_date = models.DateField(null=True, blank=True)
    next_maintenance_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.name} ({self.serial_number})"
    
    def active_warnings_count(self):
        return self.warnings.filter(resolved_at=None).count()

class WarningRule(models.Model):
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    COMPARISON_CHOICES = [
        ('>', 'Greater Than'),
        ('>=', 'Greater Than or Equal'),
        ('<', 'Less Than'),
        ('<=', 'Less Than or Equal'),
        ('==', 'Equal'),
        ('!=', 'Not Equal'),
    ]
    
    name = models.CharField(max_length=100)
    parameter = models.CharField(max_length=50)
    comparison_operator = models.CharField(max_length=2, choices=COMPARISON_CHOICES)
    threshold_value = models.FloatField()
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.parameter} {self.comparison_operator} {self.threshold_value})"

class Telemetry(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='telemetry')
    timestamp = models.DateTimeField(auto_now_add=True)
    parameter = models.CharField(max_length=50)
    value = models.FloatField()
    
    class Meta:
        verbose_name_plural = 'Telemetry'
        ordering = ['-timestamp']
        
    def __str__(self):
        return f"{self.machine.name} - {self.parameter}: {self.value}"

class Warning(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='warnings')
    rule = models.ForeignKey(WarningRule, on_delete=models.SET_NULL, null=True)
    telemetry = models.ForeignKey(Telemetry, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField()
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.machine.name} - {self.description}"
        
    @property
    def is_active(self):
        return self.resolved_at is None
        
class ServiceRecord(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='service_records')
    technician = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    service_date = models.DateTimeField()
    description = models.TextField()
    resolved_warnings = models.ManyToManyField(Warning, blank=True)
    
    def __str__(self):
        return f"{self.machine.name} - {self.service_date}"

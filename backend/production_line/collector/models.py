from django.db import models
from django.contrib.auth.models import User
import datetime

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

class Route(models.Model):
    STATUS_CHOICES = [
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ]
    
    name = models.CharField(max_length=100)
    technician = models.ForeignKey(User, on_delete=models.CASCADE, related_name='routes')
    date = models.DateField()
    estimated_duration = models.FloatField(help_text="Estimated duration in hours")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    machines = models.ManyToManyField(Machine, through='RouteStop')
    start_location = models.CharField(max_length=255, default="Warsaw, Poland")
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Route {self.name} - {self.date} ({self.technician.username})"
    
    @property
    def is_delegation(self):
        return self.estimated_duration > 8.0
    
    def calculate_estimated_duration(self):
        """Calculate the estimated duration of the route based on stops and travel times using geographic data"""
        from math import radians, cos, sin, asin, sqrt
        
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
        
        # Average speed in km/h for car travel
        avg_speed = 60
        
        # Warsaw coordinates (headquarters)
        hq_lat, hq_lng = 52.2297, 21.0122
        
        total_hours = 0
        stops = list(self.routestop_set.all().order_by('order'))
        
        if not stops:
            self.estimated_duration = 0
            self.save()
            return 0
            
        # Calculate distance from HQ to first stop
        first_stop = stops[0]
        if first_stop.machine.location:
            first_lat = float(first_stop.machine.location.latitude)
            first_lng = float(first_stop.machine.location.longitude)
            distance_to_first = calculate_distance(hq_lat, hq_lng, first_lat, first_lng)
            travel_time_to_first = distance_to_first / avg_speed
            total_hours += travel_time_to_first
            
        # Add service time for each stop
        for stop in stops:
            total_hours += stop.estimated_service_time
            
        # Calculate travel time between stops
        for i in range(len(stops) - 1):
            current_stop = stops[i]
            next_stop = stops[i + 1]
            
            if current_stop.machine.location and next_stop.machine.location:
                current_lat = float(current_stop.machine.location.latitude)
                current_lng = float(current_stop.machine.location.longitude)
                next_lat = float(next_stop.machine.location.latitude)
                next_lng = float(next_stop.machine.location.longitude)
                
                distance = calculate_distance(current_lat, current_lng, next_lat, next_lng)
                travel_time = distance / avg_speed
                total_hours += travel_time
        
        # Calculate return trip from last stop to HQ
        last_stop = stops[-1]
        if last_stop.machine.location:
            last_lat = float(last_stop.machine.location.latitude)
            last_lng = float(last_stop.machine.location.longitude)
            distance_to_hq = calculate_distance(last_lat, last_lng, hq_lat, hq_lng)
            travel_time_to_hq = distance_to_hq / avg_speed
            total_hours += travel_time_to_hq
        
        # Add buffer time (15% for unexpected delays)
        total_hours *= 1.15
        
        self.estimated_duration = round(total_hours, 1)
        self.save()
        return total_hours

class RouteStop(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE)
    order = models.PositiveIntegerField()
    estimated_service_time = models.FloatField(default=1.0, help_text="Estimated service time in hours")
    completed = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['order']
        unique_together = ('route', 'order')
        
    def __str__(self):
        return f"{self.route.name} - Stop {self.order}: {self.machine.name}"

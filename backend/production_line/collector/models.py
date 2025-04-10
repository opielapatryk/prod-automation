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
    start_location = models.CharField(max_length=255, default="Warsaw, Poland (Basecamp)")  # Updated to emphasize basecamp status
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Route {self.name} - {self.date} ({self.technician.username})"
    
    @property
    def is_delegation(self):
        return self.estimated_duration > 8.0
    
    def calculate_estimated_duration(self):
        """
        Calculate the estimated duration of the route based on stops and travel times.
        Routes always start and end at headquarters (Warsaw basecamp).
        """
        from math import radians, cos, sin, asin, sqrt
        import datetime
        import json
        
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
        
        # Average speed in km/h for car travel - adjustable for different road conditions
        avg_speeds = {
            'city': 30,      # km/h in city traffic
            'suburban': 70,  # km/h in suburban areas
            'highway': 100   # km/h on highways
        }
        
        # Default to mixed travel type - 70% highway, 20% suburban, 10% city
        def estimate_travel_speed(distance):
            if distance < 5:     # Short city trips
                return avg_speeds['city']
            elif distance < 30:  # Suburban/mixed
                return (avg_speeds['city'] * 0.2 + avg_speeds['suburban'] * 0.8)
            else:                # Longer highway trips
                return (avg_speeds['highway'] * 0.7 + avg_speeds['suburban'] * 0.2 + avg_speeds['city'] * 0.1)
        
        # Warsaw coordinates (headquarters/basecamp)
        hq_lat, hq_lng = 52.2297, 21.0122
        
        # Initialize variables for tracking
        total_hours = 0
        total_distance = 0
        detailed_segments = []
        
        stops = list(self.routestop_set.all().order_by('order'))
        
        if not stops:
            self.estimated_duration = 0
            self.save()
            return 0
        
        # Sequential travel - from HQ to first stop, then between stops, then back to HQ
        prev_lat, prev_lng = hq_lat, hq_lng
        prev_name = "Headquarters"
        
        # Visit each stop in order
        for stop in stops:
            if stop.machine.location:
                curr_lat = float(stop.machine.location.latitude)
                curr_lng = float(stop.machine.location.longitude)
                curr_name = stop.machine.name
                
                # Calculate travel from previous stop (or HQ) to this stop
                distance = calculate_distance(prev_lat, prev_lng, curr_lat, curr_lng)
                speed = estimate_travel_speed(distance)
                travel_time = distance / speed
                
                total_distance += distance
                total_hours += travel_time
                
                # Record this travel segment
                detailed_segments.append({
                    'type': 'travel',
                    'from': prev_name,
                    'to': curr_name,
                    'distance': round(distance, 1),
                    'duration': round(travel_time, 2),
                    'speed': round(speed, 1)
                })
                
                # Service time at this location
                service_time = stop.estimated_service_time
                total_hours += service_time
                
                # Record the service segment
                detailed_segments.append({
                    'type': 'service',
                    'location': curr_name,
                    'duration': service_time,
                    'address': stop.machine.location.address if stop.machine.location else "No address"
                })
                
                # Update previous location for next segment
                prev_lat, prev_lng = curr_lat, curr_lng
                prev_name = curr_name
        
        # Finally, travel from last stop back to headquarters (basecamp)
        if stops:
            last_stop = stops[-1]
            if last_stop.machine.location:
                distance_to_hq = calculate_distance(
                    float(last_stop.machine.location.latitude),
                    float(last_stop.machine.location.longitude),
                    hq_lat, hq_lng
                )
                speed = estimate_travel_speed(distance_to_hq)
                travel_time_to_hq = distance_to_hq / speed
                
                total_distance += distance_to_hq
                total_hours += travel_time_to_hq
                
                detailed_segments.append({
                    'type': 'travel',
                    'from': last_stop.machine.name,
                    'to': 'Headquarters (Basecamp)',  # Updated to emphasize basecamp status
                    'distance': round(distance_to_hq, 1),
                    'duration': round(travel_time_to_hq, 2),
                    'speed': round(speed, 1)
                })
        
        # Add buffer time (15% for unexpected delays)
        raw_hours = total_hours
        buffer_hours = total_hours * 0.15
        total_hours += buffer_hours
        
        # Format for human-readable time
        hours = int(total_hours)
        minutes = int((total_hours - hours) * 60)
        formatted_duration = f"{hours}h {minutes}min"
        
        # Store the detailed segments as a property in notes field for future reference
        summary = {
            'total_distance': round(total_distance, 1),
            'raw_duration_hours': round(raw_hours, 2),
            'buffer_hours': round(buffer_hours, 2),
            'total_duration_hours': round(total_hours, 2),
            'formatted_duration': formatted_duration,
            'segments': detailed_segments
        }
        
        # Add the route calculation details to notes but preserve any existing notes
        original_notes = self.notes or ""
        if "Route calculation details" in original_notes:
            # Replace the old calculation
            import re
            self.notes = re.sub(
                r'\n\nRoute calculation details \(auto-generated\):.*', 
                f'\n\nRoute calculation details (auto-generated):\n{json.dumps(summary, indent=2)}',
                original_notes, 
                flags=re.DOTALL
            )
        else:
            # Append the new calculation
            self.notes = original_notes + f"\n\nRoute calculation details (auto-generated):\n{json.dumps(summary, indent=2)}"
        
        # Store the route time information
        self.estimated_duration = round(total_hours, 2)
        self.save()
        
        # Return the total duration in hours for convenience
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

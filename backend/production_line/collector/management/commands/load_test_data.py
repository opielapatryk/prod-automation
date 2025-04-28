from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from collector.models import Location, Machine, WarningRule, Telemetry, Warning, ServiceRecord, Route, RouteStop
from django.utils import timezone
from datetime import timedelta, date
import random
import decimal

class Command(BaseCommand):
    help = 'Load test data for production line monitoring system'

    def handle(self, *args, **kwargs):
        self.stdout.write('Starting test data loading...')
        
        self.clear_data()
        
        technicians = self.create_users()
        locations = self.create_locations()
        machines = self.create_machines(locations)
        rules = self.create_warning_rules()
        
        self.create_telemetry_and_warnings(machines, rules)
        self.create_service_records(machines)
        self.create_routes(technicians, machines)
        
        self.stdout.write(self.style.SUCCESS('Test data loaded successfully!'))

    def clear_data(self):
        self.stdout.write('Clearing existing data...')
        ServiceRecord.objects.all().delete()
        Warning.objects.all().delete()
        Telemetry.objects.all().delete()
        WarningRule.objects.all().delete()
        RouteStop.objects.all().delete()
        Route.objects.all().delete()
        Machine.objects.all().delete()
        Location.objects.all().delete()

    def create_users(self):
        self.stdout.write('Creating users...')
        
        admin = None
        if not User.objects.filter(username='admin').exists():
            admin = User.objects.create_superuser(
                username='admin',
                email='admin@example.com',
                password='admin123'
            )
        else:
            admin = User.objects.get(username='admin')
        
        technicians = []
        for i in range(1, 4):
            username = f'tech{i}'
            if not User.objects.filter(username=username).exists():
                tech = User.objects.create_user(
                    username=username,
                    email=f'tech{i}@example.com',
                    password='tech123',
                    first_name=f'Technician {i}',
                    last_name='Service'
                )
                technicians.append(tech)
            else:
                tech = User.objects.get(username=username)
                technicians.append(tech)
                
        if not technicians and admin:
            technicians.append(admin)
        
        return technicians

    def create_locations(self):
        self.stdout.write('Creating locations...')
        
        locations = [
            Location.objects.create(
                latitude=decimal.Decimal('52.2297'),
                longitude=decimal.Decimal('21.0122'),
                address='Warsaw, Poland'
            ),
            Location.objects.create(
                latitude=decimal.Decimal('50.0647'),
                longitude=decimal.Decimal('19.9450'),
                address='Krakow, Poland'
            ),
            Location.objects.create(
                latitude=decimal.Decimal('51.1079'),
                longitude=decimal.Decimal('17.0385'),
                address='Wroclaw, Poland'
            ),
            Location.objects.create(
                latitude=decimal.Decimal('54.3520'),
                longitude=decimal.Decimal('18.6466'),
                address='Gdansk, Poland'
            ),
            Location.objects.create(
                latitude=decimal.Decimal('53.1235'),
                longitude=decimal.Decimal('18.0084'),
                address='Bydgoszcz, Poland'
            )
        ]
        
        return locations

    def create_machines(self, locations):
        self.stdout.write('Creating machines...')
        
        manufacturers = ['ABB', 'Siemens', 'Bosch', 'Fanuc', 'Mitsubishi']
        models = ['ProMill X7', 'AutoLath 2000', 'RoboPress V3', 'InjectMax 500', 'AssemblyBot']
        statuses = ['operational', 'warning', 'critical', 'offline', 'maintenance']
        
        machines = []
        for i in range(1, 21):
            location = random.choice(locations)
            manufacturer = random.choice(manufacturers)
            model = random.choice(models)
            status = random.choice(statuses)
            
            installation_date = timezone.now() - timedelta(days=random.randint(30, 1095))
            last_maintenance = installation_date + timedelta(days=random.randint(1, 90))
            next_maintenance = last_maintenance + timedelta(days=90)
            
            machine = Machine.objects.create(
                name=f'Machine {i}',
                serial_number=f'SN-{manufacturer[:3]}-{100000 + i}',
                model=model,
                manufacturer=manufacturer,
                status=status,
                location=location,
                installation_date=installation_date.date(),
                last_maintenance_date=last_maintenance.date(),
                next_maintenance_date=next_maintenance.date()
            )
            machines.append(machine)
            
        return machines

    def create_warning_rules(self):
        self.stdout.write('Creating warning rules...')
        
        admin_user = User.objects.get(username='admin')
        
        rules = [
            WarningRule.objects.create(
                name='High Temperature',
                parameter='temperature',
                comparison_operator='>',
                threshold_value=85.0,
                severity='high',
                created_by=admin_user
            ),
            WarningRule.objects.create(
                name='Critical Temperature',
                parameter='temperature',
                comparison_operator='>',
                threshold_value=95.0,
                severity='critical',
                created_by=admin_user
            ),
            WarningRule.objects.create(
                name='Low Pressure',
                parameter='pressure',
                comparison_operator='<',
                threshold_value=20.0,
                severity='medium',
                created_by=admin_user
            ),
            WarningRule.objects.create(
                name='High RPM',
                parameter='rpm',
                comparison_operator='>',
                threshold_value=1800.0,
                severity='high',
                created_by=admin_user
            ),
            WarningRule.objects.create(
                name='Low Oil Level',
                parameter='oil_level',
                comparison_operator='<',
                threshold_value=15.0,
                severity='medium',
                created_by=admin_user
            ),
            WarningRule.objects.create(
                name='Critical Oil Level',
                parameter='oil_level',
                comparison_operator='<',
                threshold_value=5.0,
                severity='critical',
                created_by=admin_user
            )
        ]
        
        return rules

    def create_telemetry_and_warnings(self, machines, rules):
        self.stdout.write('Generating telemetry and warnings...')
        
        parameters = {
            'temperature': (60.0, 100.0),
            'pressure': (10.0, 50.0),
            'rpm': (800, 2200),
            'oil_level': (1.0, 40.0),
            'vibration': (0.1, 5.0),
            'humidity': (30.0, 90.0)
        }
        
        for machine in machines:
            for day in range(5):
                for hour in range(0, 24, 3):
                    timestamp = timezone.now() - timedelta(days=day, hours=hour)
                    
                    for param, (min_val, max_val) in parameters.items():
                        value = random.uniform(min_val, max_val)
                        
                        if random.random() < 0.1:
                            if param == 'temperature':
                                value = random.uniform(90.0, 110.0)
                            elif param == 'pressure':
                                value = random.uniform(5.0, 15.0)
                            elif param == 'oil_level':
                                value = random.uniform(1.0, 10.0)
                                
                        telemetry = Telemetry.objects.create(
                            machine=machine,
                            parameter=param,
                            value=value,
                        )
                        
                        Telemetry.objects.filter(id=telemetry.id).update(timestamp=timestamp)
                        
                        for rule in rules:
                            if rule.parameter == param:
                                is_violation = False
                                
                                if rule.comparison_operator == '>' and value > rule.threshold_value:
                                    is_violation = True
                                elif rule.comparison_operator == '>=' and value >= rule.threshold_value:
                                    is_violation = True
                                elif rule.comparison_operator == '<' and value < rule.threshold_value:
                                    is_violation = True
                                elif rule.comparison_operator == '<=' and value <= rule.threshold_value:
                                    is_violation = True
                                elif rule.comparison_operator == '==' and value == rule.threshold_value:
                                    is_violation = True
                                elif rule.comparison_operator == '!=' and value != rule.threshold_value:
                                    is_violation = True
                                    
                                if is_violation:
                                    warning = Warning.objects.create(
                                        machine=machine,
                                        rule=rule,
                                        telemetry=telemetry,
                                        description=f"Warning: {param} {rule.comparison_operator} {rule.threshold_value} (Actual: {value:.2f})"
                                    )
                                    
                                    Warning.objects.filter(id=warning.id).update(created_at=timestamp)
                                    
                                    if random.random() < 0.6:
                                        resolve_time = timestamp + timedelta(hours=random.randint(1, 24))
                                        if resolve_time < timezone.now():
                                            Warning.objects.filter(id=warning.id).update(resolved_at=resolve_time)
                                    
                                    if day == 0 and rule.severity == 'critical' and not warning.resolved_at:
                                        machine.status = 'critical'
                                        machine.save()
                                    elif day == 0 and rule.severity in ['high', 'medium'] and not warning.resolved_at and machine.status != 'critical':
                                        machine.status = 'warning'
                                        machine.save()

    def create_service_records(self, machines):
        self.stdout.write('Creating service records...')
        
        technicians = User.objects.filter(username__startswith='tech')
        if not technicians:
            return
        
        for machine in machines:
            for _ in range(random.randint(0, 3)):
                technician = random.choice(technicians)
                service_date = timezone.now() - timedelta(days=random.randint(1, 180))
                
                descriptions = [
                    f"Oil and filter change. Detailed inspection.",
                    f"Repair of {random.choice(['pump', 'motor', 'gearbox', 'controller'])} failure.",
                    f"Regular machine maintenance.",
                    f"Replacement of worn parts: {random.choice(['bearings', 'belts', 'joints', 'clutch'])}.",
                    f"Control software update.",
                    f"Cleaning and calibration.",
                ]
                
                description = random.choice(descriptions)
                
                service_record = ServiceRecord.objects.create(
                    machine=machine,
                    technician=technician,
                    service_date=service_date,
                    description=description
                )
                
                resolved_warnings = Warning.objects.filter(
                    machine=machine, 
                    resolved_at__gte=service_date - timedelta(hours=1),
                    resolved_at__lte=service_date + timedelta(hours=1)
                )
                
                if resolved_warnings.exists():
                    service_record.resolved_warnings.add(*resolved_warnings)

    def create_routes(self, technicians, machines):
        self.stdout.write('Creating example routes...')
        
        if not technicians:
            return []
        
        today = date.today()
        
        route_names = [
            "Quarterly Review - Warsaw",
            "Machine Inspection - Krakow",
            "Maintenance - Wroclaw",
            "Technical Review - Gdansk",
            "Equipment Repair - Poznan",
            "Pre-season Inspection - Zakopane",
            "Emergency Intervention - Lodz"
        ]
        
        statuses = ['planned', 'in_progress', 'completed']
        
        routes = []
        for i in range(5):
            tech = random.choice(technicians)
            route_date = today + timedelta(days=random.randint(0, 30))
            name = random.choice(route_names) + f" #{i+1}"
            
            route = Route.objects.create(
                name=name,
                technician=tech,
                date=route_date,
                estimated_duration=0,
                status=random.choice(statuses),
                start_location='Warsaw, Poland',
                notes=f"Example route created automatically. ID: {i+1}"
            )
            
            try:
                route_machines = random.sample(list(machines), min(random.randint(3, 5), len(machines)))
                
                for idx, machine in enumerate(route_machines, 1):
                    RouteStop.objects.create(
                        route=route,
                        machine=machine,
                        order=idx,
                        estimated_service_time=1.0,
                        completed=(route.status == 'completed')
                    )
                
                route.calculate_estimated_duration()
            except Exception:
                pass
            
            routes.append(route)
            
        return routes

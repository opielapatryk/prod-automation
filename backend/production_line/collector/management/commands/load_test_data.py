from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from collector.models import Location, Machine, WarningRule, Telemetry, Warning, ServiceRecord, Route, RouteStop
from django.utils import timezone
from datetime import timedelta, date
import random
import decimal

class Command(BaseCommand):
    help = 'Ładuje przykładowe dane testowe do systemu monitorowania linii produkcyjnej'

    def handle(self, *args, **kwargs):
        self.stdout.write('Rozpoczynam ładowanie danych testowych...')
        
        # Usuń istniejące dane (opcjonalnie)
        self.clear_data()
        
        # Tworzenie użytkownika administratora jeśli nie istnieje
        technicians = self.create_users()
        
        # Tworzenie lokalizacji
        locations = self.create_locations()
        
        # Tworzenie maszyn
        machines = self.create_machines(locations)
        
        # Tworzenie reguł ostrzegawczych
        rules = self.create_warning_rules()
        
        # Generowanie danych telemetrycznych i ostrzeżeń
        self.create_telemetry_and_warnings(machines, rules)
        
        # Tworzenie historii serwisowej
        self.create_service_records(machines)
        
        # Tworzenie przykładowych tras
        self.create_routes(technicians, machines)
        
        self.stdout.write(self.style.SUCCESS('Dane testowe zostały pomyślnie załadowane!'))

    def clear_data(self):
        """Usuwa istniejące dane"""
        self.stdout.write('Usuwanie istniejących danych...')
        ServiceRecord.objects.all().delete()
        Warning.objects.all().delete()
        Telemetry.objects.all().delete()
        WarningRule.objects.all().delete()
        RouteStop.objects.all().delete()  # Dodane usuwanie przystanków trasy
        Route.objects.all().delete()      # Dodane usuwanie tras
        Machine.objects.all().delete()
        Location.objects.all().delete()

    def create_users(self):
        """Tworzy użytkowników jeśli nie istnieją"""
        self.stdout.write('Tworzenie użytkowników...')
        
        # Utwórz administratora
        admin = None
        if not User.objects.filter(username='admin').exists():
            admin = User.objects.create_superuser(
                username='admin',
                email='admin@example.com',
                password='admin123'
            )
            self.stdout.write(f'Utworzono administratora: {admin.username}')
        else:
            admin = User.objects.get(username='admin')
        
        # Utwórz techników
        technicians = []
        for i in range(1, 4):
            username = f'tech{i}'
            if not User.objects.filter(username=username).exists():
                tech = User.objects.create_user(
                    username=username,
                    email=f'tech{i}@example.com',
                    password='tech123',
                    first_name=f'Technik {i}',
                    last_name='Serwisowy'
                )
                technicians.append(tech)
                self.stdout.write(f'Utworzono technika: {tech.username}')
            else:
                # Dodaj istniejących techników do listy
                tech = User.objects.get(username=username)
                technicians.append(tech)
                
        # Jeśli brak techników, dodaj administratora do listy techników
        if not technicians and admin:
            technicians.append(admin)
        
        return technicians

    def create_locations(self):
        """Tworzy przykładowe lokalizacje"""
        self.stdout.write('Tworzenie lokalizacji...')
        
        locations = [
            Location.objects.create(
                latitude=decimal.Decimal('52.2297'),
                longitude=decimal.Decimal('21.0122'),
                address='Warszawa, Polska'
            ),
            Location.objects.create(
                latitude=decimal.Decimal('50.0647'),
                longitude=decimal.Decimal('19.9450'),
                address='Kraków, Polska'
            ),
            Location.objects.create(
                latitude=decimal.Decimal('51.1079'),
                longitude=decimal.Decimal('17.0385'),
                address='Wrocław, Polska'
            ),
            Location.objects.create(
                latitude=decimal.Decimal('54.3520'),
                longitude=decimal.Decimal('18.6466'),
                address='Gdańsk, Polska'
            ),
            Location.objects.create(
                latitude=decimal.Decimal('53.1235'),
                longitude=decimal.Decimal('18.0084'),
                address='Bydgoszcz, Polska'
            )
        ]
        
        self.stdout.write(f'Utworzono {len(locations)} lokalizacji')
        return locations

    def create_machines(self, locations):
        """Tworzy przykładowe maszyny w różnych lokalizacjach"""
        self.stdout.write('Tworzenie maszyn...')
        
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
                name=f'Maszyna {i}',
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
            
        self.stdout.write(f'Utworzono {len(machines)} maszyn')
        return machines

    def create_warning_rules(self):
        """Tworzy reguły ostrzegawcze"""
        self.stdout.write('Tworzenie reguł ostrzegawczych...')
        
        admin_user = User.objects.get(username='admin')
        
        rules = [
            WarningRule.objects.create(
                name='Wysoka temperatura',
                parameter='temperature',
                comparison_operator='>',
                threshold_value=85.0,
                severity='high',
                created_by=admin_user
            ),
            WarningRule.objects.create(
                name='Krytyczna temperatura',
                parameter='temperature',
                comparison_operator='>',
                threshold_value=95.0,
                severity='critical',
                created_by=admin_user
            ),
            WarningRule.objects.create(
                name='Niskie ciśnienie',
                parameter='pressure',
                comparison_operator='<',
                threshold_value=20.0,
                severity='medium',
                created_by=admin_user
            ),
            WarningRule.objects.create(
                name='Wysokie obroty',
                parameter='rpm',
                comparison_operator='>',
                threshold_value=1800.0,
                severity='high',
                created_by=admin_user
            ),
            WarningRule.objects.create(
                name='Niski poziom oleju',
                parameter='oil_level',
                comparison_operator='<',
                threshold_value=15.0,
                severity='medium',
                created_by=admin_user
            ),
            WarningRule.objects.create(
                name='Krytyczny poziom oleju',
                parameter='oil_level',
                comparison_operator='<',
                threshold_value=5.0,
                severity='critical',
                created_by=admin_user
            )
        ]
        
        self.stdout.write(f'Utworzono {len(rules)} reguł ostrzegawczych')
        return rules

    def create_telemetry_and_warnings(self, machines, rules):
        """Generuje przykładowe dane telemetryczne i ostrzeżenia"""
        self.stdout.write('Generowanie danych telemetrycznych i ostrzeżeń...')
        
        parameters = {
            'temperature': (60.0, 100.0),
            'pressure': (10.0, 50.0),
            'rpm': (800, 2200),
            'oil_level': (1.0, 40.0),
            'vibration': (0.1, 5.0),
            'humidity': (30.0, 90.0)
        }
        
        telemetry_count = 0
        warnings_count = 0
        
        # Generuj dane dla każdej maszyny
        for machine in machines:
            # Generuj dane z ostatnich 5 dni
            for day in range(5):
                # Kilka odczytów dziennie
                for hour in range(0, 24, 3):
                    timestamp = timezone.now() - timedelta(days=day, hours=hour)
                    
                    # Generuj telemetrię dla różnych parametrów
                    for param, (min_val, max_val) in parameters.items():
                        # Dodaj losowe wahania dla bardziej realistycznych danych
                        value = random.uniform(min_val, max_val)
                        
                        # Celowo generuj wartości przekraczające progi dla niektórych odczytów
                        if random.random() < 0.1:  # 10% szans na wartość poza normą
                            if param == 'temperature':
                                value = random.uniform(90.0, 110.0)
                            elif param == 'pressure':
                                value = random.uniform(5.0, 15.0)
                            elif param == 'oil_level':
                                value = random.uniform(1.0, 10.0)
                                
                        # Zapisz telemetrię
                        telemetry = Telemetry.objects.create(
                            machine=machine,
                            parameter=param,
                            value=value,
                        )
                        
                        # Ustaw timestamp (aby nie były wszystkie w chwili uruchomienia)
                        Telemetry.objects.filter(id=telemetry.id).update(timestamp=timestamp)
                        
                        telemetry_count += 1
                        
                        # Sprawdź czy wartość narusza którąś regułę
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
                                    
                                    # Ustaw timestamp (aby odpowiadał telemetrii)
                                    Warning.objects.filter(id=warning.id).update(created_at=timestamp)
                                    
                                    # Rozwiąż część ostrzeżeń
                                    if random.random() < 0.6:  # 60% szans że ostrzeżenie zostało rozwiązane
                                        resolve_time = timestamp + timedelta(hours=random.randint(1, 24))
                                        if resolve_time < timezone.now():  # Tylko jeśli czas rozwiązania jest w przeszłości
                                            Warning.objects.filter(id=warning.id).update(resolved_at=resolve_time)
                                    
                                    warnings_count += 1
                                    
                                    # Aktualizuj status maszyny na podstawie ostatnich ostrzeżeń
                                    if day == 0 and rule.severity == 'critical' and not warning.resolved_at:
                                        machine.status = 'critical'
                                        machine.save()
                                    elif day == 0 and rule.severity in ['high', 'medium'] and not warning.resolved_at and machine.status != 'critical':
                                        machine.status = 'warning'
                                        machine.save()
        
        self.stdout.write(f'Wygenerowano {telemetry_count} rekordów telemetrii i {warnings_count} ostrzeżeń')

    def create_service_records(self, machines):
        """Tworzy historię serwisową dla maszyn"""
        self.stdout.write('Tworzenie historii serwisowej...')
        
        technicians = User.objects.filter(username__startswith='tech')
        if not technicians:
            return
        
        service_records_count = 0
        
        for machine in machines:
            # Losowa liczba zapisów serwisowych (0-3 na maszynę)
            for _ in range(random.randint(0, 3)):
                # Losowy technik
                technician = random.choice(technicians)
                
                # Data serwisu (w przeszłości)
                service_date = timezone.now() - timedelta(days=random.randint(1, 180))
                
                # Opis serwisu
                descriptions = [
                    f"Wymiana oleju i filtrów. Szczegółowy przegląd.",
                    f"Naprawa awarii {random.choice(['pompy', 'silnika', 'przekładni', 'sterownika'])}.",
                    f"Regularna konserwacja maszyny.",
                    f"Wymiana zużytych części: {random.choice(['łożyska', 'paski', 'przeguby', 'sprzęgło'])}.",
                    f"Aktualizacja oprogramowania sterującego.",
                    f"Czyszczenie i kalibracja.",
                ]
                
                description = random.choice(descriptions)
                
                # Utwórz rekord serwisowy
                service_record = ServiceRecord.objects.create(
                    machine=machine,
                    technician=technician,
                    service_date=service_date,
                    description=description
                )
                
                # Dodaj rozwiązane ostrzeżenia (jeśli istnieją)
                resolved_warnings = Warning.objects.filter(
                    machine=machine, 
                    resolved_at__gte=service_date - timedelta(hours=1),
                    resolved_at__lte=service_date + timedelta(hours=1)
                )
                
                if resolved_warnings.exists():
                    service_record.resolved_warnings.add(*resolved_warnings)
                
                service_records_count += 1
        
        self.stdout.write(f'Utworzono {service_records_count} rekordów serwisowych')

    def create_routes(self, technicians, machines):
        """Tworzy przykładowe trasy dla techników"""
        self.stdout.write('Tworzenie przykładowych tras...')
        
        if not technicians or len(technicians) == 0:
            self.stdout.write(self.style.WARNING('Brak techników do przypisania tras'))
            return []
        
        # Upewnienie się, że istnieją technici - jeśli nie, tworzymy ich
        if not technicians:
            for i in range(1, 4):
                username = f'tech{i}'
                tech = User.objects.create_user(
                    username=username,
                    email=f'tech{i}@example.com',
                    password='tech123',
                    first_name=f'Technik {i}',
                    last_name='Serwisowy'
                )
                technicians.append(tech)
                self.stdout.write(f'Utworzono technika: {tech.username}')
                
        today = date.today()
        
        # Tworzenie przykładowych nazw tras
        route_names = [
            "Przegląd kwartalny - Warszawa",
            "Przegląd maszyn - Kraków",
            "Konserwacja pianek - Wrocław",
            "Przegląd techniczny - Gdańsk",
            "Naprawa urządzeń - Poznań",
            "Przegląd przedsezonowy - Zakopane",
            "Interwencja awaryjna - Łódź"
        ]
        
        # Statusy tras
        statuses = ['planned', 'in_progress', 'completed']
        
        routes = []
        # Tworzenie kilku tras
        for i in range(5):
            # Wybierz losowego technika
            tech = random.choice(technicians)
            
            # Ustal datę trasy (od dziś do 30 dni w przyszłość)
            route_date = today + timedelta(days=random.randint(0, 30))
            
            # Wybierz nazwę trasy
            name = random.choice(route_names) + f" #{i+1}"
            
            # Utwórz trasę
            route = Route.objects.create(
                name=name,
                technician=tech,
                date=route_date,
                estimated_duration=0,  # Zostanie obliczone później
                status=random.choice(statuses),
                start_location='Warsaw, Poland',
                notes=f"Przykładowa trasa utworzona automatycznie. ID: {i+1}"
            )
            
            # Dodaj 3-5 losowych maszyn do trasy
            try:
                route_machines = random.sample(list(machines), min(random.randint(3, 5), len(machines)))
                
                for idx, machine in enumerate(route_machines, 1):
                    RouteStop.objects.create(
                        route=route,
                        machine=machine,
                        order=idx,
                        estimated_service_time=1.0,  # 1 godzina na maszynę
                        completed=(route.status == 'completed')
                    )
                
                # Oblicz szacowany czas trwania
                route.calculate_estimated_duration()
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Błąd przy dodawaniu przystanków do trasy: {e}"))
            
            routes.append(route)
            
        # Debug info
        self.stdout.write(f'Utworzono {len(routes)} tras')
        for route in routes:
            self.stdout.write(f'  - {route.name} dla {route.technician.username}, przystanki: {route.routestop_set.count()}')
        
        return routes

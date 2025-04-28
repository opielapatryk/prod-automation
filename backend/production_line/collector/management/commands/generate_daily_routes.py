from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from collector.models import Machine, Route, RouteStop
from datetime import date, timedelta
import requests
import json
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Automatyczne generowanie tras serwisowych na podstawie aktywnych awarii'

    def handle(self, *args, **options):
        """
        Generuje trasy serwisowe dla maszyn z aktywnymi awariami na następny dzień roboczy.
        Jeśli dziś jest piątek/sobota/niedziela, generuje trasy na poniedziałek.
        """
        self.stdout.write('Rozpoczynam generowanie automatycznych tras serwisowych...')
        
        # Ustal datę docelową (następny dzień roboczy)
        target_date = self._get_next_working_day()
        self.stdout.write(f"Tworzenie tras na dzień: {target_date}")
        
        # Pobierz maszyny z aktywnymi awariami
        machines_with_warnings = self._get_machines_with_warnings()
        
        if not machines_with_warnings:
            self.stdout.write(self.style.WARNING('Brak maszyn z aktywnymi awariami. Nie utworzono żadnych tras.'))
            return
            
        # Pogrupuj maszyny według lokalizacji/regionów
        machine_groups = self._group_machines_by_region(machines_with_warnings)
        
        # Pobierz dostępnych serwisantów
        technicians = User.objects.filter(is_active=True).exclude(is_staff=True, is_superuser=True)
        
        if not technicians:
            technicians = User.objects.filter(username='admin')
            if not technicians:
                self.stdout.write(self.style.ERROR('Brak dostępnych serwisantów do przypisania tras.'))
                return
                
        tech_index = 0
        created_routes = 0
        
        # Dla każdej grupy maszyn stwórz trasę
        for region, machines in machine_groups.items():
            if not machines:
                continue
                
            # Przydziel serwisanta rotacyjnie
            technician = technicians[tech_index % len(technicians)]
            tech_index += 1
            
            # Przygotuj dane do optymalizacji trasy
            machine_ids = [machine.id for machine in machines]
            
            # Optymalizuj trasę przez API
            optimized_data = self._optimize_route(machine_ids)
            
            if optimized_data:
                # Utwórz trasę z zoptymalizowanymi punktami
                route_name = f"Auto-{region}-{target_date}"
                
                try:
                    route = Route.objects.create(
                        name=route_name,
                        technician=technician,
                        date=target_date,
                        estimated_duration=optimized_data.get('total_duration', 4.0),
                        start_location='Warsaw, Poland',
                        status='planned',
                        notes=f"Trasa utworzona automatycznie dla regionu {region}. Liczba maszyn: {len(machines)}"
                    )
                    
                    # Dodaj przystanki w zoptymalizowanej kolejności
                    for idx, machine_data in enumerate(optimized_data.get('optimized_machines', []), 1):
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
                            self.stdout.write(self.style.WARNING(f"Nie znaleziono maszyny o ID {machine_data['id']}"))
                            continue
                    
                    created_routes += 1
                    self.stdout.write(self.style.SUCCESS(f"Utworzono trasę '{route_name}' dla serwisanta {technician.username}"))
                
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Błąd podczas tworzenia trasy: {str(e)}"))
        
        self.stdout.write(self.style.SUCCESS(f"Zakończono generowanie tras. Utworzono {created_routes} nowych tras."))

    def _get_next_working_day(self):
        """Zwraca datę następnego dnia roboczego (omijając weekendy)"""
        today = date.today()
        days_ahead = 1  # Domyślnie następny dzień
        
        # Jeśli dziś piątek, sobota lub niedziela, przejdź do poniedziałku
        if today.weekday() == 4:  # Piątek
            days_ahead = 3
        elif today.weekday() == 5:  # Sobota
            days_ahead = 2
        elif today.weekday() == 6:  # Niedziela
            days_ahead = 1
            
        return today + timedelta(days=days_ahead)
        
    def _get_machines_with_warnings(self):
        """Pobiera maszyny z aktywnymi ostrzeżeniami"""
        return list(Machine.objects.filter(status__in=['warning', 'critical']).exclude(location=None))
        
    def _group_machines_by_region(self, machines):
        """
        Grupuje maszyny według regionów na podstawie lokalizacji
        Użyj prostej heurystyki bazującej na pierwszych cyfrach współrzędnych
        """
        regions = {}
        
        for machine in machines:
            if not machine.location:
                continue
                
            # Używamy pierwszych cyfr współrzędnych jako prostego wyznacznika regionu
            lat = float(machine.location.latitude)
            lng = float(machine.location.longitude)
            
            # Przykład prostej regionalizacji dla Polski
            if lat > 54:
                region = "Północ"
            elif lat > 52:
                region = "Centrum"
            else:
                region = "Południe"
                
            if region not in regions:
                regions[region] = []
                
            regions[region].append(machine)
            
        return regions
        
    def _optimize_route(self, machine_ids):
        """
        Wywołuje wewnętrzne API optymalizacji tras
        """
        try:
            # Przygotuj dane zapytania w formacie API
            data = {
                'machine_ids': machine_ids
            }
            
            # Użyj wewnętrznego wywołania API (alternatywnie można użyć bezpośrednio funkcji z views.py)
            # W prawdziwej implementacji lepiej użyć Django test client lub bezpośredniego wywołania funkcji
            response = requests.post(
                'http://localhost:8000/routes/optimize/',
                headers={'Content-Type': 'application/json'},
                data=json.dumps(data)
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                self.stdout.write(self.style.ERROR(f"Błąd podczas optymalizacji trasy: {response.text}"))
                return None
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Wyjątek podczas optymalizacji trasy: {str(e)}"))
            return None

#!/bin/bash

# Czekaj na dostępność bazy danych
echo "Czekanie na PostgreSQL..."
sleep 5

# Wykonaj migracje
echo "Wykonywanie migracji..."
python manage.py makemigrations collector
python manage.py migrate

# Ładowanie danych testowych
echo "Ładowanie danych testowych..."
python manage.py load_test_data

# Sprawdzenie stanu danych - używamy manage.py shell zamiast bezpośredniego wywołania Pythona
echo "Sprawdzam dane w bazie..."
python manage.py shell -c "
from collector.models import Route, RouteStop, User
from django.db import connection

print(f'Liczba tras w bazie danych: {Route.objects.count()}')
print('Przykładowe trasy:')
for route in Route.objects.all()[:3]:
    print(f' - {route.name} ({route.date}), technik: {route.technician.username}, przystanki: {route.routestop_set.count()}')

print(f'Liczba techników w bazie danych: {User.objects.filter(is_superuser=False).count()}')
for tech in User.objects.filter(is_superuser=False):
    print(f' - {tech.username} ({tech.first_name} {tech.last_name})')

# Wypisanie wszystkich tabel w bazie
cursor = connection.cursor()
cursor.execute('''
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
''')
tables = cursor.fetchall()
print('\\nTabele w bazie danych:')
for table in tables:
    print(f' - {table[0]}')
"

# Uruchom serwer
echo "Uruchamianie serwera Django..."
python manage.py runserver 0.0.0.0:8000

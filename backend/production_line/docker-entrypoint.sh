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

# Uruchom serwer
echo "Uruchamianie serwera Django..."
python manage.py runserver 0.0.0.0:8000

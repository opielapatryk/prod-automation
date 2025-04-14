#!/bin/bash

echo "Waiting for PostgreSQL..."
sleep 5

echo "Running migrations..."
python manage.py makemigrations collector
python manage.py migrate

echo "Loading test data..."
python manage.py load_test_data

echo "Starting Django server..."
python manage.py runserver 0.0.0.0:8000

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Stworzenie struktury katalogów
RUN mkdir -p /app/collector/templates/collector

# Kopiowanie i instalacja zależności
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Kopiowanie całej zawartości projektu
COPY . .

# Dodanie uprawnień wykonawczych dla skryptu startowego
RUN chmod +x /app/docker-entrypoint.sh

# Domyślne polecenie jest teraz definiowane w docker-compose.yaml
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
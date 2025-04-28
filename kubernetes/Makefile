.PHONY: build push deploy port-forward logs clean-pyc rebuild-image

# Set variables
DOCKER_IMAGE=patrykopiela/django-production-line
IMAGE_TAG=19.0

build:
	docker build -t $(DOCKER_IMAGE):$(IMAGE_TAG) ./backend/production_line

push:
	docker push $(DOCKER_IMAGE):$(IMAGE_TAG)

deploy:
	kubectl apply -f kubernetes/

port-forward:
	kubectl port-forward svc/django 8000:8000

logs:
	kubectl logs -f -l app=django

dev:
	docker-compose up

makemigrations:
	docker-compose exec django python manage.py makemigrations

migrate:
	docker-compose exec django python manage.py migrate

test:
	docker-compose exec django python manage.py test

shell:
	docker-compose exec django python manage.py shell

# Clean Python bytecode files that might be causing import problems
clean-pyc:
	docker-compose exec django find . -name "*.pyc" -delete
	docker-compose exec django find . -name "__pycache__" -delete

# Rebuild container from scratch (no cache)
rebuild-image:
	docker build --no-cache -t $(DOCKER_IMAGE):$(IMAGE_TAG) ../backend/production_line

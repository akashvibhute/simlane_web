#!/bin/bash

# Production Deployment Script for Simlane
# This script handles the deployment process on the VPS

set -e

cd /opt/simlane

echo "🚀 Starting Simlane deployment..."

# Create a backup before deployment
echo "Creating pre-deployment backup..."
docker compose -f docker-compose.production.yml run --rm postgres backup

# Pull latest code
echo "Pulling latest code..."
git pull origin master

# Pull updated Docker images
echo "Pulling updated Docker images..."
docker compose -f docker-compose.production.yml pull

# Start services with zero-downtime deployment
echo "Updating services..."
docker compose -f docker-compose.production.yml up -d --remove-orphans

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 10

# Run database migrations
echo "Running database migrations..."
docker compose -f docker-compose.production.yml exec -T django python manage.py migrate

# Collect static files
echo "Collecting static files..."
docker compose -f docker-compose.production.yml exec -T django python manage.py collectstatic --noinput

# Run Django system checks
echo "Running Django system checks..."
docker compose -f docker-compose.production.yml exec -T django python manage.py check --deploy

# Clean up unused Docker objects
echo "Cleaning up Docker system..."
docker system prune -f

echo "✅ Deployment completed successfully!"

# Show service status
echo "Current service status:"
docker compose -f docker-compose.production.yml ps

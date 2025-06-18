#!/bin/bash

# Health Check Script for Simlane Production
# This script checks if all services are running properly

set -e

cd /opt/simlane

echo "🔍 Checking Simlane production health..."

# Check if containers are running
echo "Checking container status..."
docker compose -f docker-compose.production.yml ps

# Check Django health
echo "Checking Django health..."
if docker compose -f docker-compose.production.yml exec -T django python manage.py check --deploy; then
    echo "✅ Django health check passed"
else
    echo "❌ Django health check failed"
    exit 1
fi

# Check database connectivity
echo "Checking database connectivity..."
if docker compose -f docker-compose.production.yml exec -T django python manage.py dbshell -c "SELECT 1;" > /dev/null 2>&1; then
    echo "✅ Database connectivity check passed"
else
    echo "❌ Database connectivity check failed"
    exit 1
fi

# Check Redis connectivity
echo "Checking Redis connectivity..."
if docker compose -f docker-compose.production.yml exec -T redis redis-cli ping | grep -q PONG; then
    echo "✅ Redis connectivity check passed"
else
    echo "❌ Redis connectivity check failed"
    exit 1
fi

# Check if website is accessible
echo "Checking website accessibility..."
if curl -f -s http://localhost > /dev/null; then
    echo "✅ Website is accessible"
else
    echo "❌ Website is not accessible"
    exit 1
fi

# Check disk space
echo "Checking disk space..."
df -h /

# Check memory usage
echo "Checking memory usage..."
free -h

# Check logs for errors
echo "Checking recent logs for errors..."
docker compose -f docker-compose.production.yml logs --tail=50 django | grep -i error || echo "No recent errors found"

echo "✅ All health checks passed!"

#!/bin/bash

# VPS Setup Script for Simlane Production Deployment
# Run this script on your Ubuntu VPS to prepare it for deployment

set -e

echo "🚀 Setting up VPS for Simlane deployment..."

# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y git curl

# Install Docker if not already installed
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
fi

# Install Docker Compose if not already installed
if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Create application directory
sudo mkdir -p /opt/simlane
sudo chown $USER:$USER /opt/simlane

# Clone repository
cd /opt/simlane
if [ ! -d ".git" ]; then
    git clone https://github.com/YOUR_USERNAME/simlane.git .
fi

# Create environment directories
mkdir -p .envs/.production

# Create production environment files (you'll need to fill these in)
cat > .envs/.production/.django << 'EOF'
# Django Settings
DJANGO_SECRET_KEY=your-super-secret-key-here
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# Database
DATABASE_URL=postgres://postgres:postgres@postgres:5432/simlane_production

# Email (configure your email provider)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.your-provider.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@domain.com
EMAIL_HOST_PASSWORD=your-email-password

# AWS S3 (if using S3 for static files)
DJANGO_AWS_ACCESS_KEY_ID=your-aws-access-key
DJANGO_AWS_SECRET_ACCESS_KEY=your-aws-secret-key
DJANGO_AWS_STORAGE_BUCKET_NAME=your-bucket-name
DJANGO_AWS_S3_CUSTOM_DOMAIN=your-cloudfront-domain.com

# Redis
REDIS_URL=redis://redis:6379/0

# Celery
CELERY_BROKER_URL=redis://redis:6379/0

# Discord Bot
DISCORD_BOT_TOKEN=your-discord-bot-token-here

# Discord OAuth (for allauth social login)
DISCORD_CLIENT_ID=your-discord-client-id-here
DISCORD_CLIENT_SECRET=your-discord-client-secret-here

# Garage61 OAuth (for allauth social login)
GARAGE61_CLIENT_ID=your-garage61-client-id-here
GARAGE61_CLIENT_SECRET=your-garage61-client-secret-here
EOF

cat > .envs/.production/.postgres << 'EOF'
# PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=simlane_production
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-secure-postgres-password
EOF

# Set up firewall
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw --force enable

# The backup directory is managed by Docker volumes (production_postgres_data_backups)
# No need to create it manually - it's handled by the existing backup system

# Set up log rotation
sudo tee /etc/logrotate.d/simlane << 'EOF'
/opt/simlane/logs/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 root root
}
EOF

echo "✅ VPS setup completed!"
echo ""
echo "Next steps:"
echo "1. Edit the environment files in .envs/.production/ with your actual values"
echo "2. Set up your domain DNS to point to this server"
echo "3. Configure GitHub Actions secrets"
echo "4. Push to master branch to trigger deployment"
echo ""
echo "GitHub Actions secrets to configure:"
echo "- VPS_HOST: $(curl -s ifconfig.me)"
echo "- VPS_USERNAME: $USER"
echo "- VPS_SSH_KEY: Your private SSH key content"
echo "- DOCKER_USERNAME: Your Docker Hub username"
echo "- DOCKER_PASSWORD: Your Docker Hub password"

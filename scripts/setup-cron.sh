#!/bin/bash

# Cron Setup Script for Simlane Production
# This script sets up automated backups and maintenance tasks

set -e

echo "⏰ Setting up automated maintenance tasks..."

# Create backup script that uses the existing postgres backup system
cat > /opt/simlane/scripts/automated-backup.sh << 'EOF'
#!/bin/bash
cd /opt/simlane
echo "$(date): Starting automated backup..." >> /var/log/simlane-backup.log
docker compose -f docker-compose.production.yml run --rm postgres backup >> /var/log/simlane-backup.log 2>&1
echo "$(date): Backup completed" >> /var/log/simlane-backup.log
EOF

chmod +x /opt/simlane/scripts/automated-backup.sh

# Create log cleanup script
cat > /opt/simlane/scripts/cleanup-logs.sh << 'EOF'
#!/bin/bash
cd /opt/simlane
# Clean up old backup files (keep last 30 days)
docker compose -f docker-compose.production.yml run --rm postgres sh -c 'find /backups -name "backup_*.sql.gz" -mtime +30 -delete'
# Clean up Docker logs
docker system prune -f --filter "until=24h"
EOF

chmod +x /opt/simlane/scripts/cleanup-logs.sh

# Add cron jobs
(crontab -l 2>/dev/null; echo "# Simlane automated backup - daily at 2 AM") | crontab -
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/simlane/scripts/automated-backup.sh") | crontab -
(crontab -l 2>/dev/null; echo "# Simlane cleanup - weekly on Sunday at 3 AM") | crontab -
(crontab -l 2>/dev/null; echo "0 3 * * 0 /opt/simlane/scripts/cleanup-logs.sh") | crontab -

# Create log file with proper permissions
sudo touch /var/log/simlane-backup.log
sudo chown $USER:$USER /var/log/simlane-backup.log

echo "✅ Cron jobs set up successfully!"
echo "Current cron jobs:"
crontab -l

echo ""
echo "Backup commands you can run manually:"
echo "- Create backup: docker compose -f docker-compose.production.yml run --rm postgres backup"
echo "- List backups: docker compose -f docker-compose.production.yml run --rm postgres backups"
echo "- Restore backup: docker compose -f docker-compose.production.yml run --rm postgres restore <backup_filename>"
echo "- Remove backup: docker compose -f docker-compose.production.yml run --rm postgres rmbackup <backup_filename>"

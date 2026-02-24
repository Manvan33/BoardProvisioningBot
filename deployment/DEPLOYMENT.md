# Production Deployment Guide

This guide covers deploying the Board Provisioning Bot on a Linux VM using systemd and nginx.

## Prerequisites

- Linux VM (Ubuntu 20.04+ or similar)
- Python 3.9+
- nginx
- systemd
- Domain name pointing to your server
- SSL certificate (Let's Encrypt recommended)

## Deployment Steps

### 1. Create Service User

```bash
# Create a dedicated user for the bot (if not exists)
sudo useradd -m -s /bin/bash deploy
# Or use existing deploy user
```

### 2. Install Application

```bash
# Switch to deploy user
sudo -u deploy -i

# Clone or copy application files
cd /home/deploy
git clone https://github.com/yourusername/BoardProvisioningBot.git
# Or: copy files to /home/deploy/BoardProvisioningBot

# Install uv or create virtual environment
cd /home/deploy/BoardProvisioningBot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
# Create .env file
sudo -u deploy nano /home/deploy/BoardProvisioningBot/.env
```

Add your configuration:
```env
BOT_TOKEN=your_bot_token_here
OAUTH_CLIENT_ID=your_oauth_client_id
OAUTH_CLIENT_SECRET=your_oauth_client_secret
OAUTH_REDIRECT_URI=https://your-domain.com/oauth/callback
```

Secure the file:
```bash
chmod 600 /home/deploy/BoardProvisioningBot/.env
```

### 4. Install Systemd Service

```bash
# Copy service file
sudo cp deployment/boardbot.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable boardbot

# Start the service
sudo systemctl start boardbot

# Check status
sudo systemctl status boardbot
```

### 5. Configure nginx

```bash
# Install nginx if not already installed
sudo apt update
sudo apt install nginx

# Copy nginx configuration
sudo cp deployment/nginx.conf /etc/nginx/sites-available/boardbot

# Update the configuration with your domain and SSL paths
sudo nano /etc/nginx/sites-available/boardbot

# Enable the site
sudo ln -s /etc/nginx/sites-available/boardbot /etc/nginx/sites-enabled/

# Test nginx configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### 6. SSL Certificate (Let's Encrypt)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d your-domain.com

# Certbot will automatically configure nginx for SSL
# Certificates will auto-renew
```

## Managing the Service

```bash
# Start the service
sudo systemctl start boardbot

# Stop the service
sudo systemctl stop boardbot

# Restart the service
sudo systemctl restart boardbot

# View logs
sudo journalctl -u boardbot -f

# View recent logs
sudo journalctl -u boardbot -n 100 --no-pager
```

## Monitoring

### View Logs

```bash
# Real-time logs
sudo journalctl -u boardbot -f

# Logs from today
sudo journalctl -u boardbot --since today

# Logs with specific priority
sudo journalctl -u boardbot -p err
```

### Check Service Status

```bash
sudo systemctl status boardbot
```

## Updating the Application

```bash
# Stop the service
sudo systemctl stop boardbot

# Switch to deploy user
sudo -u deploy -i

# Pull latest changes (if using git)
cd /home/deploy/BoardProvisioningBot
git pull

# Update dependencies
source .venv/bin/activate
pip install -r requirements.txt --upgrade

# Exit deploy user
exit

# Restart the service
sudo systemctl start boardbot

# Verify it's running
sudo systemctl status boardbot
```

## Troubleshooting

### Service won't start

```bash
# Check detailed logs
sudo journalctl -u boardbot -n 100 --no-pager

# Check file permissions
ls -la /home/deploy/BoardProvisioningBot/

# Verify environment file exists
sudo -u deploy cat /home/deploy/BoardProvisioningBot/.env
```

### nginx errors

```bash
# Test configuration
sudo nginx -t

# View error logs
sudo tail -f /var/log/nginx/boardbot_error.log

# View access logs
sudo tail -f /var/log/nginx/boardbot_access.log
```

### Connection issues

```bash
# Check if OAuth server port is listening
sudo netstat -tlnp | grep python

# Check firewall
sudo ufw status
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

## Security Best Practices

1. **Keep secrets secure**: Never commit `.env` files to git
2. **Use SSL/TLS**: Always use HTTPS in production
3. **Regular updates**: Keep Python packages and system updated
4. **Firewall**: Only expose necessary ports (80, 443)
5. **Backup data**: Regularly backup `bot_data.json`
6. **Monitor logs**: Set up log rotation and monitoring

## Additional Considerations

### Log Rotation

Systemd journal handles rotation automatically, but for nginx:

```bash
# nginx log rotation is typically configured at
sudo nano /etc/logrotate.d/nginx
```

### Backup Script

```bash
#!/bin/bash
# Save as /home/deploy/BoardProvisioningBot/backup.sh
BACKUP_DIR="/home/deploy/BoardProvisioningBot/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
cp /home/deploy/BoardProvisioningBot/bot_data.json $BACKUP_DIR/bot_data_$DATE.json

# Keep only last 30 days
find $BACKUP_DIR -name "bot_data_*.json" -mtime +30 -delete
```

Add to crontab:
```bash
sudo -u deploy crontab -e
# Add: 0 2 * * * /home/deploy/BoardProvisioningBot/backup.sh
```

## Notes on OAuth Redirect URI

Make sure your `OAUTH_REDIRECT_URI` in the `.env` file matches:
1. The domain configured in nginx
2. The OAuth configuration in your Webex integration settings
3. Should be: `https://your-domain.com/oauth/callback`

## Port Configuration

Check your `oauth_manager.py` to see what port the OAuth HTTP server uses (likely 8080), and ensure nginx's upstream configuration matches.

# WemX Admin Panel

A comprehensive web-based administration panel for WemX hosting management.

## 🎯 Features

- **Environment Editor** - Edit `/var/www/wemx/.env` via web interface
- **Nginx Configuration** - Edit `/etc/nginx/sites-available/wemx.conf` 
- **Configuration Management** - Edit admin panel settings and IP whitelist
- **License Manager** - Update WemX license with `php artisan license:update`
- **WemX Management** - Clear cache, restart services, fix permissions
- **User Management** - Create/delete/reset Ubuntu system users
- **System Monitoring** - Real-time service status monitoring
- **Security** - IP-based access control with auto-redirect

## 📋 System Requirements

### Operating System
- **Ubuntu 18.04+** (recommended)
- **Debian 10+** 
- **CentOS 8+** / **Rocky Linux 8+**
- Any Linux distribution with systemd support

### Hardware Requirements
- **CPU**: 1 core minimum (2+ cores recommended)
- **RAM**: 512MB minimum (1GB+ recommended)
- **Storage**: 2GB free space minimum
- **Network**: Internet connection required for license validation

## 🔧 Software Dependencies

### Required Software
```bash
# Core system packages
sudo apt update && sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    nginx \
    curl \
    wget \
    sudo \
    systemd
```

### WemX Requirements
- **WemX Installation** at `/var/www/wemx/`
- **PHP 8.0+** with PHP-FPM
- **Nginx** web server
- **WemX .env file** at `/var/www/wemx/.env`
- **Valid WemX License** (for license management features)

### Python Requirements
- **Python 3.7+** (3.8+ recommended)
- **pip3** package manager
- **venv** module for virtual environments

## 📦 Python Dependencies

### Core Dependencies (requirements.txt)
```txt
Flask==3.0.0
Werkzeug==3.0.1
Jinja2==3.1.2
MarkupSafe==2.1.3
itsdangerous==2.1.2
click==8.1.7
blinker==1.7.0
```

### Installation
```bash
cd /opt/wemx-admin
source venv/bin/activate
pip install -r requirements.txt
```

## 🔐 Required Permissions

### File Permissions
```bash
# Admin panel directory
sudo chown -R root:root /opt/wemx-admin
sudo chmod -R 755 /opt/wemx-admin
sudo chmod +x /opt/wemx-admin/wemx_app.py

# WemX .env file (read/write access)
sudo chmod 666 /var/www/wemx/.env
sudo chown www-data:www-data /var/www/wemx/.env

# Nginx configuration (read/write access)
sudo chmod 644 /etc/nginx/sites-available/wemx.conf
sudo chown root:www-data /etc/nginx/sites-available/wemx.conf

# Admin configuration file
sudo chmod 644 /opt/wemx-admin/wemx_config.py
sudo chown root:www-data /opt/wemx-admin/wemx_config.py
```

### Sudo Permissions
```bash
# Add to /etc/sudoers.d/wemx-admin
your-user ALL=(ALL) NOPASSWD: /usr/sbin/useradd
your-user ALL=(ALL) NOPASSWD: /usr/sbin/userdel
your-user ALL=(ALL) NOPASSWD: /usr/bin/passwd
your-user ALL=(ALL) NOPASSWD: /bin/systemctl restart nginx
your-user ALL=(ALL) NOPASSWD: /bin/systemctl reload nginx
your-user ALL=(ALL) NOPASSWD: /bin/systemctl restart php*-fpm
your-user ALL=(ALL) NOPASSWD: /bin/systemctl restart wemx-admin
your-user ALL=(ALL) NOPASSWD: /usr/sbin/nginx -t
```

## 🌐 Network Requirements

### Ports
- **5000/tcp** - WemX Admin Panel (default)
- **80/tcp** - HTTP (if using Nginx reverse proxy)
- **443/tcp** - HTTPS (if using SSL)

### Firewall Configuration
```bash
# Allow admin panel port
sudo ufw allow 5000/tcp

# Or restrict to specific networks
sudo ufw allow from 192.168.1.0/24 to any port 5000

# If using Nginx reverse proxy
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

### Internet Access
- Required for WemX license validation
- Required for IP detection features
- Required for downloading updates

## 📁 Directory Structure

```
/opt/wemx-admin/
├── wemx_app.py                 # Main Flask application
├── wemx_config.py              # Configuration settings  
├── requirements.txt            # Python dependencies
├── venv/                       # Python virtual environment
│   ├── bin/
│   ├── lib/
│   └── ...
├── templates/                  # HTML templates
│   ├── wemx_editor.html       # Environment editor
│   ├── nginx_editor.html      # Nginx config editor
│   ├── config_editor.html     # Admin config editor
│   ├── license_manager.html   # License management
│   └── wemx_commands.html     # Commands interface
└── logs/                      # Log files (optional)
```

## ⚙️ Configuration Requirements

### wemx_config.py
```python
# IP addresses allowed to access admin panel
WHITELISTED_IPS = [
    '127.0.0.1',        # localhost
    '::1',
     '92.25.173.186',         # localhost IPv6
    '192.168.1.100',    # Your IP address
    # Add more IPs as needed
]

# WemX installation path
WEMX_PATH = '/var/www/wemx'
WEMX_ENV_FILE = '/var/www/wemx/.env'

# Web server settings
WEB_SERVER = 'nginx'
PHP_VERSION = '8.1'  # Adjust to match your PHP version
```

### Environment Variables (Optional)
```bash
# Can be set in systemd service or shell
export FLASK_ENV=production
export FLASK_DEBUG=0
export WEMX_ADMIN_PORT=5000
export WEMX_ADMIN_HOST=0.0.0.0
```

## 🚀 Installation Steps

### 1. Prerequisites Check
```bash
# Check Python version
python3 --version  # Should be 3.7+

# Check if WemX exists
ls -la /var/www/wemx/

# Check if .env exists
ls -la /var/www/wemx/.env

# Check PHP version
php --version  # Should be 8.0+

# Check Nginx
nginx -v
```

### 2. Create Project Directory
```bash
sudo mkdir -p /opt/wemx-admin
cd /opt/wemx-admin
sudo chown -R $USER:$USER /opt/wemx-admin
```

### 3. Set Up Python Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
```

### 4. Install Dependencies
```bash
pip install Flask==3.0.0 Werkzeug==3.0.1 Jinja2==3.1.2 MarkupSafe==2.1.3 itsdangerous==2.1.2 click==8.1.7 blinker==1.7.0
```

### 5. Create Application Files
```bash
# Create directory structure
mkdir -p templates logs

# Create main files (copy content from provided artifacts)
touch wemx_app.py
touch wemx_config.py  
touch requirements.txt
touch templates/wemx_editor.html
touch templates/nginx_editor.html
touch templates/config_editor.html
touch templates/license_manager.html
touch templates/wemx_commands.html
```

### 6. Configure Permissions
```bash
# Set file permissions
sudo chmod -R 755 /opt/wemx-admin
sudo chmod +x /opt/wemx-admin/wemx_app.py

# Set WemX permissions
sudo chmod 666 /var/www/wemx/.env
sudo chmod 644 /etc/nginx/sites-available/wemx.conf

# Configure sudo access
sudo tee /etc/sudoers.d/wemx-admin << 'EOF'
root ALL=(ALL) NOPASSWD: /usr/sbin/useradd
root ALL=(ALL) NOPASSWD: /usr/sbin/userdel  
root ALL=(ALL) NOPASSWD: /usr/bin/passwd
root ALL=(ALL) NOPASSWD: /bin/systemctl restart nginx
root ALL=(ALL) NOPASSWD: /bin/systemctl reload nginx
root ALL=(ALL) NOPASSWD: /bin/systemctl restart php*-fpm
root ALL=(ALL) NOPASSWD: /bin/systemctl restart wemx-admin
root ALL=(ALL) NOPASSWD: /usr/sbin/nginx -t
EOF
```

### 7. Create Systemd Service
```bash
sudo tee /etc/systemd/system/wemx-admin.service << 'EOF'
[Unit]
Description=WemX Admin Panel
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/wemx-admin
Environment="PATH=/opt/wemx-admin/venv/bin"
ExecStart=/opt/wemx-admin/venv/bin/python wemx_app.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable wemx-admin
sudo systemctl start wemx-admin
```

## 🔍 Verification

### Check Service Status
```bash
sudo systemctl status wemx-admin
```

### Test Web Interface
```bash
curl http://localhost:5000
```

### Check Logs
```bash
sudo journalctl -u wemx-admin -f
```

### Verify Network Access
```bash
netstat -tlnp | grep 5000
```

## ⚠️ Common Issues

### Permission Denied Errors
```bash
# Fix file permissions
sudo chown -R root:root /opt/wemx-admin
sudo chmod -R 755 /opt/wemx-admin

# Fix WemX permissions  
sudo chmod 666 /var/www/wemx/.env
```

### Python Module Errors
```bash
# Reinstall requirements
cd /opt/wemx-admin
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

### Port Already in Use
```bash
# Find process using port 5000
sudo lsof -i :5000

# Kill process
sudo kill $(sudo lsof -t -i:5000)
```

### Service Won't Start
```bash
# Check detailed logs
sudo journalctl -u wemx-admin -n 50

# Test manual start
cd /opt/wemx-admin
source venv/bin/activate
python wemx_app.py
```

## 🔒 Security Considerations

### Access Control
- Configure IP whitelist in `wemx_config.py`
- Use strong passwords for system users
- Regularly review access logs
- Consider VPN access for remote administration

### File Security
- Restrict file permissions appropriately
- Regular security updates
- Monitor system logs
- Backup configuration files

### Network Security
- Use firewall rules to restrict access
- Consider SSL/TLS encryption
- Monitor network connections
- Use fail2ban for brute force protection

## 📞 Support

### Log Locations
- **Application Logs**: `sudo journalctl -u wemx-admin`
- **Nginx Logs**: `/var/log/nginx/error.log`
- **System Logs**: `/var/log/syslog`

### Debugging Commands
```bash
# Check service status
sudo systemctl status wemx-admin

# Check file permissions
ls -la /opt/wemx-admin/
ls -la /var/www/wemx/.env

# Test Python environment
cd /opt/wemx-admin && source venv/bin/activate && python -c "import flask; print('OK')"

# Check network connectivity
curl -I http://localhost:5000
```

## 📄 License

This admin panel is designed for WemX management. Ensure you have a valid WemX license for production use.

## 🔗 Access

Once installed and running, access the admin panel at:
- **Local**: http://localhost:5000
- **Remote**: http://your-server-ip:5000

## 📊 Monitoring

### Service Management
```bash
# Start/stop/restart
sudo systemctl start wemx-admin
sudo systemctl stop wemx-admin  
sudo systemctl restart wemx-admin

# View status and logs
sudo systemctl status wemx-admin
sudo journalctl -u wemx-admin -f
```

### Health Checks
- Service responds on port 5000
- No errors in system logs
- WemX .env file accessible
- Nginx configuration valid

---

**Version**: 1.0  
**Compatible with**: WemX 1.8+  
**Minimum PHP**: 8.0+  
**Minimum Python**: 3.7+

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
import subprocess
import shutil
from datetime import datetime
import re
import pwd
import grp
from wemx_config import WHITELISTED_IPS

app = Flask(__name__)
app.secret_key = 'wemx-secret-key-change-this'

ENV_FILE_PATH = '/var/www/wemx/.env'

def check_root_permissions():
    """Check if running with sufficient privileges"""
    return os.geteuid() == 0

def run_command_with_privileges(command, timeout=30, shell=True, cwd=None):
    """Run command with proper error handling and privileges"""
    try:
        if isinstance(command, str) and not shell:
            command = command.split()
        
        # Set a proper environment with PATH
        env = os.environ.copy()
        env['PATH'] = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
        
        result = subprocess.run(
            command, 
            shell=shell,
            capture_output=True, 
            text=True, 
            timeout=timeout,
            cwd=cwd,
            env=env  # Use proper environment
        )
        
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'stdout': '',
            'stderr': 'Command timed out',
            'returncode': -1
        }
    except Exception as e:
        return {
            'success': False,
            'stdout': '',
            'stderr': str(e),
            'returncode': -1
        }

def stop_nginx_service():
    """Stop nginx service"""
    return run_command_with_privileges(['/usr/bin/systemctl', 'stop', 'nginx'], shell=False, timeout=30)

def start_nginx_service():
    """Start nginx service"""  
    return run_command_with_privileges(['/usr/bin/systemctl', 'start', 'nginx'], shell=False, timeout=30)

def check_ip():
    """Check if the request IP is whitelisted"""
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    if client_ip not in WHITELISTED_IPS:
        return False
    return True

@app.before_request
def before_request():
    """Check IP whitelist and permissions before each request"""
    if not check_ip():
        return redirect('https://acd.swiftpeakhosting.com/')
    
    # Log permission status
    if not check_root_permissions():
        app.logger.warning("Application not running with root privileges - some functions may fail")

def parse_env_file(file_path):
    """Parse .env file into key-value pairs"""
    env_vars = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            env_vars[key.strip()] = value.strip()
        except PermissionError:
            app.logger.error(f"Permission denied reading {file_path}")
        except Exception as e:
            app.logger.error(f"Error parsing {file_path}: {str(e)}")
    return env_vars

def write_env_file(file_path, env_vars):
    """Write environment variables back to .env file"""
    try:
        # Create backup
        if os.path.exists(file_path):
            backup_path = f"{file_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(file_path, backup_path)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w') as f:
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")
        
        # Set proper ownership and permissions
        if check_root_permissions():
            # Get www-data user/group IDs
            www_data_user = pwd.getpwnam('www-data')
            os.chown(file_path, www_data_user.pw_uid, www_data_user.pw_gid)
            os.chmod(file_path, 0o644)
            
    except Exception as e:
        app.logger.error(f"Error writing {file_path}: {str(e)}")
        raise

@app.route('/')
def editor():
    """Main .env editor page"""
    env_vars = parse_env_file(ENV_FILE_PATH)
    return render_template('wemx_editor.html', env_vars=env_vars)

@app.route('/save-env', methods=['POST'])
def save_env():
    """Save .env file changes"""
    try:
        env_vars = {}
        form_data = request.form.to_dict()
        
        # Process form data
        for key, value in form_data.items():
            if key.startswith('key_'):
                index = key.split('_')[1]
                var_key = form_data.get(f'key_{index}', '').strip()
                var_value = form_data.get(f'value_{index}', '').strip()
                if var_key:  # Only add if key is not empty
                    env_vars[var_key] = var_value
        
        write_env_file(ENV_FILE_PATH, env_vars)
        flash('WemX environment file saved successfully!', 'success')
    except Exception as e:
        flash(f'Error saving file: {str(e)}', 'error')
    
    return redirect(url_for('editor'))

@app.route('/commands')
def commands():
    """Commands page for WemX management"""
    # Get list of system users for dropdown
    try:
        result = run_command_with_privileges(['/usr/bin/cut', '-d:', '-f1', '/etc/passwd'], shell=False)
        if result['success']:
            all_users = result['stdout'].strip().split('\n')
            # Filter to only show users with home directories
            system_users = []
            for user in all_users:
                home_dir = f'/home/{user}'
                if os.path.exists(home_dir):
                    system_users.append(user)
        else:
            system_users = []
    except:
        system_users = []
    
    return render_template('wemx_commands.html', system_users=system_users)

@app.route('/restart-wemx', methods=['POST'])
def restart_wemx():
    """Restart WemX services"""
    try:
        # Common WemX restart commands
        commands = [
            'cd /var/www/wemx && /usr/bin/php artisan config:cache',
            'cd /var/www/wemx && /usr/bin/php artisan route:cache', 
            'cd /var/www/wemx && /usr/bin/php artisan view:cache',
            '/usr/bin/systemctl restart nginx',
            '/usr/bin/systemctl restart php8.1-fpm',  # Adjust PHP version as needed
            '/usr/bin/systemctl restart php8.2-fpm'   # Alternative PHP version
        ]
        
        output = []
        success_count = 0
        
        for cmd in commands:
            result = run_command_with_privileges(cmd, timeout=30)
            output.append(f"Command: {cmd}")
            output.append(f"Output: {result['stdout']}")
            if result['stderr']:
                output.append(f"Error: {result['stderr']}")
            if result['success']:
                output.append("✅ Success")
                success_count += 1
            else:
                output.append("❌ Failed")
            output.append("---")
        
        # Fix WemX permissions after restart
        fix_wemx_permissions()
        
        return jsonify({
            'success': success_count > len(commands) // 2,  # Success if more than half commands succeeded
            'output': '\n'.join(output),
            'message': f'{success_count}/{len(commands)} commands executed successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/clear-cache', methods=['POST'])
def clear_cache():
    """Clear WemX cache"""
    try:
        commands = [
            '/usr/bin/php artisan cache:clear',
            '/usr/bin/php artisan config:clear',
            '/usr/bin/php artisan route:clear',
            '/usr/bin/php artisan view:clear'
        ]
        
        output = []
        success_count = 0
        
        for cmd in commands:
            result = run_command_with_privileges(cmd, cwd='/var/www/wemx')
            if result['success']:
                output.append(f"✅ {cmd}")
                success_count += 1
            else:
                output.append(f"❌ {cmd} - {result['stderr']}")
            
            if result['stderr'] and 'warning' in result['stderr'].lower():
                output.append(f"⚠️ Warning: {result['stderr']}")
        
        return jsonify({
            'success': success_count == len(commands),
            'output': '\n'.join(output) + f'\n\n🎉 WemX cache operations completed ({success_count}/{len(commands)} successful)!'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

def fix_wemx_permissions():
    """Fix WemX file permissions - internal function"""
    try:
        commands = [
            '/usr/bin/chown -R www-data:www-data /var/www/wemx',
            '/usr/bin/find /var/www/wemx -type f -exec chmod 644 {} \\;',
            '/usr/bin/find /var/www/wemx -type d -exec chmod 755 {} \\;',
            '/usr/bin/chmod -R 775 /var/www/wemx/storage',
            '/usr/bin/chmod -R 775 /var/www/wemx/bootstrap/cache',
            '/usr/bin/chmod -R 775 /var/www/wemx/public'
        ]
        
        for cmd in commands:
            run_command_with_privileges(cmd)
            
    except Exception as e:
        app.logger.error(f"Error fixing permissions: {str(e)}")

@app.route('/update-permissions', methods=['POST'])
def update_permissions():
    """Fix WemX file permissions"""
    try:
        if not check_root_permissions():
            return jsonify({
                'success': False,
                'error': 'Root privileges required for permission changes'
            })
        
        commands = [
            '/usr/bin/chown -R www-data:www-data /var/www/wemx',
            '/usr/bin/find /var/www/wemx -type f -exec chmod 644 {} \\;',
            '/usr/bin/find /var/www/wemx -type d -exec chmod 755 {} \\;',
            '/usr/bin/chmod -R 775 /var/www/wemx/storage',
            '/usr/bin/chmod -R 775 /var/www/wemx/bootstrap/cache',
            '/usr/bin/chmod -R 775 /var/www/wemx/public',
            '/usr/bin/chmod 600 /var/www/wemx/.env'
        ]
        
        output = []
        success_count = 0
        
        for cmd in commands:
            result = run_command_with_privileges(cmd, timeout=60)
            if result['success']:
                output.append(f"✅ {cmd}")
                success_count += 1
            else:
                output.append(f"❌ {cmd} - {result['stderr']}")
        
        return jsonify({
            'success': success_count == len(commands),
            'output': '\n'.join(output) + f'\n\n🔒 WemX permissions update completed ({success_count}/{len(commands)} successful)!'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/create-user', methods=['POST'])
def create_user():
    """Create Ubuntu system user"""
    try:
        if not check_root_permissions():
            return jsonify({
                'success': False, 
                'error': 'Root privileges required for user creation'
            })
            
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Username and password are required'})
        
        # Validate username
        if not re.match(r'^[a-z][a-z0-9_-]*$', username):
            return jsonify({'success': False, 'error': 'Invalid username format'})
        
        # Check if user already exists
        try:
            pwd.getpwnam(username)
            return jsonify({'success': False, 'error': f'User {username} already exists'})
        except KeyError:
            pass  # User doesn't exist, proceed with creation
        
        # Create user
        create_result = run_command_with_privileges(['/usr/sbin/useradd', '-m', '-s', '/bin/bash', username], shell=False)
        
        if not create_result['success']:
            return jsonify({'success': False, 'error': f'Failed to create user: {create_result["stderr"]}'})
        
        # Set password using chpasswd (more reliable)
        passwd_result = run_command_with_privileges(f'echo "{username}:{password}" | /usr/sbin/chpasswd')
        
        if not passwd_result['success']:
            # If password setting failed, remove the user
            run_command_with_privileges(['/usr/sbin/userdel', '-r', username], shell=False)
            return jsonify({'success': False, 'error': f'Failed to set password: {passwd_result["stderr"]}'})
        
        return jsonify({
            'success': True,
            'output': f'User {username} created successfully with home directory at /home/{username}'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/delete-user', methods=['POST'])
def delete_user():
    """Delete Ubuntu system user"""
    try:
        if not check_root_permissions():
            return jsonify({
                'success': False, 
                'error': 'Root privileges required for user deletion'
            })
            
        username = request.form.get('username', '').strip()
        
        if not username:
            return jsonify({'success': False, 'error': 'Username is required'})
        
        # Safety check - don't delete system users
        system_users = ['root', 'daemon', 'bin', 'sys', 'sync', 'games', 'man', 'lp', 
                       'mail', 'news', 'uucp', 'proxy', 'www-data', 'backup', 'list', 
                       'nobody', 'systemd-timesync', 'systemd-network', 'systemd-resolve',
                       'ubuntu', 'admin']
        
        if username in system_users:
            return jsonify({'success': False, 'error': 'Cannot delete system users'})
        
        # Check if user exists
        try:
            pwd.getpwnam(username)
        except KeyError:
            return jsonify({'success': False, 'error': f'User {username} does not exist'})
        
        result = run_command_with_privileges(['/usr/sbin/userdel', '-r', username], shell=False)
        
        if not result['success']:
            return jsonify({'success': False, 'error': f'Failed to delete user: {result["stderr"]}'})
        
        return jsonify({
            'success': True,
            'output': f'User {username} and home directory deleted successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/reset-password', methods=['POST'])
def reset_password():
    """Reset Ubuntu user password"""
    try:
        if not check_root_permissions():
            return jsonify({
                'success': False, 
                'error': 'Root privileges required for password reset'
            })
            
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Username and password are required'})
        
        # Check if user exists
        try:
            pwd.getpwnam(username)
        except KeyError:
            return jsonify({'success': False, 'error': f'User {username} does not exist'})
        
        # Set password using chpasswd
        result = run_command_with_privileges(f'echo "{username}:{password}" | /usr/sbin/chpasswd')
        
        if not result['success']:
            return jsonify({'success': False, 'error': f'Failed to reset password: {result["stderr"]}'})
        
        return jsonify({
            'success': True,
            'output': f'Password reset successfully for user {username}'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/nginx-config')
def nginx_config():
    """Nginx configuration editor"""
    nginx_file_path = '/etc/nginx/sites-available/wemx.conf'
    config_content = ""
    
    try:
        if os.path.exists(nginx_file_path):
            with open(nginx_file_path, 'r') as f:
                config_content = f.read()
    except Exception as e:
        flash(f'Error reading nginx config: {str(e)}', 'error')
    
    return render_template('nginx_editor.html', config_content=config_content)

@app.route('/save-nginx-config', methods=['POST'])
def save_nginx_config():
    """Save nginx configuration"""
    try:
        if not check_root_permissions():
            return jsonify({
                'success': False, 
                'error': 'Root privileges required for nginx configuration changes'
            })
            
        nginx_file_path = '/etc/nginx/sites-available/wemx.conf'
        config_content = request.form.get('config_content', '')
        
        # Create backup
        if os.path.exists(nginx_file_path):
            backup_path = f"{nginx_file_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(nginx_file_path, backup_path)
        
        # Write new config
        with open(nginx_file_path, 'w') as f:
            f.write(config_content)
        
        # Test configuration
        test_result = run_command_with_privileges(['/usr/sbin/nginx', '-t'], shell=False)
        
        if not test_result['success']:
            # Restore backup if test fails
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, nginx_file_path)
            return jsonify({
                'success': False, 
                'error': f'Configuration test failed: {test_result["stderr"]}'
            })
        
        return jsonify({'success': True, 'message': 'Nginx configuration saved and tested successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/test-nginx-config', methods=['POST'])
def test_nginx_config():
    """Test nginx configuration"""
    try:
        result = run_command_with_privileges(['/usr/sbin/nginx', '-t'], shell=False)
        
        return jsonify({
            'success': result['success'],
            'output': result['stdout'] + result['stderr'],
            'message': 'Nginx configuration is valid!' if result['success'] else 'Nginx configuration has errors!'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/reload-nginx', methods=['POST'])
def reload_nginx():
    """Reload nginx configuration"""
    try:
        if not check_root_permissions():
            return jsonify({
                'success': False, 
                'error': 'Root privileges required for nginx reload'
            })
            
        # Test config first
        test_result = run_command_with_privileges(['/usr/sbin/nginx', '-t'], shell=False)
        
        if not test_result['success']:
            return jsonify({
                'success': False,
                'error': f'Config test failed: {test_result["stderr"]}'
            })
        
        # Reload nginx
        reload_result = run_command_with_privileges(['/usr/bin/systemctl', 'reload', 'nginx'], shell=False)
        
        return jsonify({
            'success': reload_result['success'],
            'output': 'Nginx configuration reloaded successfully!' if reload_result['success'] else reload_result['stderr']
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# =====================================================
# CERTBOT ROUTES
# =====================================================

@app.route('/install-certbot', methods=['POST'])
def install_certbot():
    """Install Certbot and nginx plugin - Ubuntu version"""
    try:
        if not check_root_permissions():
            return jsonify({
                'success': False,
                'error': 'Root privileges required for certbot installation'
            })
        
        # Use full path to apt to avoid PATH issues
        update_cmd = '/usr/bin/apt update'
        install_cmd = '/usr/bin/apt install -y certbot python3-certbot-nginx'
        
        app.logger.info(f"Updating packages with: {update_cmd}")
        
        # Update packages first
        update_result = run_command_with_privileges(update_cmd, timeout=120)
        if not update_result['success']:
            return jsonify({
                'success': False,
                'error': 'Failed to update package lists',
                'output': f"Command: {update_cmd}\nSTDOUT: {update_result['stdout']}\nSTDERR: {update_result['stderr']}"
            })
        
        app.logger.info(f"Installing certbot with: {install_cmd}")
        
        # Install certbot and nginx plugin
        install_result = run_command_with_privileges(install_cmd, timeout=300)
        
        if install_result['success']:
            return jsonify({
                'success': True,
                'message': 'Certbot and nginx plugin installed successfully on Ubuntu',
                'output': update_result['stdout'] + '\n\n' + install_result['stdout']
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to install Certbot',
                'output': f"Command: {install_cmd}\nSTDOUT: {install_result['stdout']}\nSTDERR: {install_result['stderr']}"
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Installation failed: {str(e)}',
            'output': ''
        })

@app.route('/generate-certificate', methods=['POST'])
def generate_certificate():
    """Generate SSL certificate using Certbot"""
    try:
        if not check_root_permissions():
            return jsonify({
                'success': False,
                'error': 'Root privileges required for certificate generation'
            })
        
        domains = request.form.get('domains', '').strip()
        email = request.form.get('email', '').strip()
        
        if not domains or not email:
            return jsonify({
                'success': False,
                'error': 'Both domains and email are required',
                'output': ''
            })
        
        # Clean domain input (remove spaces, split by comma)
        domain_list = [d.strip() for d in domains.split(',') if d.strip()]
        domain_args = ' '.join([f'-d {domain}' for domain in domain_list])
        
        output_log = []
        
        # Stop nginx first
        app.logger.info("Stopping nginx service for certificate generation...")
        stop_result = stop_nginx_service()
        output_log.append(f"Stopping nginx:\n{stop_result['stdout']}\n{stop_result['stderr']}\n")
        
        # Generate certificate using standalone mode
        certbot_cmd = f'/usr/bin/certbot certonly --standalone {domain_args} --email {email} --agree-tos --non-interactive --expand'
        app.logger.info(f"Generating certificate: {certbot_cmd}")
        
        cert_result = run_command_with_privileges(certbot_cmd, timeout=300)
        output_log.append(f"Certificate generation:\n{cert_result['stdout']}\n{cert_result['stderr']}\n")
        
        # Start nginx again
        app.logger.info("Starting nginx service...")
        start_result = start_nginx_service()
        output_log.append(f"Starting nginx:\n{start_result['stdout']}\n{start_result['stderr']}")
        
        if cert_result['success']:
            return jsonify({
                'success': True,
                'message': f'SSL certificate generated successfully for: {", ".join(domain_list)}',
                'output': ''.join(output_log)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Certificate generation failed',
                'output': ''.join(output_log)
            })
            
    except Exception as e:
        # Make sure to start nginx even if there's an error
        try:
            start_nginx_service()
        except:
            pass
        return jsonify({
            'success': False,
            'error': f'Certificate generation failed: {str(e)}',
            'output': ''
        })

@app.route('/renew-certificates', methods=['POST'])
def renew_certificates():
    """Renew all SSL certificates"""
    try:
        if not check_root_permissions():
            return jsonify({
                'success': False,
                'error': 'Root privileges required for certificate renewal'
            })
        
        output_log = []
        
        # Stop nginx first
        app.logger.info("Stopping nginx for certificate renewal...")
        stop_result = stop_nginx_service()
        output_log.append(f"Stopping nginx:\n{stop_result['stdout']}\n{stop_result['stderr']}\n")
        
        # Renew certificates
        renew_result = run_command_with_privileges('/usr/bin/certbot renew --force-renewal', timeout=300)
        output_log.append(f"Certificate renewal:\n{renew_result['stdout']}\n{renew_result['stderr']}\n")
        
        # Start nginx again
        app.logger.info("Starting nginx service...")
        start_result = start_nginx_service()
        output_log.append(f"Starting nginx:\n{start_result['stdout']}\n{start_result['stderr']}")
        
        return jsonify({
            'success': renew_result['success'],
            'message': 'Certificate renewal completed' if renew_result['success'] else 'Certificate renewal failed',
            'output': ''.join(output_log)
        })
        
    except Exception as e:
        # Make sure to start nginx even if there's an error
        try:
            start_nginx_service()
        except:
            pass
        return jsonify({
            'success': False,
            'error': f'Certificate renewal failed: {str(e)}',
            'output': ''
        })

@app.route('/list-certificates', methods=['POST'])
def list_certificates():
    """List all SSL certificates"""
    try:
        list_result = run_command_with_privileges('/usr/bin/certbot certificates', timeout=30)
        
        return jsonify({
            'success': list_result['success'],
            'output': list_result['stdout'] + list_result['stderr'] if list_result['stdout'] or list_result['stderr'] else 'No certificates found or certbot not installed'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to list certificates: {str(e)}',
            'output': ''
        })

@app.route('/revoke-certificate', methods=['POST'])
def revoke_certificate():
    """Revoke SSL certificate"""
    try:
        if not check_root_permissions():
            return jsonify({
                'success': False,
                'error': 'Root privileges required for certificate revocation'
            })
        
        domain = request.form.get('domain', '').strip()
        
        if not domain:
            return jsonify({
                'success': False,
                'error': 'Domain name is required',
                'output': ''
            })
        
        output_log = []
        
        # Stop nginx first
        app.logger.info("Stopping nginx service...")
        stop_result = stop_nginx_service()
        output_log.append(f"Stopping nginx:\n{stop_result['stdout']}\n{stop_result['stderr']}\n")
        
        # Revoke certificate
        cert_path = f'/etc/letsencrypt/live/{domain}/cert.pem'
        revoke_cmd = f'/usr/bin/certbot revoke --cert-path {cert_path} --non-interactive'
        
        app.logger.info(f"Revoking certificate: {revoke_cmd}")
        revoke_result = run_command_with_privileges(revoke_cmd, timeout=120)
        output_log.append(f"Certificate revocation:\n{revoke_result['stdout']}\n{revoke_result['stderr']}\n")
        
        # Start nginx again
        app.logger.info("Starting nginx service...")
        start_result = start_nginx_service()
        output_log.append(f"Starting nginx:\n{start_result['stdout']}\n{start_result['stderr']}")
        
        if revoke_result['success']:
            return jsonify({
                'success': True,
                'message': f'Certificate for {domain} has been revoked',
                'output': ''.join(output_log)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Certificate revocation failed',
                'output': ''.join(output_log)
            })
            
    except Exception as e:
        # Make sure to start nginx even if there's an error
        try:
            start_nginx_service()
        except:
            pass
        return jsonify({
            'success': False,
            'error': f'Certificate revocation failed: {str(e)}',
            'output': ''
        })

@app.route('/check-certbot-status', methods=['POST'])
def check_certbot_status():
    """Check Certbot and system status"""
    try:
        output_log = []
        
        # Check system info
        uname_result = run_command_with_privileges('/usr/bin/uname -a', timeout=30)
        output_log.append(f"System Info:\n{uname_result['stdout']}\n")
        
        # Check Ubuntu version
        if os.path.exists('/etc/os-release'):
            try:
                with open('/etc/os-release', 'r') as f:
                    content = f.read()
                output_log.append(f"OS Release:\n{content}\n")
            except:
                pass
        
        # Check certbot version
        version_result = run_command_with_privileges('/usr/bin/certbot --version', timeout=30)
        output_log.append(f"Certbot Version:\n{version_result['stdout']}\n{version_result['stderr']}\n")
        
        # Check nginx status
        nginx_result = run_command_with_privileges('/usr/bin/systemctl status nginx --no-pager -l', timeout=30)
        output_log.append(f"Nginx Status:\n{nginx_result['stdout']}\n{nginx_result['stderr']}\n")
        
        # Check certificate expiry
        cert_check = run_command_with_privileges('/usr/bin/certbot certificates', timeout=30)
        output_log.append(f"Certificate Status:\n{cert_check['stdout']}\n{cert_check['stderr']}\n")
        
        # Check if certbot timer is active (auto-renewal)
        timer_result = run_command_with_privileges('/usr/bin/systemctl status certbot.timer --no-pager -l', timeout=30)
        output_log.append(f"Certbot Auto-renewal Timer:\n{timer_result['stdout']}\n{timer_result['stderr']}")
        
        return jsonify({
            'success': True,
            'output': ''.join(output_log)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Status check failed: {str(e)}',
            'output': ''
        })

# =====================================================
# ENHANCED NGINX MANAGEMENT ROUTES
# =====================================================

@app.route('/stop-nginx', methods=['POST'])
def stop_nginx():
    """Stop nginx service"""
    try:
        if not check_root_permissions():
            return jsonify({
                'success': False,
                'error': 'Root privileges required for nginx service control'
            })
        
        result = stop_nginx_service()
        
        return jsonify({
            'success': result['success'],
            'message': 'Nginx stopped successfully' if result['success'] else 'Failed to stop nginx',
            'output': result['stdout'] + result['stderr']
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to stop nginx: {str(e)}',
            'output': ''
        })

@app.route('/start-nginx', methods=['POST'])
def start_nginx():
    """Start nginx service"""
    try:
        if not check_root_permissions():
            return jsonify({
                'success': False,
                'error': 'Root privileges required for nginx service control'
            })
        
        result = start_nginx_service()
        
        return jsonify({
            'success': result['success'],
            'message': 'Nginx started successfully' if result['success'] else 'Failed to start nginx',
            'output': result['stdout'] + result['stderr']
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to start nginx: {str(e)}',
            'output': ''
        })

@app.route('/license')
def license_manager():
    """WemX license management page"""
    return render_template('license_manager.html')

@app.route('/update-license', methods=['POST'])
def update_license():
    """Update WemX license"""
    try:
        license_key = request.form.get('license_key', '').strip()
        
        if not license_key:
            return jsonify({'success': False, 'error': 'License key is required'})
        
        # Change to WemX directory and run artisan command
        result = run_command_with_privileges(f'echo "{license_key}" | /usr/bin/php artisan license:update', cwd='/var/www/wemx')
        
        output = result['stdout'] + result['stderr']
        
        return jsonify({
            'success': result['success'],
            'output': output,
            'message': 'License updated successfully!' if result['success'] else 'License update failed. Please check the output for details.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/check-license', methods=['POST'])
def check_license():
    """Check current WemX license status"""
    try:
        result = run_command_with_privileges(['/usr/bin/php', 'artisan', 'license:check'], shell=False, cwd='/var/www/wemx')
        
        output = result['stdout'] + result['stderr']
        
        return jsonify({
            'success': True,
            'output': output,
            'valid': result['success']
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/config-editor')
def config_editor():
    """Configuration file editor"""
    config_file_path = '/opt/wemx-admin/wemx_config.py'
    config_content = ""
    
    try:
        if os.path.exists(config_file_path):
            with open(config_file_path, 'r') as f:
                config_content = f.read()
    except Exception as e:
        flash(f'Error reading config file: {str(e)}', 'error')
    
    return render_template('config_editor.html', config_content=config_content)

@app.route('/save-config', methods=['POST'])
def save_config():
    """Save configuration file"""
    try:
        config_file_path = '/opt/wemx-admin/wemx_config.py'
        config_content = request.form.get('config_content', '')
        
        # Create backup
        if os.path.exists(config_file_path):
            backup_path = f"{config_file_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(config_file_path, backup_path)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(config_file_path), exist_ok=True)
        
        # Write new config
        with open(config_file_path, 'w') as f:
            f.write(config_content)
        
        # Set proper permissions
        if check_root_permissions():
            os.chmod(config_file_path, 0o600)  # Secure permissions
        
        return jsonify({'success': True, 'message': 'Configuration saved successfully! Restart the admin panel to apply changes.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/test-config', methods=['POST'])
def test_config():
    """Test configuration syntax"""
    try:
        config_content = request.form.get('config_content', '')
        
        # Create temporary file to test syntax
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
            temp_file.write(config_content)
            temp_file_path = temp_file.name
        
        # Try to compile the Python code
        try:
            with open(temp_file_path, 'r') as f:
                compile(f.read(), temp_file_path, 'exec')
            
            # Try to import and check required variables
            import importlib.util
            spec = importlib.util.spec_from_file_location("test_config", temp_file_path)
            test_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(test_module)
            
            # Check for required variables
            required_vars = ['WHITELISTED_IPS']
            missing_vars = []
            for var in required_vars:
                if not hasattr(test_module, var):
                    missing_vars.append(var)
            
            if missing_vars:
                return jsonify({
                    'success': False,
                    'error': f'Missing required variables: {", ".join(missing_vars)}'
                })
            
            # Check WHITELISTED_IPS format
            if not isinstance(test_module.WHITELISTED_IPS, list):
                return jsonify({
                    'success': False,
                    'error': 'WHITELISTED_IPS must be a list'
                })
            
            return jsonify({
                'success': True,
                'message': 'Configuration syntax is valid!'
            })
            
        except SyntaxError as e:
            return jsonify({
                'success': False,
                'error': f'Syntax error: {str(e)}'
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Configuration error: {str(e)}'
            })
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/restart-admin', methods=['POST'])
def restart_admin():
    """Restart the admin panel service"""
    try:
        if not check_root_permissions():
            return jsonify({
                'success': False, 
                'error': 'Root privileges required for service restart'
            })
            
        result = run_command_with_privileges(['/usr/bin/systemctl', 'restart', 'wemx-admin'], shell=False)
        
        return jsonify({
            'success': result['success'],
            'output': 'Admin panel service restart initiated. Please refresh the page in a few seconds.' if result['success'] else result['stderr']
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/status')
def status():
    """WemX system status check"""
    try:
        # Check if WemX directory exists and is accessible
        wemx_status = os.path.exists('/var/www/wemx') and os.access('/var/www/wemx', os.R_OK)
        
        # Check if .env file exists
        env_status = os.path.exists(ENV_FILE_PATH)
        
        # Check web server status
        nginx_result = run_command_with_privileges(['/usr/bin/systemctl', 'is-active', 'nginx'], shell=False)
        nginx_status = nginx_result['success'] and nginx_result['stdout'].strip() == 'active'
        
        # Check PHP-FPM status (common versions)
        php_versions = ['8.2', '8.1', '8.0', '7.4']
        php_status = False
        active_php_version = None
        
        for version in php_versions:
            result = run_command_with_privileges(['/usr/bin/systemctl', 'is-active', f'php{version}-fpm'], shell=False)
            if result['success'] and result['stdout'].strip() == 'active':
                php_status = True
                active_php_version = version
                break
        
        # Check root privileges
        root_status = check_root_permissions()
        
        return jsonify({
            'wemx_directory': wemx_status,
            'env_file': env_status,
            'nginx': nginx_status,
            'php_fpm': php_status,
            'php_version': active_php_version,
            'root_privileges': root_status,
            'overall_status': all([wemx_status, env_status, nginx_status, php_status, root_status])
        })
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    # Check if running as root
    if not check_root_permissions():
        print("WARNING: Not running as root. Some functionality may be limited.")
        print("For full functionality, run as root or configure proper sudo permissions.")
    
    # Ensure WemX permissions are correct on startup
    if check_root_permissions():
        fix_wemx_permissions()
    
    app.run(host='0.0.0.0', port=5000, debug=False)  # Disable debug in production

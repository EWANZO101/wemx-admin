from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
import subprocess
import shutil
from datetime import datetime
import re
from wemx_config import WHITELISTED_IPS

app = Flask(__name__)
app.secret_key = 'wemx-secret-key-change-this'

ENV_FILE_PATH = '/var/www/wemx/.env'

def check_ip():
    """Check if the request IP is whitelisted"""
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    if client_ip not in WHITELISTED_IPS:
        return False
    return True

@app.before_request
def before_request():
    """Check IP whitelist before each request"""
    if not check_ip():
        return redirect('https://acd.swiftpeakhosting.com/')

def parse_env_file(file_path):
    """Parse .env file into key-value pairs"""
    env_vars = {}
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
    return env_vars

def write_env_file(file_path, env_vars):
    """Write environment variables back to .env file"""
    # Create backup
    if os.path.exists(file_path):
        backup_path = f"{file_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(file_path, backup_path)
    
    with open(file_path, 'w') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")

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
        result = subprocess.run(['cut', '-d:', '-f1', '/etc/passwd'], 
                              capture_output=True, text=True)
        all_users = result.stdout.strip().split('\n')
        # Filter to only show users with home directories
        system_users = []
        for user in all_users:
            home_dir = f'/home/{user}'
            if os.path.exists(home_dir):
                system_users.append(user)
    except:
        system_users = []
    
    return render_template('wemx_commands.html', system_users=system_users)

@app.route('/restart-wemx', methods=['POST'])
def restart_wemx():
    """Restart WemX services"""
    try:
        # Common WemX restart commands
        commands = [
            'cd /var/www/wemx && php artisan config:cache',
            'cd /var/www/wemx && php artisan route:cache', 
            'cd /var/www/wemx && php artisan view:cache',
            'sudo systemctl restart nginx',
            'sudo systemctl restart php8.1-fpm'  # Adjust PHP version as needed
        ]
        
        output = []
        for cmd in commands:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            output.append(f"Command: {cmd}")
            output.append(f"Output: {result.stdout}")
            if result.stderr:
                output.append(f"Error: {result.stderr}")
            output.append("---")
        
        return jsonify({
            'success': True,
            'output': '\n'.join(output)
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
            'cd /var/www/wemx && php artisan cache:clear',
            'cd /var/www/wemx && php artisan config:clear',
            'cd /var/www/wemx && php artisan route:clear',
            'cd /var/www/wemx && php artisan view:clear'
        ]
        
        output = []
        for cmd in commands:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            output.append(f"✅ {cmd.split(' && ')[1]}")
            if result.stderr:
                output.append(f"⚠️ Warning: {result.stderr}")
        
        return jsonify({
            'success': True,
            'output': '\n'.join(output) + '\n\n🎉 WemX cache cleared successfully!'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/update-permissions', methods=['POST'])
def update_permissions():
    """Fix WemX file permissions"""
    try:
        commands = [
            'sudo chown -R www-data:www-data /var/www/wemx',
            'sudo chmod -R 755 /var/www/wemx',
            'sudo chmod -R 777 /var/www/wemx/storage',
            'sudo chmod -R 777 /var/www/wemx/bootstrap/cache'
        ]
        
        output = []
        for cmd in commands:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            output.append(f"✅ {cmd}")
            if result.stderr:
                output.append(f"⚠️ {result.stderr}")
        
        return jsonify({
            'success': True,
            'output': '\n'.join(output) + '\n\n🔒 WemX permissions updated successfully!'
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
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Username and password are required'})
        
        # Validate username
        if not re.match(r'^[a-z][a-z0-9_-]*$', username):
            return jsonify({'success': False, 'error': 'Invalid username format'})
        
        # Create user
        create_result = subprocess.run(['sudo', 'useradd', '-m', '-s', '/bin/bash', username], 
                                     capture_output=True, text=True)
        
        if create_result.returncode != 0:
            return jsonify({'success': False, 'error': f'Failed to create user: {create_result.stderr}'})
        
        # Set password
        passwd_process = subprocess.Popen(['sudo', 'passwd', username], 
                                        stdin=subprocess.PIPE, 
                                        stdout=subprocess.PIPE, 
                                        stderr=subprocess.PIPE, 
                                        text=True)
        
        stdout, stderr = passwd_process.communicate(input=f'{password}\n{password}\n')
        
        if passwd_process.returncode != 0:
            # If password setting failed, remove the user
            subprocess.run(['sudo', 'userdel', '-r', username], capture_output=True)
            return jsonify({'success': False, 'error': f'Failed to set password: {stderr}'})
        
        return jsonify({
            'success': True,
            'output': f'User {username} created successfully'
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
        username = request.form.get('username', '').strip()
        
        if not username:
            return jsonify({'success': False, 'error': 'Username is required'})
        
        # Safety check - don't delete system users
        system_users = ['root', 'daemon', 'bin', 'sys', 'sync', 'games', 'man', 'lp', 
                       'mail', 'news', 'uucp', 'proxy', 'www-data', 'backup', 'list', 
                       'nobody', 'systemd-timesync', 'systemd-network', 'systemd-resolve']
        
        if username in system_users:
            return jsonify({'success': False, 'error': 'Cannot delete system users'})
        
        result = subprocess.run(['sudo', 'userdel', '-r', username], 
                              capture_output=True, text=True)
        
        if result.returncode != 0:
            return jsonify({'success': False, 'error': f'Failed to delete user: {result.stderr}'})
        
        return jsonify({
            'success': True,
            'output': f'User {username} deleted successfully'
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
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Username and password are required'})
        
        # Set password
        passwd_process = subprocess.Popen(['sudo', 'passwd', username], 
                                        stdin=subprocess.PIPE, 
                                        stdout=subprocess.PIPE, 
                                        stderr=subprocess.PIPE, 
                                        text=True)
        
        stdout, stderr = passwd_process.communicate(input=f'{password}\n{password}\n')
        
        if passwd_process.returncode != 0:
            return jsonify({'success': False, 'error': f'Failed to reset password: {stderr}'})
        
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
        nginx_file_path = '/etc/nginx/sites-available/wemx.conf'
        config_content = request.form.get('config_content', '')
        
        # Create backup
        if os.path.exists(nginx_file_path):
            backup_path = f"{nginx_file_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(nginx_file_path, backup_path)
        
        # Write new config
        with open(nginx_file_path, 'w') as f:
            f.write(config_content)
        
        return jsonify({'success': True, 'message': 'Nginx configuration saved successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/test-nginx-config', methods=['POST'])
def test_nginx_config():
    """Test nginx configuration"""
    try:
        result = subprocess.run(['sudo', 'nginx', '-t'], 
                              capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return jsonify({
                'success': True,
                'output': result.stdout + result.stderr,
                'message': 'Nginx configuration is valid!'
            })
        else:
            return jsonify({
                'success': False,
                'output': result.stdout + result.stderr,
                'error': 'Nginx configuration has errors!'
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/reload-nginx', methods=['POST'])
def reload_nginx():
    """Reload nginx configuration"""
    try:
        # Test config first
        test_result = subprocess.run(['sudo', 'nginx', '-t'], 
                                   capture_output=True, text=True, timeout=30)
        
        if test_result.returncode != 0:
            return jsonify({
                'success': False,
                'error': f'Config test failed: {test_result.stderr}'
            })
        
        # Reload nginx
        reload_result = subprocess.run(['sudo', 'systemctl', 'reload', 'nginx'], 
                                     capture_output=True, text=True, timeout=30)
        
        if reload_result.returncode == 0:
            return jsonify({
                'success': True,
                'output': 'Nginx configuration reloaded successfully!'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to reload nginx: {reload_result.stderr}'
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

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
        cmd = f'cd /var/www/wemx && echo "{license_key}" | php artisan license:update'
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
        
        output = result.stdout + result.stderr
        
        if result.returncode == 0:
            return jsonify({
                'success': True,
                'output': output,
                'message': 'License updated successfully!'
            })
        else:
            return jsonify({
                'success': False,
                'output': output,
                'error': 'License update failed. Please check the output for details.'
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/check-license', methods=['POST'])
def check_license():
    """Check current WemX license status"""
    try:
        # Run license check command
        result = subprocess.run(['php', 'artisan', 'license:check'], 
                              cwd='/var/www/wemx',
                              capture_output=True, text=True, timeout=30)
        
        output = result.stdout + result.stderr
        
        return jsonify({
            'success': True,
            'output': output,
            'valid': result.returncode == 0
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
        
        # Write new config
        with open(config_file_path, 'w') as f:
            f.write(config_content)
        
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
            os.unlink(temp_file_path)
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/restart-admin', methods=['POST'])
def restart_admin():
    """Restart the admin panel service"""
    try:
        # Try to restart the systemd service
        result = subprocess.run(['sudo', 'systemctl', 'restart', 'wemx-admin'], 
                              capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return jsonify({
                'success': True,
                'output': 'Admin panel service restart initiated. Please refresh the page in a few seconds.'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to restart service: {result.stderr}'
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
        nginx_status = subprocess.run(['systemctl', 'is-active', 'nginx'], 
                                    capture_output=True, text=True).stdout.strip() == 'active'
        
        # Check PHP-FPM status (common versions)
        php_versions = ['8.1', '8.0', '7.4']
        php_status = False
        for version in php_versions:
            if subprocess.run(['systemctl', 'is-active', f'php{version}-fpm'], 
                            capture_output=True, text=True).stdout.strip() == 'active':
                php_status = True
                break
        
        return jsonify({
            'wemx_directory': wemx_status,
            'env_file': env_status,
            'nginx': nginx_status,
            'php_fpm': php_status,
            'overall_status': all([wemx_status, env_status, nginx_status, php_status])
        })
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

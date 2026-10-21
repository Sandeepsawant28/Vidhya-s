#!/usr/bin/env python
"""
Vidya’s Liquor Loft - Standalone Desktop Launcher
Handles single-instance locking, automated migrations, local IP discovery,
Waitress WSGI server startup, and browser launch.
"""
import os
import sys
import socket
import threading
import time
import webbrowser
from pathlib import Path

# Dedicated local port to prevent duplicate instances from running
LOCK_PORT = 49152
_lock_socket = None

def acquire_single_instance_lock():
    """Ensures only one copy of the liquor shop application runs at a time."""
    global _lock_socket
    _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        _lock_socket.bind(('127.0.0.1', LOCK_PORT))
        _lock_socket.listen(1)
        return True
    except socket.error:
        return False

def get_lan_ip():
    """Finds the local network IP for staff phone access."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def main():
    # 1. Enforce Single-Instance Check
    if not acquire_single_instance_lock():
        print("=" * 60)
        print("Vidya’s Liquor Loft is ALREADY RUNNING on this computer!")
        print("Opening the counter register in your browser...")
        print("=" * 60)
        webbrowser.open('http://127.0.0.1:8000')
        time.sleep(2)
        sys.exit(0)

    # 2. Guarantee Data Directory Exists
    program_data = os.environ.get('PROGRAMDATA', r'C:\ProgramData')
    data_dir = os.environ.get('LIQUOR_SHOP_DATA_DIR', os.path.join(program_data, 'LiquorShop'))
    try:
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(os.path.join(data_dir, 'backups'), exist_ok=True)
        os.makedirs(os.path.join(data_dir, 'logs'), exist_ok=True)
    except Exception as e:
        print(f"Notice: Data directory fallback to home folder: {e}")

    # 3. Configure Django Settings
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liquor_shop.settings')
    
    # If running from a PyInstaller bundle, fix module search paths
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys._MEIPASS)
        sys.path.insert(0, str(base_dir))
    else:
        base_dir = Path(__file__).resolve().parent

    import django
    django.setup()

    # 4. Run Database Migrations Automatically
    print("=" * 60)
    print("  VIDYA'S LIQUOR LOFT - INITIALIZING LOCAL SERVER")
    print("=" * 60)
    print("Checking database schema and applying any pending migrations...")
    try:
        from django.core.management import call_command
        call_command('migrate', interactive=False)
        print("Database is ready and up to date.")
    except Exception as err:
        print(f"Database migration alert: {err}")

    # 5. Discover LAN IP for Phones
    lan_ip = get_lan_ip()
    phone_url = f"http://{lan_ip}:8000"

    print("-" * 60)
    print(f"  MAIN COUNTER URL (This PC) : http://127.0.0.1:8000")
    print(f"  STAFF PHONES URL (Shop Wi-Fi): {phone_url}")
    print("-" * 60)
    print("Tip: If Windows Firewall shows an alert, check 'Private networks'")
    print("and click 'Allow access' so phones can connect over shop Wi-Fi.")
    print("=" * 60)
    print("Starting background server. Press Ctrl+C in this window to stop.")

    # 6. Auto-Open Browser after Server Starts
    def open_browser():
        time.sleep(1.8)
        webbrowser.open('http://127.0.0.1:8000')

    threading.Thread(target=open_browser, daemon=True).start()

    # 7. Start Waitress Production WSGI Server
    from waitress import serve
    from liquor_shop.wsgi import application

    try:
        serve(
            application,
            host='0.0.0.0',
            port=8000,
            threads=6,
            channel_timeout=30,
            cleanup_interval=30
        )
    except KeyboardInterrupt:
        print("\nStopping server safely. Goodbye!")
        sys.exit(0)

if __name__ == '__main__':
    main()

import os
import shutil
import sqlite3
import time
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import ShopSettings, AuditLog

class Command(BaseCommand):
    help = "Safely backs up the SQLite database using SQLite's backup API and purges backups older than 30 days."

    def handle(self, *args, **options):
        self.stdout.write("Starting automated SQLite database backup...")
        data_dir = settings.DATA_DIR
        backup_dir = os.path.join(data_dir, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        source_db = settings.DATABASES['default']['NAME']
        if not os.path.exists(source_db):
            self.stderr.write(f"Source database file not found at: {source_db}")
            return

        # Output filename: shop_YYYY-MM-DD.db (or with time if multiple per day)
        timestamp_str = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        date_str = datetime.now().strftime('%Y-%m-%d')
        backup_filename = f"shop_{date_str}.db"
        dest_path = os.path.join(backup_dir, backup_filename)

        # 1. Execute safe online backup using SQLite backup API
        try:
            src_conn = sqlite3.connect(source_db)
            dst_conn = sqlite3.connect(dest_path)
            with dst_conn:
                src_conn.backup(dst_conn)
            dst_conn.close()
            src_conn.close()
            self.stdout.write(self.style.SUCCESS(f"Primary backup created: {dest_path}"))
        except Exception as e:
            self.stderr.write(f"Database backup failed: {e}")
            return

        # 2. Copy to secondary folder (e.g. USB drive or external directory set in Settings)
        try:
            shop_settings = ShopSettings.get_settings()
            sec_dir = shop_settings.secondary_backup_path.strip()
            if sec_dir and os.path.exists(sec_dir):
                sec_path = os.path.join(sec_dir, backup_filename)
                shutil.copy2(dest_path, sec_path)
                self.stdout.write(self.style.SUCCESS(f"Secondary backup saved to: {sec_path}"))
            elif sec_dir:
                self.stdout.write(self.style.WARNING(f"Secondary backup path not reachable: {sec_dir}"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Could not copy to secondary path: {e}"))

        # 3. Clean up backup files older than 30 days
        self.stdout.write("Cleaning up backups older than 30 days...")
        cutoff_time = time.time() - (30 * 86400)
        deleted_count = 0
        try:
            for fname in os.listdir(backup_dir):
                if fname.startswith("shop_") and fname.endswith(".db"):
                    fpath = os.path.join(backup_dir, fname)
                    if os.path.isfile(fpath):
                        if os.path.getmtime(fpath) < cutoff_time:
                            os.remove(fpath)
                            deleted_count += 1
                            self.stdout.write(f"Deleted old backup: {fname}")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Purge error: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Backup task finished. Purged {deleted_count} outdated backups."))

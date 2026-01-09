from django.apps import AppConfig


class PortfolioConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "portfolio"

    def ready(self):
        # Only run scheduler once when the app is ready
        import os
        import sys
        if os.environ.get('DJANGO_SETTINGS_MODULE') == 'config.settings':
            # Avoid starting scheduler during management commands like collectstatic.
            management_commands = {
                'collectstatic', 'migrate', 'makemigrations', 'shell', 'createsuperuser',
                'test', 'check', 'loaddata', 'dumpdata', 'flush'
            }
            if any(cmd in sys.argv for cmd in management_commands):
                return
            try:
                from apscheduler.schedulers.background import BackgroundScheduler
                from django.core.management import call_command
                import atexit
                
                # Check if scheduler is already running
                if not hasattr(self, '_scheduler_started'):
                    scheduler = BackgroundScheduler()
                    scheduler.add_job(
                        lambda: call_command('daily_networth_snapshot'),
                        'cron',
                        hour=0,  # Run at midnight
                        minute=0,  # Run at midnight
                        id='networth_snapshot_job'
                    )
                    scheduler.start()
                    self._scheduler_started = True
                    atexit.register(lambda: scheduler.shutdown())
                    print("Net worth snapshot scheduler started - will run daily at midnight")
            except Exception as e:
                print(f"Failed to start scheduler: {e}")

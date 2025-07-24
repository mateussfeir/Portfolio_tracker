from django.apps import AppConfig


class PortfolioConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "portfolio"

    def ready(self):
        from apscheduler.schedulers.background import BackgroundScheduler
        from django.core.management import call_command
        import atexit
        import os
        # Prevent scheduler from running multiple times in development (runserver reload)
        if os.environ.get('RUN_MAIN', None) != 'true':
            return
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            lambda: call_command('daily_networth_snapshot'),
            'interval',
            hours=6,
            next_run_time=None  # avoids running immediately on startup
        )
        scheduler.start()
        atexit.register(lambda: scheduler.shutdown())

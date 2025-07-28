from django.core.management.base import BaseCommand
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.base import STATE_RUNNING, STATE_STOPPED

class Command(BaseCommand):
    help = 'Check the status of the APScheduler'

    def handle(self, *args, **options):
        try:
            # Try to get the scheduler instance
            from portfolio.apps import PortfolioConfig
            app_config = PortfolioConfig()
            
            if hasattr(app_config, '_scheduler_started'):
                self.stdout.write(self.style.SUCCESS('✓ Scheduler is running'))
                self.stdout.write('  - Net worth snapshots will be taken every 6 hours')
                self.stdout.write('  - Next run will be 6 hours from the last execution')
            else:
                self.stdout.write(self.style.WARNING('⚠ Scheduler is not running'))
                self.stdout.write('  - This might be because the app is not fully loaded')
                self.stdout.write('  - Try restarting the Django application')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error checking scheduler: {e}'))
            
        # Show recent snapshots to verify functionality
        self.stdout.write('\nRecent snapshots:')
        try:
            from portfolio.models import NetWorthSnapshot
            recent_snapshots = NetWorthSnapshot.objects.all().order_by('-date')[:5]
            if recent_snapshots:
                for snapshot in recent_snapshots:
                    self.stdout.write(f'  {snapshot.user.username} - {snapshot.date}: ${snapshot.net_worth:,.2f}')
            else:
                self.stdout.write('  No snapshots found')
        except Exception as e:
            self.stdout.write(f'  Error fetching snapshots: {e}') 
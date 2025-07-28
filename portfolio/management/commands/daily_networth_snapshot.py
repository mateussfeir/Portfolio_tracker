from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from portfolio.models import NetWorthSnapshot
from portfolio.views import get_user_total_net_worth
from datetime import date, datetime

class Command(BaseCommand):
    help = 'Take daily net worth snapshot for all users'

    def handle(self, *args, **kwargs):
        User = get_user_model()
        today = date.today()
        users = User.objects.all()
        
        self.stdout.write(f'Starting net worth snapshots for {users.count()} users on {today}')
        
        success_count = 0
        error_count = 0
        
        for user in users:
            try:
                # Get current net worth
                net_worth = get_user_total_net_worth(user, 'USD')
                
                # Create or update snapshot
                snapshot, created = NetWorthSnapshot.objects.get_or_create(
                    user=user, date=today,
                    defaults={'net_worth': net_worth}
                )
                
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Created snapshot for {user.username}: ${net_worth:,.2f}')
                    )
                else:
                    # Update existing snapshot if value changed
                    if snapshot.net_worth != net_worth:
                        old_value = snapshot.net_worth
                        snapshot.net_worth = net_worth
                        snapshot.save()
                        self.stdout.write(
                            self.style.WARNING(f'↻ Updated snapshot for {user.username}: ${old_value:,.2f} → ${net_worth:,.2f}')
                        )
                    else:
                        self.stdout.write(f'  - {user.username}: ${net_worth:,.2f} (no change)')
                
                success_count += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Error processing {user.username}: {e}')
                )
                error_count += 1
        
        self.stdout.write(f'\nSummary: {success_count} successful, {error_count} errors')
        self.stdout.write(
            self.style.SUCCESS(f'Net worth snapshots completed at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        ) 
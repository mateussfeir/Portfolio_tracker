from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from portfolio.models import NetWorthSnapshot
from portfolio.views import get_user_total_net_worth
from datetime import date, datetime

class Command(BaseCommand):
    help = 'Test net worth snapshot functionality'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='Specific username to test')
        parser.add_argument('--force', action='store_true', help='Force create snapshot even if exists')

    def handle(self, *args, **options):
        User = get_user_model()
        today = date.today()
        username = options.get('username')
        force = options.get('force')
        
        if username:
            try:
                users = [User.objects.get(username=username)]
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'User "{username}" not found'))
                return
        else:
            users = User.objects.all()
        
        self.stdout.write(f'Testing snapshots for {len(users)} user(s) on {today}')
        
        for user in users:
            try:
                # Get current net worth
                net_worth = get_user_total_net_worth(user, 'USD')
                self.stdout.write(f'User: {user.username}, Net Worth: ${net_worth:,.2f}')
                
                # Check if snapshot already exists for today
                existing_snapshot = NetWorthSnapshot.objects.filter(user=user, date=today).first()
                
                if existing_snapshot and not force:
                    self.stdout.write(f'  → Snapshot already exists: ${existing_snapshot.net_worth:,.2f}')
                else:
                    if existing_snapshot and force:
                        old_value = existing_snapshot.net_worth
                        existing_snapshot.net_worth = net_worth
                        existing_snapshot.save()
                        self.stdout.write(
                            self.style.SUCCESS(f'  → Updated snapshot: ${old_value:,.2f} → ${net_worth:,.2f}')
                        )
                    else:
                        snapshot, created = NetWorthSnapshot.objects.get_or_create(
                            user=user, date=today,
                            defaults={'net_worth': net_worth}
                        )
                        if created:
                            self.stdout.write(
                                self.style.SUCCESS(f'  → Created new snapshot: ${net_worth:,.2f}')
                            )
                        else:
                            self.stdout.write(f'  → Snapshot already exists: ${snapshot.net_worth:,.2f}')
                            
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  → Error processing {user.username}: {e}')
                )
        
        # Show recent snapshots
        self.stdout.write('\nRecent snapshots:')
        recent_snapshots = NetWorthSnapshot.objects.all().order_by('-date')[:10]
        for snapshot in recent_snapshots:
            self.stdout.write(f'  {snapshot.user.username} - {snapshot.date}: ${snapshot.net_worth:,.2f}') 
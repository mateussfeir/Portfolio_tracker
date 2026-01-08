from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from portfolio.models import NetWorthSnapshot
from portfolio.views import get_user_total_net_worth
from datetime import date, timedelta
from django.utils import timezone

class Command(BaseCommand):
    help = 'Fill in missing daily snapshots for all users'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30, help='Number of days back to check for missing snapshots')
        parser.add_argument('--username', type=str, help='Specific username to process')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be created without actually creating snapshots')

    def handle(self, *args, **options):
        User = get_user_model()
        days_back = options.get('days', 30)
        username = options.get('username')
        dry_run = options.get('dry_run', False)
        
        if username:
            try:
                users = [User.objects.get(username=username)]
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'User "{username}" not found'))
                return
        else:
            users = User.objects.all()
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        self.stdout.write(f'Checking for missing snapshots from {start_date} to {end_date}')
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No snapshots will be created'))
        
        total_created = 0
        total_skipped = 0
        
        for user in users:
            self.stdout.write(f'\nProcessing user: {user.username}')
            
            # Get existing snapshots for this user in the date range
            existing_snapshots = NetWorthSnapshot.objects.filter(
                user=user,
                date__gte=start_date,
                date__lte=end_date
            ).values_list('date', flat=True)
            
            existing_dates = set(existing_snapshots)
            
            # Check each day in the range
            current_date = start_date
            user_created = 0
            user_skipped = 0
            
            while current_date <= end_date:
                if current_date not in existing_dates:
                    # Check if this is the user's first snapshot
                    existing_snapshots = NetWorthSnapshot.objects.filter(user=user)
                    
                    if existing_snapshots.exists():
                        # User has snapshots, create missing one
                        if not dry_run:
                            try:
                                net_worth = get_user_total_net_worth(user, 'USD')
                                NetWorthSnapshot.objects.create(
                                    user=user,
                                    date=current_date,
                                    net_worth=net_worth
                                )
                                self.stdout.write(
                                    self.style.SUCCESS(f'  ✓ Created snapshot for {current_date}: ${net_worth:,.2f}')
                                )
                                user_created += 1
                            except Exception as e:
                                self.stdout.write(
                                    self.style.ERROR(f'  ✗ Error creating snapshot for {current_date}: {e}')
                                )
                        else:
                            self.stdout.write(f'  → Would create snapshot for {current_date}')
                            user_created += 1
                    else:
                        # This is the user's first time - check if 45 minutes have passed since account creation
                        user_created_time = user.date_joined
                        current_time = timezone.now()
                        time_since_creation = current_time - user_created_time
                        
                        if time_since_creation > timedelta(minutes=10):
                            if not dry_run:
                                try:
                                    net_worth = get_user_total_net_worth(user, 'USD')
                                    NetWorthSnapshot.objects.create(
                                        user=user,
                                        date=current_date,
                                        net_worth=net_worth
                                    )
                                    self.stdout.write(
                                        self.style.SUCCESS(f'  ✓ Created first snapshot for {current_date}: ${net_worth:,.2f}')
                                    )
                                    user_created += 1
                                except Exception as e:
                                    self.stdout.write(
                                        self.style.ERROR(f'  ✗ Error creating first snapshot for {current_date}: {e}')
                                    )
                            else:
                                self.stdout.write(f'  → Would create first snapshot for {current_date}')
                                user_created += 1
                        else:
                            minutes_remaining = 45 - int(time_since_creation.total_seconds() / 60)
                            self.stdout.write(
                                self.style.WARNING(f'  ⏳ Skipping {current_date}: First snapshot in {minutes_remaining} minutes')
                            )
                            user_skipped += 1
                else:
                    user_skipped += 1
                
                current_date += timedelta(days=1)
            
            self.stdout.write(f'  Summary: {user_created} created, {user_skipped} skipped')
            total_created += user_created
            total_skipped += user_skipped
        
        self.stdout.write(f'\nOverall Summary: {total_created} snapshots created, {total_skipped} skipped')
        if dry_run:
            self.stdout.write(self.style.WARNING('This was a dry run - no actual changes were made'))

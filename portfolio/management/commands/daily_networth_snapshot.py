from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from portfolio.models import NetWorthSnapshot
from portfolio.views import get_user_total_net_worth
from datetime import date, datetime
from django.utils import timezone
from datetime import timedelta
import logging

# Set up logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Take daily net worth snapshot for all users'

    def handle(self, *args, **kwargs):
        User = get_user_model()
        today = date.today()
        users = User.objects.all()
        
        self.stdout.write(f'Starting daily net worth snapshots for {users.count()} users on {today}')
        logger.info(f'Daily snapshot job started for {users.count()} users on {today}')
        
        success_count = 0
        error_count = 0
        skipped_count = 0
        
        for user in users:
            try:
                # Check if this is the user's first snapshot
                existing_snapshots = NetWorthSnapshot.objects.filter(user=user)
                
                if existing_snapshots.exists():
                    # User has snapshots, create today's snapshot normally
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
                else:
                    # This is the user's first time - check if 45 minutes have passed since account creation
                    user_created_time = user.date_joined
                    current_time = timezone.now()
                    time_since_creation = current_time - user_created_time
                    
                    # Only create snapshot if more than 45 minutes have passed
                    if time_since_creation > timedelta(minutes=45):
                        net_worth = get_user_total_net_worth(user, 'USD')
                        NetWorthSnapshot.objects.create(
                            user=user, date=today,
                            net_worth=net_worth
                        )
                        self.stdout.write(
                            self.style.SUCCESS(f'✓ Created first snapshot for {user.username}: ${net_worth:,.2f}')
                        )
                        success_count += 1
                    else:
                        minutes_remaining = 45 - int(time_since_creation.total_seconds() / 60)
                        self.stdout.write(
                            self.style.WARNING(f'⏳ Skipping {user.username}: First snapshot in {minutes_remaining} minutes')
                        )
                        skipped_count += 1
                
            except Exception as e:
                error_msg = f'Error processing {user.username}: {e}'
                self.stdout.write(
                    self.style.ERROR(f'✗ {error_msg}')
                )
                logger.error(error_msg)
                error_count += 1
        
        summary_msg = f'Summary: {success_count} successful, {skipped_count} skipped (new users), {error_count} errors'
        self.stdout.write(f'\n{summary_msg}')
        logger.info(summary_msg)
        
        completion_msg = f'Net worth snapshots completed at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
        self.stdout.write(
            self.style.SUCCESS(completion_msg)
        )
        logger.info(completion_msg) 

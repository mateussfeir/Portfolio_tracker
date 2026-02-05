from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from portfolio.models import NetWorthSnapshot
from datetime import date
from decimal import Decimal

class Command(BaseCommand):
    help = 'Edit a specific user\'s net worth snapshot for a given date'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username')
        parser.add_argument('date', type=str, help='Date in YYYY-MM-DD format')
        parser.add_argument('net_worth', type=float, help='New net worth value')

    def handle(self, *args, **kwargs):
        username = kwargs['username']
        date_str = kwargs['date']
        net_worth = kwargs['net_worth']
        
        try:
            # Parse date
            snapshot_date = date.fromisoformat(date_str)
            
            # Get user
            User = get_user_model()
            user = User.objects.get(username=username)
            
            # Update existing snapshot only (creation disabled)
            snapshot = NetWorthSnapshot.objects.filter(user=user, date=snapshot_date).first()
            if snapshot is None:
                self.stdout.write(
                    self.style.ERROR(
                        f'No snapshot found for {username} on {date_str} (creation disabled)'
                    )
                )
                return

            old_value = snapshot.net_worth
            snapshot.net_worth = Decimal(str(net_worth))
            snapshot.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Updated snapshot for {username} on {date_str}: '
                    f'{old_value} → {net_worth}'
                )
            )
                
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'User "{username}" not found')
            )
        except ValueError as e:
            self.stdout.write(
                self.style.ERROR(f'Invalid date format: {e}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {e}')
            ) 

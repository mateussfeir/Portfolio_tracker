from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from portfolio.models import NetWorthSnapshot
from portfolio.views import get_user_total_net_worth
from datetime import date

class Command(BaseCommand):
    help = 'Take daily net worth snapshot for all users'

    def handle(self, *args, **kwargs):
        User = get_user_model()
        today = date.today()
        users = User.objects.all()
        for user in users:
            # You may want to skip inactive users, etc.
            net_worth = get_user_total_net_worth(user, 'USD')  # Or loop over currencies if needed
            NetWorthSnapshot.objects.get_or_create(
                user=user, date=today,
                defaults={'net_worth': net_worth}
            )
        self.stdout.write(self.style.SUCCESS('Daily net worth snapshots updated for all users.')) 
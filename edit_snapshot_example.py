# Example: How to edit a snapshot using Django shell
# Run this in Django shell: python manage.py shell

from portfolio.models import NetWorthSnapshot
from django.contrib.auth import get_user_model
from datetime import date
from decimal import Decimal

# Get your user
User = get_user_model()
user = User.objects.get(username='your_username')  # Replace with your username

# Get today's snapshot
today = date.today()
snapshot = NetWorthSnapshot.objects.get(user=user, date=today)

# Edit the net worth value (replace with the correct value)
snapshot.net_worth = Decimal('123456.78')  # Replace with correct value
snapshot.save()

print(f"Updated snapshot for {today}: {snapshot.net_worth}")

# Or edit a specific date
specific_date = date(2024, 1, 15)  # Replace with desired date
snapshot = NetWorthSnapshot.objects.get(user=user, date=specific_date)
snapshot.net_worth = Decimal('98765.43')  # Replace with correct value
snapshot.save()

print(f"Updated snapshot for {specific_date}: {snapshot.net_worth}") 
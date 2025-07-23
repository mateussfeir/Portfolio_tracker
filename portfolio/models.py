from django.db import models
from django.contrib.auth.models import User

class Asset(models.Model):
    ASSET_TYPE_CHOICES = [
        ('crypto', 'Crypto'),
        ('stock', 'Stock'),
        ('cash', 'Cash'),
        ('real_estate', 'Real Estate'),
        ('other', 'Other'),
    ]

    ticker = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=19, decimal_places=8)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=20, choices=ASSET_TYPE_CHOICES, default='crypto')
    currency = models.CharField(max_length=5, blank=True, null=True)  # For cash positions

    def __str__(self):
        return f"{self.ticker} ({self.amount})"

class NetWorthSnapshot(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    net_worth = models.DecimalField(max_digits=20, decimal_places=2)

    class Meta:
        unique_together = ('user', 'date')
        ordering = ['date']

    def __str__(self):
        return f"{self.user.username} - {self.date}: {self.net_worth}"

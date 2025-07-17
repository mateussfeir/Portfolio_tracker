from django.db import models
from django.contrib.auth.models import User

class Asset(models.Model):
    ASSET_TYPE_CHOICES = [
        ('crypto', 'Crypto'),
        ('stock', 'Stock'),
        ('cash', 'Cash'),
        ('other', 'Other'),
    ]

    ticker = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=19, decimal_places=8)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=10, choices=ASSET_TYPE_CHOICES, default='crypto')
    currency = models.CharField(max_length=5, blank=True, null=True)  # For cash positions

    def __str__(self):
        return f"{self.ticker} ({self.amount})"

from django.db import models
from django.contrib.auth.models import User

class Asset(models.Model):
    ASSET_TYPE_CHOICES = [
        ('crypto', 'Crypto'),
        ('stock', 'Stock'),
    ]

    ticker = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=19, decimal_places=2)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=10, choices=ASSET_TYPE_CHOICES, default='crypto')

    def __str__(self):
        return f"{self.ticker} ({self.amount})"

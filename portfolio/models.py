from django.db import models
from django.contrib.auth.models import User

class Asset(models.Model):
    ticker = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=19, decimal_places=2)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.ticker} ({self.amount})"

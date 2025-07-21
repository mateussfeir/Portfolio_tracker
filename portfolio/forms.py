from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Asset

CASH_CURRENCIES = [
    ('USD', 'US Dollar'),
    ('CAD', 'Canadian Dollar'),
    ('BRL', 'Brazilian Real'),
    ('KRW', 'Korean Won'),
    ('INR', 'Indian Rupee'),
    ('EUR', 'Euro'),
    ('GBP', 'British Pound'),
    ('JPY', 'Japanese Yen'),
    ('AUD', 'Australian Dollar'),
    ('CHF', 'Swiss Franc'),
]

class SignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'password1', 'password2')  # we have 2 passwords because we ask the user to input twice to be sure it was written correctly

class AddAssetForm(forms.ModelForm):
    currency = forms.ChoiceField(choices=CASH_CURRENCIES, required=False, initial='USD', label='Currency')

    class Meta:
        model = Asset
        fields = ['ticker', 'amount', 'currency']
        widgets = {
            'ticker': forms.TextInput(attrs={'placeholder': 'e.g. BTC or Cash for USD'}),
            'amount': forms.NumberInput(attrs={'placeholder': 'e.g. 1.5'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show currency field for cash assets (or always show, but only required for cash)
        # Optionally, you can hide for non-cash by JS in the template

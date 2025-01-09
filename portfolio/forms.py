from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Asset

class SignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'password1', 'password2')  # we have 2 passwords because we ask the user to input twice to be sure it was written correctly

class AddAssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = ['ticker', 'amount']
        widgets = {
            'ticker': forms.TextInput(attrs={'placeholder': 'e.g. BTC'}),
            'amount': forms.NumberInput(attrs={'placeholder': 'e.g. 1.5'}),
        }

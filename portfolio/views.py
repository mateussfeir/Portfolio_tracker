from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .forms import AddAssetForm, SignUpForm
from .models import Asset
from django.contrib.auth import login, authenticate
import requests
from django.shortcuts import render

def get_bitcoin_price():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data['bitcoin']['usd']
    except requests.exceptions.RequestException:
        return None

def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return redirect('home')  # Redirect to the homepage after signup
    else:
        form = SignUpForm()
    return render(request, 'signup.html', {'form': form})

@login_required
def home(request):
    # Fetch Bitcoin price
    bitcoin_price = get_bitcoin_price()

    # Handle form submission
    if request.method == 'POST':
        form = AddAssetForm(request.POST)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.owner = request.user  # Link the asset to the logged-in user
            asset.save()
            return redirect('home')  # Refresh the page after adding the asset
    else:
        form = AddAssetForm()

    # Fetch all crypto positions for the logged-in user
    user_assets = Asset.objects.filter(owner=request.user)
    return render(request, 'home.html', {
        'username': request.user.username,
        'assets': user_assets,
        'form': form,
        'bitcoin_price': bitcoin_price,  # Pass Bitcoin price to the template
    })
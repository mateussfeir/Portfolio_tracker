from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .forms import AddAssetForm, SignUpForm
from .models import Asset
from django.contrib.auth import login, authenticate
import requests
from decimal import Decimal

# Function to fetch the current price of a specific asset
def get_asset_price(ticker):
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ticker}&vs_currencies=usd"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get(ticker, {}).get('usd', None)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching price for {ticker}: {e}")  # Debugging output
        return None

def get_multiple_asset_prices(tickers):
    ids = ','.join(tickers)
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()  # Returns a dictionary with prices
    except requests.exceptions.RequestException as e:
        print(f"Error fetching prices: {e}")
        return {}

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
    # Handle form submission for adding assets
    if request.method == 'POST':
        form = AddAssetForm(request.POST)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.owner = request.user
            asset.save()
            return redirect('home')  # Refresh the page after adding the asset
    else:
        form = AddAssetForm()

    # Fetch all crypto positions for the logged-in user
    user_assets = Asset.objects.filter(owner=request.user)

    # Map user tickers to CoinGecko identifiers
    tickers = [COINGECKO_TICKER_MAPPING.get(asset.ticker.lower(), asset.ticker.lower()) for asset in user_assets]
    prices = get_multiple_asset_prices(tickers)  # Fetch prices for all mapped tickers

    # Calculate the worth for each asset
    assets_with_value = []
    for asset in user_assets:
        coin_id = COINGECKO_TICKER_MAPPING.get(asset.ticker.lower(), asset.ticker.lower())
        price = prices.get(coin_id, {}).get('usd')  # Fetch price from API response
        if price:
            price = Decimal(str(price))  # Convert price to Decimal for compatibility
        value = price * asset.amount if price else None
        assets_with_value.append({
            'ticker': asset.ticker,
            'amount': asset.amount,
            'value': value
        })

    # Fetch Bitcoin price for display (optional)
    bitcoin_price = prices.get('bitcoin', {}).get('usd')

    return render(request, 'home.html', {
        'username': request.user.username,
        'assets': assets_with_value,
        'form': form,
        'bitcoin_price': bitcoin_price,  # Pass Bitcoin price to the template
    })

COINGECKO_TICKER_MAPPING = {
    'btc': 'bitcoin',
    'eth': 'ethereum',
    'sol': 'solana',
    # Add more mappings as needed
}
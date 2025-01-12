from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .forms import AddAssetForm, SignUpForm
from .models import Asset
from django.contrib.auth import login, authenticate
import requests
from decimal import Decimal
import plotly.graph_objects as go

# Function to fetch prices for multiple tickers in one API call
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

# Signup view
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

    # Collect tickers for API call
    tickers = [COINGECKO_TICKER_MAPPING.get(asset.ticker.lower(), asset.ticker.lower()) for asset in user_assets]
    prices = get_multiple_asset_prices(tickers)  # Fetch prices for all tickers at once

    # Calculate the worth for each asset and total net worth
    total_net_worth = Decimal(0)
    assets_with_value = []
    labels = []  # For pie chart labels
    values = []  # For pie chart values (percentages)
    for asset in user_assets:
        coin_id = COINGECKO_TICKER_MAPPING.get(asset.ticker.lower(), asset.ticker.lower())
        price = prices.get(coin_id, {}).get('usd')
        if price is not None:
            price = Decimal(str(price))
        value = price * asset.amount if price else None
        total_net_worth += value if value else Decimal(0)
        assets_with_value.append({
            'ticker': asset.ticker,
            'amount': asset.amount,
            'value': value,
        })

    # Calculate percentage allocation for pie chart
    for asset in assets_with_value:
        if total_net_worth > 0 and asset['value']:
            percentage = (asset['value'] / total_net_worth) * 100
            asset['percentage'] = percentage
            labels.append(asset['ticker'])
            values.append(percentage)
        else:
            asset['percentage'] = None

    # Generate Pie Chart with Plotly
    fig = go.Figure(data=[go.Pie(labels=labels, values=values, textinfo='label+percent')])
    fig.update_layout(
        title="Crypto Portfolio Distribution",
        margin=dict(t=50, b=50, l=25, r=25),
        paper_bgcolor="#121212",  # Dark background for the entire chart
        plot_bgcolor="#121212",  # Dark background for the plot area
        font=dict(color="#e0e0e0")  # Light text color
    )
    chart_html = fig.to_html(full_html=False)  # Generate HTML snippet for the chart

    return render(request, 'home.html', {
        'username': request.user.username,
        'assets': assets_with_value,
        'form': form,
        'bitcoin_price': prices.get('bitcoin', {}).get('usd'),
        'total_net_worth': total_net_worth,
        'chart': chart_html,  # Pass the chart HTML to the template
    })

# Mapping user-friendly tickers to CoinGecko identifiers

COINGECKO_TICKER_MAPPING = {
    'btc': 'bitcoin',
    'eth': 'ethereum',
    'usdt': 'tether',
    'bnb': 'binancecoin',
    'sol': 'solana',
    'doge': 'dogecoin',
    'usdc': 'usd-coin',
    'ada': 'cardano',
    'steth': 'staked-ether',
    'trx': 'tron',
    'wsteth': 'wrapped-steth',
    'sui': 'sui',
    'ton': 'toncoin',
    'link': 'chainlink',
    'shiba': 'shiba-inu',
    'wbtc': 'wrapped-bitcoin',
    'xlm': 'stellar',
    'hbar': 'hedera-hashgraph',
    'dot': 'polkadot',
    'weth': 'weth',
    'bch': 'bitcoin-cash',
    'leo': 'leo-token',
    'ltc': 'litecoin',
    'uni': 'uniswap',
    'bgb': 'bitget-token',
    'pepe': 'pepecoin',
    'avax': 'avalanche-2',
    'apt': 'aptos',
    'aave': 'aave',
    'mnt': 'mantlenetwork',
    'pol': 'polygon',
    'cro': 'cronos',
    'etc': 'ethereum-classic',
    'render': 'render-token',
    'tao': 'bittensor',
    'om': 'mantra-dao',
    'vet': 'vechain',
    'xmr': 'monero',
    'tkx': 'tokenize-xchange',
    'fet': 'fetch-ai',
    'dai': 'dai',
    'virtual': 'virtuals-protocol',
    'arb': 'arbitrum',
    'xrp': 'ripple',
    'icp': 'internet-computer',
    'stg': 'stargate-finance',  # Added entry for STG
    'matic': 'polygon',         # Added entry for MATIC (Note: 'pol' already points to 'polygon')
    'algo': 'algorand',
}

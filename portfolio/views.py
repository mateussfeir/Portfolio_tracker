from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib import messages
from .forms import AddAssetForm, SignUpForm
from .models import Asset
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

# Helper function to map user-friendly tickers to CoinGecko identifiers
def map_ticker(ticker):
    return COINGECKO_TICKER_MAPPING.get(ticker.lower(), ticker.lower())

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
    if request.method == 'POST':
        form = AddAssetForm(request.POST)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.owner = request.user
            asset.save()
            return redirect('home')  # Refresh the page after adding the asset
        else:
            messages.error(request, "Failed to add asset. Please check your inputs.")
    else:
        form = AddAssetForm()

    # Get user assets
    user_assets = Asset.objects.filter(owner=request.user)
    tickers = ['bitcoin'] + [map_ticker(asset.ticker) for asset in user_assets]
    prices = get_multiple_asset_prices(tickers)

    # Fetch Bitcoin price explicitly
    bitcoin_price = prices.get('bitcoin', {}).get('usd', 'N/A')

    # Calculate total net worth
    total_net_worth = sum(
        (Decimal(str(prices.get(map_ticker(asset.ticker), {}).get('usd', 0))) * asset.amount)
        for asset in user_assets
    )

    # Populate assets and chart data
    assets_with_value = []
    labels = []
    values = []
    for asset in user_assets:
        coin_id = map_ticker(asset.ticker)
        price = prices.get(coin_id, {}).get('usd')  # Get price per token
        if price is not None:
            price = Decimal(str(price))
        value = price * asset.amount if price else None
        asset_dict = {
            'id': asset.id,
            'ticker': asset.ticker,
            'amount': asset.amount,
            'price': price if price else '-',  # Add price per token
            'value': value if value else '-',
        }
        if total_net_worth > 0 and value:
            percentage = (value / total_net_worth) * 100
            asset_dict['percentage'] = percentage
        else:
            asset_dict['percentage'] = '-'
        assets_with_value.append(asset_dict)

        # Prepare chart data
        if value and total_net_worth > 0:
            labels.append(asset.ticker)
            values.append(float(value / total_net_worth * 100))

    # Prepare pie chart
    if labels and values:
        fig = go.Figure(data=[go.Pie(labels=labels, values=values, textinfo='label+percent')])
        fig.update_layout(
            title="Crypto Portfolio Distribution",
            margin=dict(t=50, b=50, l=25, r=25),
            paper_bgcolor="#121212",
            plot_bgcolor="#121212",
            font=dict(color="#e0e0e0")
        )
        chart_html = fig.to_html(full_html=False)
    else:
        chart_html = None

    # Render the page
    return render(request, 'home.html', {
        'username': request.user.username,
        'assets': assets_with_value,
        'form': form,
        'bitcoin_price': bitcoin_price,  # Pass the Bitcoin price to the template
        'total_net_worth': total_net_worth,
        'chart': chart_html,
    })

@login_required
def delete_holding(request, pk):
    asset = get_object_or_404(Asset, pk=pk, owner=request.user)  # Ensures that only the asset owner can delete it
    asset.delete()
    messages.success(request, "Asset deleted successfully.")
    return redirect('home')  # Redirect back to the homepage after deletion

def root_redirect(request):
    if request.user.is_authenticated:
        return redirect('home')  # Redirect to 'home' if the user is logged in
    else:
        return redirect('login')  # Redirect to 'login' if the user is not logged in

def resume(request):
    return render(request, 'resume.html')


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
    'pepe': 'pepe',
    'avax': 'avalanche-2',
    'apt': 'aptos',
    'aave': 'aave',
    'mnt': 'mantlenetwork',
    'pol': 'polygon',
    'cro': 'crypto-com-chain',
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
    'stg': 'stargate-finance',
    'matic': 'polygon',
    'algo': 'algorand',
    'cash' : 'tether',
    'trump' : 'official-trump',
    'opul' : 'opulous',
    'memag': 'meta-masters-guild-games',
    'ray': 'raydium',
    'daddy': 'daddy-tate',
    'kas': 'kaspa',
    'egld': 'multiversx',
    'mina': 'mina-protocol',
    'croge': 'crogecoin',
    'brett' : 'brett-2',
}

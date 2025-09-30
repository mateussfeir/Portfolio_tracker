from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib import messages
from .forms import AddAssetForm, SignUpForm
from .models import Asset, NetWorthSnapshot
import requests
from decimal import Decimal, InvalidOperation
import plotly.graph_objects as go
from django.shortcuts import render
import yfinance as yf
from django.urls import reverse
from django.http import HttpResponseRedirect
from datetime import date
import time
import threading
from django.core.cache import cache
from django.utils import timezone
import re
from datetime import timedelta
from django.db.models import Max
from django.db.models.functions import TruncDate

# Currency conversion function
_exchange_rate_cache = {}
_exchange_rate_cache_time = {}
_exchange_rate_cache_lock = threading.Lock()
CACHE_TTL_SECONDS = 180  # 3 minutes

def get_exchange_rates(base_currency='USD'):
    """Get exchange rates from USD to other currencies using a free API, with 3-minute cache."""
    now = time.time()
    cache_key = base_currency
    with _exchange_rate_cache_lock:
        if (
            cache_key in _exchange_rate_cache and
            (now - _exchange_rate_cache_time.get(cache_key, 0)) < CACHE_TTL_SECONDS
        ):
            return _exchange_rate_cache[cache_key]
    try:
        # Using exchangerate-api.com (free tier)
        url = f"https://api.exchangerate-api.com/v4/latest/{base_currency}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        rates = data.get('rates', {})
        with _exchange_rate_cache_lock:
            _exchange_rate_cache[cache_key] = rates
            _exchange_rate_cache_time[cache_key] = now
        return rates
    except Exception as e:
        print(f"Error fetching exchange rates: {e}")
        # Fallback rates (approximate)
        fallback = {
            'USD': 1,
            'CAD': 1.35,
            'BRL': 52,
            'KRW': 1300,
            'INR': 83,
            'EUR': 0.92,
            'GBP': 0.79,
            'JPY': 150,
            'AUD': 10.52,
            'CHF': 0.88
        }
        with _exchange_rate_cache_lock:
            _exchange_rate_cache[cache_key] = fallback
            _exchange_rate_cache_time[cache_key] = now
        return fallback

def convert_currency(amount, from_currency='USD', to_currency='USD'):
    """Convert amount from one currency to another"""
    if from_currency == to_currency:
        return amount
    
    rates = get_exchange_rates(from_currency)
    if to_currency in rates:
        # Convert the rate to Decimal to avoid type mismatch
        rate = Decimal(str(rates[to_currency]))
        return amount * rate
    return amount

# Simple in-memory cache for crypto prices
_crypto_price_cache = {}
_crypto_price_cache_time = {}

# Function to fetch prices for multiple tickers in one API call
# Now with 3-minute cache
CACHE_TTL_SECONDS = 180

def get_multiple_asset_prices(tickers):
    global _crypto_price_cache, _crypto_price_cache_time
    ids = ','.join(sorted(tickers))  # sort to ensure consistent cache key
    now = time.time()
    # Check cache
    if ids in _crypto_price_cache and (now - _crypto_price_cache_time.get(ids, 0)) < CACHE_TTL_SECONDS:
        return _crypto_price_cache[ids]
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        _crypto_price_cache[ids] = data
        _crypto_price_cache_time[ids] = now
        return data  # Returns a dictionary with prices
    except requests.exceptions.RequestException as e:
        print(f"Error fetching prices: {e}")
        # Return last cached value if available
        if ids in _crypto_price_cache:
            return _crypto_price_cache[ids]
        return {}

# --- Stock price cache function ---
STOCK_CACHE_TTL_SECONDS = 180  # 3 minutes

def get_multiple_stock_prices(tickers):
    """
    Fetch and cache stock prices for a list of tickers for 3 minutes.
    Returns a dict: {ticker: price}
    """
    if not tickers:
        return {}
    # Create a cache key based on the sorted tickers
    cache_key = "stock_prices_" + "_".join(sorted(tickers))
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    prices = {}
    try:
        if len(tickers) == 1:
            ticker = tickers[0]
            data = yf.Ticker(ticker).history(period='1d')
            if not data.empty:
                prices[ticker] = float(data['Close'].iloc[-1])
            else:
                prices[ticker] = None
        else:
            data = yf.download(
                tickers=tickers,
                period='1d',
                interval='1d',
                group_by='ticker',
                threads=True,
                progress=False
            )
            for ticker in tickers:
                try:
                    prices[ticker] = float(data[ticker]['Close'].iloc[-1])
                except Exception:
                    prices[ticker] = None
    except Exception:
        prices = {ticker: None for ticker in tickers}

    cache.set(cache_key, prices, timeout=STOCK_CACHE_TTL_SECONDS)
    return prices

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
            return redirect('general')  # Redirect to the General tab after signup
    else:
        form = SignUpForm()
    return render(request, 'signup.html', {'form': form})

@login_required
def home(request):
    selected_currency = request.GET.get('currency', 'USD')
    currency_symbol = CURRENCY_SYMBOLS.get(selected_currency, selected_currency)
    
    # Clear cache to ensure fresh calculations including vehicles
    cache_key = f"total_net_worth_{request.user.id}_{selected_currency}"
    cache.delete(cache_key)
    
    total_net_worth = get_user_total_net_worth(request.user, selected_currency)
    true_total_net_worth = total_net_worth
    true_total_net_worth_float = float(true_total_net_worth)
    if request.method == 'POST':
        form = AddAssetForm(request.POST, asset_type='crypto')
        if form.is_valid():
            asset = form.save(commit=False)
            asset.owner = request.user
            asset.type = 'crypto'
            asset.save()
            return redirect('home')
        else:
            messages.error(request, "Failed to add asset. Please check your inputs.")
    else:
        form = AddAssetForm(asset_type='crypto')

    user_assets = Asset.objects.filter(owner=request.user, type='crypto')
    tickers = ['bitcoin'] + [map_ticker(asset.ticker) for asset in user_assets]
    prices = get_multiple_asset_prices(tickers)
    bitcoin_price = prices.get('bitcoin', {}).get('usd', 'N/A')

    assets_with_value = []
    percent_mode = request.GET.get('percent', 'section')
    for asset in user_assets:
        coin_id = map_ticker(asset.ticker)
        price_usd = prices.get(coin_id, {}).get('usd')  # Get price per token in USD
        if price_usd is not None:
            price_usd = Decimal(str(price_usd))
            # Convert price to selected currency
            price = convert_currency(price_usd, 'USD', selected_currency)
        else:
            price = None
        value = price * asset.amount if price else None
        asset_dict = {
            'id': asset.id,
            'ticker': asset.ticker,
            'amount': asset.amount,
            'price': price if price else '-',  # Add price per token
            'value': value if value else '-',
        }
        assets_with_value.append(asset_dict)

    # Sort assets by value descending (robust to '-' or non-numeric)
    def get_value_for_sort(x):
        try:
            return float(x['value'])
        except Exception:
            return 0
    assets_with_value.sort(key=get_value_for_sort, reverse=True)

    # Calculate and attach percentage directly to each asset dict
    section_sum = sum([float(a['value']) for a in assets_with_value if a['value'] != '-'])
    for asset in assets_with_value:
        value = asset['value'] if asset['value'] != '-' else 0
        if percent_mode == 'total' and true_total_net_worth_float > 0:
            asset['percentage'] = round((float(value) / true_total_net_worth_float * 100), 2) if true_total_net_worth_float > 0 else 0
        else:
            asset['percentage'] = round((float(value) / section_sum * 100), 2) if section_sum > 0 else 0

    # Calculate section net worth (crypto) in selected currency
    section_net_worth = sum([float(a['value']) for a in assets_with_value if a['value'] != '-'])

    # Calculate BTC equivalent
    total_net_worth_usd = get_user_total_net_worth(request.user, 'USD')
    btc_equivalent = get_btc_equivalent(total_net_worth_usd)

    # Get available currencies for dropdown
    available_currencies = {
        'USD': 'US Dollar',
        'CAD': 'Canadian Dollar',
        'BRL': 'Brazilian Real',
        'KRW': 'Korean Won',
        'EUR': 'Euro',
        'JPY': 'Japanese Yen',
        'AUD': 'Australian Dollar',
        'VND': 'Vietnamese Dong',
    }

    # Prepare pie and bar charts for crypto
    cache_key = f"bar_chart_html_{request.user.id}_{selected_currency}"
    bar_chart_html = cache.get(cache_key)
    # --- Always generate pie_chart_html ---
    pie_chart_html = None
    if assets_with_value:
        # Pie chart values: use correct basis depending on percent_mode
        if percent_mode == 'total' and true_total_net_worth_float > 0:
            pie_values = [safe_float(asset['value']) / true_total_net_worth_float * 100 for asset in assets_with_value]
            sum_crypto_pct = sum(pie_values)
            if sum_crypto_pct < 100:
                labels_with_other = [asset['ticker'] for asset in assets_with_value] + ['Other']
                pie_values_with_other = pie_values + [100 - sum_crypto_pct]
            else:
                labels_with_other = [asset['ticker'] for asset in assets_with_value]
                pie_values_with_other = pie_values
            fig_pie = go.Figure(data=[go.Pie(
                labels=labels_with_other, 
                values=pie_values_with_other, 
                textinfo='label+percent',
                texttemplate='%{label}<br>%{value:.0f}%',
                textposition='outside',
                showlegend=False,
                hole=0.6,  # Creates slim donut chart
                textfont=dict(size=12, color='white'),
                hovertemplate='%{label}<br>%{value:.0f}%<extra></extra>'
            )])
        else:
            section_sum = sum([safe_float(asset['value']) for asset in assets_with_value])
            pie_values = [safe_float(asset['value']) / section_sum * 100 if section_sum > 0 else 0 for asset in assets_with_value]
            fig_pie = go.Figure(data=[go.Pie(
                labels=[asset['ticker'] for asset in assets_with_value], 
                values=pie_values, 
                textinfo='label+percent',
                texttemplate='%{label}<br>%{value:.0f}%',
                textposition='outside',
                showlegend=False,
                hole=0.6,  # Creates slim donut chart
                textfont=dict(size=12, color='white'),
                hovertemplate='%{label}<br>%{value:.0f}%<extra></extra>'
            )])
        fig_pie.update_layout(
            title="Crypto Portfolio Distribution",
            margin=dict(t=50, b=50, l=50, r=50),  # Increased margins for external labels
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e0e0e0"),
            # Center the donut chart
            xaxis=dict(
                domain=[0.1, 0.9],  # Use 80% of width, centered
                showgrid=False,
                showticklabels=False,
                zeroline=False,
                showline=False,
            ),
            yaxis=dict(
                domain=[0.1, 0.9],  # Use 80% of height for donut chart
                showgrid=False,
                showticklabels=False,
                zeroline=False,
                showline=False,
            ),
            # No legend needed since labels are outside
            showlegend=False,
            # Ensure responsive behavior
            autosize=True,
            height=400,  # Height for donut chart with external labels
        )
        pie_chart_html = fig_pie.to_html(full_html=False, config={"responsive": True, "displayModeBar": False})
    # --- Only cache and reuse bar_chart_html ---
    if not bar_chart_html:
        if assets_with_value:
            # Stacked bar chart
            bar_segments = []
            colors = ["#4caf50", "#2196f3", "#ff9800", "#9c27b0", "#e91e63"]
            section_sum = sum([safe_float(asset['value']) for asset in assets_with_value])
            section_percent_of_total = section_sum / true_total_net_worth_float * 100 if true_total_net_worth_float > 0 else 0
            xaxis_max = 100 if percent_mode == 'section' else section_percent_of_total
            if percent_mode == 'total':
                bar_chart_values = [safe_float(asset['value']) / true_total_net_worth_float * 100 if true_total_net_worth_float > 0 else 0 for asset in assets_with_value]
            else:
                bar_chart_values = [safe_float(asset['value']) / section_sum * 100 if section_sum > 0 else 0 for asset in assets_with_value]
            for i, (label, percent) in enumerate(zip([asset['ticker'] for asset in assets_with_value], bar_chart_values)):
                bar_segments.append(go.Bar(
                    x=[percent],  # Use actual percentage value instead of rounding
                    y=[""],
                    name=label,
                    orientation='h',
                    marker=dict(color=colors[i % len(colors)]),
                    text=[f"{label}\n{percent:.1f}%"],  # Show one decimal place
                    textposition='inside',
                    insidetextanchor='middle',
                    hovertemplate=f"{label}: {{x:.2f}}%<extra></extra>",
                ))
            fig_bar = go.Figure(data=bar_segments)
            fig_bar.update_layout(
                barmode='stack',
                title='Portfolio Distribution (stacked bar)',
                margin=dict(t=50, b=0, l=0, r=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e0e0e0"),
                xaxis=dict(title=None, range=[0, xaxis_max], ticksuffix='%', ticklen=4, tickwidth=1),
                yaxis=dict(
                    tickfont=dict(size=11, color='#cccccc'),
                    tickformat=',',
                    tickwidth=1,
                    ticklen=4,
                    tickcolor='#333333',
                    showgrid=True,
                    gridcolor='rgba(255,255,255,0.1)',
                    gridwidth=1,
                    zeroline=False,
                    showline=True,
                    linecolor='rgba(255,255,255,0.2)',
                    linewidth=1,
                    side='left',
                    automargin=True,
                    range=[-0.5, 0.5]  # Start from min value with some padding
                ),
                showlegend=False,
                legend=dict(orientation="h", x=0.5, y=-0.35, xanchor="center"),
                height=200,
                autosize=True
            )
            bar_chart_html = fig_bar.to_html(full_html=False, config={"responsive": True, "displayModeBar": False})
            cache.set(cache_key, bar_chart_html, timeout=180)
        else:
            bar_chart_html = None

    return render(request, 'home.html', {
        'username': request.user.username,
        'assets': assets_with_value,
        'form': form,
        'bitcoin_price': bitcoin_price,  # Pass the Bitcoin price to the template
        'total_net_worth': total_net_worth,
        'section_net_worth': section_net_worth,
        'selected_currency': selected_currency,
        'available_currencies': available_currencies,
        'currency_symbol': currency_symbol,
        'pie_chart': pie_chart_html,
        'bar_chart': bar_chart_html,
        'percent_mode': percent_mode,
        'btc_equivalent': btc_equivalent,
    })

@login_required
def delete_holding(request, pk):
    asset = get_object_or_404(Asset, pk=pk, owner=request.user)
    asset.delete()
    messages.success(request, "Asset deleted successfully.")
    # Redirect back to the referring page
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('home')

@login_required
def edit_holding(request, pk):
    asset = get_object_or_404(Asset, pk=pk, owner=request.user)
    available_currencies = {
        'USD': 'US Dollar',
        'CAD': 'Canadian Dollar',
        'BRL': 'Brazilian Real',
        'KRW': 'Korean Won',
        'INR': 'Indian Rupee',
        'EUR': 'Euro',
        'GBP': 'British Pound',
        'JPY': 'Japanese Yen',
        'AUD': 'Australian Dollar',
        'CHF': 'Swiss Franc',
        'VND': 'Vietnamese Dong',
    }
    if request.method == 'POST':
        form = AddAssetForm(request.POST, instance=asset, asset_type=asset.type)
        if form.is_valid():
            form.save()
            messages.success(request, "Asset updated successfully.")
            if asset.type == 'stock':
                return redirect('stocks')
            elif asset.type == 'crypto':
                return redirect('home')
            elif asset.type == 'real_estate':
                return redirect('real_estate')
            elif asset.type == 'vehicle':
                return redirect('vehicles')
            elif asset.type == 'cash':
                return redirect('cash')
            elif asset.type == 'other':
                return redirect('other')
            else:
                return redirect('general')
    else:
        form = AddAssetForm(instance=asset, asset_type=asset.type)
    return render(request, 'edit_holding.html', {'form': form, 'asset': asset, 'available_currencies': available_currencies})


@login_required
def stocks(request):
    selected_currency = request.GET.get('currency', 'USD')
    currency_symbol = CURRENCY_SYMBOLS.get(selected_currency, selected_currency)
    # Calculate true total net worth for navbar (all assets)
    total_net_worth = get_user_total_net_worth(request.user, selected_currency)
    # Calculate section (stocks) net worth for tab display
    if request.method == 'POST':
        form = AddAssetForm(request.POST, asset_type='stock')
        if form.is_valid():
            asset = form.save(commit=False)
            asset.owner = request.user
            asset.type = 'stock'
            asset.ticker = asset.ticker.upper()
            asset.save()
            return redirect('stocks')
        else:
            messages.error(request, "Failed to add asset. Please check your inputs.")
    else:
        form = AddAssetForm(asset_type='stock')

    user_assets = Asset.objects.filter(owner=request.user, type='stock')
    tickers = [asset.ticker.upper() for asset in user_assets]

    # Fetch stock prices using the new cache function
    prices = get_multiple_stock_prices(tickers)

    # Calculate section net worth in USD first
    section_net_worth_usd = 0
    for asset in user_assets:
        price = prices.get(asset.ticker.upper())
        try:
            price_decimal = safe_decimal(price)
        except Exception:
            price_decimal = Decimal('0')
        section_net_worth_usd += price_decimal * asset.amount
    # Convert to selected currency
    section_net_worth = convert_currency(section_net_worth_usd, 'USD', selected_currency)

    # Populate assets and chart data
    assets_with_value = []
    labels = []
    values = []
    percent_mode = request.GET.get('percent', 'section')
    # Calculate true total net worth (copy from general view)
    crypto_assets_all = Asset.objects.filter(owner=request.user, type='crypto')
    stock_assets_all = Asset.objects.filter(owner=request.user, type='stock')
    cash_assets_all = Asset.objects.filter(owner=request.user, type='cash')
    real_estate_assets_all = Asset.objects.filter(owner=request.user, type='real_estate')
    vehicle_assets_all = Asset.objects.filter(owner=request.user, type='vehicle')
    other_assets_all = Asset.objects.filter(owner=request.user, type='other')
    # Crypto
    crypto_tickers_all = ['bitcoin'] + [map_ticker(asset.ticker) for asset in crypto_assets_all]
    crypto_prices_all = get_multiple_asset_prices(crypto_tickers_all)
    total_crypto_usd_all = sum((Decimal(str(crypto_prices_all.get(map_ticker(asset.ticker), {}).get('usd', 0))) * asset.amount) for asset in crypto_assets_all)
    total_crypto_all = convert_currency(total_crypto_usd_all, 'USD', selected_currency)
    # Stocks
    stock_tickers_all = [asset.ticker.upper() for asset in stock_assets_all]
    stock_prices_all = get_multiple_stock_prices(stock_tickers_all)
    total_stocks_usd_all = 0
    for asset in stock_assets_all:
        price = stock_prices_all.get(asset.ticker.upper())
        price_decimal = safe_decimal(price)
        total_stocks_usd_all += price_decimal * asset.amount
    total_stocks_all = convert_currency(total_stocks_usd_all, 'USD', selected_currency)
    # Cash
    total_cash_all = sum(convert_currency(cash.amount, cash.currency or 'USD', selected_currency) for cash in cash_assets_all)
    # Real Estate
    total_real_estate_all = sum(convert_currency(re.amount, re.currency or 'USD', selected_currency) for re in real_estate_assets_all)
    # Vehicle
    total_vehicle_all = sum(convert_currency(v.amount, v.currency or 'USD', selected_currency) for v in vehicle_assets_all)
    # Other
    total_other_all = sum(convert_currency(o.amount, o.currency or 'USD', selected_currency) for o in other_assets_all)
    # True total net worth
    true_total_net_worth = total_crypto_all + total_stocks_all + total_real_estate_all + total_vehicle_all + total_cash_all + total_other_all
    true_total_net_worth_float = float(true_total_net_worth)
    # Build assets_with_value and calculate percentages in one pass
    section_sum = 0
    for asset in user_assets:
        ticker = asset.ticker.upper()
        price_usd = prices.get(ticker)
        try:
            price_usd_decimal = safe_decimal(price_usd)
            price = convert_currency(price_usd_decimal, 'USD', selected_currency)
        except Exception:
            price = Decimal('0')
        value = price * asset.amount if price else None
        asset_dict = {
            'id': asset.id,
            'ticker': asset.ticker,
            'amount': asset.amount,
            'price': price if price else '-',
            'value': value if value else '-',
        }
        if value:
            section_sum += float(value)
        assets_with_value.append(asset_dict)

    # Sort assets by value descending BEFORE calculating percentages
    def get_value_for_sort(x):
        try:
            return float(x['value'])
        except Exception:
            return 0
    assets_with_value.sort(key=get_value_for_sort, reverse=True)

    # Now calculate percentages for both table and chart (after sorting)
    section_sum = sum([safe_float(a['value']) for a in assets_with_value])
    for i, asset in enumerate(assets_with_value):
        value = asset['value'] if isinstance(asset['value'], (int, float, Decimal)) else None
        if value:
            if percent_mode == 'total' and true_total_net_worth_float > 0:
                pct = float(value) / true_total_net_worth_float * 100
            elif percent_mode == 'section' and section_sum > 0:
                pct = float(value) / section_sum * 100
            else:
                pct = 0
            asset['percentage'] = round(pct, 2)
            labels.append(asset['ticker'])
            values.append(pct)
        else:
            asset['percentage'] = 0

    # --- STOCKS PIE CHART LOGIC ---
    if labels and values:
        if percent_mode == 'total' and true_total_net_worth_float > 0:
            sum_section_pct = sum(values)
            if sum_section_pct < 100:
                labels_with_other = labels + ['Other']
                values_with_other = values + [100 - sum_section_pct]
            else:
                labels_with_other = labels
                values_with_other = values
            fig_pie = go.Figure(data=[go.Pie(
                labels=labels_with_other, 
                values=values_with_other, 
                textinfo='label+percent',
                texttemplate='%{label}<br>%{value:.0f}%',
                textposition='outside',
                showlegend=False,
                hole=0.6,  # Creates slim donut chart
                textfont=dict(size=12, color='white'),
                hovertemplate='%{label}<br>%{value:.0f}%<extra></extra>'
            )])
        else:
            fig_pie = go.Figure(data=[go.Pie(
                labels=labels, 
                values=values, 
                textinfo='label+percent',
                texttemplate='%{label}<br>%{value:.0f}%',
                textposition='outside',
                showlegend=False,
                hole=0.6,  # Creates slim donut chart
                textfont=dict(size=12, color='white'),
                hovertemplate='%{label}<br>%{value:.0f}%<extra></extra>'
            )])
        fig_pie.update_layout(
            title="Stock Portfolio Distribution",
            margin=dict(t=50, b=50, l=50, r=50),  # Increased margins for external labels
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e0e0e0"),
            # Center the donut chart
            xaxis=dict(
                domain=[0.1, 0.9],  # Use 80% of width, centered
                showgrid=False,
                showticklabels=False,
                zeroline=False,
                showline=False,
            ),
            yaxis=dict(
                domain=[0.1, 0.9],  # Use 80% of height for donut chart
                showgrid=False,
                showticklabels=False,
                zeroline=False,
                showline=False,
            ),
            # No legend needed since labels are outside
            showlegend=False,
            # Ensure responsive behavior
            autosize=True,
            height=400,  # Height for donut chart with external labels
        )
        pie_chart_html = fig_pie.to_html(full_html=False)
        # --- STOCKS BAR CHART LOGIC ---
        if labels and values:
            bar_segments = []
            colors = ["#4caf50", "#2196f3", "#ff9800", "#9c27b0", "#e91e63"]
            for i, (label, percent) in enumerate(zip(labels, values)):
                bar_segments.append(go.Bar(
                    x=[percent],  # Use actual percentage value instead of rounding
                    y=[""],
                    name=label,
                    orientation='h',
                    marker=dict(color=colors[i % len(colors)]),
                    text=[f"{label}\n{percent:.1f}%"],  # Show one decimal place
                    textposition='inside',
                    insidetextanchor='middle',
                    hovertemplate=f"{label}: {{x:.2f}}%<extra></extra>",
                ))
            # Calculate section's percent of total net worth for bar chart x-axis
            section_percent_of_total = sum(values) if percent_mode == 'total' else 100
            xaxis_max = 100 if percent_mode == 'section' else section_percent_of_total
            fig_bar = go.Figure(data=bar_segments)
            fig_bar.update_layout(
                barmode='stack',
                title='Portfolio Distribution (stacked bar)',
                margin=dict(t=50, b=0, l=0, r=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e0e0e0"),
                xaxis=dict(title=None, range=[0, xaxis_max], ticksuffix='%', ticklen=4, tickwidth=1),
                yaxis=dict(
                    tickfont=dict(size=11, color='#cccccc'),
                    tickformat=',',
                    tickwidth=1,
                    ticklen=4,
                    tickcolor='#333333',
                    showgrid=True,
                    gridcolor='rgba(255,255,255,0.1)',
                    gridwidth=1,
                    zeroline=False,
                    showline=True,
                    linecolor='rgba(255,255,255,0.2)',
                    linewidth=1,
                    side='left',
                    automargin=True,
                    range=[-0.5, 0.5]  # Start from min value with some padding
                ),
                showlegend=False,
                legend=dict(orientation="h", x=0.5, y=-0.35, xanchor="center"),
                height=200,
                autosize=True
            )
            bar_chart_html = fig_bar.to_html(full_html=False, config={"responsive": True, "displayModeBar": False})
        else:
            pie_chart_html = None
            bar_chart_html = None
    else:
        pie_chart_html = None
        bar_chart_html = None

    # Get available currencies for dropdown
    available_currencies = {
        'USD': 'US Dollar',
        
        'CAD': 'Canadian Dollar',
        'BRL': 'Brazilian Real',
        'KRW': 'Korean Won',
        'EUR': 'Euro',
        'JPY': 'Japanese Yen',
        'AUD': 'Australian Dollar',
        'VND': 'Vietnamese Dong',
    }

    # Calculate BTC equivalent
    total_net_worth_usd = get_user_total_net_worth(request.user, 'USD')
    btc_equivalent = get_btc_equivalent(total_net_worth_usd)

    return render(request, 'stocks.html', {
        'username': request.user.username,
        'assets': assets_with_value,
        'form': form,
        'total_net_worth': total_net_worth,  # This is now always the true total net worth
        'section_net_worth': section_net_worth,  # For tab display only
        'selected_currency': selected_currency,
        'available_currencies': available_currencies,
        'currency_symbol': currency_symbol,
        'pie_chart': pie_chart_html,
        'bar_chart': bar_chart_html,
        'percent_mode': percent_mode,
        'btc_equivalent': btc_equivalent,
    })

@login_required
def real_estate(request):
    selected_currency = request.GET.get('currency', 'USD')
    currency_symbol = CURRENCY_SYMBOLS.get(selected_currency, selected_currency)
    total_net_worth = get_user_total_net_worth(request.user, selected_currency)
    true_total_net_worth = total_net_worth
    true_total_net_worth_float = float(true_total_net_worth)
    percent_mode = request.GET.get('percent', 'section')
    if request.method == 'POST':
        form = AddAssetForm(request.POST)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.owner = request.user
            asset.type = 'real_estate'
            asset.save()
            return redirect('real_estate')
    else:
        form = AddAssetForm()
    user_assets = Asset.objects.filter(owner=request.user, type='real_estate')
    assets_with_value = []
    for asset in user_assets:
        price = convert_currency(asset.amount, asset.currency or 'USD', selected_currency)
        value = price
        asset_dict = {
            'id': asset.id,
            'ticker': asset.ticker,
            'amount': asset.amount,
            'currency': asset.currency,
            'value': value,
        }
        assets_with_value.append(asset_dict)
    def get_value_for_sort(x):
        try:
            return float(x['value'])
        except Exception:
            return 0
    assets_with_value.sort(key=get_value_for_sort, reverse=True)
    section_sum = sum([float(a['value']) for a in assets_with_value])
    for asset in assets_with_value:
        value = asset['value']
        if percent_mode == 'total' and true_total_net_worth_float > 0:
            asset['percentage'] = round((float(value) / true_total_net_worth_float * 100), 2) if true_total_net_worth_float > 0 else 0
        else:
            asset['percentage'] = round((float(value) / section_sum * 100), 2) if section_sum > 0 else 0
    labels = [asset['ticker'] for asset in assets_with_value]
    values = [float(asset['value']) for asset in assets_with_value]
    pie_chart_html = None
    bar_chart_html = None
    if labels and values:
        total = sum(values)
        if percent_mode == 'total' and true_total_net_worth_float > 0:
            pie_values = [float(v) / true_total_net_worth_float * 100 for v in values]
            sum_section_pct = sum(pie_values)
            if sum_section_pct < 100:
                labels_with_other = labels + ['Other']
                pie_values_with_other = pie_values + [100 - sum_section_pct]
            else:
                labels_with_other = labels
                pie_values_with_other = pie_values
            fig_pie = go.Figure(data=[go.Pie(
                labels=labels_with_other, 
                values=pie_values_with_other, 
                textinfo='label+percent',
                texttemplate='%{label}<br>%{value:.0f}%',
                textposition='outside',
                showlegend=False,
                hole=0.6,  # Creates slim donut chart
                textfont=dict(size=12, color='white'),
                hovertemplate='%{label}<br>%{value:.0f}%<extra></extra>'
            )])
        else:
            section_sum = sum(values)
            pie_values = [float(v) / section_sum * 100 if section_sum > 0 else 0 for v in values]
            fig_pie = go.Figure(data=[go.Pie(
                labels=labels, 
                values=pie_values, 
                textinfo='label+percent',
                texttemplate='%{label}<br>%{value:.0f}%',
                textposition='outside',
                showlegend=False,
                hole=0.6,  # Creates slim donut chart
                textfont=dict(size=12, color='white'),
                hovertemplate='%{label}<br>%{value:.0f}%<extra></extra>'
            )])
        fig_pie.update_layout(
            title="Real Estate Portfolio Distribution",
            margin=dict(t=50, b=50, l=50, r=50),  # Increased margins for external labels
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e0e0e0"),
            # Center the pie chart
            xaxis=dict(
                domain=[0.1, 0.9],  # Use 80% of width, centered
                showgrid=False,
                showticklabels=False,
                zeroline=False,
                showline=False,
            ),
            yaxis=dict(
                domain=[0.1, 0.9],  # Use 80% of height for donut chart
                showgrid=False,
                showticklabels=False,
                zeroline=False,
                showline=False,
            ),
            # Position legend below the chart
            showlegend=False,
            legend=dict(
                orientation="h",  # Horizontal legend
                y=-0.35,  # Position further below the chart
                x=0.5,
                xanchor="center",
                yanchor="top",
                bgcolor='rgba(0,0,0,0)',
                bordercolor='rgba(0,0,0,0)',
                font=dict(size=12)
            ),
            # Ensure responsive behavior
            autosize=True,
            height=400,  # Height for donut chart with external labels
        )
        pie_chart_html = fig_pie.to_html(full_html=False, config={"responsive": True})
        # Bar chart
        bar_segments = []
        colors = ["#4caf50", "#2196f3", "#ff9800", "#9c27b0", "#e91e63"]
        if percent_mode == 'total' and true_total_net_worth_float > 0:
            bar_chart_values = [float(v) / true_total_net_worth_float * 100 for v in values]
            xaxis_max = sum(bar_chart_values)
        else:
            bar_chart_values = [float(v) / section_sum * 100 if section_sum > 0 else 0 for v in values]
            xaxis_max = 100
        for i, (label, percent) in enumerate(zip(labels, bar_chart_values)):
            bar_segments.append(go.Bar(
                x=[int(round(percent))],
                y=[""],
                name=label,
                orientation='h',
                marker=dict(color=colors[i % len(colors)]),
                text=[f"{label}\n{int(round(percent))}%"],
                textposition='inside',
                insidetextanchor='middle',
                hovertemplate=f"{label}: {{x}}%<extra></extra>",
            ))
        fig_bar = go.Figure(data=bar_segments)
        fig_bar.update_layout(
            barmode='stack',
            title='Portfolio Distribution (stacked bar)',
            margin=dict(t=50, b=0, l=0, r=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e0e0e0"),
            xaxis=dict(title=None, range=[0, xaxis_max], ticksuffix='%', ticklen=4, tickwidth=1),
            yaxis=dict(title=None, showticklabels=False, showgrid=False, zeroline=False, visible=False, ticklen=4, tickwidth=1),
            showlegend=False,
            legend=dict(orientation="h", x=0.5, y=-0.35, xanchor="center"),
            height=200,
            autosize=True
        )
        bar_chart_html = fig_bar.to_html(full_html=False, config={"responsive": True, "displayModeBar": False})
    available_currencies = {
        'USD': 'US Dollar',
        'CAD': 'Canadian Dollar',
        'BRL': 'Brazilian Real',
        'KRW': 'Korean Won',
        'EUR': 'Euro',
        'JPY': 'Japanese Yen',
        'AUD': 'Australian Dollar',
        'VND': 'Vietnamese Dong',
    }
    
    # Calculate BTC equivalent
    total_net_worth_usd = get_user_total_net_worth(request.user, 'USD')
    btc_equivalent = get_btc_equivalent(total_net_worth_usd)
    
    return render(request, 'real_estate.html', {
        'username': request.user.username,
        'assets': assets_with_value,
        'form': form,
        'total_net_worth': total_net_worth,
        'section_net_worth': section_sum,
        'selected_currency': selected_currency,
        'available_currencies': available_currencies,
        'currency_symbol': currency_symbol,
        'pie_chart': pie_chart_html,
        'bar_chart': bar_chart_html,
        'percent_mode': percent_mode,
        'btc_equivalent': btc_equivalent,
    })

@login_required
def vehicles(request):
    selected_currency = request.GET.get('currency', 'USD')
    currency_symbol = CURRENCY_SYMBOLS.get(selected_currency, selected_currency)
    total_net_worth = get_user_total_net_worth(request.user, selected_currency)
    true_total_net_worth = total_net_worth
    true_total_net_worth_float = float(true_total_net_worth)
    percent_mode = request.GET.get('percent', 'section')
    if request.method == 'POST':
        form = AddAssetForm(request.POST)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.owner = request.user
            asset.type = 'vehicle'
            asset.save()
            return redirect('vehicles')
    else:
        form = AddAssetForm()
    user_assets = Asset.objects.filter(owner=request.user, type='vehicle')
    assets_with_value = []
    for asset in user_assets:
        price = convert_currency(asset.amount, asset.currency or 'USD', selected_currency)
        value = price
        asset_dict = {
            'id': asset.id,
            'ticker': asset.ticker,
            'amount': asset.amount,
            'currency': asset.currency,
            'value': value,
        }
        assets_with_value.append(asset_dict)
    def get_value_for_sort(x):
        try:
            return float(x['value'])
        except Exception:
            return 0
    assets_with_value.sort(key=get_value_for_sort, reverse=True)
    section_sum = sum([float(a['value']) for a in assets_with_value])
    for asset in assets_with_value:
        value = asset['value']
        if percent_mode == 'total' and true_total_net_worth_float > 0:
            asset['percentage'] = round((float(value) / true_total_net_worth_float * 100), 2) if true_total_net_worth_float > 0 else 0
        else:
            asset['percentage'] = round((float(value) / section_sum * 100), 2) if section_sum > 0 else 0
    labels = [asset['ticker'] for asset in assets_with_value]
    values = [float(asset['value']) for asset in assets_with_value]
    pie_chart_html = None
    bar_chart_html = None
    if labels and values:
        total = sum(values)
        if percent_mode == 'total' and true_total_net_worth_float > 0:
            pie_values = [float(v) / true_total_net_worth_float * 100 for v in values]
            sum_section_pct = sum(pie_values)
            if sum_section_pct < 100:
                labels_with_other = labels + ['Other']
                pie_values_with_other = pie_values + [100 - sum_section_pct]
            else:
                labels_with_other = labels
                pie_values_with_other = pie_values
            fig_pie = go.Figure(data=[go.Pie(
                labels=labels_with_other, 
                values=pie_values_with_other, 
                textinfo='label+percent',
                texttemplate='%{label}<br>%{value:.0f}%',
                textposition='outside',
                showlegend=False,
                hole=0.6,  # Creates slim donut chart
                textfont=dict(size=12, color='white'),
                hovertemplate='%{label}<br>%{value:.0f}%<extra></extra>'
            )])
        else:
            section_sum = sum(values)
            pie_values = [float(v) / section_sum * 100 if section_sum > 0 else 0 for v in values]
            fig_pie = go.Figure(data=[go.Pie(
                labels=labels, 
                values=pie_values, 
                textinfo='label+percent',
                texttemplate='%{label}<br>%{value:.0f}%',
                textposition='outside',
                showlegend=False,
                hole=0.6,  # Creates slim donut chart
                textfont=dict(size=12, color='white'),
                hovertemplate='%{label}<br>%{value:.0f}%<extra></extra>'
            )])
        fig_pie.update_layout(
            title="Vehicle Portfolio Distribution",
            margin=dict(t=50, b=50, l=50, r=50),  # Increased margins for external labels
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e0e0e0"),
            # Center the pie chart
            xaxis=dict(
                domain=[0.1, 0.9],  # Use 80% of width, centered
                showgrid=False,
                showticklabels=False,
                zeroline=False,
                showline=False,
            ),
            yaxis=dict(
                domain=[0.1, 0.9],  # Use 80% of height for donut chart
                showgrid=False,
                showticklabels=False,
                zeroline=False,
                showline=False,
            ),
            # Position legend below the chart
            showlegend=False,
            legend=dict(
                orientation="h",  # Horizontal legend
                y=-0.35,  # Position further below the chart
                x=0.5,
                xanchor="center",
                yanchor="top",
                bgcolor='rgba(0,0,0,0)',
                bordercolor='rgba(0,0,0,0)',
                font=dict(size=12)
            ),
            # Ensure responsive behavior
            autosize=True,
            height=400,  # Height for donut chart with external labels
        )
        pie_chart_html = fig_pie.to_html(full_html=False, config={"responsive": True})
        # Bar chart
        bar_segments = []
        colors = ["#4caf50", "#2196f3", "#ff9800", "#9c27b0", "#e91e63"]
        if percent_mode == 'total' and true_total_net_worth_float > 0:
            bar_chart_values = [float(v) / true_total_net_worth_float * 100 for v in values]
            xaxis_max = sum(bar_chart_values)
        else:
            bar_chart_values = [float(v) / section_sum * 100 if section_sum > 0 else 0 for v in values]
            xaxis_max = 100
        for i, (label, percent) in enumerate(zip(labels, bar_chart_values)):
            bar_segments.append(go.Bar(
                x=[int(round(percent))],
                y=[""],
                name=label,
                orientation='h',
                marker=dict(color=colors[i % len(colors)]),
                text=[f"{label}\n{int(round(percent))}%"],
                textposition='inside',
                insidetextanchor='middle',
                hovertemplate=f"{label}: {{x}}%<extra></extra>",
            ))
        fig_bar = go.Figure(data=bar_segments)
        fig_bar.update_layout(
            barmode='stack',
            title='Portfolio Distribution (stacked bar)',
            margin=dict(t=50, b=0, l=0, r=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e0e0e0"),
            xaxis=dict(title=None, range=[0, xaxis_max], ticksuffix='%', ticklen=4, tickwidth=1),
            yaxis=dict(title=None, showticklabels=False, showgrid=False, zeroline=False, visible=False, ticklen=4, tickwidth=1),
            showlegend=False,
            legend=dict(orientation="h", x=0.5, y=-0.35, xanchor="center"),
            height=200,
            autosize=True
        )
        bar_chart_html = fig_bar.to_html(full_html=False, config={"responsive": True, "displayModeBar": False})
    available_currencies = {
        'USD': 'US Dollar',
        
        'CAD': 'Canadian Dollar',
        'BRL': 'Brazilian Real',
        'KRW': 'Korean Won',
        'EUR': 'Euro',
        'JPY': 'Japanese Yen',
        'AUD': 'Australian Dollar',
        'VND': 'Vietnamese Dong',
    }
    
    # Calculate BTC equivalent
    total_net_worth_usd = get_user_total_net_worth(request.user, 'USD')
    btc_equivalent = get_btc_equivalent(total_net_worth_usd)
    
    return render(request, 'vehicles.html', {
        'username': request.user.username,
        'assets': assets_with_value,
        'form': form,
        'total_net_worth': total_net_worth,
        'section_net_worth': section_sum,
        'selected_currency': selected_currency,
        'available_currencies': available_currencies,
        'currency_symbol': currency_symbol,
        'pie_chart': pie_chart_html,
        'bar_chart': bar_chart_html,
        'percent_mode': percent_mode,
        'btc_equivalent': btc_equivalent,
    })

@login_required
def cash(request):
    selected_currency = request.GET.get('currency', 'USD')
    currency_symbol = CURRENCY_SYMBOLS.get(selected_currency, selected_currency)
    total_net_worth = get_user_total_net_worth(request.user, selected_currency)
    true_total_net_worth = total_net_worth
    true_total_net_worth_float = float(true_total_net_worth)
    percent_mode = request.GET.get('percent', 'section')
    if request.method == 'POST':
        form = AddAssetForm(request.POST)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.owner = request.user
            asset.type = 'cash'
            asset.save()
            return redirect('cash')
    else:
        form = AddAssetForm()
    user_assets = Asset.objects.filter(owner=request.user, type='cash')
    assets_with_value = []
    for asset in user_assets:
        price = convert_currency(asset.amount, asset.currency or 'USD', selected_currency)
        value = price
        asset_dict = {
            'id': asset.id,
            'ticker': asset.ticker,
            'amount': asset.amount,
            'currency': asset.currency,
            'value': value,
        }
        assets_with_value.append(asset_dict)
    def get_value_for_sort(x):
        try:
            return float(x['value'])
        except Exception:
            return 0
    assets_with_value.sort(key=get_value_for_sort, reverse=True)
    section_sum = sum([float(a['value']) for a in assets_with_value])
    for asset in assets_with_value:
        value = asset['value']
        if percent_mode == 'total' and true_total_net_worth_float > 0:
            asset['percentage'] = round((float(value) / true_total_net_worth_float * 100), 2) if true_total_net_worth_float > 0 else 0
        else:
            asset['percentage'] = round((float(value) / section_sum * 100), 2) if section_sum > 0 else 0
    labels = [asset['ticker'] for asset in assets_with_value]
    values = [float(asset['value']) for asset in assets_with_value]
    pie_chart_html = None
    bar_chart_html = None
    if labels and values:
        total = sum(values)
        if percent_mode == 'total' and true_total_net_worth_float > 0:
            pie_values = [float(v) / true_total_net_worth_float * 100 for v in values]
            sum_section_pct = sum(pie_values)
            if sum_section_pct < 100:
                labels_with_other = labels + ['Other']
                pie_values_with_other = pie_values + [100 - sum_section_pct]
            else:
                labels_with_other = labels
                pie_values_with_other = pie_values
            fig_pie = go.Figure(data=[go.Pie(
                labels=labels_with_other, 
                values=pie_values_with_other, 
                textinfo='label+percent',
                texttemplate='%{label}<br>%{value:.0f}%',
                textposition='outside',
                showlegend=False,
                hole=0.6,  # Creates slim donut chart
                textfont=dict(size=12, color='white'),
                hovertemplate='%{label}<br>%{value:.0f}%<extra></extra>'
            )])
        else:
            section_sum = sum(values)
            pie_values = [float(v) / section_sum * 100 if section_sum > 0 else 0 for v in values]
            fig_pie = go.Figure(data=[go.Pie(
                labels=labels, 
                values=pie_values, 
                textinfo='label+percent',
                texttemplate='%{label}<br>%{value:.0f}%',
                textposition='outside',
                showlegend=False,
                hole=0.6,  # Creates slim donut chart
                textfont=dict(size=12, color='white'),
                hovertemplate='%{label}<br>%{value:.0f}%<extra></extra>'
            )])
        fig_pie.update_layout(
            title="Cash/Fixed Income Portfolio Distribution",
            margin=dict(t=50, b=50, l=50, r=50),  # Increased margins for external labels
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e0e0e0"),
            # Center the pie chart
            xaxis=dict(
                domain=[0.1, 0.9],  # Use 80% of width, centered
                showgrid=False,
                showticklabels=False,
                zeroline=False,
                showline=False,
            ),
            yaxis=dict(
                domain=[0.1, 0.9],  # Use 80% of height for donut chart
                showgrid=False,
                showticklabels=False,
                zeroline=False,
                showline=False,
            ),
            # Position legend below the chart
            showlegend=False,
            legend=dict(
                orientation="h",  # Horizontal legend
                y=-0.35,  # Position further below the chart
                x=0.5,
                xanchor="center",
                yanchor="top",
                bgcolor='rgba(0,0,0,0)',
                bordercolor='rgba(0,0,0,0)',
                font=dict(size=12)
            ),
            # Ensure responsive behavior
            autosize=True,
            height=400,  # Height for donut chart with external labels
        )
        pie_chart_html = fig_pie.to_html(full_html=False, config={"responsive": True})
        # Bar chart
        bar_segments = []
        colors = ["#4caf50", "#2196f3", "#ff9800", "#9c27b0", "#e91e63"]
        if percent_mode == 'total' and true_total_net_worth_float > 0:
            bar_chart_values = [float(v) / true_total_net_worth_float * 100 for v in values]
            xaxis_max = sum(bar_chart_values)
        else:
            bar_chart_values = [float(v) / section_sum * 100 if section_sum > 0 else 0 for v in values]
            xaxis_max = 100
        for i, (label, percent) in enumerate(zip(labels, bar_chart_values)):
            bar_segments.append(go.Bar(
                x=[int(round(percent))],
                y=[""],
                name=label,
                orientation='h',
                marker=dict(color=colors[i % len(colors)]),
                text=[f"{label}\n{int(round(percent))}%"],
                textposition='inside',
                insidetextanchor='middle',
                hovertemplate=f"{label}: {{x}}%<extra></extra>",
            ))
        fig_bar = go.Figure(data=bar_segments)
        fig_bar.update_layout(
            barmode='stack',
            title='Portfolio Distribution (stacked bar)',
            margin=dict(t=50, b=0, l=0, r=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e0e0e0"),
            xaxis=dict(title=None, range=[0, xaxis_max], ticksuffix='%', ticklen=4, tickwidth=1),
            yaxis=dict(
                tickfont=dict(size=11, color='#cccccc'),
                tickformat=',',
                tickwidth=1,
                ticklen=4,
                tickcolor='#333333',
                showgrid=True,
                gridcolor='rgba(255,255,255,0.1)',
                gridwidth=1,
                zeroline=False,
                showline=True,
                linecolor='rgba(255,255,255,0.2)',
                linewidth=1,
                side='left',
                automargin=True,
                range=[-0.5, 0.5]  # Fixed range for horizontal bar chart
            ),
            showlegend=False,
            legend=dict(orientation="h", x=0.5, y=-0.35, xanchor="center"),
            height=200,
            autosize=True
        )
        bar_chart_html = fig_bar.to_html(full_html=False, config={"responsive": True, "displayModeBar": False})
    available_currencies = {
        'USD': 'US Dollar',
        
        'CAD': 'Canadian Dollar',
        'BRL': 'Brazilian Real',
        'KRW': 'Korean Won',
        'EUR': 'Euro',
        'JPY': 'Japanese Yen',
        'AUD': 'Australian Dollar',
        'VND': 'Vietnamese Dong',
    }
    
    # Calculate BTC equivalent
    total_net_worth_usd = get_user_total_net_worth(request.user, 'USD')
    btc_equivalent = get_btc_equivalent(total_net_worth_usd)
    
    return render(request, 'cash.html', {
        'username': request.user.username,
        'assets': assets_with_value,
        'form': form,
        'total_net_worth': total_net_worth,
        'section_net_worth': section_sum,
        'selected_currency': selected_currency,
        'available_currencies': available_currencies,
        'currency_symbol': currency_symbol,
        'pie_chart': pie_chart_html,
        'bar_chart': bar_chart_html,
        'percent_mode': percent_mode,
        'btc_equivalent': btc_equivalent,
    })

@login_required
def other(request):
    selected_currency = request.GET.get('currency', 'USD')
    currency_symbol = CURRENCY_SYMBOLS.get(selected_currency, selected_currency)
    total_net_worth = get_user_total_net_worth(request.user, selected_currency)
    true_total_net_worth = total_net_worth
    true_total_net_worth_float = float(true_total_net_worth)
    percent_mode = request.GET.get('percent', 'section')
    if request.method == 'POST':
        form = AddAssetForm(request.POST)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.owner = request.user
            asset.type = 'other'
            asset.save()
            return redirect('other')
    else:
        form = AddAssetForm()
    user_assets = Asset.objects.filter(owner=request.user, type='other')
    assets_with_value = []
    for asset in user_assets:
        price = convert_currency(asset.amount, asset.currency or 'USD', selected_currency)
        value = price
        asset_dict = {
            'id': asset.id,
            'ticker': asset.ticker,
            'amount': asset.amount,
            'currency': asset.currency,
            'value': value,
        }
        assets_with_value.append(asset_dict)
    def get_value_for_sort(x):
        try:
            return float(x['value'])
        except Exception:
            return 0
    assets_with_value.sort(key=get_value_for_sort, reverse=True)
    section_sum = sum([float(a['value']) for a in assets_with_value])
    for asset in assets_with_value:
        value = asset['value']
        if percent_mode == 'total' and true_total_net_worth_float > 0:
            asset['percentage'] = round((float(value) / true_total_net_worth_float * 100), 2) if true_total_net_worth_float > 0 else 0
        else:
            asset['percentage'] = round((float(value) / section_sum * 100), 2) if section_sum > 0 else 0
    labels = [asset['ticker'] for asset in assets_with_value]
    values = [float(asset['value']) for asset in assets_with_value]
    pie_chart_html = None
    bar_chart_html = None
    if labels and values:
        total = sum(values)
        if percent_mode == 'total' and true_total_net_worth_float > 0:
            pie_values = [float(v) / true_total_net_worth_float * 100 for v in values]
            sum_section_pct = sum(pie_values)
            if sum_section_pct < 100:
                labels_with_other = labels + ['Other']
                pie_values_with_other = pie_values + [100 - sum_section_pct]
            else:
                labels_with_other = labels
                pie_values_with_other = pie_values
            fig_pie = go.Figure(data=[go.Pie(
                labels=labels_with_other, 
                values=pie_values_with_other, 
                textinfo='label+percent',
                texttemplate='%{label}<br>%{value:.0f}%',
                textposition='outside',
                showlegend=False,
                hole=0.6,  # Creates slim donut chart
                textfont=dict(size=12, color='white'),
                hovertemplate='%{label}<br>%{value:.0f}%<extra></extra>'
            )])
        else:
            section_sum = sum(values)
            pie_values = [float(v) / section_sum * 100 if section_sum > 0 else 0 for v in values]
            fig_pie = go.Figure(data=[go.Pie(
                labels=labels, 
                values=pie_values, 
                textinfo='label+percent',
                texttemplate='%{label}<br>%{value:.0f}%',
                textposition='outside',
                showlegend=False,
                hole=0.6,  # Creates slim donut chart
                textfont=dict(size=12, color='white'),
                hovertemplate='%{label}<br>%{value:.0f}%<extra></extra>'
            )])
        fig_pie.update_layout(
            title="Other Portfolio Distribution",
            margin=dict(t=50, b=50, l=50, r=50),  # Increased margins for external labels
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e0e0e0"),
            # Center the pie chart
            xaxis=dict(
                domain=[0.1, 0.9],  # Use 80% of width, centered
                showgrid=False,
                showticklabels=False,
                zeroline=False,
                showline=False,
            ),
            yaxis=dict(
                domain=[0.1, 0.9],  # Use 80% of height for donut chart
                showgrid=False,
                showticklabels=False,
                zeroline=False,
                showline=False,
            ),
            # Position legend below the chart
            showlegend=False,
            legend=dict(
                orientation="h",  # Horizontal legend
                y=-0.35,  # Position further below the chart
                x=0.5,
                xanchor="center",
                yanchor="top",
                bgcolor='rgba(0,0,0,0)',
                bordercolor='rgba(0,0,0,0)',
                font=dict(size=12)
            ),
            # Ensure responsive behavior
            autosize=True,
            height=400,  # Height for donut chart with external labels
        )
        pie_chart_html = fig_pie.to_html(full_html=False, config={"responsive": True})
        # Bar chart
        bar_segments = []
        colors = ["#4caf50", "#2196f3", "#ff9800", "#9c27b0", "#e91e63"]
        if percent_mode == 'total' and true_total_net_worth_float > 0:
            bar_chart_values = [float(v) / true_total_net_worth_float * 100 for v in values]
            xaxis_max = sum(bar_chart_values)
        else:
            bar_chart_values = [float(v) / section_sum * 100 if section_sum > 0 else 0 for v in values]
            xaxis_max = 100
        for i, (label, percent) in enumerate(zip(labels, bar_chart_values)):
            bar_segments.append(go.Bar(
                x=[int(round(percent))],
                y=[""],
                name=label,
                orientation='h',
                marker=dict(color=colors[i % len(colors)]),
                text=[f"{label}\n{int(round(percent))}%"],
                textposition='inside',
                insidetextanchor='middle',
                hovertemplate=f"{label}: {{x}}%<extra></extra>",
            ))
        fig_bar = go.Figure(data=bar_segments)
        fig_bar.update_layout(
            barmode='stack',
            title='Portfolio Distribution (stacked bar)',
            margin=dict(t=50, b=0, l=0, r=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e0e0e0"),
            xaxis=dict(title=None, range=[0, xaxis_max], ticksuffix='%', ticklen=4, tickwidth=1),
            yaxis=dict(title=None, showticklabels=False, showgrid=False, zeroline=False, visible=False, ticklen=4, tickwidth=1),
            showlegend=False,
            legend=dict(orientation="h", x=0.5, y=-0.35, xanchor="center"),
            height=200,
            autosize=True
        )
        bar_chart_html = fig_bar.to_html(full_html=False, config={"responsive": True, "displayModeBar": False})
    available_currencies = {
        'USD': 'US Dollar',
        
        'CAD': 'Canadian Dollar',
        'BRL': 'Brazilian Real',
        'KRW': 'Korean Won',
        'EUR': 'Euro',
        'JPY': 'Japanese Yen',
        'AUD': 'Australian Dollar',
        'VND': 'Vietnamese Dong',
    }
    
    # Calculate BTC equivalent
    total_net_worth_usd = get_user_total_net_worth(request.user, 'USD')
    btc_equivalent = get_btc_equivalent(total_net_worth_usd)
    
    return render(request, 'other.html', {
        'username': request.user.username,
        'assets': assets_with_value,
        'form': form,
        'total_net_worth': total_net_worth,
        'section_net_worth': section_sum,
        'selected_currency': selected_currency,
        'available_currencies': available_currencies,
        'currency_symbol': currency_symbol,
        'pie_chart': pie_chart_html,
        'bar_chart': bar_chart_html,
        'percent_mode': percent_mode,
        'btc_equivalent': btc_equivalent,
    })

def general(request):
    selected_currency = request.GET.get('currency', 'USD')
    currency_symbol = CURRENCY_SYMBOLS.get(selected_currency, selected_currency)
    selected_range = request.GET.get('range', '1m')
    show_cash_form = request.GET.get('show_cash_form') == '1'
    show_other_form = request.GET.get('show_other_form') == '1'
    cash_currencies = ['USD', 'CAD', 'BRL', 'KRW', 'INR', 'EUR', 'GBP', 'JPY', 'AUD', 'CHF']

    # Clear cache to ensure fresh calculations including vehicles
    cache_key = f"total_net_worth_{request.user.id}_{selected_currency}"
    cache.delete(cache_key)

    # Handle cash form submission
    if request.method == 'POST' and request.POST.get('form_type') == 'add_cash':
        amount = request.POST.get('amount')
        currency = request.POST.get('currency')
        if amount and currency:
            Asset.objects.create(
                owner=request.user,
                type='cash',
                ticker='CASH',
                amount=Decimal(amount),
                currency=currency
            )
            return redirect(f"{request.path}?currency={selected_currency}")

    # Handle other asset form submission
    if request.method == 'POST' and request.POST.get('form_type') == 'add_other':
        name = request.POST.get('name')
        amount = request.POST.get('amount')
        currency = request.POST.get('currency')
        if name and amount and currency:
            Asset.objects.create(
                owner=request.user,
                type='other',
                ticker=name,
                amount=Decimal(amount),
                currency=currency
            )
            return redirect(f"{request.path}?currency={selected_currency}")

    # Get all user assets by type
    crypto_assets = Asset.objects.filter(owner=request.user, type='crypto')
    stock_assets = Asset.objects.filter(owner=request.user, type='stock')
    cash_assets = Asset.objects.filter(owner=request.user, type='cash')
    real_estate_assets = Asset.objects.filter(owner=request.user, type='real_estate')
    vehicle_assets = Asset.objects.filter(owner=request.user, type='vehicle')
    other_assets = Asset.objects.filter(owner=request.user, type='other')

    # Get prices for crypto
    crypto_tickers = ['bitcoin'] + [map_ticker(asset.ticker) for asset in crypto_assets]
    crypto_prices = get_multiple_asset_prices(crypto_tickers)

    # Calculate total crypto net worth in USD
    total_crypto_usd = sum(
        (Decimal(str(crypto_prices.get(map_ticker(asset.ticker), {}).get('usd', 0))) * asset.amount)
        for asset in crypto_assets
    )
    # Convert to selected currency
    total_crypto = convert_currency(total_crypto_usd, 'USD', selected_currency)

    # Get prices for stocks
    stock_tickers = [asset.ticker.upper() for asset in stock_assets]
    stock_prices = get_multiple_stock_prices(stock_tickers)

    # Calculate total stocks net worth in USD
    total_stocks_usd = sum(
        (Decimal(str(stock_prices.get(asset.ticker.upper(), 0))) * asset.amount)
        for asset in stock_assets
    )
    # Convert to selected currency
    total_stocks = convert_currency(total_stocks_usd, 'USD', selected_currency)

    # Calculate total cash in selected currency
    total_cash = Decimal('0')
    for cash in cash_assets:
        cash_value = convert_currency(cash.amount, cash.currency or 'USD', selected_currency)
        total_cash += cash_value

    # Calculate total real estate in selected currency
    total_real_estate = Decimal('0')
    for real_estate in real_estate_assets:
        real_estate_value = convert_currency(real_estate.amount, real_estate.currency or 'USD', selected_currency)
        total_real_estate += real_estate_value

    # Calculate total vehicle in selected currency
    total_vehicle = Decimal('0')
    for vehicle in vehicle_assets:
        vehicle_value = convert_currency(vehicle.amount, vehicle.currency or 'USD', selected_currency)
        total_vehicle += vehicle_value

    # Calculate total other in selected currency
    total_other = Decimal('0')
    for other in other_assets:
        other_value = convert_currency(other.amount, other.currency or 'USD', selected_currency)
        total_other += other_value

    # Calculate the true total net worth (sum of all asset types)
    total_net_worth = total_crypto + total_stocks + total_real_estate + total_vehicle + total_cash + total_other

    # Pie chart data
    labels = []
    values = []
    if total_crypto > 0:
        labels.append('Crypto')
        values.append(float(total_crypto))
    if total_stocks > 0:
        labels.append('Stocks')
        values.append(float(total_stocks))
    if total_real_estate > 0:
        labels.append('Real Estate')
        values.append(float(total_real_estate))
    if total_vehicle > 0:
        labels.append('Vehicles')
        values.append(float(total_vehicle))
    if total_cash > 0:
        labels.append('Cash')
        values.append(float(total_cash))
    if total_other > 0:
        labels.append('Others')
        values.append(float(total_other))

    available_currencies = {
        'USD': 'US Dollar',
        
        'CAD': 'Canadian Dollar',
        'BRL': 'Brazilian Real',
        'KRW': 'Korean Won',
        'EUR': 'Euro',
        'JPY': 'Japanese Yen',
        'AUD': 'Australian Dollar',
        'VND': 'Vietnamese Dong',
    }

    # Calculate percentages based on the true total net worth
    if total_net_worth > 0:
        crypto_percent = (total_crypto / total_net_worth) * 100
        stocks_percent = (total_stocks / total_net_worth) * 100
        real_estate_percent = (total_real_estate / total_net_worth) * 100
        vehicle_percent = (total_vehicle / total_net_worth) * 100
        cash_percent = (total_cash / total_net_worth) * 100
        other_percent = (total_other / total_net_worth) * 100
    else:
        crypto_percent = 0
        stocks_percent = 0
        real_estate_percent = 0
        vehicle_percent = 0
        cash_percent = 0
        other_percent = 0
    totals = [
        {'type': 'Crypto', 'url': 'home', 'value': total_crypto, 'percent': crypto_percent},
        {'type': 'Stocks', 'url': 'stocks', 'value': total_stocks, 'percent': stocks_percent},
        {'type': 'Real Estate', 'url': 'real_estate', 'value': total_real_estate, 'percent': real_estate_percent},
        {'type': 'Vehicles', 'url': 'vehicles', 'value': total_vehicle, 'percent': vehicle_percent},
        {'type': 'Cash/Fixed Income', 'url': 'cash', 'value': total_cash, 'percent': cash_percent},
        {'type': 'Others', 'url': 'other', 'value': total_other, 'percent': other_percent},
    ]
    totals.sort(key=lambda x: float(x['value']), reverse=True)

    # Build labels and values from sorted totals for charts
    chart_labels = [t['type'] for t in totals]
    chart_values = [float(t['value']) for t in totals]
    chart_percentages = [t['percent'] for t in totals]  # Use the same percentages as the table
    if chart_labels and chart_values:
        # Futuristic color palette with neon-like colors
        futuristic_colors = [
            '#0080ff',  # Electric Blue - for Real Estate
            '#ff6b00',  # Neon Orange - for Vehicles  
            '#00ff88',  # Neon Green - for Stocks
            '#ff00ff',  # Magenta - for Crypto
            '#00ff88',  # Neon Green - for Cash/Fixed Income
            '#ffff00'   # Neon Yellow - for Others
        ]
        
        # Enhanced donut chart with futuristic styling
        fig_pie = go.Figure(data=[go.Pie(
            labels=chart_labels, 
            values=chart_percentages,  # Use percentages instead of raw values
            textinfo='label+percent',
            texttemplate='<b style="color:#ffffff; text-shadow: 0 0 10px #00ffff;">%{label}</b><br><span style="color:#00ffff; font-size:14px; text-shadow: 0 0 8px #00ffff;">%{value:.0f}%</span>',
            textposition='outside',
            showlegend=False,
            hole=0.6,  # Larger hole for futuristic look
            textfont=dict(size=12, color='white', family='Courier New, monospace'),
            hovertemplate='<b style="color:#ffffff;">%{label}</b><br><span style="color:#00ffff;">%{value:.0f}%</span><extra></extra>',
            marker=dict(
                colors=futuristic_colors,
                line=dict(
                    color='#ffffff',
                    width=1
                )
            )
        )])
        fig_pie.update_layout(
            title=dict(
                text="<span style='color:#00ffff; font-family:Courier New, monospace; font-size:16px; text-shadow: 0 0 12px #00ffff;'>PORTFOLIO DISTRIBUTION</span>",
                x=0.5,  # Center horizontally
                xanchor='center',  # Anchor point for centering
                font=dict(color="#00ffff")
            ),
            margin=dict(t=40, b=40, l=30, r=30),  # Reduced margins for mobile optimization
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            # Center the donut chart
            xaxis=dict(
                domain=[0.15, 0.85],  # Use 70% of width, centered
                showgrid=False,
                showticklabels=False,
                zeroline=False,
                showline=False,
            ),
            yaxis=dict(
                domain=[0.15, 0.85],  # Use 70% of height for donut chart
                showgrid=False,
                showticklabels=False,
                zeroline=False,
                showline=False,
            ),
            # No legend needed since labels are outside
            showlegend=False,
            # Ensure responsive behavior
            autosize=True,
            height=350,  # Reduced height for better mobile fit
        )
        pie_chart_html = fig_pie.to_html(full_html=False, config={"responsive": True, "displayModeBar": False})
        
        # Futuristic stacked bar chart
        bar_segments = []
        # Use the same futuristic color palette
        bar_colors = futuristic_colors
        # Use the same percentages from the table for consistency
        table_percentages = [t['percent'] for t in totals]
        int_percentages = [int(round(p)) for p in table_percentages]
        for i, (label, percent) in enumerate(zip(chart_labels, int_percentages)):
            bar_segments.append(go.Bar(
                x=[percent],
                y=[""],
                name=label,
                orientation='h',
                marker=dict(
                    color=bar_colors[i % len(bar_colors)],
                    line=dict(
                        color='#ffffff',
                        width=1
                    )
                ),
                text=[f"<b style='color:#ffffff; text-shadow: 0 0 5px #00ffff;'>{label}</b><br><span style='color:#00ffff; font-size:14px;'>{percent}%</span>"],
                textposition='inside',
                insidetextanchor='middle',
                textfont=dict(color='white', size=12, family='Courier New, monospace'),
                hovertemplate=f"<b style='color:#ffffff;'>{label}</b><br><span style='color:#00ffff;'>{{x}}%</span><extra></extra>",
            ))
        fig_bar = go.Figure(data=bar_segments)
        fig_bar.update_layout(
            barmode='stack',
            title=dict(
                text="<span style='color:#00ffff; font-family:Courier New, monospace; font-size:18px; text-shadow: 0 0 12px #00ffff;'>PORTFOLIO DISTRIBUTION [BAR]</span>",
                x=0.5,
                xanchor='center',
                font=dict(color="#00ffff")
            ),
            margin=dict(t=50, b=0, l=0, r=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#00ffff", family='Courier New, monospace'),
            xaxis=dict(
                title=None, 
                range=[0, 100], 
                ticksuffix='%', 
                ticklen=4, 
                tickwidth=1,
                tickfont=dict(color='#00ffff', size=10, family='Courier New, monospace')
            ),
            yaxis=dict(title=None, showticklabels=False, showgrid=False, zeroline=False, visible=False, ticklen=4, tickwidth=1),
            showlegend=False,
            height=200,
            autosize=True
        )
        bar_chart_html = fig_bar.to_html(full_html=False, config={"responsive": True, "displayModeBar": False})
    else:
        pie_chart_html = None
        bar_chart_html = None

    # Save snapshot in USD for consistency with daily command
    today = date.today()
    total_net_worth_usd = get_user_total_net_worth(request.user, 'USD')
    
    # Check if this is the user's first snapshot
    existing_snapshots = NetWorthSnapshot.objects.filter(user=request.user)
    if existing_snapshots.exists():
        # User has snapshots, create today's snapshot normally
        NetWorthSnapshot.objects.get_or_create(
            user=request.user, date=today,
            defaults={'net_worth': total_net_worth_usd}
        )
    else:
        # This is the user's first time - check if 10 minutes have passed since account creation
        from django.utils import timezone
        from datetime import timedelta
        
        # Get the user's first snapshot (which should be the only one if it exists)
        first_snapshot = existing_snapshots.first()
        
        if first_snapshot is None:
            # No snapshots exist yet - check if 10 minutes have passed since user creation
            user_created_time = request.user.date_joined
            current_time = timezone.now()
            time_since_creation = current_time - user_created_time
            
            # Only create snapshot if more than 10 minutes have passed
            if time_since_creation > timedelta(minutes=10):
                NetWorthSnapshot.objects.create(
                    user=request.user, date=today,
                    net_worth=total_net_worth_usd
                )

    # Calculate BTC equivalent
    btc_equivalent = get_btc_equivalent(total_net_worth_usd)

    # Check if user is new and show appropriate message
    show_new_user_message = False
    new_user_minutes_remaining = 0
    
    if not NetWorthSnapshot.objects.filter(user=request.user).exists():
        from django.utils import timezone
        from datetime import timedelta
        
        user_created_time = request.user.date_joined
        current_time = timezone.now()
        time_since_creation = current_time - user_created_time
        
        if time_since_creation <= timedelta(minutes=10):
            show_new_user_message = True
            new_user_minutes_remaining = 10 - int(time_since_creation.total_seconds() / 60)

    # Net Worth Over Time Chart
    # Get only the latest snapshot per day for smooth chart
    from django.db.models import Max
    from django.db.models.functions import TruncDate
    
    # Get the latest snapshot ID for each day
    latest_snapshot_ids = (
        NetWorthSnapshot.objects
        .filter(user=request.user)
        .values('date')
        .annotate(latest_id=Max('id'))
        .values_list('latest_id', flat=True)
    )
    
    # Get the actual snapshots using those IDs
    snapshots = NetWorthSnapshot.objects.filter(
        id__in=latest_snapshot_ids
    ).order_by('date')
    
    # Apply date filtering based on selected_range
    if selected_range != 'all' and snapshots.exists():
        from datetime import timedelta
        from django.utils import timezone
        
        # Use timezone-aware today
        today = timezone.now().date()
        
        # Handle both lowercase and uppercase range values
        range_lower = selected_range.lower()
        
        if range_lower == '1w':
            start_date = today - timedelta(days=7)
        elif range_lower == '1m':
            start_date = today - timedelta(days=30)
        elif range_lower == '3m':
            start_date = today - timedelta(days=90)
        elif range_lower == '6m':
            start_date = today - timedelta(days=180)
        elif range_lower == '1y':
            start_date = today - timedelta(days=365)
        else:
            start_date = None
            
        if start_date:
            # Filter snapshots to only include those from start_date onwards
            snapshots = snapshots.filter(date__gte=start_date)
    
    dates = [snap.date.strftime('%Y-%m-%d') for snap in snapshots]
    values = [float(convert_currency(snap.net_worth, 'USD', selected_currency)) for snap in snapshots]
    
    # Calculate performance metrics
    performance_info = ""
    if len(values) >= 2:
        first_value = values[0]
        last_value = values[-1]
        difference = last_value - first_value
        percentage_change = (difference / first_value) * 100 if first_value != 0 else 0
        
        # Format the difference with proper sign and currency
        if difference >= 0:
            sign = "+"
            color = "#4caf50"  # Green for gains
        else:
            sign = ""
            color = "#f44336"  # Red for losses
        
        # Format the amount with proper currency symbol
        formatted_difference = f"{sign}{difference:,.0f}"
        
        # Get the time period label
        time_period_map = {
            '1w': '1W',
            '1m': '1M', 
            '3m': '3M',
            '1y': '1Y',
            'all': 'All'
        }
        time_period = time_period_map.get(selected_range, selected_range.upper())
        
        # Create performance info string
        performance_info = f": {formatted_difference}{currency_symbol} ({percentage_change:+.1f}%) [{time_period}]"
    
    networth_line_chart = None
    if dates and values:
        try:
            fig = go.Figure()
            
            # Modern gradient line chart
            fig.add_trace(go.Scatter(
                x=dates, 
                y=values, 
                mode='lines+markers', 
                name='Net Worth',
                line=dict(
                    width=3,
                    color='#4caf50',
                    shape='spline'  # Smooth curved lines
                ),
                marker=dict(
                    size=6,
                    color='#4caf50',
                    line=dict(width=2, color='#ffffff'),
                    symbol='circle'
                ),
                fill='tonexty',  # Fill area below the line
                fillcolor='rgba(76, 175, 80, 0.1)',  # Light green fill
                hovertemplate='<b>%{x}</b><br>Net Worth: <b>%{y:,.0f} ' + currency_symbol + '</b><extra></extra>'
            ))
            
            # Modern layout configuration
            fig.update_layout(
                title=dict(
                    text=f"Net Worth Over Time{performance_info}",
                    font=dict(size=20, color='#ffffff', family='Arial, sans-serif'),
                    x=0.5,
                    xanchor='center'
                ),
                xaxis_title=None,  # Remove x-axis title for cleaner look
                yaxis_title=None,  # Remove y-axis title for cleaner look
                paper_bgcolor="rgba(0,0,0,0)",  # Transparent background
                plot_bgcolor="rgba(0,0,0,0)",  # Transparent plot background
                font=dict(color="#e0e0e0", family='Arial, sans-serif'),
                # Responsive settings
                autosize=True,
                height=400,  # Keep same height
                margin=dict(t=60, b=40, l=40, r=20),  # Adjusted margins for modern look
                # Modern x-axis styling
                xaxis=dict(
                    tickangle=0,
                    tickmode='auto',
                    nticks=min(8, len(dates)),
                    tickformat='%b %d',
                    tickfont=dict(size=11, color='#cccccc'),
                    tickcolor='#333333',
                    tickwidth=1,
                    ticklen=4,
                    showgrid=True,
                    gridcolor='rgba(255,255,255,0.1)',
                    gridwidth=1,
                    zeroline=False,
                    showline=True,
                    linecolor='rgba(255,255,255,0.2)',
                    linewidth=1
                ),
                # Modern y-axis styling - initially show values, will be hidden by JavaScript if privacy mode is on
                yaxis=dict(
                    tickfont=dict(size=11, color='#cccccc'),
                    tickformat=',',
                    tickwidth=1,
                    ticklen=4,
                    tickcolor='#333333',
                    showgrid=True,
                    gridcolor='rgba(255,255,255,0.1)',
                    gridwidth=1,
                    zeroline=False,
                    showline=True,
                    linecolor='rgba(255,255,255,0.2)',
                    linewidth=1,
                    side='left',
                    automargin=True,
                    range=[min(values) * 0.999, max(values) * 1.001]  # Tighter range with minimal padding
                ),
                # Hide legend for cleaner look
                showlegend=False,
                # Modern hover styling
                hovermode='x unified',
                hoverlabel=dict(
                    bgcolor='rgba(0,0,0,0.9)',
                    bordercolor='#4caf50',
                    font=dict(size=12, color='#ffffff')
                )
            )
            
            # Generate chart with modern config
            networth_line_chart = fig.to_html(
                full_html=False, 
                config={
                    "responsive": True,
                    "displayModeBar": True,
                    "displaylogo": False,
                    "modeBarButtonsToRemove": ["pan2d", "lasso2d", "select2d", "zoomIn2d", "zoomOut2d"],
                    "toImageButtonOptions": {
                        "format": "png",
                        "filename": "net_worth_chart",
                        "height": 400,
                        "width": 800,
                        "scale": 2
                    }
                }
            )
            
            # Add JavaScript to handle privacy mode for the chart
            privacy_script = """
            <script>
            document.addEventListener('DOMContentLoaded', function() {
                // Check if privacy mode is enabled and apply to chart
                const privacyState = localStorage.getItem('privacyMode');
                if (privacyState === 'on' && typeof Plotly !== 'undefined') {
                    const plotElements = document.querySelectorAll('.js-plotly-plot');
                    plotElements.forEach(function(element) {
                        if (element && element.layout) {
                            // Hide Y-axis tick labels when privacy mode is on
                            Plotly.relayout(element, {
                                'yaxis.showticklabels': false,
                                'yaxis.tickformat': '',
                                'yaxis.title': ''
                            });
                        }
                    });
                }
            });
            </script>
            """
            
            # Append the privacy script to the chart HTML
            networth_line_chart += privacy_script
            
        except Exception as e:
            print(f"ERROR generating chart: {e}")
            networth_line_chart = None

    return render(request, 'general.html', {
        'username': request.user.username,
        'totals': totals,
        'total_net_worth': total_net_worth,
        'pie_chart': pie_chart_html,
        'bar_chart': bar_chart_html,
        'selected_currency': selected_currency,
        'available_currencies': available_currencies,
        'show_cash_form': show_cash_form,
        'show_other_form': show_other_form,
        'cash_currencies': cash_currencies,
        'currency_symbol': currency_symbol,
        'user': request.user,
        'selected_range': selected_range,
        'networth_line_chart': networth_line_chart,
        'btc_equivalent': btc_equivalent,
        'show_new_user_message': show_new_user_message,
        'new_user_minutes_remaining': new_user_minutes_remaining,
    })

@login_required
def performance(request):
    user = request.user
    today = date.today()
    selected_currency = request.GET.get('currency', 'USD')
    currency_symbol = CURRENCY_SYMBOLS.get(selected_currency, selected_currency)

    # --- Calculate current net worth (reuse logic from general) ---
    total_net_worth = get_user_total_net_worth(user, selected_currency)
    # --- Save snapshot if not already saved today ---
    # Always save snapshot in USD for consistency with daily command
    total_net_worth_usd = get_user_total_net_worth(user, 'USD')
    
    # Check if this is the user's first snapshot
    existing_snapshots = NetWorthSnapshot.objects.filter(user=user)
    if existing_snapshots.exists():
        # User has snapshots, create today's snapshot normally
        NetWorthSnapshot.objects.get_or_create(
            user=user, date=today,
            defaults={'net_worth': total_net_worth_usd}
        )
    else:
        # This is the user's first time - check if 10 minutes have passed since account creation
        from django.utils import timezone
        from datetime import timedelta
        
        # Get the user's first snapshot (which should be the only one if it exists)
        first_snapshot = existing_snapshots.first()
        
        if first_snapshot is None:
            # No snapshots exist yet - check if 10 minutes have passed since user creation
            user_created_time = user.date_joined
            current_time = timezone.now()
            time_since_creation = current_time - user_created_time
            
            # Only create snapshot if more than 10 minutes have passed
            if time_since_creation > timedelta(minutes=10):
                NetWorthSnapshot.objects.create(
                    user=user, date=today,
                    net_worth=total_net_worth_usd
                )

    # Calculate BTC equivalent
    btc_equivalent = get_btc_equivalent(total_net_worth_usd)

    # --- Get all snapshots for this user ---
    # Get only the latest snapshot per day for smooth chart
    latest_snapshot_ids = (
        NetWorthSnapshot.objects
        .filter(user=user)
        .values('date')
        .annotate(latest_id=Max('id'))
        .values_list('latest_id', flat=True)
    )
    
    # Get the actual snapshots using those IDs
    snapshots = NetWorthSnapshot.objects.filter(
        id__in=latest_snapshot_ids
    ).order_by('date')
    
    dates = [snap.date.strftime('%Y-%m-%d') for snap in snapshots]
    values = [float(convert_currency(snap.net_worth, 'USD', selected_currency)) for snap in snapshots]

    # Calculate performance metrics for performance view
    performance_info = ""
    if len(values) >= 2:
        first_value = values[0]
        last_value = values[-1]
        difference = last_value - first_value
        percentage_change = (difference / first_value) * 100 if first_value != 0 else 0
        
        # Format the difference with proper sign and currency
        if difference >= 0:
            sign = "+"
        else:
            sign = ""
        
        # Format the amount with proper currency symbol
        formatted_difference = f"{sign}{difference:,.0f}"
        
        # Create performance info string (no time period for performance view)
        performance_info = f": {formatted_difference}{currency_symbol} ({percentage_change:+.1f}%)"

    # --- Plotly line chart ---
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=values, mode='lines+markers', name='Net Worth'))
    
    # Responsive layout configuration
    fig.update_layout(
        title=f"Net Worth Over Time{performance_info}",
        xaxis_title="Date",
        yaxis_title=f"Net Worth ({currency_symbol})",
        paper_bgcolor="#121212",
        plot_bgcolor="#121212",
        font=dict(color="#e0e0e0"),
        # Responsive settings
        autosize=True,
        height=400,  # Fixed height for consistency
        margin=dict(t=50, b=80, l=60, r=20),  # Adjusted margins for mobile
        # Mobile-friendly x-axis configuration
        xaxis=dict(
            tickangle=0,  # Horizontal labels instead of vertical
            tickmode='auto',
            nticks=min(8, len(dates)),  # Limit number of ticks on mobile
            tickformat='%b %d',  # Shorter date format
            tickfont=dict(size=10),  # Smaller font for mobile
        ),
        # Mobile-friendly y-axis configuration
        yaxis=dict(
            tickfont=dict(size=10),  # Smaller font for mobile
            tickformat=',',  # Add commas to large numbers
        ),
        # Hide modebar on mobile (optional)
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=10)
        )
    )
    
    # Generate chart with responsive config
    chart_html = fig.to_html(
        full_html=False, 
        config={
            "responsive": True,
            "displayModeBar": True,
            "displaylogo": False,
            "modeBarButtonsToRemove": ["pan2d", "lasso2d", "select2d"],
            "toImageButtonOptions": {
                "format": "png",
                "filename": "net_worth_chart",
                "height": 400,
                "width": 800,
                "scale": 2
            }
        }
    )

    return render(request, 'performance.html', {
        'chart': chart_html,
        'snapshots': snapshots,
        'selected_currency': selected_currency,
        'currency_symbol': currency_symbol,
        'user': request.user,
        'btc_equivalent': btc_equivalent,
    })

def root_redirect(request):
    if request.user.is_authenticated:
        return redirect('general')  # Redirect to 'general' if the user is logged in
    else:
        return redirect('login')  # Redirect to 'login' if the user is not logged in

def resume(request):
    return render(request, 'resume.html', {'user': request.user})

def bio(request):
    return render(request, 'bio.html', {'user': request.user})

def projects(request):
    return render(request, 'projects.html', {'user': request.user})

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
    'wld': 'worldcoin-wld',
    'inj': 'injective-protocol',
    'ldo': 'lido-dao',
    'sei': 'sei-network',
    'pyth': 'pyth-network',
    'ltc': 'litecoin',
    'uni': 'uniswap',
    'bgb': 'bitget-token',
    'pepe': 'pepe',
    'avax': 'avalanche-2',
    'apt': 'aptos',
    'aave': 'aave',
    'mnt': 'mantlenetwork',
    'pol': 'matic-network',
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
    'virtual': 'virtual-protocol',
    'arb': 'arbitrum',
    'xrp': 'ripple',
    'icp': 'internet-computer',
    'stg': 'stargate-finance',
    'matic': 'matic-network',
    'algo': 'algorand',
    'cash' : 'tether',
    'trump' : 'official-trump',
    'opul' : 'opulous',
    'memag': 'meta-masters-guild-games',
    'ray': 'raydium',
    'daddy': 'daddy-tate',
    'kas': 'kaspa',
    'egld': 'elrond-erd-2',
    'mina': 'mina-protocol',
    'croge': 'crogecoin',
    'brett' : 'based-brett',
    'aster' : 'aster-2'
}

CURRENCY_SYMBOLS = {
    'USD': '$',
    'BRL': 'R$',
    'EUR': '€',
    'CAD': 'C$',
    'KRW': '₩',
    'JPY': '¥',
    'AUD': 'A$',
    'VND': '₫',
}

def safe_decimal(val):
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0')

def safe_float(val):
    try:
        return float(val)
    except Exception:
        return 0

def get_user_total_net_worth(user, selected_currency):
    """Compute and cache the user's total net worth in the selected currency for 3 minutes."""
    cache_key = f"total_net_worth_{user.id}_{selected_currency}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    from decimal import Decimal
    from .models import Asset
    # --- Always sum in USD first ---
    # Crypto
    crypto_assets = Asset.objects.filter(owner=user, type='crypto')
    crypto_tickers = ['bitcoin'] + [map_ticker(asset.ticker) for asset in crypto_assets]
    crypto_prices = get_multiple_asset_prices(crypto_tickers)
    total_crypto_usd = sum(
        safe_decimal(crypto_prices.get(map_ticker(asset.ticker), {}).get('usd', 0)) * asset.amount
        for asset in crypto_assets
    )
    # Stocks
    stock_assets = Asset.objects.filter(owner=user, type='stock')
    stock_tickers = [asset.ticker.upper() for asset in stock_assets]
    stock_prices = get_multiple_stock_prices(stock_tickers)
    total_stocks_usd = sum(
        safe_decimal(stock_prices.get(asset.ticker.upper(), 0)) * asset.amount
        for asset in stock_assets
    )
    # Cash
    cash_assets = Asset.objects.filter(owner=user, type='cash')
    total_cash_usd = sum(convert_currency(cash.amount, cash.currency or 'USD', 'USD') for cash in cash_assets)
    # Real Estate
    real_estate_assets = Asset.objects.filter(owner=user, type='real_estate')
    total_real_estate_usd = sum(convert_currency(re.amount, re.currency or 'USD', 'USD') for re in real_estate_assets)
    # Vehicle
    vehicle_assets = Asset.objects.filter(owner=user, type='vehicle')
    total_vehicle_usd = sum(convert_currency(v.amount, v.currency or 'USD', 'USD') for v in vehicle_assets)
    # Other
    other_assets = Asset.objects.filter(owner=user, type='other')
    total_other_usd = sum(convert_currency(o.amount, o.currency or 'USD', 'USD') for o in other_assets)
    # Sum all in USD
    total_net_worth_usd = total_crypto_usd + total_stocks_usd + total_real_estate_usd + total_cash_usd + total_vehicle_usd + total_other_usd
    # Convert to selected currency
    total_net_worth = convert_currency(total_net_worth_usd, 'USD', selected_currency)
    cache.set(cache_key, total_net_worth, timeout=180)
    return total_net_worth

def get_btc_equivalent(total_net_worth_usd):
    """Calculate BTC equivalent of the total net worth"""
    try:
        btc_price_data = get_multiple_asset_prices(['bitcoin'])
        btc_price_usd = safe_decimal(btc_price_data.get('bitcoin', {}).get('usd', 0))
        if btc_price_usd > 0:
            btc_equivalent = total_net_worth_usd / btc_price_usd
            return btc_equivalent
        else:
            return Decimal('0')
    except Exception:
        return Decimal('0')

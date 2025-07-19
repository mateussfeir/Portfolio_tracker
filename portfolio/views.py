from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib import messages
from .forms import AddAssetForm, SignUpForm
from .models import Asset
import requests
from decimal import Decimal, InvalidOperation
import plotly.graph_objects as go
from django.shortcuts import render
import yfinance as yf
from django.urls import reverse
from django.http import HttpResponseRedirect
# test

# Currency conversion function
def get_exchange_rates(base_currency='USD'):
    """Get exchange rates from USD to other currencies using a free API"""
    try:
        # Using exchangerate-api.com (free tier)
        url = f"https://api.exchangerate-api.com/v4/latest/{base_currency}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        return data.get('rates', {})
    except Exception as e:
        print(f"Error fetching exchange rates: {e}")
        # Fallback rates (approximate)
        return {
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
            return redirect('general')  # Redirect to the General tab after signup
    else:
        form = SignUpForm()
    return render(request, 'signup.html', {'form': form})

@login_required
def home(request):
    # Get selected currency from request, default to USD
    selected_currency = request.GET.get('currency', 'USD')
    currency_symbol = CURRENCY_SYMBOLS.get(selected_currency, selected_currency)
    if request.method == 'POST':
        form = AddAssetForm(request.POST)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.owner = request.user
            # Ensure new assets added from home are crypto
            asset.type = 'crypto'
            asset.save()
            return redirect('home')  # Refresh the page after adding the asset
        else:
            messages.error(request, "Failed to add asset. Please check your inputs.")
    else:
        form = AddAssetForm()

    # Get user crypto assets only
    user_assets = Asset.objects.filter(owner=request.user, type='crypto')
    tickers = ['bitcoin'] + [map_ticker(asset.ticker) for asset in user_assets]
    prices = get_multiple_asset_prices(tickers)

    # Fetch Bitcoin price explicitly
    bitcoin_price = prices.get('bitcoin', {}).get('usd', 'N/A')

    # Calculate total net worth in USD first
    total_net_worth_usd = sum(
        (Decimal(str(prices.get(map_ticker(asset.ticker), {}).get('usd', 0))) * asset.amount)
        for asset in user_assets
    )
    
    # Convert to selected currency
    total_net_worth = convert_currency(total_net_worth_usd, 'USD', selected_currency)

    # Populate assets and chart data
    assets_with_value = []
    labels = []
    values = []
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

    # Prepare pie and bar charts for crypto
    if labels and values:
        total = sum(values)
        percentages = [(v / total) * 100 if total > 0 else 0 for v in values]
        # Pie chart
        fig_pie = go.Figure(data=[go.Pie(labels=labels, values=values, textinfo='percent+label', showlegend=True)])
        fig_pie.update_layout(
            title="Crypto Portfolio Distribution",
            margin=dict(t=50, b=50, l=25, r=25),
            paper_bgcolor="#121212",
            plot_bgcolor="#121212",
            font=dict(color="#e0e0e0")
        )
        pie_chart_html = fig_pie.to_html(full_html=False)
        # Stacked bar chart
        bar_segments = []
        colors = ["#4caf50", "#2196f3", "#ff9800", "#9c27b0", "#e91e63"]
        for i, (label, percent) in enumerate(zip(labels, percentages)):
            bar_segments.append(go.Bar(
                x=[percent],
                y=[""],
                name=label,
                orientation='h',
                marker=dict(color=colors[i % len(colors)]),
                text=[f"{label}\n{percent:.2f}%"],
                textposition='inside',
                hovertemplate=f"{label}: {{x:.2f}}%<extra></extra>",
            ))
        fig_bar = go.Figure(data=bar_segments)
        fig_bar.update_layout(
            barmode='stack',
            title="Crypto Portfolio Distribution (Stacked Bar)",
            margin=dict(t=50, b=50, l=25, r=25),
            paper_bgcolor="#121212",
            plot_bgcolor="#121212",
            font=dict(color="#e0e0e0"),
            xaxis=dict(title='Percentage', range=[0, 100], ticksuffix='%'),
            yaxis=dict(showticklabels=False),
            showlegend=True,
            height=180,
        )
        bar_chart_html = fig_bar.to_html(full_html=False)
    else:
        pie_chart_html = None
        bar_chart_html = None

    # Get available currencies for dropdown
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
        'CHF': 'Swiss Franc'
    }

    # Sort assets by value descending (robust to '-' or non-numeric)
    def get_value_for_sort(x):
        try:
            return float(x['value'])
        except Exception:
            return 0
    assets_with_value.sort(key=get_value_for_sort, reverse=True)

    # Render the page
    return render(request, 'home.html', {
        'username': request.user.username,
        'assets': assets_with_value,
        'form': form,
        'bitcoin_price': bitcoin_price,  # Pass the Bitcoin price to the template
        'total_net_worth': total_net_worth,
        'selected_currency': selected_currency,
        'available_currencies': available_currencies,
        'currency_symbol': currency_symbol,
        'pie_chart': pie_chart_html,
        'bar_chart': bar_chart_html,
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
        'CHF': 'Swiss Franc'
    }
    if request.method == 'POST':
        form = AddAssetForm(request.POST, instance=asset)
        if form.is_valid():
            form.save()
            messages.success(request, "Asset updated successfully.")
            if asset.type == 'stock':
                return redirect('stocks')
            elif asset.type == 'crypto':
                return redirect('home')
            elif asset.type == 'real_estate':
                return redirect('real_estate')
            elif asset.type == 'cash':
                return redirect('cash')
            elif asset.type == 'other':
                return redirect('other')
            else:
                return redirect('general')
    else:
        form = AddAssetForm(instance=asset)
    return render(request, 'edit_holding.html', {'form': form, 'asset': asset, 'available_currencies': available_currencies})


@login_required
def stocks(request):
    # Get selected currency from request, default to USD
    selected_currency = request.GET.get('currency', 'USD')
    currency_symbol = CURRENCY_SYMBOLS.get(selected_currency, selected_currency)
    if request.method == 'POST':
        form = AddAssetForm(request.POST)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.owner = request.user
            asset.type = 'stock'
            asset.ticker = asset.ticker.upper()  # Ensure ticker is uppercase
            asset.save()
            return redirect('stocks')
        else:
            messages.error(request, "Failed to add asset. Please check your inputs.")
    else:
        form = AddAssetForm()

    # Get user stock assets
    user_assets = Asset.objects.filter(owner=request.user, type='stock')
    tickers = [asset.ticker.upper() for asset in user_assets]

    # Fetch stock prices using yfinance
    prices = {}
    if tickers:
        if len(tickers) == 1:
            # Handle single ticker separately
            ticker = tickers[0]
            try:
                data = yf.Ticker(ticker).history(period='1d')
                if not data.empty:
                    prices[ticker] = float(data['Close'].iloc[-1])
                else:
                    prices[ticker] = None
            except Exception:
                prices[ticker] = None
        else:
            try:
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

    # Calculate total net worth in USD first
    total_net_worth_usd = 0
    for asset in user_assets:
        price = prices.get(asset.ticker.upper())
        try:
            price_decimal = safe_decimal(price)
        except Exception:
            price_decimal = Decimal('0')
        total_net_worth_usd += price_decimal * asset.amount
    
    # Convert to selected currency
    total_net_worth = convert_currency(total_net_worth_usd, 'USD', selected_currency)

    # Populate assets and chart data
    assets_with_value = []
    labels = []
    values = []
    for asset in user_assets:
        ticker = asset.ticker.upper()
        price_usd = prices.get(ticker)
        try:
            price_usd_decimal = safe_decimal(price_usd)
            # Convert price to selected currency
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

    # Prepare pie and bar charts for stocks
    if labels and values:
        total = sum(values)
        percentages = [(v / total) * 100 if total > 0 else 0 for v in values]
        # Pie chart
        fig_pie = go.Figure(data=[go.Pie(labels=labels, values=values, textinfo='percent+label', showlegend=True)])
        fig_pie.update_layout(
            title="Stock Portfolio Distribution",
            margin=dict(t=50, b=50, l=25, r=25),
            paper_bgcolor="#121212",
            plot_bgcolor="#121212",
            font=dict(color="#e0e0e0")
        )
        pie_chart_html = fig_pie.to_html(full_html=False)
        # Stacked bar chart
        bar_segments = []
        colors = ["#4caf50", "#2196f3", "#ff9800", "#9c27b0", "#e91e63"]
        for i, (label, percent) in enumerate(zip(labels, percentages)):
            bar_segments.append(go.Bar(
                x=[percent],
                y=[""],
                name=label,
                orientation='h',
                marker=dict(color=colors[i % len(colors)]),
                text=[f"{label}\n{percent:.2f}%"],
                textposition='inside',
                hovertemplate=f"{label}: {{x:.2f}}%<extra></extra>",
            ))
        fig_bar = go.Figure(data=bar_segments)
        fig_bar.update_layout(
            barmode='stack',
            title="Stock Portfolio Distribution (Stacked Bar)",
            margin=dict(t=50, b=50, l=25, r=25),
            paper_bgcolor="#121212",
            plot_bgcolor="#121212",
            font=dict(color="#e0e0e0"),
            xaxis=dict(title='Percentage', range=[0, 100], ticksuffix='%'),
            yaxis=dict(showticklabels=False),
            showlegend=True,
            height=180,
        )
        bar_chart_html = fig_bar.to_html(full_html=False)
    else:
        pie_chart_html = None
        bar_chart_html = None

    # Get available currencies for dropdown
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
        'CHF': 'Swiss Franc'
    }

    # Sort assets by value descending (robust to '-' or non-numeric)
    def get_value_for_sort(x):
        try:
            return float(x['value'])
        except Exception:
            return 0
    assets_with_value.sort(key=get_value_for_sort, reverse=True)

    return render(request, 'stocks.html', {
        'username': request.user.username,
        'assets': assets_with_value,
        'form': form,
        'total_net_worth': total_net_worth,
        'selected_currency': selected_currency,
        'available_currencies': available_currencies,
        'currency_symbol': currency_symbol,
        'pie_chart': pie_chart_html,
        'bar_chart': bar_chart_html,
    })

@login_required
def real_estate(request):
    selected_currency = request.GET.get('currency', 'USD')
    currency_symbol = CURRENCY_SYMBOLS.get(selected_currency, selected_currency)
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
    # Get all real estate assets
    assets = Asset.objects.filter(owner=request.user, type='real_estate')
    # Calculate values in selected currency
    total_net_worth = Decimal('0')
    assets_with_value = []
    for asset in assets:
        value = convert_currency(asset.amount, asset.currency or 'USD', selected_currency)
        total_net_worth += value
        assets_with_value.append({
            'id': asset.id,
            'ticker': asset.ticker,
            'amount': asset.amount,
            'currency': asset.currency,
            'value': value,
        })
    # Sort assets by value descending
    assets_with_value.sort(key=lambda x: x['value'], reverse=True)
    # Pie and bar chart code ...
    labels = [a['ticker'] for a in assets_with_value]
    values = [float(a['value']) for a in assets_with_value]
    if labels and values:
        total = sum(values)
        percentages = [(v / total) * 100 if total > 0 else 0 for v in values]
        # Pie chart
        fig_pie = go.Figure(data=[go.Pie(labels=labels, values=values, textinfo='percent+label', showlegend=True)])
        fig_pie.update_layout(
            title="Real Estate Portfolio Distribution",
            margin=dict(t=50, b=50, l=25, r=25),
            paper_bgcolor="#121212",
            plot_bgcolor="#121212",
            font=dict(color="#e0e0e0")
        )
        pie_chart_html = fig_pie.to_html(full_html=False)
        # Stacked bar chart
        bar_segments = []
        colors = ["#4caf50", "#2196f3", "#ff9800", "#9c27b0", "#e91e63"]
        for i, (label, percent) in enumerate(zip(labels, percentages)):
            bar_segments.append(go.Bar(
                x=[percent],
                y=[""],
                name=label,
                orientation='h',
                marker=dict(color=colors[i % len(colors)]),
                text=[f"{label}\n{percent:.2f}%"],
                textposition='inside',
                hovertemplate=f"{label}: {{x:.2f}}%<extra></extra>",
            ))
        fig_bar = go.Figure(data=bar_segments)
        fig_bar.update_layout(
            barmode='stack',
            title="Real Estate Portfolio Distribution (Stacked Bar)",
            margin=dict(t=50, b=50, l=25, r=25),
            paper_bgcolor="#121212",
            plot_bgcolor="#121212",
            font=dict(color="#e0e0e0"),
            xaxis=dict(title='Percentage', range=[0, 100], ticksuffix='%'),
            yaxis=dict(showticklabels=False),
            showlegend=True,
            height=180,
        )
        bar_chart_html = fig_bar.to_html(full_html=False)
    else:
        pie_chart_html = None
        bar_chart_html = None

    # Get available currencies for dropdown
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
        'CHF': 'Swiss Franc'
    }
    return render(request, 'real_estate.html', {
        'username': request.user.username,
        'assets': assets_with_value,
        'total_net_worth': total_net_worth,
        'form': form,
        'pie_chart': pie_chart_html,
        'bar_chart': bar_chart_html,
        'selected_currency': selected_currency,
        'available_currencies': available_currencies,
        'currency_symbol': currency_symbol,
    })

@login_required
def cash(request):
    selected_currency = request.GET.get('currency', 'USD')
    currency_symbol = CURRENCY_SYMBOLS.get(selected_currency, selected_currency)
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
    # Get all cash assets
    assets = Asset.objects.filter(owner=request.user, type='cash')
    # Calculate values in selected currency
    total_net_worth = Decimal('0')
    assets_with_value = []
    for asset in assets:
        value = convert_currency(asset.amount, asset.currency or 'USD', selected_currency)
        total_net_worth += value
        assets_with_value.append({
            'id': asset.id,
            'ticker': asset.ticker,
            'amount': asset.amount,
            'currency': asset.currency,
            'value': value,
        })
    # Sort assets by value descending
    assets_with_value.sort(key=lambda x: x['value'], reverse=True)
    # Pie and bar chart code ...
    labels = [a['ticker'] for a in assets_with_value]
    values = [float(a['value']) for a in assets_with_value]
    if labels and values:
        total = sum(values)
        percentages = [(v / total) * 100 if total > 0 else 0 for v in values]
        # Pie chart
        fig_pie = go.Figure(data=[go.Pie(labels=labels, values=values, textinfo='percent+label', showlegend=True)])
        fig_pie.update_layout(
            title="Cash Portfolio Distribution",
            margin=dict(t=50, b=50, l=25, r=25),
            paper_bgcolor="#121212",
            plot_bgcolor="#121212",
            font=dict(color="#e0e0e0")
        )
        pie_chart_html = fig_pie.to_html(full_html=False)
        # Stacked bar chart
        bar_segments = []
        colors = ["#4caf50", "#2196f3", "#ff9800", "#9c27b0", "#e91e63"]
        for i, (label, percent) in enumerate(zip(labels, percentages)):
            bar_segments.append(go.Bar(
                x=[percent],
                y=[""],
                name=label,
                orientation='h',
                marker=dict(color=colors[i % len(colors)]),
                text=[f"{label}\n{percent:.2f}%"],
                textposition='inside',
                hovertemplate=f"{label}: {{x:.2f}}%<extra></extra>",
            ))
        fig_bar = go.Figure(data=bar_segments)
        fig_bar.update_layout(
            barmode='stack',
            title="Cash Portfolio Distribution (Stacked Bar)",
            margin=dict(t=50, b=50, l=25, r=25),
            paper_bgcolor="#121212",
            plot_bgcolor="#121212",
            font=dict(color="#e0e0e0"),
            xaxis=dict(title='Percentage', range=[0, 100], ticksuffix='%'),
            yaxis=dict(showticklabels=False),
            showlegend=True,
            height=180,
        )
        bar_chart_html = fig_bar.to_html(full_html=False)
    else:
        pie_chart_html = None
        bar_chart_html = None

    # Get available currencies for dropdown
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
        'CHF': 'Swiss Franc'
    }
    return render(request, 'cash.html', {
        'username': request.user.username,
        'assets': assets_with_value,
        'total_net_worth': total_net_worth,
        'form': form,
        'pie_chart': pie_chart_html,
        'bar_chart': bar_chart_html,
        'selected_currency': selected_currency,
        'available_currencies': available_currencies,
        'currency_symbol': currency_symbol,
    })

@login_required
def other(request):
    selected_currency = request.GET.get('currency', 'USD')
    currency_symbol = CURRENCY_SYMBOLS.get(selected_currency, selected_currency)
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
    # Get all other assets
    assets = Asset.objects.filter(owner=request.user, type='other')
    # Calculate values in selected currency
    total_net_worth = Decimal('0')
    assets_with_value = []
    for asset in assets:
        value = convert_currency(asset.amount, asset.currency or 'USD', selected_currency)
        total_net_worth += value
        assets_with_value.append({
            'id': asset.id,
            'ticker': asset.ticker,
            'amount': asset.amount,
            'currency': asset.currency,
            'value': value,
        })
    # Sort assets by value descending
    assets_with_value.sort(key=lambda x: x['value'], reverse=True)
    # Pie and bar chart code ...
    labels = [a['ticker'] for a in assets_with_value]
    values = [float(a['value']) for a in assets_with_value]
    if labels and values:
        total = sum(values)
        percentages = [(v / total) * 100 if total > 0 else 0 for v in values]
        # Pie chart
        fig_pie = go.Figure(data=[go.Pie(labels=labels, values=values, textinfo='percent+label', showlegend=True)])
        fig_pie.update_layout(
            title="Other Portfolio Distribution",
            margin=dict(t=50, b=50, l=25, r=25),
            paper_bgcolor="#121212",
            plot_bgcolor="#121212",
            font=dict(color="#e0e0e0")
        )
        pie_chart_html = fig_pie.to_html(full_html=False)
        # Stacked bar chart
        bar_segments = []
        colors = ["#4caf50", "#2196f3", "#ff9800", "#9c27b0", "#e91e63"]
        for i, (label, percent) in enumerate(zip(labels, percentages)):
            bar_segments.append(go.Bar(
                x=[percent],
                y=[""],
                name=label,
                orientation='h',
                marker=dict(color=colors[i % len(colors)]),
                text=[f"{label}\n{percent:.2f}%"],
                textposition='inside',
                hovertemplate=f"{label}: {{x:.2f}}%<extra></extra>",
            ))
        fig_bar = go.Figure(data=bar_segments)
        fig_bar.update_layout(
            barmode='stack',
            title="Other Portfolio Distribution (Stacked Bar)",
            margin=dict(t=50, b=50, l=25, r=25),
            paper_bgcolor="#121212",
            plot_bgcolor="#121212",
            font=dict(color="#e0e0e0"),
            xaxis=dict(title='Percentage', range=[0, 100], ticksuffix='%'),
            yaxis=dict(showticklabels=False),
            showlegend=True,
            height=180,
        )
        bar_chart_html = fig_bar.to_html(full_html=False)
    else:
        pie_chart_html = None
        bar_chart_html = None

    # Get available currencies for dropdown
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
        'CHF': 'Swiss Franc'
    }
    return render(request, 'other.html', {
        'username': request.user.username,
        'assets': assets_with_value,
        'total_net_worth': total_net_worth,
        'form': form,
        'pie_chart': pie_chart_html,
        'bar_chart': bar_chart_html,
        'selected_currency': selected_currency,
        'available_currencies': available_currencies,
        'currency_symbol': currency_symbol,
    })

def general(request):
    selected_currency = request.GET.get('currency', 'USD')
    currency_symbol = CURRENCY_SYMBOLS.get(selected_currency, selected_currency)
    show_cash_form = request.GET.get('show_cash_form') == '1'
    show_other_form = request.GET.get('show_other_form') == '1'
    cash_currencies = ['USD', 'CAD', 'BRL', 'KRW', 'INR', 'EUR', 'GBP', 'JPY', 'AUD', 'CHF']

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
    stock_prices = {}
    if stock_tickers:
        import yfinance as yf
        if len(stock_tickers) == 1:
            ticker = stock_tickers[0]
            try:
                data = yf.Ticker(ticker).history(period='1d')
                if not data.empty:
                    stock_prices[ticker] = float(data['Close'].iloc[-1])
                else:
                    stock_prices[ticker] = None
            except Exception:
                stock_prices[ticker] = None
        else:
            try:
                data = yf.download(
                    tickers=stock_tickers,
                    period='1d',
                    interval='1d',
                    group_by='ticker',
                    threads=True,
                    progress=False
                )
                for ticker in stock_tickers:
                    try:
                        stock_prices[ticker] = float(data[ticker]['Close'].iloc[-1])
                    except Exception:
                        stock_prices[ticker] = None
            except Exception:
                stock_prices = {ticker: None for ticker in stock_tickers}

    # Calculate total stock net worth in USD
    total_stocks_usd = 0
    for asset in stock_assets:
        price = stock_prices.get(asset.ticker.upper())
        try:
            price_decimal = safe_decimal(price)
        except Exception:
            price_decimal = Decimal('0')
        total_stocks_usd += price_decimal * asset.amount
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

    # Calculate total other in selected currency
    total_other = Decimal('0')
    for other in other_assets:
        other_value = convert_currency(other.amount, other.currency or 'USD', selected_currency)
        total_other += other_value

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
    if total_cash > 0:
        labels.append('Cash')
        values.append(float(total_cash))
    if total_other > 0:
        labels.append('Others')
        values.append(float(total_other))
    if labels and values:
        # Calculate percentages
        total = sum(values)
        percentages = [(v / total) * 100 if total > 0 else 0 for v in values]
        # Pie chart (percent only)
        fig_pie = go.Figure(data=[go.Pie(labels=labels, values=values, textinfo='percent+label', showlegend=True)])
        fig_pie.update_layout(
            title="Portfolio Distribution",
            margin=dict(t=50, b=50, l=25, r=25),
            paper_bgcolor="#121212",
            plot_bgcolor="#121212",
            font=dict(color="#e0e0e0")
        )
        pie_chart_html = fig_pie.to_html(full_html=False)
        # Stacked bar chart (single bar, 5 segments)
        bar_segments = []
        colors = ["#4caf50", "#2196f3", "#ff9800", "#9c27b0", "#e91e63"]
        for i, (label, percent) in enumerate(zip(labels, percentages)):
            bar_segments.append(go.Bar(
                x=[percent],
                y=[""],
                name=label,
                orientation='h',
                marker=dict(color=colors[i % len(colors)]),
                text=[f"{label}\n{percent:.2f}%"],
                textposition='inside',
                hovertemplate=f"{label}: {{x:.2f}}%<extra></extra>",
            ))
        fig_bar = go.Figure(data=bar_segments)
        fig_bar.update_layout(
            barmode='stack',
            title="Portfolio Distribution (Stacked Bar)",
            margin=dict(t=50, b=50, l=25, r=25),
            paper_bgcolor="#121212",
            plot_bgcolor="#121212",
            font=dict(color="#e0e0e0"),
            xaxis=dict(title='Percentage', range=[0, 100], ticksuffix='%'),
            yaxis=dict(showticklabels=False),
            showlegend=True,
            height=180,
        )
        bar_chart_html = fig_bar.to_html(full_html=False)
    else:
        pie_chart_html = None
        bar_chart_html = None

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
        'CHF': 'Swiss Franc'
    }

    # After calculating total_crypto and total_stocks
    total_net_worth = total_crypto + total_stocks + total_real_estate + total_cash + total_other
    if total_net_worth > 0:
        crypto_percent = (total_crypto / total_net_worth) * 100
        stocks_percent = (total_stocks / total_net_worth) * 100
        real_estate_percent = (total_real_estate / total_net_worth) * 100
        cash_percent = (total_cash / total_net_worth) * 100
        other_percent = (total_other / total_net_worth) * 100
    else:
        crypto_percent = 0
        stocks_percent = 0
        real_estate_percent = 0
        cash_percent = 0
        other_percent = 0

    # Build and sort totals list for the table
    totals = [
        {'type': 'Crypto', 'url': 'home', 'value': total_crypto, 'percent': crypto_percent},
        {'type': 'Stocks', 'url': 'stocks', 'value': total_stocks, 'percent': stocks_percent},
        {'type': 'Real Estate', 'url': 'real_estate', 'value': total_real_estate, 'percent': real_estate_percent},
        {'type': 'Cash/Fixed Income', 'url': 'cash', 'value': total_cash, 'percent': cash_percent},
        {'type': 'Others', 'url': 'other', 'value': total_other, 'percent': other_percent},
    ]
    totals.sort(key=lambda x: float(x['value']), reverse=True)

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
    })

def root_redirect(request):
    if request.user.is_authenticated:
        return redirect('general')  # Redirect to 'general' if the user is logged in
    else:
        return redirect('login')  # Redirect to 'login' if the user is not logged in

def resume(request):
    return render(request, 'resume.html')

def bio(request):
    return render(request, 'bio.html')

def projects(request):
    return render(request, 'projects.html')

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
    'virtual': 'virtuals-protocol',
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
}

CURRENCY_SYMBOLS = {
    'USD': '$',
    'BRL': 'R$',
    'EUR': '€',
    'GBP': '£',
    'CAD': 'C$',
    'KRW': '₩',
    'INR': '₹',
    'JPY': '¥',
    'AUD': 'A$',
    'CHF': 'Fr.',
}

def safe_decimal(val):
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0')

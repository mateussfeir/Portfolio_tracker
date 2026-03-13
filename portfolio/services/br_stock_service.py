from django.conf import settings
from django.core.cache import cache

import requests


STOCK_CACHE_TTL_SECONDS = 180  # 3 minutes


def get_br_stock_price(symbol):
    return get_br_stock_prices([symbol]).get((symbol or "").strip().upper())


def get_br_stock_prices(symbols):
    """
    Fetch and cache Brazilian stock prices for 3 minutes.
    Only uncached symbols are requested from BRAPI.
    Returns a dict: {symbol: price}
    """
    normalized_symbols = []
    seen = set()
    for symbol in symbols or []:
        normalized_symbol = (symbol or "").strip().upper()
        if normalized_symbol and normalized_symbol not in seen:
            normalized_symbols.append(normalized_symbol)
            seen.add(normalized_symbol)

    if not normalized_symbols:
        return {}

    prices = {}
    missing_symbols = []

    for symbol in normalized_symbols:
        cache_key = f"br_stock_price_{symbol}"
        cached = cache.get(cache_key)
        if cached is not None:
            prices[symbol] = cached
        else:
            missing_symbols.append(symbol)

    if missing_symbols:
        headers = {}
        api_key = getattr(settings, "BRAPI_API_KEY", None)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        fetched_prices = {symbol: None for symbol in missing_symbols}
        try:
            response = requests.get(
                f"https://brapi.dev/api/quote/{','.join(missing_symbols)}",
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
            results = payload.get("results") or []
            for result in results:
                symbol = (result.get("symbol") or "").strip().upper()
                if symbol in fetched_prices:
                    price = result.get("regularMarketPrice")
                    fetched_prices[symbol] = float(price) if price is not None else None
        except Exception:
            pass

        for symbol, price in fetched_prices.items():
            cache.set(f"br_stock_price_{symbol}", price, timeout=STOCK_CACHE_TTL_SECONDS)
            prices[symbol] = price

    return {symbol: prices.get(symbol) for symbol in normalized_symbols}

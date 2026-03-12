from django.conf import settings
from django.core.cache import cache

import requests


STOCK_CACHE_TTL_SECONDS = 180  # 3 minutes


def get_br_stock_price(symbol):
    """
    Fetch and cache a Brazilian stock price for 3 minutes.
    Returns the BRL price as a float or None if unavailable.
    """
    normalized_symbol = (symbol or "").strip().upper()
    if not normalized_symbol:
        return None

    cache_key = f"br_stock_price_{normalized_symbol}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    headers = {}
    api_key = getattr(settings, "BRAPI_API_KEY", None)
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    price = None
    try:
        response = requests.get(
            f"https://brapi.dev/api/quote/{normalized_symbol}",
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results") or []
        if results:
            price = results[0].get("regularMarketPrice")
            if price is not None:
                price = float(price)
    except Exception:
        price = None

    cache.set(cache_key, price, timeout=STOCK_CACHE_TTL_SECONDS)
    return price

import requests
import pandas as pd

BYBIT = "https://api.bybit.com/v5/market/kline"

# Bybit usa "1","3","5","15","30","60","120","240","D","W","M"
INTERVAL_MAP = {
    "1m":"1","3m":"3","5m":"5","15m":"15","30m":"30",
    "1h":"60","2h":"120","4h":"240","1d":"D"
}

def fetch_ohlcv(symbol="BTCUSDT", interval="5m", limit=500, start_ms=None, end_ms=None, category="linear"):
    """Bybit v5 klines. category: linear (perps USDT) | spot."""
    params = {
        "category": category,
        "symbol": symbol,
        "interval": INTERVAL_MAP.get(interval, "5"),
        "limit": min(limit, 1000)
    }
    if start_ms: params["start"] = start_ms
    if end_ms: params["end"] = end_ms

    r = requests.get(BYBIT, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    if data.get("retCode") != 0:
        raise RuntimeError(f"Bybit error: {data}")

    rows = data["result"]["list"]
    if not rows:
        raise RuntimeError(f"No klines returned for {symbol} {interval}")

    # Bybit devuelve más reciente primero → invertir
    rows = rows[::-1]
    df = pd.DataFrame(rows, columns=["time","open","high","low","close","volume","turnover"])
    df = df.astype({"open":float,"high":float,"low":float,"close":float,"volume":float,"time":"int64"})
    df["dt"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    return df

def fetch_session_first_candle(symbol="BTCUSDT"):
    df = fetch_ohlcv(symbol, "5m", 100)
    return df.iloc[-1]

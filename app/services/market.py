import requests
import pandas as pd

# OKX no tiene geo-block desde Railway US
OKX = "https://www.okx.com/api/v5/market/candles"
BYBIT_TESTNET = "https://api-testnet.bybit.com/v5/market/kline"

# OKX usa: 1m,3m,5m,15m,30m,1H,2H,4H,6H,12H,1D
OKX_INTERVAL = {
    "1m":"1m","3m":"3m","5m":"5m","15m":"15m","30m":"30m",
    "1h":"1H","2h":"2H","4h":"4H","1d":"1D"
}
BYBIT_INTERVAL = {
    "1m":"1","3m":"3","5m":"5","15m":"15","30m":"30",
    "1h":"60","2h":"120","4h":"240","1d":"D"
}

def _to_okx_symbol(s):
    """BTCUSDT -> BTC-USDT-SWAP (perp) o BTC-USDT (spot)."""
    if s.endswith("USDT"):
        base = s[:-4]
        return f"{base}-USDT-SWAP"
    return s

def _fetch_okx(symbol, interval, limit):
    inst = _to_okx_symbol(symbol)
    params = {"instId": inst, "bar": OKX_INTERVAL.get(interval,"5m"), "limit": min(limit,300)}
    r = requests.get(OKX, params=params, timeout=20,
                     headers={"User-Agent":"Mozilla/5.0"})
    r.raise_for_status()
    j = r.json()
    if j.get("code") != "0":
        raise RuntimeError(f"OKX error: {j}")
    rows = j["data"]  # más reciente primero
    if not rows: raise RuntimeError("OKX empty")
    rows = rows[::-1]
    # OKX: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
    df = pd.DataFrame(rows, columns=["time","open","high","low","close","volume","volCcy","volQ","confirm"])
    df = df[["time","open","high","low","close","volume"]]
    df = df.astype({"open":float,"high":float,"low":float,"close":float,"volume":float,"time":"int64"})
    df["dt"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    return df

def _fetch_bybit_testnet(symbol, interval, limit):
    params = {"category":"linear","symbol":symbol,
              "interval":BYBIT_INTERVAL.get(interval,"5"), "limit":min(limit,1000)}
    r = requests.get(BYBIT_TESTNET, params=params, timeout=20)
    r.raise_for_status()
    j = r.json()
    if j.get("retCode") != 0: raise RuntimeError(f"Bybit testnet: {j}")
    rows = j["result"]["list"]
    if not rows: raise RuntimeError("Bybit testnet empty")
    rows = rows[::-1]
    df = pd.DataFrame(rows, columns=["time","open","high","low","close","volume","turnover"])
    df = df[["time","open","high","low","close","volume"]]
    df = df.astype({"open":float,"high":float,"low":float,"close":float,"volume":float,"time":"int64"})
    df["dt"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    return df

def fetch_ohlcv(symbol="BTCUSDT", interval="5m", limit=500, start_ms=None, end_ms=None):
    """Prioriza OKX (sin geo-block, datos reales). Fallback: Bybit testnet."""
    last_err = None
    for fn in (_fetch_okx, _fetch_bybit_testnet):
        try:
            return fn(symbol, interval, limit)
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"All exchanges unreachable. Last: {last_err}")

def fetch_session_first_candle(symbol="BTCUSDT"):
    df = fetch_ohlcv(symbol, "5m", 100)
    return df.iloc[-1]

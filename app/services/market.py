import requests
import pandas as pd

BINANCE = "https://api.binance.com/api/v3/klines"

def fetch_ohlcv(symbol="BTCUSDT", interval="5m", limit=500, start_ms=None, end_ms=None):
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    if start_ms: params["startTime"] = start_ms
    if end_ms: params["endTime"] = end_ms
    data = requests.get(BINANCE, params=params, timeout=20).json()
    df = pd.DataFrame(data, columns=[
        "time","open","high","low","close","volume",
        "close_time","qav","trades","tbbav","tbqav","ignore"
    ])
    df = df.astype({"open":float,"high":float,"low":float,"close":float,"volume":float,"time":"int64"})
    df["dt"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    return df

def fetch_session_first_candle(symbol="BTCUSDT"):
    df = fetch_ohlcv(symbol, "5m", 100)
    return df.iloc[-1]

import os
import requests
import pandas as pd
import yfinance as yf

OKX = "https://www.okx.com/api/v5/market/candles"
BYBIT_TESTNET = "https://api-testnet.bybit.com/v5/market/kline"

OKX_INTERVAL = {
    "1m":"1m","3m":"3m","5m":"5m","15m":"15m","30m":"30m",
    "1h":"1H","2h":"2H","4h":"4H","1d":"1D"
}
BYBIT_INTERVAL = {
    "1m":"1","3m":"3","5m":"5","15m":"15","30m":"30",
    "1h":"60","2h":"120","4h":"240","1d":"D"
}
YF_INTERVAL = {
    "1m":"1m","5m":"5m","15m":"15m","30m":"30m","1h":"60m","1d":"1d"
}
# Mapeo símbolo lógico -> ticker yfinance
YF_SYMBOL_MAP = {
    "NQ": "NQ=F",
    "NQM5": "NQ=F",
    "MNQ": "MNQ=F",
    "ES": "ES=F",
    "MES": "MES=F",
}


def _is_futures_symbol(s):
    return s.upper() in YF_SYMBOL_MAP or s.endswith("=F")


def _to_okx_symbol(s):
    if s.endswith("USDT"):
        base = s[:-4]
        return f"{base}-USDT-SWAP"
    return s


def _fetch_okx(symbol, interval, limit):
    inst = _to_okx_symbol(symbol)
    params = {"instId": inst, "bar": OKX_INTERVAL.get(interval, "5m"), "limit": min(limit, 300)}
    r = requests.get(OKX, params=params, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    j = r.json()
    if j.get("code") != "0":
        raise RuntimeError(f"OKX error: {j}")
    rows = j["data"]
    if not rows:
        raise RuntimeError("OKX empty")
    rows = rows[::-1]
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
    if j.get("retCode") != 0:
        raise RuntimeError(f"Bybit testnet: {j}")
    rows = j["result"]["list"]
    if not rows:
        raise RuntimeError("Bybit testnet empty")
    rows = rows[::-1]
    df = pd.DataFrame(rows, columns=["time","open","high","low","close","volume","turnover"])
    df = df[["time","open","high","low","close","volume"]]
    df = df.astype({"open":float,"high":float,"low":float,"close":float,"volume":float,"time":"int64"})
    df["dt"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    return df


def _fetch_yfinance(symbol, interval, limit):
    """Datos NQ/MNQ/ES via yfinance. Delay ~15min, suficiente para shadow."""
    ticker = YF_SYMBOL_MAP.get(symbol.upper(), symbol)
    yf_int = YF_INTERVAL.get(interval, "15m")

    # yfinance limita period según interval. Para 15m: máx 60d.
    if interval in ("1m",):
        period = "7d"
    elif interval in ("5m", "15m", "30m"):
        period = "60d"
    elif interval == "1h":
        period = "730d"
    else:
        period = "5y"

    raw = yf.download(ticker, period=period, interval=yf_int,
                      progress=False, auto_adjust=False, prepost=False)
    if raw is None or raw.empty:
        raise RuntimeError(f"yfinance empty for {ticker}")

    # Flatten columnas si son MultiIndex
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    raw = raw.reset_index()
    ts_col = "Datetime" if "Datetime" in raw.columns else "Date"
    df = pd.DataFrame({
        "dt": pd.to_datetime(raw[ts_col], utc=True),
        "open": raw["Open"].astype(float),
        "high": raw["High"].astype(float),
        "low": raw["Low"].astype(float),
        "close": raw["Close"].astype(float),
        "volume": raw["Volume"].astype(float).fillna(0),
    })
    df["time"] = (df["dt"].astype("int64") // 10**6).astype("int64")
    df = df[["time","open","high","low","close","volume","dt"]]
    df = df.dropna().tail(limit).reset_index(drop=True)
    return df


def fetch_ohlcv(symbol="BTCUSDT", interval="5m", limit=500, start_ms=None, end_ms=None):
    """Router: futures -> yfinance, crypto -> OKX (fallback Bybit testnet)."""
    if _is_futures_symbol(symbol):
        return _fetch_yfinance(symbol, interval, limit)

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

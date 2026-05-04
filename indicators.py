import pandas as pd
import numpy as np

def detect_fvg(df: pd.DataFrame):
    """FVG real: gap entre vela i-2 y vela i (3-candle pattern)."""
    fvgs = []
    for i in range(2, len(df)):
        c0, c2 = df.iloc[i-2], df.iloc[i]
        if c2["low"] > c0["high"]:
            fvgs.append({"idx": i, "direction": "bullish", "gap_low": c0["high"], "gap_high": c2["low"]})
        elif c2["high"] < c0["low"]:
            fvgs.append({"idx": i, "direction": "bearish", "gap_low": c2["high"], "gap_high": c0["low"]})
    return fvgs

def latest_fvg(df):
    fvgs = detect_fvg(df)
    return fvgs[-1] if fvgs else None

def atr(df, period=14):
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def rsi(df, period=14):
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def macd(df, fast=12, slow=26, signal=9):
    ema_fast = df["close"].ewm(span=fast).mean()
    ema_slow = df["close"].ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def momentum_indicators(df):
    rsi_v = rsi(df).iloc[-1]
    m, s, h = macd(df)
    return {
        "rsi_14": float(rsi_v) if not pd.isna(rsi_v) else 50,
        "macd": float(m.iloc[-1]) if not pd.isna(m.iloc[-1]) else 0,
        "macd_signal": float(s.iloc[-1]) if not pd.isna(s.iloc[-1]) else 0,
        "macd_hist": float(h.iloc[-1]) if not pd.isna(h.iloc[-1]) else 0
    }

def liquidity_levels(df, interval="5m", market="crypto"):
    n = SESSION_CANDLES.get(interval, {}).get(market, 288)
    curr = df.tail(n)
    prev = df.tail(n*2).head(n)
    if prev.empty:
        prev = curr
    sh, sl = float(curr["high"].max()), float(curr["low"].min())
    psh, psl = float(prev["high"].max()), float(prev["low"].min())
    last = float(df["close"].iloc[-1])
    recent = df.tail(5)
    swept_high = bool((recent["high"] > psh).any() and last < psh)
    swept_low = bool((recent["low"] < psl).any() and last > psl)
    return {
        "prev_session_high": psh,
        "prev_session_low": psl,
        "swept_high": swept_high,
        "swept_low": swept_low
    }

def volatility_pct(df, period=20):
    """Devuelve % (no decimal). 0.5 = 0.5%."""
    s = df["close"].pct_change().rolling(period).std().iloc[-1]
    return float((s or 0) * 100)

def relative_volume(df, period=20):
    avg = df["volume"].rolling(period).mean().iloc[-1]
    if not avg or avg == 0: return 0
    return float(df["volume"].iloc[-1] / avg)

# Velas por sesión segun timeframe
SESSION_CANDLES = {
    "5m":  {"crypto": 288, "stocks": 78},   # 24h vs 6.5h
    "15m": {"crypto": 96,  "stocks": 26},
    "1h":  {"crypto": 24,  "stocks": 7}
}

def session_range(df, interval="5m", market="crypto"):
    n = SESSION_CANDLES.get(interval, {}).get(market, 288)
    sess = df.tail(n)
    return float(sess["high"].max()), float(sess["low"].min())

def build_context(df, symbol="BTCUSDT", interval="5m", market="crypto"):
    fvg = latest_fvg(df)
    sh, sl = session_range(df, interval, market)
    return {
        "symbol": symbol,
        "session_high": sh,
        "session_low": sl,
        "fvg_detected": fvg is not None,
        "fvg_direction": fvg["direction"] if fvg else None,
        "fvg_gap_high": fvg["gap_high"] if fvg else None,
        "fvg_gap_low": fvg["gap_low"] if fvg else None,
        "volatility": volatility_pct(df),
        "relative_volume": relative_volume(df),
        "atr": float(atr(df).iloc[-1] or 0),
        "last_close": float(df["close"].iloc[-1])
    }

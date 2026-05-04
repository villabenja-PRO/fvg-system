import numpy as np
import pandas as pd
from app.services.indicators import detect_fvg, atr, volatility_pct

def simulate(df, sl_mult=1.0, tp_mult=2.0, vol_min=0.5, rvol_min=1.2,
             risk_pct=0.01, equity0=1000):
    """vol_min en % (0.5 = 0.5%)."""
    df = df.copy().reset_index(drop=True)
    df["atr"] = atr(df, 14)
    df["vol20"] = df["volume"].rolling(20).mean()
    df["ret"] = df["close"].pct_change()
    df["volat_pct"] = df["ret"].rolling(20).std() * 100  # en %

    fvgs = detect_fvg(df)
    trades = []
    equity = equity0
    peak = equity0

    for f in fvgs:
        i = f["idx"]
        if i + 1 >= len(df) - 1: continue
        r = df.iloc[i]
        if pd.isna(r["atr"]) or pd.isna(r["volat_pct"]): continue
        rvol = r["volume"] / r["vol20"] if r["vol20"] else 0
        if r["volat_pct"] < vol_min or rvol < rvol_min: continue

        entry = float(df.iloc[i+1]["open"])
        a = float(r["atr"])
        if f["direction"] == "bullish":
            sl, tp = entry - a*sl_mult, entry + a*tp_mult
            side = 1
        else:
            sl, tp = entry + a*sl_mult, entry - a*tp_mult
            side = -1

        outcome = None
        for j in range(i+1, min(i+50, len(df))):
            hi, lo = df.iloc[j]["high"], df.iloc[j]["low"]
            if side == 1:
                if lo <= sl: outcome = ("loss", sl); break
                if hi >= tp: outcome = ("win", tp); break
            else:
                if hi >= sl: outcome = ("loss", sl); break
                if lo <= tp: outcome = ("win", tp); break
        if not outcome:
            outcome = ("timeout", float(df.iloc[min(i+50,len(df)-1)]["close"]))

        risk_usd = equity * risk_pct
        r_mult = (outcome[1] - entry) / (entry - sl) * side if (entry - sl) else 0
        pnl = risk_usd * r_mult
        equity += pnl
        peak = max(peak, equity)
        trades.append({"i": i, "side": side, "entry": entry, "sl": sl, "tp": tp,
                       "exit": outcome[1], "result": outcome[0], "r": r_mult,
                       "pnl": pnl, "equity": equity})

    return trades, equity, peak

def metrics(trades, equity0=1000):
    if not trades:
        return {"trades":0,"winrate":0,"pf":0,"max_dd":0,"sharpe":0,"final_equity":equity0}
    df = pd.DataFrame(trades)
    wins = df[df["pnl"] > 0]["pnl"].sum()
    losses = abs(df[df["pnl"] < 0]["pnl"].sum())
    pf = wins / losses if losses > 0 else float("inf")
    eq = pd.Series([equity0] + df["equity"].tolist())
    dd = ((eq - eq.cummax()) / eq.cummax()).min() * 100
    rets = df["pnl"] / equity0
    sharpe = (rets.mean() / rets.std() * np.sqrt(252)) if rets.std() else 0
    return {
        "trades": len(df),
        "winrate": float((df["result"]=="win").mean()),
        "pf": float(pf) if pf != float("inf") else 99.0,
        "max_dd": float(dd),
        "sharpe": float(sharpe),
        "final_equity": float(df["equity"].iloc[-1])
    }

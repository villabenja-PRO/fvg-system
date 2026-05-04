import itertools
import pandas as pd
from app.services.market import fetch_ohlcv
from app.backtest.engine import simulate, metrics
from app.services import supa

GRID = {
    "sl_mult": [0.8, 1.0, 1.2, 1.5],
    "tp_mult": [1.5, 2.0, 2.5, 3.0],
    "vol_min": [0.3, 0.5, 0.8],   # en %
    "rvol_min": [1.0, 1.2, 1.5]
}

def grid_search(df, grid=GRID):
    best = None
    for sl, tp, vm, rv in itertools.product(grid["sl_mult"], grid["tp_mult"],
                                             grid["vol_min"], grid["rvol_min"]):
        if tp <= sl: continue
        trades, _, _ = simulate(df, sl, tp, vm, rv)
        m = metrics(trades)
        if m["trades"] < 5: continue
        score = m["sharpe"] * (1 if m["max_dd"] > -25 else 0.5)
        if best is None or score > best["score"]:
            best = {"params": {"sl_mult":sl,"tp_mult":tp,"vol_min":vm,"rvol_min":rv},
                    "metrics": m, "score": score}
    return best

def is_robust(is_m, oos_m):
    """Gate anti-overfitting."""
    if oos_m["trades"] < 3: return False, "too_few_oos_trades"
    if oos_m["sharpe"] < 0.5: return False, f"oos_sharpe_low_{oos_m['sharpe']:.2f}"
    if oos_m["sharpe"] < is_m["sharpe"] * 0.4: return False, "oos_decay_>60pct"
    if oos_m["max_dd"] < -25: return False, f"oos_dd_{oos_m['max_dd']:.1f}pct"
    if oos_m["pf"] < 1.1: return False, f"oos_pf_low_{oos_m['pf']:.2f}"
    return True, "ok"

def walk_forward(symbol="BTCUSDT", interval="5m", days=90, is_days=60, oos_days=30):
    candles_per_day = 288 if interval == "5m" else 96
    total = days * candles_per_day
    df_full = []
    chunks = (total // 1000) + 1
    end_ms = None
    for _ in range(chunks):
        df = fetch_ohlcv(symbol, interval, 1000, end_ms=end_ms)
        if df.empty: break
        df_full.append(df)
        end_ms = int(df.iloc[0]["time"]) - 1
    df = pd.concat(df_full[::-1]).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    df = df.tail(total).reset_index(drop=True)

    is_n = is_days * candles_per_day
    is_df = df.iloc[:is_n].reset_index(drop=True)
    oos_df = df.iloc[is_n:].reset_index(drop=True)

    best = grid_search(is_df)
    if not best:
        return {"error": "no valid params in IS"}

    oos_trades, _, _ = simulate(oos_df, **best["params"])
    oos_m = metrics(oos_trades)

    robust, reason = is_robust(best["metrics"], oos_m)

    if robust:
        supa.update("wfo_params", f"?symbol=eq.{symbol}&active=is.true", {"active": False})

    supa.insert("wfo_params", {
        "symbol": symbol,
        **best["params"],
        "is_sharpe": best["metrics"]["sharpe"],
        "oos_sharpe": oos_m["sharpe"],
        "is_winrate": best["metrics"]["winrate"],
        "oos_winrate": oos_m["winrate"],
        "is_pf": best["metrics"]["pf"],
        "oos_pf": oos_m["pf"],
        "max_dd": oos_m["max_dd"],
        "active": robust,
        "window_start": str(df["dt"].iloc[0].date()),
        "window_end": str(df["dt"].iloc[-1].date())
    })
    return {"is": best, "oos": oos_m, "params": best["params"], "robust": robust, "reason": reason}

import os
from fastapi import FastAPI, BackgroundTasks
from app.services.market import fetch_ohlcv
from app.services.indicators import build_context
from app.services import supa
from app.agents.orchestrator import run_fvg_pipeline
from app.backtest.wfo import walk_forward
from app.backtest.engine import simulate, metrics
from app.services.resolver import resolve_pending

app = FastAPI(title="FVG Trading System")

INTERVAL = os.getenv("FVG_INTERVAL", "15m")  # 15m crypto reduce ruido
MARKET = os.getenv("FVG_MARKET", "crypto")    # crypto | stocks
PAPER = os.getenv("PAPER_TRADING", "true").lower() == "true"

@app.get("/health")
def health():
    return {"ok": True, "interval": INTERVAL, "market": MARKET, "paper": PAPER}

@app.get("/trade/fvg")
def trade_fvg(symbol: str = "BTCUSDT"):
    df = fetch_ohlcv(symbol, INTERVAL, 300)
    ctx = build_context(df, symbol, INTERVAL, MARKET)
    decision = run_fvg_pipeline(ctx, symbol)
    if decision.get("action") in ("buy", "sell") and not decision.get("skipped"):
        sig = supa.insert("signals", {
            "symbol": symbol,
            "direction": ctx.get("fvg_direction"),
            "gap_high": ctx.get("fvg_gap_high"),
            "gap_low": ctx.get("fvg_gap_low"),
            "volatility": ctx["volatility"],
            "relative_volume": ctx["relative_volume"],
            "session_high": ctx["session_high"],
            "session_low": ctx["session_low"]
        })
        # Idempotencia: rechazar si ya hay trade pending del mismo símbolo+día
        existing = supa.select("trades",
            f"?symbol=eq.{symbol}&status=eq.pending&ts=gte.{ctx.get('today','1970-01-01')}T00:00:00Z&limit=1")
        if existing:
            return {"context": ctx, "decision": {**decision, "skipped": True, "reason": "duplicate_pending"}}
        supa.insert("trades", {
            "symbol": symbol,
            "signal_id": sig[0]["id"],
            "action": decision["action"],
            "entry": decision["entry"],
            "stop_loss": decision["stop_loss"],
            "take_profit": decision["take_profit"],
            "risk_percent": decision.get("risk_percent", 1.0),
            "confidence": decision.get("confidence", 0),
            "size_usd": decision.get("size_usd", 0),
            "is_simulated": PAPER,
            "raw_ia_response": decision
        })
    return {"context": ctx, "decision": decision}

@app.post("/wfo/run")
def wfo_run(symbol: str = "BTCUSDT", days: int = 90, bg: BackgroundTasks = None):
    bg.add_task(walk_forward, symbol, INTERVAL, days)
    return {"status": "scheduled", "symbol": symbol, "interval": INTERVAL}

@app.get("/wfo/active")
def wfo_active(symbol: str = "BTCUSDT"):
    return supa.get_active_params(symbol)

@app.get("/risk/state")
def risk_state():
    return supa.get_risk_state()

@app.post("/resolver/run")
def resolver_run():
    return {"resolved": resolve_pending()}

@app.get("/backtest")
def backtest(symbol: str = "BTCUSDT", days: int = 30):
    candles = {"5m":288,"15m":96,"1h":24}.get(INTERVAL, 96)
    df = fetch_ohlcv(symbol, INTERVAL, min(1000, days * candles))
    p = supa.get_active_params(symbol)
    trades, _, _ = simulate(df, p["sl_mult"], p["tp_mult"], p["vol_min"], p["rvol_min"])
    return {"params": p, "metrics": metrics(trades), "n_trades": len(trades)}

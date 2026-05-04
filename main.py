import os
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, BackgroundTasks, HTTPException, Header
from app.services.market import fetch_ohlcv
from app.services.indicators import build_context, momentum_indicators, liquidity_levels
from app.services import supa
from app.agents.orchestrator import run_fvg_pipeline
from app.backtest.wfo import walk_forward
from app.backtest.engine import simulate, metrics
from app.services.resolver import resolve_pending

app = FastAPI(title="FVG Trading System")

INTERVAL = os.getenv("FVG_INTERVAL", "15m")
MARKET = os.getenv("FVG_MARKET", "crypto")
PAPER = os.getenv("PAPER_TRADING", "true").lower() == "true"
EMERGENCY_TOKEN = os.getenv("EMERGENCY_TOKEN", "change-me-please")

@app.get("/health")
def health():
    return {"ok": True, "interval": INTERVAL, "market": MARKET, "paper": PAPER}

@app.get("/health/deep")
def health_deep():
    """Verifica todas las dependencias."""
    out = {"fastapi": "ok"}
    try:
        df = fetch_ohlcv("BTCUSDT", "15m", 5)
        out["okx"] = "ok" if len(df) > 0 else "empty"
    except Exception as e:
        out["okx"] = f"error: {e}"
    try:
        supa.get_risk_state()
        out["supabase"] = "ok"
    except Exception as e:
        out["supabase"] = f"error: {e}"
    state = supa.get_risk_state() if out.get("supabase") == "ok" else None
    out["weekly_stop_active"] = state.get("weekly_stop_active") if state else None
    out["paper_trading"] = PAPER
    return out

@app.get("/trade/fvg")
def trade_fvg(symbol: str = "BTCUSDT"):
    df = fetch_ohlcv(symbol, INTERVAL, 300)
    ctx = build_context(df, symbol, INTERVAL, MARKET)
    mom = momentum_indicators(df)
    liq = liquidity_levels(df, INTERVAL, MARKET)
    decision = run_fvg_pipeline(ctx, symbol, momentum=mom, liquidity=liq)
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
        existing = supa.select("trades",
            f"?symbol=eq.{symbol}&status=eq.pending&limit=1")
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
            "strategy_version": decision.get("strategy_version", "v1.0"),
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

@app.get("/metrics")
def get_metrics(days: int = 30, symbol: str = None):
    """Métricas en tiempo real desde la DB."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    flt = f"?ts=gte.{since}&status=in.(win,loss,timeout)"
    if symbol:
        flt += f"&symbol=eq.{symbol}"
    trades = supa.select("trades", flt)
    if not trades:
        return {"trades": 0, "winrate": 0, "pf": 0, "pnl_total": 0, "days": days}

    wins = [t for t in trades if t["status"] == "win"]
    losses = [t for t in trades if t["status"] == "loss"]
    pnl_wins = sum(float(t.get("pnl_usd") or 0) for t in wins)
    pnl_losses = abs(sum(float(t.get("pnl_usd") or 0) for t in losses))
    pnl_total = sum(float(t.get("pnl_usd") or 0) for t in trades)

    # Cooldown stats
    last_loss = max([t["closed_at"] for t in losses if t.get("closed_at")], default=None)

    return {
        "days": days,
        "symbol": symbol or "all",
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "winrate": round(len(wins) / len(trades) * 100, 2),
        "pf": round(pnl_wins / pnl_losses, 2) if pnl_losses > 0 else None,
        "pnl_total": round(pnl_total, 2),
        "avg_r": round(sum(float(t.get("pnl_r") or 0) for t in trades) / len(trades), 2),
        "last_loss_at": last_loss
    }

@app.get("/decisions/recent")
def decisions_recent(limit: int = 20):
    """Últimas N decisiones del orchestrator (para debugging)."""
    return supa.select("decisions_log", f"?order=ts.desc&limit={limit}")

@app.post("/emergency/stop")
def emergency_stop(token: str = Header(None, alias="X-Emergency-Token")):
    """Activa weekly_stop. Detiene todas las operaciones nuevas."""
    if token != EMERGENCY_TOKEN:
        raise HTTPException(status_code=403, detail="invalid token")
    state = supa.get_risk_state()
    if state:
        supa.update("risk_state", f"?id=eq.{state['id']}", {"weekly_stop_active": True})
    return {"status": "stopped", "weekly_stop_active": True}

@app.post("/emergency/resume")
def emergency_resume(token: str = Header(None, alias="X-Emergency-Token")):
    if token != EMERGENCY_TOKEN:
        raise HTTPException(status_code=403, detail="invalid token")
    state = supa.get_risk_state()
    if state:
        supa.update("risk_state", f"?id=eq.{state['id']}", {"weekly_stop_active": False})
    return {"status": "resumed", "weekly_stop_active": False}

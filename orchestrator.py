from app.agents.fvg_agent import fvg_agent
from app.agents.momentum_agent import momentum_agent
from app.agents.liquidity_agent import liquidity_agent
from app.agents.ensemble import ensemble_vote
from app.services import supa
from app.risk.manager import position_size, can_trade, adjust_for_drawdown

def run_fvg_pipeline(context, symbol="BTCUSDT", momentum=None, liquidity=None):
    ok, reason = can_trade()
    if not ok:
        return {"action": "hold", "reason": reason, "skipped": True}

    params = supa.get_active_params(symbol)

    # 3 agentes en paralelo conceptual (secuencial por ahora)
    fvg_sig = fvg_agent(context, params)
    fvg_sig["agent"] = "FVG"

    signals = [fvg_sig]
    if momentum:
        signals.append({**momentum_agent(context, momentum), "agent": "MOMENTUM"})
    if liquidity:
        signals.append({**liquidity_agent(context, liquidity), "agent": "LIQUIDITY"})

    vote = ensemble_vote(signals)

    if vote["action"] == "hold":
        return {**vote, "skipped": True, "reason": "ensemble_hold", "signals": signals}

    if not context["fvg_detected"]:
        return {**vote, "action": "hold", "skipped": True, "reason": "no_fvg", "signals": signals}
    if context["volatility"] < params["vol_min"] or context["relative_volume"] < params["rvol_min"]:
        return {**vote, "action": "hold", "skipped": True, "reason": "filters", "signals": signals}

    # Toma entry/SL/TP del FVG agent (es quien define niveles)
    entry = fvg_sig.get("entry")
    sl = fvg_sig.get("stop_loss")
    tp = fvg_sig.get("take_profit")

    state = supa.get_risk_state()
    equity = state["equity_usd"] if state else 1000
    peak = state.get("peak_equity") if state else equity
    mult = adjust_for_drawdown(equity, peak)
    size = position_size(equity * mult, entry, sl) if entry and sl else 0

    return {
        "action": vote["action"],
        "entry": entry,
        "stop_loss": sl,
        "take_profit": tp,
        "risk_percent": 1.0,
        "confidence": vote["ensemble_confidence"],
        "ensemble_score": vote["score"],
        "votes": vote["votes"],
        "size_usd": size,
        "dd_multiplier": mult,
        "signals": signals
    }

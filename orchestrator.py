from app.agents.fvg_agent import fvg_agent
from app.agents.momentum_agent import momentum_agent
from app.agents.liquidity_agent import liquidity_agent
from app.agents.ensemble import ensemble_vote
from app.services import supa
from app.risk.manager import position_size, can_trade, adjust_for_drawdown


def _hypothetical_levels(context, params):
    last_close = context.get("last_close", 0)
    atr_val = context.get("atr", 0)
    fvg_dir = context.get("fvg_direction", "bullish")
    sl_mult = params.get("sl_mult", 1.5)
    tp_mult = params.get("tp_mult", 2.5)
    if not last_close or not atr_val:
        return None, None, None, None
    if fvg_dir == "bullish":
        hyp_sl = last_close - atr_val * sl_mult
        hyp_tp = last_close + atr_val * tp_mult
    else:
        hyp_sl = last_close + atr_val * sl_mult
        hyp_tp = last_close - atr_val * tp_mult
    hyp_rr = round(tp_mult / sl_mult, 2)
    vol = context.get("volatility", 0)
    regime = "low_vol" if vol < 0.3 else "normal" if vol < 0.8 else "high_vol"
    s_high = context.get("session_high", 0)
    s_low = context.get("session_low", 1)
    session_range_pct = round((s_high - s_low) / s_low * 100, 3) if s_low else None
    return round(hyp_sl, 4), round(hyp_tp, 4), hyp_rr, regime, session_range_pct


def run_fvg_pipeline(context, symbol="BTCUSDT", momentum=None, liquidity=None):
    ok, reason = can_trade()
    if not ok:
        return {"action": "hold", "reason": reason, "skipped": True}

    params = supa.get_active_params(symbol)
    hyp_sl, hyp_tp, hyp_rr, regime, session_range_pct = _hypothetical_levels(context, params)

    fvg_sig = fvg_agent(context, params)
    fvg_sig["agent"] = "FVG"
    signals = [fvg_sig]

    if momentum:
        signals.append({**momentum_agent(context, momentum), "agent": "MOMENTUM"})
    if liquidity:
        signals.append({**liquidity_agent(context, liquidity), "agent": "LIQUIDITY"})

    vote = ensemble_vote(signals)

    base = {
        "hypothetical_entry": context.get("last_close"),
        "hypothetical_sl":    hyp_sl,
        "hypothetical_tp":    hyp_tp,
        "hypothetical_rr":    hyp_rr,
        "market_regime":      regime,
        "session_range_pct":  session_range_pct,
    }

    if vote["action"] == "hold":
        return {**vote, **base, "skipped": True, "reason": "ensemble_hold", "signals": signals}

    if not context["fvg_detected"]:
        return {**vote, **base, "action": "hold", "skipped": True, "reason": "no_fvg", "signals": signals}

    if context["volatility"] < params["vol_min"] or context["relative_volume"] < params["rvol_min"]:
        return {**vote, **base, "action": "hold", "skipped": True, "reason": "filters", "signals": signals}

    entry = fvg_sig.get("entry")
    sl    = fvg_sig.get("stop_loss")
    tp    = fvg_sig.get("take_profit")

    state  = supa.get_risk_state()
    equity = state["equity_usd"] if state else 1000
    peak   = state.get("peak_equity") if state else equity
    mult   = adjust_for_drawdown(equity, peak)
    size   = position_size(equity * mult, entry, sl) if entry and sl else 0

    return {
        "action":         vote["action"],
        "entry":          entry,
        "stop_loss":      sl,
        "take_profit":    tp,
        "risk_percent":   1.0,
        "confidence":     vote["ensemble_confidence"],
        "ensemble_score": vote["score"],
        "votes":          vote["votes"],
        "size_usd":       size,
        "dd_multiplier":  mult,
        "signals":        signals,
        **base,
    }

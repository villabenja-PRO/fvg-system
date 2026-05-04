from app.agents.fvg_agent import fvg_agent
from app.services import supa
from app.risk.manager import position_size, can_trade, adjust_for_drawdown

def run_fvg_pipeline(context, symbol="BTCUSDT"):
    ok, reason = can_trade()
    if not ok:
        return {"action": "hold", "reason": reason, "skipped": True}

    params = supa.get_active_params(symbol)
    decision = fvg_agent(context, params)

    if decision.get("action") not in ("buy", "sell"):
        return {**decision, "skipped": True, "reason": "agent_hold"}

    if not context["fvg_detected"]:
        return {**decision, "action": "hold", "skipped": True, "reason": "no_fvg"}
    if context["volatility"] < params["vol_min"] or context["relative_volume"] < params["rvol_min"]:
        return {**decision, "action": "hold", "skipped": True, "reason": "filters"}

    state = supa.get_risk_state()
    equity = state["equity_usd"] if state else 1000
    peak = state.get("peak_equity") if state else equity
    mult = adjust_for_drawdown(equity, peak)
    size = position_size(equity * mult, decision["entry"], decision["stop_loss"])
    decision["size_usd"] = size
    decision["dd_multiplier"] = mult
    return decision

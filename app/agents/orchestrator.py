import time
from app.agents.fvg_agent import fvg_agent
from app.agents.momentum_agent import momentum_agent
from app.agents.liquidity_agent import liquidity_agent
from app.agents.ensemble import ensemble_vote
from app.agents.pre_filter import pre_filter
from app.services import supa
from app.risk.manager import position_size, can_trade, adjust_for_drawdown

STRATEGY_VERSION = "v1.0"

def _log_decision(symbol, context, signals, vote, skipped, reason, claude_calls, pre_passed):
    try:
        supa.insert("decisions_log", {
            "symbol": symbol,
            "strategy_version": STRATEGY_VERSION,
            "context": context,
            "signals": signals,
            "ensemble": vote,
            "skipped": skipped,
            "skip_reason": reason,
            "claude_calls": claude_calls,
            "pre_filter_passed": pre_passed
        })
    except Exception as e:
        print(f"[log_decision_error] {e}")

def _log_health(component, status, error=None, latency_ms=None):
    try:
        supa.insert("health_log", {
            "component": component, "status": status,
            "error": str(error) if error else None,
            "latency_ms": latency_ms
        })
    except Exception:
        pass

def run_fvg_pipeline(context, symbol="BTCUSDT", momentum=None, liquidity=None):
    ok, reason = can_trade()
    if not ok:
        _log_decision(symbol, context, [], None, True, reason, 0, False)
        return {"action": "hold", "reason": reason, "skipped": True}

    params = supa.get_active_params(symbol)

    # Pre-filter: ahorra calls Claude
    passed, pre_reason = pre_filter(context, params)
    if not passed:
        _log_decision(symbol, context, [], None, True, pre_reason, 0, False)
        return {"action": "hold", "reason": pre_reason, "skipped": True, "pre_filter": False}

    signals = []
    claude_calls = 0

    t0 = time.time()
    fvg_sig = fvg_agent(context, params)
    fvg_sig["agent"] = "FVG"
    signals.append(fvg_sig)
    claude_calls += 1
    _log_health("claude_fvg", "ok" if "error" not in fvg_sig else "error",
                fvg_sig.get("error"), int((time.time()-t0)*1000))

    if momentum:
        t0 = time.time()
        mom_sig = momentum_agent(context, momentum)
        mom_sig["agent"] = "MOMENTUM"
        signals.append(mom_sig)
        claude_calls += 1
        _log_health("claude_momentum", "ok" if "error" not in mom_sig else "error",
                    mom_sig.get("error"), int((time.time()-t0)*1000))

    if liquidity:
        t0 = time.time()
        liq_sig = liquidity_agent(context, liquidity)
        liq_sig["agent"] = "LIQUIDITY"
        signals.append(liq_sig)
        claude_calls += 1
        _log_health("claude_liquidity", "ok" if "error" not in liq_sig else "error",
                    liq_sig.get("error"), int((time.time()-t0)*1000))

    vote = ensemble_vote(signals)

    if vote["action"] == "hold":
        _log_decision(symbol, context, signals, vote, True, "ensemble_hold", claude_calls, True)
        return {**vote, "skipped": True, "reason": "ensemble_hold", "signals": signals}

    entry = fvg_sig.get("entry")
    sl = fvg_sig.get("stop_loss")
    tp = fvg_sig.get("take_profit")

    if not entry or not sl or entry == sl:
        _log_decision(symbol, context, signals, vote, True, "no_levels", claude_calls, True)
        return {**vote, "action": "hold", "skipped": True, "reason": "no_levels", "signals": signals}

    state = supa.get_risk_state()
    equity = state["equity_usd"] if state else 1000
    peak = state.get("peak_equity") if state else equity
    mult = adjust_for_drawdown(equity, peak)
    size = position_size(equity * mult, entry, sl)

    decision = {
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
        "signals": signals,
        "strategy_version": STRATEGY_VERSION
    }
    _log_decision(symbol, context, signals, vote, False, None, claude_calls, True)
    return decision

from datetime import date
from app.services import supa

MAX_TRADES_DAY = 3
WEEKLY_STOP_PCT = -5.0
RISK_PER_TRADE = 0.01

def position_size(equity, entry, stop_loss, risk_pct=RISK_PER_TRADE):
    risk_usd = equity * risk_pct
    dist = abs(entry - stop_loss)
    if dist == 0: return 0
    qty = risk_usd / dist
    return round(qty * entry, 2)

def can_trade():
    s = supa.get_risk_state()
    if not s: return True, "no_state"
    if s.get("weekly_stop_active"): return False, "weekly_stop"
    if s.get("trades_today", 0) >= MAX_TRADES_DAY: return False, "max_trades_day"
    if s.get("daily_reset_date") != str(date.today()):
        supa.update("risk_state", f"?id=eq.{s['id']}", {
            "trades_today": 0, "pnl_today": 0,
            "daily_reset_date": str(date.today())
        })
    return True, "ok"

def adjust_for_drawdown(equity, peak):
    if peak == 0: return 1.0
    dd = (equity - peak) / peak * 100
    if dd < -10: return 0.5
    if dd < -5: return 0.75
    return 1.0

def register_trade(pnl_usd):
    s = supa.get_risk_state()
    if not s: return
    new_eq = s["equity_usd"] + pnl_usd
    peak = max(s.get("peak_equity") or new_eq, new_eq)
    dd = (new_eq - peak) / peak * 100 if peak else 0
    pnl_week = (s.get("pnl_week") or 0) + pnl_usd
    weekly_stop = pnl_week / s["equity_usd"] * 100 <= WEEKLY_STOP_PCT
    supa.update("risk_state", f"?id=eq.{s['id']}", {
        "equity_usd": new_eq,
        "peak_equity": peak,
        "drawdown_pct": dd,
        "trades_today": (s.get("trades_today") or 0) + 1,
        "trades_week": (s.get("trades_week") or 0) + 1,
        "pnl_today": (s.get("pnl_today") or 0) + pnl_usd,
        "pnl_week": pnl_week,
        "weekly_stop_active": weekly_stop
    })

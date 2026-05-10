import time
from datetime import datetime, timezone
from app.services.market import fetch_ohlcv
from app.services import supa
from app.risk.manager import register_trade

TIMEOUT_HOURS = 24

def resolve_pending():
    pending = supa.select("trades", "?status=eq.pending&order=ts.asc&limit=50")
    resolved = []
    for t in pending:
        symbol = t["symbol"]
        entry = float(t["entry"])
        sl = float(t["stop_loss"])
        tp = float(t["take_profit"])
        action = t["action"]
        ts = t["ts"]
        start_dt = datetime.fromisoformat(ts.replace("Z","+00:00"))
        start_ms = int(start_dt.timestamp() * 1000)
        now_ms = int(time.time() * 1000)
        elapsed_h = (now_ms - start_ms) / 3_600_000

        df = fetch_ohlcv(symbol, "1m", 1000, start_ms=start_ms)
        if df.empty:
            continue

        outcome, exit_px = None, None
        for _, r in df.iterrows():
            hi, lo = r["high"], r["low"]
            if action == "buy":
                if lo <= sl: outcome, exit_px = "loss", sl; break
                if hi >= tp: outcome, exit_px = "win", tp; break
            else:
                if hi >= sl: outcome, exit_px = "loss", sl; break
                if lo <= tp: outcome, exit_px = "win", tp; break

        if not outcome and elapsed_h >= TIMEOUT_HOURS:
            outcome = "timeout"
            exit_px = float(df.iloc[-1]["close"])
        if not outcome:
            continue

        side = 1 if action == "buy" else -1
        risk_dist = abs(entry - sl)
        r_mult = ((exit_px - entry) / risk_dist) * side if risk_dist else 0
        size = float(t.get("size_usd") or 0)
        equity = supa.get_risk_state()["equity_usd"] if supa.get_risk_state() else 1000
        risk_usd = equity * (float(t.get("risk_percent") or 1) / 100)
        pnl = risk_usd * r_mult

        supa.update("trades", f"?id=eq.{t['id']}", {
            "status": outcome,
            "exit_price": exit_px,
            "pnl_r": r_mult,
            "pnl_usd": pnl,
            "closed_at": datetime.now(timezone.utc).isoformat()
        })
        # Shadow trades NO afectan risk_state (no son operaciones reales)
        if not t.get("shadow"):
            register_trade(pnl)
        resolved.append({"id": t["id"], "outcome": outcome, "pnl_usd": pnl, "r": r_mult, "shadow": bool(t.get("shadow"))})
    return resolved

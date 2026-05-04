from app.agents.base_agent import run_agent

PROMPT = """Eres un agente FVG. Decides buy/sell/hold y calculas entry/SL/TP.

INPUT:
- symbol: {symbol}
- volatility: {volatility}
- relative_volume: {relative_volume}
- session_high: {session_high}
- session_low: {session_low}
- fvg_detected: {fvg_detected}
- fvg_direction: {fvg_direction}
- fvg_gap_high: {fvg_gap_high}
- fvg_gap_low: {fvg_gap_low}
- last_close: {last_close}
- atr: {atr}
- sl_mult: {sl_mult}
- tp_mult: {tp_mult}
- vol_min: {vol_min}
- rvol_min: {rvol_min}

REGLAS:
1. Solo operar si volatility > vol_min Y relative_volume > rvol_min Y fvg_detected=true
2. Buy si fvg_direction=bullish y last_close cerca de session_high
3. Sell si fvg_direction=bearish y last_close cerca de session_low
4. entry = last_close
5. Stop loss = entry -/+ (atr * sl_mult)
6. Take profit = entry +/- (atr * tp_mult)
7. Si no aplica: action=hold con entry/SL/TP=0

OUTPUT solo JSON valido (sin markdown):
{{"action":"buy|sell|hold","entry":float,"stop_loss":float,"take_profit":float,"risk_percent":1.0,"confidence":0-100,"reason":"breve"}}"""

NEEDED = ["symbol","volatility","relative_volume","session_high","session_low",
          "fvg_detected","fvg_direction","fvg_gap_high","fvg_gap_low",
          "last_close","atr","sl_mult","tp_mult","vol_min","rvol_min"]

def fvg_agent(context, params):
    data = {**context, **{k: v for k, v in params.items() if k not in context}}
    safe = {k: data.get(k, "N/A") for k in NEEDED}
    try:
        prompt = PROMPT.format(**safe)
        return run_agent(prompt)
    except Exception as e:
        return {"action": "hold", "confidence": 0, "error": f"fvg_agent: {e}"}

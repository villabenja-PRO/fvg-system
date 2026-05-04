from app.agents.base_agent import run_agent

PROMPT = """Eres un agente de trading cuantitativo conectado a Binance.
Analizas SOLO 1 sesión diaria basada en la primera vela de 5 minutos (09:30-09:35 EST).

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

PARAMS (de WFO):
- sl_mult: {sl_mult}
- tp_mult: {tp_mult}
- vol_min: {vol_min}
- rvol_min: {rvol_min}

REGLAS:
1. Solo operar si volatility > vol_min y relative_volume > rvol_min
2. Solo operar si fvg_detected = true
3. Buy si fvg_direction=bullish y last_close rompe session_high
4. Sell si fvg_direction=bearish y last_close rompe session_low
5. Stop loss = entry -/+ (atr * sl_mult)
6. Take profit = entry +/- (atr * tp_mult) -> ratio 2R
7. Risk = 1% capital
8. Si no se cumplen reglas: action="hold"

OUTPUT solo JSON valido (sin markdown):
{{"action":"buy|sell|hold","entry":float,"stop_loss":float,"take_profit":float,"risk_percent":1.0,"confidence":0-100,"reason":"breve"}}"""

def fvg_agent(context, params):
    prompt = PROMPT.format(**context, **params)
    return run_agent(prompt)

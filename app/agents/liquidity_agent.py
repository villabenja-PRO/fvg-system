from app.agents.base_agent import run_agent

PROMPT = """Eres un agente de liquidez (ICT). Detectas sweeps de máximos/mínimos previos.

INPUT:
- symbol: {symbol}
- last_close: {last_close}
- session_high: {session_high}
- session_low: {session_low}
- prev_session_high: {prev_session_high}
- prev_session_low: {prev_session_low}
- swept_high: {swept_high}
- swept_low: {swept_low}
- fvg_direction: {fvg_direction}

REGLAS ICT:
1. Buy si: swept_low=true (precio rompió mínimo previo y volvió arriba) Y fvg_direction=bullish → reversión alcista tras stop hunt
2. Sell si: swept_high=true Y fvg_direction=bearish → reversión bajista tras stop hunt
3. Hold si: no hay sweep o sweep contradice FVG
4. Confidence alta (>70) cuando sweep + FVG en misma dirección

OUTPUT solo JSON:
{{"agent":"LIQUIDITY","action":"buy|sell|hold","confidence":0-100,"reason":"breve"}}"""

def liquidity_agent(context, liquidity):
    prompt = PROMPT.format(**context, **liquidity)
    return run_agent(prompt, max_tokens=200)

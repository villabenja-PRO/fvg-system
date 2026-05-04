from app.agents.base_agent import run_agent

PROMPT = """Eres un agente de momentum. Analizas RSI y MACD para confirmar dirección.

INPUT:
- symbol: {symbol}
- last_close: {last_close}
- rsi_14: {rsi_14}
- macd: {macd}
- macd_signal: {macd_signal}
- macd_hist: {macd_hist}
- fvg_direction: {fvg_direction}

REGLAS:
1. Buy si: rsi_14 entre 40-70 (no sobrecomprado) Y macd_hist > 0 (cruce alcista) Y fvg_direction=bullish
2. Sell si: rsi_14 entre 30-60 (no sobrevendido) Y macd_hist < 0 Y fvg_direction=bearish
3. Hold si: divergencia entre RSI y dirección FVG, o RSI extremo (<30 o >70)
4. Confidence baja (<50) si momentum débil

OUTPUT solo JSON:
{{"agent":"MOMENTUM","action":"buy|sell|hold","confidence":0-100,"reason":"breve"}}"""

def momentum_agent(context, indicators):
    prompt = PROMPT.format(**context, **indicators)
    return run_agent(prompt, max_tokens=200)

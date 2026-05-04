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
1. Buy si swept_low=true Y fvg_direction=bullish (reversion tras stop hunt)
2. Sell si swept_high=true Y fvg_direction=bearish
3. Hold si no hay sweep o sweep contradice FVG
 
OUTPUT solo JSON:
{{"action":"buy|sell|hold","confidence":0-100,"reason":"breve"}}"""
 
NEEDED = ["symbol","last_close","session_high","session_low",
         "prev_session_high","prev_session_low","swept_high","swept_low","fvg_direction"]
 
def liquidity_agent(context, liquidity):
    data = {**context, **liquidity}
    safe = {k: data.get(k, "N/A") for k in NEEDED}
    try:
        prompt = PROMPT.format(**safe)
        return run_agent(prompt, max_tokens=200)
    except Exception as e:
        return {"action":"hold","confidence":0,"error":f"liquidity_agent: {e}"}

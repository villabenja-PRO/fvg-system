from app.agents.base_agent import run_agent
 
PROMPT = """Eres un agente de momentum (RSI + MACD).
 
INPUT:
- symbol: {symbol}
- last_close: {last_close}
- rsi_14: {rsi_14}
- macd: {macd}
- macd_signal: {macd_signal}
- macd_hist: {macd_hist}
- fvg_direction: {fvg_direction}
 
REGLAS:
1. Buy si rsi_14 entre 40-70 Y macd_hist > 0 Y fvg_direction=bullish
2. Sell si rsi_14 entre 30-60 Y macd_hist < 0 Y fvg_direction=bearish
3. Hold si momentum contradice fvg_direction o RSI extremo
 
OUTPUT solo JSON:
{{"action":"buy|sell|hold","confidence":0-100,"reason":"breve"}}"""
 
NEEDED = ["symbol","last_close","rsi_14","macd","macd_signal","macd_hist","fvg_direction"]
 
def momentum_agent(context, indicators):
    data = {**context, **indicators}
    safe = {k: data.get(k, "N/A") for k in NEEDED}
    try:
        prompt = PROMPT.format(**safe)
        return run_agent(prompt, max_tokens=200)
    except Exception as e:
        return {"action":"hold","confidence":0,"error":f"momentum_agent: {e}"}

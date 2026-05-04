# FVG Trading System

Sistema FVG + WFO + Risk Management con Claude, FastAPI, n8n y Supabase.

## Stack
- **FastAPI** (Python): pipeline de decisión, WFO, resolver
- **Supabase** (schema `fvg`): signals, trades, wfo_params, risk_state
- **n8n** (Railway): scheduling y notificaciones Telegram
- **Claude Sonnet 4.5**: agente de decisión

## Arquitectura

```
n8n cron 5m (09:30-09:39 EST)
   └─> GET /trade/fvg?symbol=...
         └─> FastAPI: fetch Binance 5m → detect FVG → filtros vol/rvol
              → Claude Sonnet 4.5 → orchestrator (risk check, position size)
              → INSERT fvg.signals + fvg.trades (status=pending)
         <─ {context, decision}
   └─> IF conf>=65 → Telegram

n8n cron 5m (resolver)
   └─> POST /resolver/run
         └─> SELECT trades WHERE status=pending
              → fetch Binance 1m desde entry → detect SL/TP intra-vela
              → UPDATE trades + register_trade(pnl) → risk_state
         <─ [{id, outcome, pnl_usd, r}, ...]
   └─> Telegram WIN/LOSS por trade

n8n cron domingo 03:00 EST
   └─> POST /wfo/run?symbol=BTCUSDT&days=90
         └─> walk-forward (60d IS / 30d OOS) → grid search
              → mejores params → INSERT fvg.wfo_params (active=true)
              → desactiva params anteriores
   └─> Telegram "WFO done"
```

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | healthcheck |
| GET | `/trade/fvg?symbol=BTCUSDT` | analiza y guarda decisión |
| POST | `/wfo/run?symbol=...&days=90` | ejecuta WFO (background) |
| GET | `/wfo/active?symbol=...` | params activos |
| GET | `/risk/state` | equity / DD / trades hoy |
| POST | `/resolver/run` | resuelve trades pending |
| GET | `/backtest?symbol=...&days=30` | backtest con params activos |

## Env vars (Railway)
```
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-5
SUPABASE_URL=https://anjoyxzprmjukwzrdyqo.supabase.co
SUPABASE_SERVICE_KEY=eyJ...   # service_role key, no anon
FVG_API_URL=https://<tu-app-railway>.up.railway.app   # en n8n
TELEGRAM_BOT_TOKEN=...   # ya configurado en n8n
TELEGRAM_CHAT_ID=...
```

## Deploy

```bash
# Local
pip install -r requirements.txt
uvicorn main:app --reload

# Railway: usa start command
uvicorn main:app --host 0.0.0.0 --port $PORT
```

## Workflows n8n creados
- `[wfo-cron] FVG WFO Optimizer` — domingo 03:00 EST
- `[fvg] Binance FVG analyzer` — cron 5m + gate 09:30-09:39 EST
- `[fvg-cron] FVG resolver` — cron 5m

## Pendiente manual
1. En cada workflow n8n, **configurar credenciales del HTTP Request node** (no requiere auth si tu FastAPI es público; si quieres protegerlo, añade header bearer y `FVG_API_TOKEN` env var).
2. Establecer `FVG_API_URL` en n8n env vars.
3. Activar los 3 workflows (vienen inactivos por seguridad).
4. Deploy del FastAPI en Railway con las env vars indicadas.
5. Conseguir `SUPABASE_SERVICE_KEY` desde dashboard Supabase → Settings → API.

## Reglas de riesgo
- Risk per trade: 1% equity
- Max trades/día: 3
- Stop semanal: -5% equity
- Position size dinámico: x0.75 si DD < -5%, x0.5 si DD < -10%
- Filtros: `volatility > vol_min` AND `relative_volume > rvol_min` (de WFO)
- TP/SL: ATR-based (sl_mult, tp_mult de WFO)

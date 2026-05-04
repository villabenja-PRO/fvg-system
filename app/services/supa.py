import os
import requests

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://anjoyxzprmjukwzrdyqo.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

def _h():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Accept-Profile": "fvg",
        "Content-Profile": "fvg",
        "Prefer": "return=representation"
    }

def insert(table, row):
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=_h(), json=row, timeout=15)
    r.raise_for_status()
    return r.json()

def select(table, filters=""):
    url = f"{SUPABASE_URL}/rest/v1/{table}{filters}"
    r = requests.get(url, headers=_h(), timeout=15)
    r.raise_for_status()
    return r.json()

def update(table, filters, patch):
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/{table}{filters}", headers=_h(), json=patch, timeout=15)
    r.raise_for_status()
    return r.json()

def get_active_params(symbol="BTCUSDT"):
    rows = select("wfo_params", f"?symbol=eq.{symbol}&active=is.true&order=created_at.desc&limit=1")
    return rows[0] if rows else {"sl_mult":1.0,"tp_mult":2.0,"vol_min":0.5,"rvol_min":1.2}

def get_risk_state():
    rows = select("risk_state", "?order=updated_at.desc&limit=1")
    return rows[0] if rows else None

def pre_filter(context, params):
    """
    Retorna (passed: bool, reason: str).
    Si retorna False, NO se llama a Claude (ahorra $$).
    """
    if not context.get("fvg_detected"):
        return False, "no_fvg_detected"

    vol = context.get("volatility", 0)
    rvol = context.get("relative_volume", 0)
    if vol < params.get("vol_min", 0.5):
        return False, f"low_volatility_{vol:.2f}<{params.get('vol_min')}"
    if rvol < params.get("rvol_min", 1.2):
        return False, f"low_rvol_{rvol:.2f}<{params.get('rvol_min')}"

    if not context.get("atr"):
        return False, "no_atr"

    return True, "ok"

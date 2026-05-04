WEIGHTS = {"FVG": 0.5, "LIQUIDITY": 0.3, "MOMENTUM": 0.2}

def ensemble_vote(signals, min_score=0.4, min_agreement=2):
    """Voto ponderado. Requiere min_agreement agentes en misma dirección."""
    score = 0
    buys, sells, holds = 0, 0, 0
    contributions = []

    for s in signals:
        agent = s.get("agent", "?")
        action = s.get("action", "hold")
        conf = float(s.get("confidence", 0)) / 100
        w = WEIGHTS.get(agent, 0.2)

        if action == "buy":
            score += w * conf; buys += 1
        elif action == "sell":
            score -= w * conf; sells += 1
        else:
            holds += 1
        contributions.append({"agent": agent, "action": action, "conf": conf, "weight": w})

    if buys >= min_agreement and score > min_score:
        final = "buy"
    elif sells >= min_agreement and score < -min_score:
        final = "sell"
    else:
        final = "hold"

    avg_conf = sum(c["conf"] for c in contributions) / len(contributions) if contributions else 0
    return {
        "action": final,
        "score": round(score, 3),
        "ensemble_confidence": round(avg_conf * 100, 1),
        "votes": {"buy": buys, "sell": sells, "hold": holds},
        "contributions": contributions
    }

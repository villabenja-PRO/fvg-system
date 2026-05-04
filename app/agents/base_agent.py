import json
import re
from app.services.claude_client import call_claude

def run_agent(prompt, max_tokens=400):
    raw = call_claude(prompt, max_tokens=max_tokens)
    try:
        text = raw["content"][0]["text"]
        m = re.search(r"\{.*\}", text, re.DOTALL)
        return json.loads(m.group(0) if m else text)
    except Exception as e:
        return {"action": "hold", "confidence": 0, "error": str(e), "raw": raw}

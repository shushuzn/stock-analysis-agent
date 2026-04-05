"""Text-to-Speech price alert announcements using Windows SAPI."""

from __future__ import annotations

import subprocess


def speak(text: str, rate: int = -2) -> dict:
    """Speak text using Windows SAPI. Returns success status."""
    try:
        # Use PowerShell to call System.Speech.Synthesis
        script = f'''
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = {rate}
$synth.Speak("{text.replace('"', '').replace("'", "")}")
'''
        result = subprocess.run(
            ["powershell", "-Command", script],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return {"success": result.returncode == 0, "text": text}
    except Exception as e:
        return {"error": str(e), "text": text}


def speak_price(symbol: str, price: float, change_pct: float, reason: str = "") -> dict:
    """Speak a price alert for a symbol."""
    direction = "上涨" if change_pct > 0 else "下跌"
    msg = f"{symbol} 当前价格 {price:.2f}，{direction} {abs(change_pct):.2f}%"
    if reason:
        msg += f"，原因：{reason}"
    return speak(msg)

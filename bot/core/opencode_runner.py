import asyncio
import subprocess
from bot.core.config import TIMEOUT_SECONDS


def run_opencode(prompt: str, cwd: str) -> dict:
    result = subprocess.run(
        ["opencode", "run", prompt],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


async def ejecutar_opencode(prompt: str, cwd: str) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: run_opencode(prompt, cwd))

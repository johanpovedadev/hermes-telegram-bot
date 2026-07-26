import asyncio
import os
import subprocess
from bot.core.config import TIMEOUT_SECONDS

OPENCODE_CMD = os.path.join(os.environ.get("APPDATA", ""), "npm", "opencode.cmd")

LAST_LINES = 15


async def ejecutar_opencode(prompt: str, cwd: str, on_complete=None):
    proc = await asyncio.create_subprocess_exec(
        OPENCODE_CMD, "run", prompt,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        if on_complete:
            await on_complete({
                "returncode": -1,
                "stdout": "",
                "stderr": f"Timeout ({TIMEOUT_SECONDS}s)",
                "timeout": True,
            })
        return

    result = {
        "returncode": proc.returncode,
        "stdout": stdout.decode(errors="replace"),
        "stderr": stderr.decode(errors="replace"),
        "timeout": False,
    }

    if on_complete:
        await on_complete(result)

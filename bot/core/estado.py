"""Issue #6: /estado con datos reales y sin IA, en formato corto para el celular. Texto plano: los errores de PM2/gh traen caracteres que rompen el Markdown.

Fuentes, cada una aislada (si una falla, las demás igual salen y se dice cuál falló):
- PM2 (`pm2 jlist`): cada app online o caída, reinicios y tiempo arriba.
- Puertos de saas-bot/config/ports.json: libre u ocupado (sin depender de Node).
- /health de cada bot (servidor de estado en su LION_STATUS_PORT): responde o no.
- Último CI de cada repo de projects.yaml (`gh run list`).
- Trabajos de Hermes corriendo.
"""
import json
import os
import shutil
import socket
import subprocess
import time
import urllib.request
from typing import Callable, Dict, List, Optional, Tuple

RunCmd = Callable[[List[str], float], Tuple[int, str, str]]


def run_cmd(argv: List[str], timeout: float = 15) -> Tuple[int, str, str]:
    exe = shutil.which(argv[0]) or argv[0]  # pm2/gh en Windows son .cmd
    r = subprocess.run([exe, *argv[1:]], capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def puerto_ocupado(port: int, host: str = "127.0.0.1", timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def http_ok(url: str, timeout: float = 2) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 200 <= r.status < 300
    except Exception:
        return False


def _uptime(ms_inicio: Optional[int], ahora_ms: float) -> str:
    if not ms_inicio:
        return "?"
    s = max(0, int((ahora_ms - ms_inicio) / 1000))
    if s >= 86400:
        return f"{s // 86400}d"
    if s >= 3600:
        return f"{s // 3600}h"
    return f"{s // 60}m"


def seccion_pm2(run: RunCmd = run_cmd, ahora_ms: Optional[float] = None) -> List[str]:
    ahora_ms = ahora_ms or time.time() * 1000
    try:
        code, out, err = run(["pm2", "jlist"], 15)
        if code != 0:
            return [f"🔴 PM2 no responde ({(err or out).strip()[:80] or f'código {code}'})"]
        apps = json.loads(out or "[]")
    except FileNotFoundError:
        return ["⚪ PM2 no está instalado en este equipo"]
    except subprocess.TimeoutExpired:
        return ["🔴 PM2 no responde (se demoró más de 15 s)"]
    except (ValueError, json.JSONDecodeError):
        return ["🔴 PM2 respondió algo que no es JSON"]
    if not apps:
        return ["🔴 PM2 no tiene ninguna app corriendo"]
    lineas = []
    for a in sorted(apps, key=lambda x: x.get("name", "")):
        env = a.get("pm2_env") or {}
        st = env.get("status", "?")
        icono = "🟢" if st == "online" else "🔴"
        rein = env.get("restart_time", 0)
        extra = f" · {rein} reinicios" if rein else ""
        up = f" · {_uptime(env.get('pm_uptime'), ahora_ms)}" if st == "online" else f" · {st}"
        lineas.append(f"{icono} {a.get('name', '?')}{up}{extra}")
    return lineas


def cargar_puertos(saas_bot_dir: Optional[str]) -> Optional[List[dict]]:
    if not saas_bot_dir:
        return None
    ruta = os.path.join(saas_bot_dir, "config", "ports.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f).get("services") or []
    except (OSError, ValueError):
        return None


def seccion_bots(servicios: Optional[List[dict]], ocupado=puerto_ocupado, health=http_ok) -> List[str]:
    """Bots de WhatsApp: su servidor de estado (LION_STATUS_PORT) responde /health."""
    if servicios is None:
        return ["⚪ Sin registro de puertos (saas-bot/config/ports.json)"]
    bots = [s for s in servicios if s.get("env") == "LION_STATUS_PORT"]
    out = []
    for s in bots:
        ok = health(f"http://127.0.0.1:{s['port']}/health")
        out.append(f"{'🟢' if ok else '🔴'} {s['name']} {'responde' if ok else 'no responde'} ({s['port']})")
    otros = [s for s in servicios if s.get("env") != "LION_STATUS_PORT" and not s.get("manual")]
    for s in otros:
        out.append(f"{'🟢' if ocupado(s['port']) else '🔴'} {s['name']} :{s['port']}")
    return out or ["⚪ No hay bots registrados"]


def seccion_ci(repos: List[str], run: RunCmd = run_cmd) -> List[str]:
    out = []
    for repo in repos:
        try:
            code, stdout, err = run(["gh", "run", "list", "--repo", repo, "--limit", "1", "--json", "conclusion,status,headBranch,workflowName"], 20)
            if code != 0:
                out.append(f"⚪ {repo}: sin datos ({(err or '').strip()[:60]})")
                continue
            runs = json.loads(stdout or "[]")
            if not runs:
                out.append(f"⚪ {repo}: sin ejecuciones")
                continue
            r = runs[0]
            if r.get("status") != "completed":
                icono, txt = "🟡", "corriendo"
            elif r.get("conclusion") == "success":
                icono, txt = "🟢", "verde"
            else:
                icono, txt = "🔴", r.get("conclusion") or "falló"
            out.append(f"{icono} {repo.split('/')[-1]}: {txt} ({r.get('headBranch', '?')})")
        except FileNotFoundError:
            return ["⚪ gh (GitHub CLI) no está instalado en este equipo"]
        except Exception as e:
            out.append(f"⚪ {repo}: error ({type(e).__name__})")
    return out or ["⚪ Ningún repo en projects.yaml"]


def construir_estado(registro, manager=None, run: RunCmd = run_cmd, ocupado=puerto_ocupado, health=http_ok, ahora_ms=None) -> str:
    def seguro(fn, nombre):
        try:
            return fn()
        except Exception as e:  # una fuente rota nunca tumba el comando
            return [f"⚪ {nombre}: error ({type(e).__name__})"]

    saas = registro.obtener("saas-bot") if registro else None
    servicios = cargar_puertos(saas.carpeta if saas else None)
    repos = [p.repo for p in (registro.proyectos if registro else []) if p.repo]
    corriendo: Dict[str, int] = manager.corriendo() if manager else {}

    partes = ["🤖 Hermes — estado", "", "PM2"]
    partes += seguro(lambda: seccion_pm2(run, ahora_ms), "PM2")
    partes += ["", "Bots y servicios"]
    partes += seguro(lambda: seccion_bots(servicios, ocupado, health), "Bots")
    partes += ["", "CI"]
    partes += seguro(lambda: seccion_ci(repos, run), "CI")
    partes += ["", "Hermes"]
    partes.append("🟡 Trabajando: " + ", ".join(f"{p} #{i}" for p, i in corriendo.items()) if corriendo else "🟢 Libre")
    return "\n".join(partes)

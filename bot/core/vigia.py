"""Issue #7: Vigía. Avisa si Hermes, PM2 o una app se caen o quedan en bucle de reinicios.

Origen: el 17 oct 2026 `agentes-redes` se reinició ~3,5 millones de veces, llenó 3 GB de logs y PM2 se cayó con todos
los bots. Nadie se enteró hasta que Johan reinició el PC.

Cada HERMES_VIGIA_CADA_MIN (5) minutos revisa `pm2 jlist`:
- 🔁 bucle: una app sumó más de HERMES_VIGIA_MAX_REINICIOS (5) reinicios en HERMES_VIGIA_VENTANA_MIN (10) minutos.
- 🔴 caída: una app quedó stopped/errored.
- 🔴 PM2 no responde.
Cada problema se avisa UNA vez (no un mensaje por reinicio) y se avisa también cuando se arregla (✅).

Horas de silencio (HERMES_SILENCIO, ej. "22-7"): lo crítico (caídas, bucles, PM2 sin responder) se avisa igual; lo
demás (✅ recuperaciones) se guarda y se manda junto al terminar el silencio.

Latido externo: si HERMES_HEARTBEAT_URL está configurada, Hermes la visita en cada revisión (por ejemplo un check de
healthchecks.io con integración a Telegram). Si Hermes o el PC se caen, el aviso llega desde afuera. Ver README.
"""
import json
import os
import subprocess
import time
import urllib.request
from collections import deque
from datetime import datetime
from typing import Callable, Deque, Dict, List, Optional, Tuple

from bot.core.estado import run_cmd as _run_cmd

CAIDAS = {"stopped", "errored"}


def _env_num(nombre: str, defecto: float) -> float:
    try:
        return float(os.environ.get(nombre, defecto))
    except ValueError:
        return defecto


def parse_silencio(raw: Optional[str]) -> Optional[Tuple[int, int]]:
    """'22-7' -> (22, 7). Vacío o inválido = sin silencio."""
    try:
        a, b = str(raw or "").split("-")
        a, b = int(a), int(b)
        return (a, b) if 0 <= a <= 23 and 0 <= b <= 23 and a != b else None
    except ValueError:
        return None


def en_silencio(hora: int, rango: Optional[Tuple[int, int]]) -> bool:
    if not rango:
        return False
    a, b = rango
    return a <= hora < b if a < b else (hora >= a or hora < b)


def ping(url: str, timeout: float = 10) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 200 <= r.status < 300
    except Exception:
        return False


class Vigia:
    def __init__(self, run=_run_cmd, reloj: Callable[[], float] = time.time, hora: Optional[Callable[[], int]] = None,
                 ping_fn=ping):
        self.run = run
        self.reloj = reloj
        self.hora = hora or (lambda: datetime.now().hour)
        self.ping_fn = ping_fn
        self.max_reinicios = int(_env_num("HERMES_VIGIA_MAX_REINICIOS", 5))
        self.ventana_s = _env_num("HERMES_VIGIA_VENTANA_MIN", 10) * 60
        self.silencio = parse_silencio(os.environ.get("HERMES_SILENCIO", ""))
        self.heartbeat_url = os.environ.get("HERMES_HEARTBEAT_URL", "").strip()
        self._historial: Dict[str, Deque[Tuple[float, int]]] = {}
        self._problemas: Dict[str, str] = {}  # clave -> texto del problema avisado (para avisar una vez y luego ✅)
        self._diferidos: List[str] = []
        self._estaba_en_silencio = False
        self.ultimo_latido_ok: Optional[bool] = None

    def _leer_pm2(self) -> Optional[list]:
        try:
            code, out, _err = self.run(["pm2", "jlist"], 15)
            if code != 0:
                return None
            return json.loads(out or "[]")
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            return None

    def revisar(self) -> List[str]:
        """Una pasada. Devuelve los mensajes a enviar AHORA (lo no crítico en silencio queda diferido)."""
        ahora = self.reloj()
        criticos: List[str] = []
        normales: List[str] = []
        actuales: Dict[str, str] = {}

        apps = self._leer_pm2()
        if apps is None:
            actuales["pm2"] = "🔴 PM2 no responde: los bots pueden estar caídos. Revisa el PC (pm2 status)."
        else:
            for a in apps:
                nombre = a.get("name", "?")
                env = a.get("pm2_env") or {}
                st = env.get("status")
                rein = int(env.get("restart_time") or 0)
                h = self._historial.setdefault(nombre, deque())
                h.append((ahora, rein))
                while h and ahora - h[0][0] > self.ventana_s:
                    h.popleft()
                suma = rein - h[0][1] if h else 0
                if suma > self.max_reinicios:
                    actuales[f"bucle:{nombre}"] = (f"🔁 {nombre} está en bucle: {suma} reinicios en {int(self.ventana_s // 60)} min "
                                                   f"(total {rein}). Revisa su log o detenla: pm2 stop {nombre}")
                if st in CAIDAS:
                    actuales[f"caida:{nombre}"] = f"🔴 {nombre} está {st} en PM2. Revisa: pm2 logs {nombre} --lines 30"

        for clave, texto in actuales.items():
            if clave not in self._problemas:
                criticos.append(texto)
        for clave in list(self._problemas):
            if clave not in actuales:
                quien = clave.split(":", 1)[-1]
                normales.append("✅ PM2 volvió a responder" if clave == "pm2" else f"✅ {quien} se normalizó")
        self._problemas = actuales

        if self.heartbeat_url:
            self.ultimo_latido_ok = self.ping_fn(self.heartbeat_url)

        silencio = en_silencio(self.hora(), self.silencio)
        salida = list(criticos)
        if silencio:
            self._diferidos += normales
        else:
            if self._estaba_en_silencio and self._diferidos:
                salida.append("🌅 Mientras estabas en silencio:\n" + "\n".join(f"• {d}" for d in self._diferidos))
                self._diferidos = []
            salida += normales
        self._estaba_en_silencio = silencio
        return salida


async def bucle_vigia(vigia: Vigia, notify, cada_s: Optional[float] = None, veces: Optional[int] = None):
    """Revisión periódica (corre como tarea de fondo del bot). `veces` es para las pruebas."""
    import asyncio
    cada_s = cada_s if cada_s is not None else _env_num("HERMES_VIGIA_CADA_MIN", 5) * 60
    n = 0
    while veces is None or n < veces:
        try:
            mensajes = await asyncio.to_thread(vigia.revisar)
            for m in mensajes:
                try:
                    await notify(m)
                except Exception:
                    pass
        except Exception:
            pass  # el vigía nunca se cae por una revisión mala
        n += 1
        if veces is None or n < veces:
            await asyncio.sleep(cada_s)

"""Issue #5: el agente corre en segundo plano, con registro y avisos. Sin IA: solo código.

- Ejecutor genérico: OpenCode (`opencode run <prompt>`) o Claude Code (`claude -p <prompt>`), según HERMES_AGENT.
- Corre en segundo plano: el bot sigue respondiendo mientras tanto.
- Tiempo límite configurable (HERMES_AGENT_TIMEOUT_MIN, 45 min por defecto). Al vencerse se mata el proceso.
- Un trabajo a la vez por proyecto (candado).
- Si el agente termina bien, corre el comando de pruebas del proyecto (projects.yaml).
- Registro en SQLite (~/.jarvis/hermes_jobs.db): proyecto, prompt, agente, inicio, fin, duración, código de salida y
  resultado de las pruebas. Un trabajo que quedó "corriendo" cuando el bot se reinició se marca "interrumpido".
- Avisos: ▶️ empezó, ⏳ avance cada HERMES_AVANCE_MIN (10) min con los archivos que lleva cambiados, ✅ terminó
  (duración y pruebas), ❌ falló (últimas líneas), ⏰ timeout.

Nunca hace commit, push ni toca producción: eso es de la cola (issue #9) y siempre con aprobación de Johan.
"""
import asyncio
import os
import shutil
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable, Dict, List, Optional

Notify = Callable[[str], Awaitable[None]]

# En modo `claude -p` no hay nadie para aprobar permisos: sin estas banderas el agente no puede editar ni correr pruebas.
# Puede editar y usar la terminal dentro del worktree, pero nunca subir, hacer merge ni borrar ramas: eso es de Hermes.
CLAUDE_PROHIBIDO = ["Bash(git push:*)", "Bash(git merge:*)", "Bash(git reset --hard:*)", "Bash(git branch -D:*)",
                    "Bash(gh pr merge:*)", "Bash(rm -rf:*)", "Bash(pm2:*)"]

AGENTES = {
    "opencode": lambda prompt: ["opencode", "run", prompt],
    "claude": lambda prompt: ["claude", "-p", prompt, "--permission-mode", "acceptEdits", "--allowedTools", "Bash",
                              "--disallowedTools", *CLAUDE_PROHIBIDO],
}

# El revisor solo lee el diff que va en el prompt: sin permisos de edición ni de terminal.
REVISORES = {
    "opencode": lambda prompt: ["opencode", "run", prompt],
    "claude": lambda prompt: ["claude", "-p", prompt],
}


def agente_configurado() -> str:
    a = os.environ.get("HERMES_AGENT", "opencode").strip().lower()
    return a if a in AGENTES else "opencode"


def timeout_agente_s() -> float:
    return float(os.environ.get("HERMES_AGENT_TIMEOUT_MIN", "45")) * 60


def timeout_pruebas_s() -> float:
    return float(os.environ.get("HERMES_TEST_TIMEOUT_MIN", "20")) * 60


def _cola(texto: str, n: int) -> str:
    t = (texto or "").strip()
    return t[-n:] if len(t) > n else t


def _dur(seg: float) -> str:
    seg = int(round(seg))
    return f"{seg // 60} min {seg % 60} s" if seg >= 60 else f"{seg} s"


@dataclass
class Trabajo:
    id: int
    proyecto: str
    prompt: str
    agente: str
    estado: str
    inicio: str
    fin: Optional[str] = None
    duracion_s: Optional[float] = None
    codigo: Optional[int] = None
    pruebas: Optional[str] = None
    salida: str = ""
    error: str = ""


class JobStore:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = os.path.expanduser(db_path or os.path.join(os.environ.get("HERMES_DATA_DIR", "~/.jarvis"), "hermes_jobs.db"))
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS trabajos (
                id INTEGER PRIMARY KEY AUTOINCREMENT, proyecto TEXT NOT NULL, prompt TEXT NOT NULL, agente TEXT NOT NULL,
                estado TEXT NOT NULL, inicio TEXT NOT NULL, fin TEXT, duracion_s REAL, codigo INTEGER, pruebas TEXT,
                salida TEXT DEFAULT '', error TEXT DEFAULT '')""")

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def crear(self, proyecto: str, prompt: str, agente: str) -> int:
        with self._conn() as c:
            cur = c.execute("INSERT INTO trabajos (proyecto, prompt, agente, estado, inicio) VALUES (?, ?, ?, 'corriendo', ?)",
                            (proyecto, prompt[:2000], agente, datetime.now(timezone.utc).isoformat(timespec="seconds")))
            return cur.lastrowid

    def cerrar(self, job_id: int, estado: str, duracion_s: float, codigo: Optional[int], pruebas: Optional[str], salida: str, error: str):
        with self._conn() as c:
            c.execute("UPDATE trabajos SET estado=?, fin=?, duracion_s=?, codigo=?, pruebas=?, salida=?, error=? WHERE id=?",
                      (estado, datetime.now(timezone.utc).isoformat(timespec="seconds"), round(duracion_s, 1), codigo, pruebas,
                       _cola(salida, 3000), _cola(error, 3000), job_id))

    def marcar_interrumpidos(self) -> int:
        """Al arrancar: lo que quedó 'corriendo' de una ejecución anterior del bot ya no corre."""
        with self._conn() as c:
            return c.execute("UPDATE trabajos SET estado='interrumpido' WHERE estado='corriendo'").rowcount

    def obtener(self, job_id: int) -> Optional[Trabajo]:
        with self._conn() as c:
            r = c.execute("SELECT id, proyecto, prompt, agente, estado, inicio, fin, duracion_s, codigo, pruebas, salida, error FROM trabajos WHERE id=?", (job_id,)).fetchone()
        return Trabajo(*r) if r else None

    def ultimos(self, n: int = 10) -> List[Trabajo]:
        with self._conn() as c:
            rows = c.execute("SELECT id, proyecto, prompt, agente, estado, inicio, fin, duracion_s, codigo, pruebas, salida, error FROM trabajos ORDER BY id DESC LIMIT ?", (n,)).fetchall()
        return [Trabajo(*r) for r in rows]


def _matar_arbol(pid: int) -> None:
    """Mata el proceso y todos sus hijos (Windows: taskkill /T; Linux/Mac: el grupo de procesos)."""
    try:
        if os.name == "nt":
            import subprocess
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True, timeout=15)
        else:
            import signal
            os.killpg(os.getpgid(pid), signal.SIGKILL)
    except Exception:
        pass


def avance_git(carpeta: str) -> str:
    """Qué lleva el agente: archivos cambiados según git. Nunca falla."""
    import subprocess
    try:
        st = subprocess.run(["git", "-C", carpeta, "status", "--porcelain"], capture_output=True, text=True, timeout=15)
        if st.returncode != 0:
            return ""
        archivos = [l[3:] for l in st.stdout.splitlines() if l.strip()]
        if not archivos:
            return "\nAún sin archivos cambiados."
        muestra = ", ".join(archivos[:5]) + (f" y {len(archivos) - 5} más" if len(archivos) > 5 else "")
        return f"\n{len(archivos)} archivo(s) cambiado(s): {muestra}"
    except Exception:
        return ""


class ProyectoOcupado(Exception):
    pass


class JobManager:
    def __init__(self, store: Optional[JobStore] = None, runner=None, avance_cada_s: Optional[float] = None, avance_fn=None):
        self.store = store or JobStore()
        self.avance_cada_s = avance_cada_s if avance_cada_s is not None else float(os.environ.get("HERMES_AVANCE_MIN", "10")) * 60
        self.avance_fn = avance_fn or avance_git
        self._locks: Dict[str, int] = {}  # proyecto -> id del trabajo que lo tiene
        self._tasks: Dict[int, asyncio.Task] = {}
        self._runner = runner or self._run_proceso

    def corriendo(self) -> Dict[str, int]:
        return dict(self._locks)

    async def _run_proceso(self, argv_o_shell, cwd: str, timeout: float, shell: bool = False):
        """Ejecuta y devuelve (codigo, stdout, stderr, vencido). Mata el proceso si se vence.
        stdin vacío: `claude -p` espera datos por stdin si lo hereda abierto (pasó en PM2 el 23 oct 2026)."""
        # Grupo de procesos propio: al vencerse se mata el árbol completo (el agente lanza node, npm, pruebas...).
        extra = {} if os.name == "nt" else {"start_new_session": True}
        if shell:
            proc = await asyncio.create_subprocess_shell(argv_o_shell, cwd=cwd, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, **extra)
        else:
            exe = shutil.which(argv_o_shell[0]) or argv_o_shell[0]  # en Windows, opencode/claude son .cmd
            proc = await asyncio.create_subprocess_exec(exe, *argv_o_shell[1:], cwd=cwd, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, **extra)
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return proc.returncode, out.decode(errors="replace"), err.decode(errors="replace"), False
        except asyncio.TimeoutError:
            _matar_arbol(proc.pid)
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            await proc.wait()
            return None, "", "", True

    def iniciar(self, proyecto, prompt: str, notify: Notify, agente: Optional[str] = None) -> int:
        """Arranca el trabajo en segundo plano. Lanza ProyectoOcupado si ese proyecto ya tiene uno corriendo."""
        nombre = proyecto.nombre
        if nombre in self._locks:
            raise ProyectoOcupado(f"⏳ `{nombre}` ya tiene el trabajo #{self._locks[nombre]} corriendo. Espera a que termine.")
        agente = agente or agente_configurado()
        job_id = self.store.crear(nombre, prompt, agente)
        self._locks[nombre] = job_id
        self._tasks[job_id] = asyncio.create_task(self._correr(job_id, proyecto, prompt, agente, notify))
        return job_id

    async def esperar(self, job_id: int):
        t = self._tasks.get(job_id)
        if t:
            await t

    async def _avisar(self, notify: Notify, texto: str):
        try:
            await notify(texto)
        except Exception:
            pass  # un aviso que falla nunca deja el candado tomado

    async def _con_avances(self, coro, job_id: int, nombre: str, carpeta: str, notify: Notify, t0: float):
        """Espera al agente y, mientras tanto, avisa cada avance_cada_s qué lleva."""
        tarea = asyncio.ensure_future(coro)
        if self.avance_cada_s <= 0:
            return await tarea
        while True:
            hecho, _ = await asyncio.wait({tarea}, timeout=self.avance_cada_s)
            if hecho:
                return tarea.result()
            try:
                extra = await asyncio.to_thread(self.avance_fn, carpeta)
            except Exception:
                extra = ""
            await self._avisar(notify, f"⏳ Trabajo #{job_id} en `{nombre}` sigue trabajando ({_dur(time.monotonic() - t0)}){extra}")

    async def _correr(self, job_id: int, proyecto, prompt: str, agente: str, notify: Notify):
        nombre = proyecto.nombre
        t0 = time.monotonic()
        estado, codigo, pruebas, salida, error = "fallo", None, None, "", ""
        try:
            await self._avisar(notify, f"▶️ Trabajo #{job_id} empezó en `{nombre}` ({agente})\n📝 {prompt[:200]}")
            codigo, salida, error, vencido = await self._con_avances(
                self._runner(AGENTES[agente](prompt), proyecto.carpeta, timeout_agente_s()), job_id, nombre, proyecto.carpeta, notify, t0)
            if vencido:
                estado = "timeout"
                await self._avisar(notify, f"⏰ Trabajo #{job_id} en `{nombre}`: se venció el tiempo ({_dur(timeout_agente_s())}) y se detuvo el agente.")
                return
            if codigo != 0:
                estado = "fallo"
                await self._avisar(notify, f"❌ Trabajo #{job_id} falló en `{nombre}` (código {codigo}, {_dur(time.monotonic() - t0)})\n\n{_cola(error or salida, 600)}")
                return
            if proyecto.pruebas:
                pc, pout, perr, pvenc = await self._runner(proyecto.pruebas, proyecto.carpeta, timeout_pruebas_s(), shell=True)
                pruebas = "timeout" if pvenc else ("ok" if pc == 0 else "fallo")
                if pruebas != "ok":
                    estado = "fallo"
                    error = (error + "\n" + (perr or pout)).strip()
                    await self._avisar(notify, f"❌ Trabajo #{job_id} en `{nombre}`: el agente terminó pero las pruebas {'se vencieron' if pvenc else 'fallaron'} ({_dur(time.monotonic() - t0)})\n\n{_cola(perr or pout, 600)}")
                    return
            else:
                pruebas = "omitidas"
            estado = "ok"
            await self._avisar(notify, f"✅ Trabajo #{job_id} terminado en `{nombre}`\nTests: {'OK' if pruebas == 'ok' else pruebas}\nTiempo: {_dur(time.monotonic() - t0)}")
        except Exception as e:
            estado, error = "fallo", f"{type(e).__name__}: {e}"
            await self._avisar(notify, f"❌ Trabajo #{job_id} en `{nombre}` se cayó: {error[:300]}")
        finally:
            self.store.cerrar(job_id, estado, time.monotonic() - t0, codigo, pruebas, salida, error)
            self._locks.pop(nombre, None)
            self._tasks.pop(job_id, None)


def resumen_trabajos(manager: JobManager, n: int = 10) -> str:
    iconos = {"corriendo": "🟡", "ok": "✅", "fallo": "❌", "timeout": "⏰", "interrumpido": "⚠️"}
    lineas = ["🛠️ *Trabajos*", ""]
    act = manager.corriendo()
    lineas.append("Corriendo: " + (", ".join(f"`{p}` #{i}" for p, i in act.items()) if act else "ninguno"))
    lineas.append("")
    for t in manager.store.ultimos(n):
        dur = f" · {_dur(t.duracion_s)}" if t.duracion_s is not None else ""
        pr = f" · tests {t.pruebas}" if t.pruebas else ""
        lineas.append(f"{iconos.get(t.estado, '•')} #{t.id} `{t.proyecto}` {t.estado}{dur}{pr}")
    return "\n".join(lineas)

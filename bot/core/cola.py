"""Issue #9: cola de issues. Hermes toma los issues con la etiqueta `hermes:listo` y los trabaja uno por uno.

Por cada issue:
1. Crea un worktree aparte (`HERMES_WORKTREES_DIR`/<proyecto>/issue-<n>) en la rama `feature/issue-<n>`, sacada de la
   rama base del proyecto. La carpeta de producción NUNCA se toca.
2. Le pasa el issue al agente (OpenCode o Claude Code) en ese worktree.
3. Corre las pruebas del proyecto (projects.yaml). Si pasan, hace un commit LOCAL.
4. Pide aprobación por Telegram. Solo con "Subir" hace `git push` de la rama. Nunca hace merge ni toca `main`.

Etiquetas: hermes:listo → hermes:trabajando → hermes:esperando-aprobacion → hermes:hecho (o hermes:fallo / hermes:rechazado).

Frenos (la cola se pausa sola y avisa):
- Las pruebas fallaron (algo se rompió: hay que mirarlo antes de seguir).
- HERMES_COLA_MAX_FALLAS (2) fallas seguidas del agente.
- Tope diario de HERMES_COLA_TOPE_DIA (5) issues.
/pausar y /reanudar la manejan a mano; /cola muestra el estado.
"""
import asyncio
import dataclasses
import json
import os
from datetime import date
from typing import Awaitable, Callable, List, Optional, Tuple

from bot.core.estado import run_cmd as _run_cmd

ETQ_LISTO = "hermes:listo"
ETQ_TRABAJANDO = "hermes:trabajando"
ETQ_ESPERANDO = "hermes:esperando-aprobacion"
ETQ_HECHO = "hermes:hecho"
ETQ_FALLO = "hermes:fallo"
ETQ_RECHAZADO = "hermes:rechazado"

Notify = Callable[[str], Awaitable[None]]
PedirAprobacion = Callable[[str], Awaitable[bool]]


def _env_int(nombre: str, defecto: int) -> int:
    try:
        return int(os.environ.get(nombre, defecto))
    except ValueError:
        return defecto


@dataclasses.dataclass
class Issue:
    proyecto: str
    repo: str
    numero: int
    titulo: str
    cuerpo: str = ""


def prompt_para(issue: Issue) -> str:
    return (f"Resuelve el issue #{issue.numero} del repo {issue.repo}: {issue.titulo}\n\n{issue.cuerpo.strip()}\n\n"
            "Reglas: trabaja solo en esta carpeta, agrega o ajusta las pruebas del cambio y deja todas las pruebas en "
            "verde. No hagas commit, push ni merge: Hermes se encarga y pide aprobación.")


class EstadoCola:
    """Estado persistente (sobrevive reinicios): pausa, motivo, fallas seguidas y cuántos van hoy."""

    def __init__(self, ruta: Optional[str] = None):
        self.ruta = os.path.expanduser(ruta or os.path.join(os.environ.get("HERMES_DATA_DIR", "~/.jarvis"), "hermes_cola.json"))
        self.pausada = False
        self.motivo = ""
        self.fallas_seguidas = 0
        self.dia = ""
        self.hechos_hoy = 0
        self.actual = ""
        try:
            with open(self.ruta, encoding="utf-8") as f:
                d = json.load(f)
            for k in ("pausada", "motivo", "fallas_seguidas", "dia", "hechos_hoy"):
                if k in d:
                    setattr(self, k, d[k])
        except (OSError, ValueError):
            pass

    def guardar(self):
        os.makedirs(os.path.dirname(self.ruta), exist_ok=True)
        with open(self.ruta, "w", encoding="utf-8") as f:
            json.dump({"pausada": self.pausada, "motivo": self.motivo, "fallas_seguidas": self.fallas_seguidas,
                       "dia": self.dia, "hechos_hoy": self.hechos_hoy}, f)

    def pausar(self, motivo: str):
        self.pausada, self.motivo = True, motivo
        self.guardar()

    def reanudar(self):
        self.pausada, self.motivo, self.fallas_seguidas = False, "", 0
        self.guardar()


class Cola:
    def __init__(self, manager, registro_fn, run=_run_cmd, estado: Optional[EstadoCola] = None,
                 hoy: Callable[[], str] = lambda: date.today().isoformat(), worktrees_dir: Optional[str] = None):
        self.manager = manager
        self.registro_fn = registro_fn  # se relee projects.yaml en cada vuelta
        self.run = run
        self.estado = estado or EstadoCola()
        self.hoy = hoy
        self.worktrees_dir = os.path.expanduser(worktrees_dir or os.environ.get("HERMES_WORKTREES_DIR")
                                                or os.path.join(os.environ.get("HERMES_DATA_DIR", "~/.jarvis"), "worktrees"))
        self.max_fallas = _env_int("HERMES_COLA_MAX_FALLAS", 2)
        self.tope_dia = _env_int("HERMES_COLA_TOPE_DIA", 5)

    # --- comandos externos -------------------------------------------------
    def _cmd(self, argv: List[str], timeout: float = 120) -> Tuple[int, str, str]:
        return self.run(argv, timeout)

    def _cmd_ok(self, argv: List[str], timeout: float = 120) -> str:
        code, out, err = self._cmd(argv, timeout)
        if code != 0:
            raise RuntimeError(f"{' '.join(argv[:3])}… falló: {(err or out).strip()[:300]}")
        return out

    def _etiquetar(self, issue: Issue, quitar: Optional[str], poner: Optional[str]):
        argv = ["gh", "issue", "edit", str(issue.numero), "--repo", issue.repo]
        if quitar:
            argv += ["--remove-label", quitar]
        if poner:
            argv += ["--add-label", poner]
        try:
            self._cmd(argv, 30)  # una etiqueta que no se pudo poner nunca frena el trabajo
        except Exception:
            pass

    def _comentar(self, issue: Issue, texto: str):
        try:
            self._cmd(["gh", "issue", "comment", str(issue.numero), "--repo", issue.repo, "--body", texto], 30)
        except Exception:
            pass

    def pendientes(self) -> List[Issue]:
        """Issues abiertos con hermes:listo de los proyectos habilitados, del más viejo al más nuevo."""
        registro = self.registro_fn()
        out: List[Issue] = []
        for p in registro.proyectos:
            if not (p.habilitado and p.repo):
                continue
            code, stdout, _ = self._cmd(["gh", "issue", "list", "--repo", p.repo, "--label", ETQ_LISTO, "--state", "open",
                                         "--json", "number,title,body", "--limit", "20"], 30)
            if code != 0:
                continue
            try:
                for i in sorted(json.loads(stdout or "[]"), key=lambda x: x["number"]):
                    out.append(Issue(p.nombre, p.repo, int(i["number"]), i.get("title", ""), i.get("body") or ""))
            except (ValueError, KeyError, TypeError):
                continue
        return out

    # --- frenos -------------------------------------------------------------
    def freno(self) -> Optional[str]:
        """Motivo por el que la cola no puede tomar otro issue ahora, o None."""
        if self.estado.dia != self.hoy():
            self.estado.dia, self.estado.hechos_hoy = self.hoy(), 0
            self.estado.guardar()
        if self.estado.pausada:
            return f"⏸️ Cola en pausa: {self.estado.motivo or 'pausada a mano'}"
        if self.estado.hechos_hoy >= self.tope_dia:
            return f"🛑 Tope diario alcanzado ({self.tope_dia} issues). Sigue mañana."
        return None

    # --- una vuelta ----------------------------------------------------------
    def _preparar_worktree(self, proyecto, issue: Issue) -> Tuple[str, str]:
        rama = f"feature/issue-{issue.numero}"
        destino = os.path.join(self.worktrees_dir, proyecto.nombre, f"issue-{issue.numero}")
        if os.path.exists(destino):
            raise RuntimeError(f"ya existe {destino} (quedó de un intento anterior; revísalo o bórralo)")
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        self._cmd_ok(["git", "-C", proyecto.carpeta, "fetch", "origin", proyecto.rama_base], 180)
        self._cmd_ok(["git", "-C", proyecto.carpeta, "worktree", "add", "-b", rama, destino, f"origin/{proyecto.rama_base}"], 180)
        return destino, rama

    async def procesar_uno(self, notify: Notify, pedir_aprobacion: PedirAprobacion) -> Optional[str]:
        """Toma el siguiente issue y lo lleva hasta la aprobación. Devuelve qué pasó (para /cola y las pruebas)."""
        motivo = self.freno()
        if motivo:
            return motivo
        registro = self.registro_fn()
        ocupados = set(self.manager.corriendo())
        issue = next((i for i in await asyncio.to_thread(self.pendientes) if i.proyecto not in ocupados), None)
        if not issue:
            return "💤 No hay issues con hermes:listo"
        proyecto = registro.obtener(issue.proyecto)
        etiqueta = f"{issue.proyecto} #{issue.numero}"
        self.estado.actual = etiqueta
        self._etiquetar(issue, ETQ_LISTO, ETQ_TRABAJANDO)
        try:
            try:
                carpeta, rama = await asyncio.to_thread(self._preparar_worktree, proyecto, issue)
            except Exception as e:
                return await self._fallo(issue, notify, f"no pude preparar el worktree: {e}", contar=True)

            await notify(f"📥 Cola: tomo {etiqueta} «{issue.titulo}» en {rama}")
            en_wt = dataclasses.replace(proyecto, carpeta=carpeta)
            job_id = self.manager.iniciar(en_wt, prompt_para(issue), notify)
            await self.manager.esperar(job_id)
            t = self.manager.store.obtener(job_id)

            if not t or t.estado != "ok":
                if t and t.pruebas in ("fallo", "timeout"):
                    self.estado.pausar(f"las pruebas de {etiqueta} fallaron (trabajo #{job_id}). Revisa {carpeta} y usa /reanudar")
                    self._etiquetar(issue, ETQ_TRABAJANDO, ETQ_FALLO)
                    self._comentar(issue, f"Hermes: el agente terminó pero las pruebas fallaron (trabajo #{job_id}). No se subió nada.")
                    await notify(f"⏸️ Cola en pausa: {self.estado.motivo}")
                    return "pruebas fallaron"
                return await self._fallo(issue, notify, f"el agente no terminó bien (trabajo #{job_id}: {t.estado if t else '?'})", contar=True)

            # Commit LOCAL (reversible). El push solo con aprobación.
            await asyncio.to_thread(self._cmd_ok, ["git", "-C", carpeta, "add", "-A"])
            code, cambios, _ = await asyncio.to_thread(self._cmd, ["git", "-C", carpeta, "status", "--porcelain"])
            if code == 0 and not cambios.strip():
                return await self._fallo(issue, notify, "el agente no cambió ningún archivo", contar=True)
            await asyncio.to_thread(self._cmd_ok, ["git", "-C", carpeta, "commit", "-q", "-m", f"feat: {issue.titulo} (#{issue.numero})"])
            code, stat, _ = await asyncio.to_thread(self._cmd, ["git", "-C", carpeta, "diff", "--stat", "HEAD~1"])
            self._etiquetar(issue, ETQ_TRABAJANDO, ETQ_ESPERANDO)
            self.estado.fallas_seguidas = 0
            self.estado.hechos_hoy += 1
            self.estado.guardar()

            resumen = stat.strip().splitlines()[-1] if code == 0 and stat.strip() else "sin resumen"
            ok = await pedir_aprobacion(f"🙋 {etiqueta} listo y con pruebas en verde.\n«{issue.titulo}»\nRama: {rama}\nCambios: {resumen}\n\n¿Lo subo a GitHub? (solo push de la rama; el PR y el merge los haces tú)")
            if not ok:
                self._etiquetar(issue, ETQ_ESPERANDO, ETQ_RECHAZADO)
                await notify(f"🗑️ {etiqueta}: no se subió. El trabajo quedó en {carpeta}")
                return "rechazado"
            try:
                await asyncio.to_thread(self._cmd_ok, ["git", "-C", carpeta, "push", "-u", "origin", rama], 300)
            except Exception as e:
                self.estado.pausar(f"no pude subir {etiqueta}: {e}")
                await notify(f"⏸️ Cola en pausa: {self.estado.motivo}")
                return "push falló"
            self._etiquetar(issue, ETQ_ESPERANDO, ETQ_HECHO)
            self._comentar(issue, f"Hermes subió la rama `{rama}` con pruebas en verde. Falta abrir el PR a `{proyecto.rama_base}` y revisarlo.")
            await notify(f"🚀 {etiqueta} subido en {rama}. Abre el PR a {proyecto.rama_base}: https://github.com/{issue.repo}/compare/{proyecto.rama_base}...{rama}?expand=1")
            return "subido"
        finally:
            self.estado.actual = ""

    async def _fallo(self, issue: Issue, notify: Notify, texto: str, contar: bool) -> str:
        etiqueta = f"{issue.proyecto} #{issue.numero}"
        self._etiquetar(issue, ETQ_TRABAJANDO, ETQ_FALLO)
        self._comentar(issue, f"Hermes no pudo con este issue: {texto}. No se subió nada.")
        if contar:
            self.estado.fallas_seguidas += 1
            self.estado.guardar()
        await notify(f"❌ Cola: {etiqueta}: {texto}")
        if self.estado.fallas_seguidas >= self.max_fallas:
            self.estado.pausar(f"{self.estado.fallas_seguidas} fallas seguidas. Revisa y usa /reanudar")
            await notify(f"⏸️ Cola en pausa: {self.estado.motivo}")
        return "fallo"

    def resumen(self) -> str:
        motivo = self.freno()
        lineas = ["📋 Cola de issues (etiqueta hermes:listo)", ""]
        lineas.append(motivo or "▶️ Activa")
        if self.estado.actual:
            lineas.append(f"🛠️ Trabajando en {self.estado.actual}")
        lineas.append(f"Hoy: {self.estado.hechos_hoy}/{self.tope_dia} · fallas seguidas: {self.estado.fallas_seguidas}/{self.max_fallas}")
        try:
            pend = self.pendientes()
        except Exception as e:
            pend = None
            lineas.append(f"⚪ No pude leer GitHub ({type(e).__name__})")
        if pend is not None:
            lineas.append("")
            lineas += [f"• {i.proyecto} #{i.numero} {i.titulo[:60]}" for i in pend[:10]] or ["Sin issues pendientes"]
        return "\n".join(lineas)


async def bucle_cola(cola: Cola, notify: Notify, pedir_aprobacion: PedirAprobacion, cada_s: Optional[float] = None,
                     veces: Optional[int] = None):
    cada_s = cada_s if cada_s is not None else _env_int("HERMES_COLA_CADA_MIN", 10) * 60
    n = 0
    while veces is None or n < veces:
        try:
            await cola.procesar_uno(notify, pedir_aprobacion)
        except Exception as e:
            cola.estado.pausar(f"error inesperado: {type(e).__name__}: {e}")
            try:
                await notify(f"⏸️ Cola en pausa: {cola.estado.motivo}")
            except Exception:
                pass
        n += 1
        if veces is None or n < veces:
            await asyncio.sleep(cada_s)

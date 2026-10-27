"""Issue #9: cola de issues. Hermes toma los issues con la etiqueta `hermes:listo` y los trabaja uno por uno.

Por cada issue:
1. Crea un worktree aparte (`HERMES_WORKTREES_DIR`/<proyecto>/issue-<n>) en la rama `feature/issue-<n>`, sacada de la
   rama base del proyecto. La carpeta de producción NUNCA se toca.
2. Le pasa el issue al agente (OpenCode o Claude Code) en ese worktree.
3. Corre las pruebas del proyecto (projects.yaml). Si pasan, hace un commit LOCAL.
4. Revisión automática: un segundo agente (HERMES_REVISOR) lee el diff con las reglas del repo y responde APROBADO o
   CAMBIOS. Si pide cambios, el agente los corrige una vez y se vuelve a revisar.
5. Sube la rama y abre el PR a la rama base (una rama feature/* es reversible).
6. Te pide que lo pruebes (con los pasos que dejó el agente). Con ✅ hace el merge del PR a la rama base (squash) y borra
   el worktree; con ❌ deja el PR abierto. Nunca toca `main`: pasar a producción sigue siendo tuyo (HERMES_MERGE=0 apaga
   el merge automático).

Si las pruebas fallan, el agente tiene HERMES_COLA_REINTENTOS (1) intento más con el error de las pruebas antes de frenar.

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
from bot.core.jobs import AGENTES, REVISORES, agente_configurado

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
            "Reglas:\n"
            "1. Empieza por el cambio: lee solo los archivos que el issue nombra y modifícalos primero.\n"
            "2. Agrega o ajusta la prueba del cambio y corre SOLO esa prueba y las del archivo que tocaste "
            "(ej. `node test_x.js` o `pytest tests/test_x.py`). NO corras la suite completa: Hermes la corre al final.\n"
            "3. Trabaja solo en esta carpeta. No hagas commit, push ni merge: Hermes se encarga y pide aprobación.\n\n"
            "Termina tu respuesta con una sección que empiece exactamente con «CÓMO PROBAR:» y, en máximo 5 pasos "
            "cortos, diga cómo comprobar a mano que funciona (comandos y qué se debe ver).")


def como_probar(salida: str) -> str:
    """La sección CÓMO PROBAR: que el agente deja al final de su respuesta."""
    i = (salida or "").rfind("CÓMO PROBAR:")
    if i < 0:
        return "• (el agente no dejó pasos; mira el PR)"
    return (salida[i + len("CÓMO PROBAR:"):].strip() or "• (vacío)")[:800]


@dataclasses.dataclass
class Revision:
    aprobado: Optional[bool]  # None = el revisor no dio un veredicto claro o no pudo correr
    texto: str


PROMPT_REVISOR = """REVISOR. Eres el revisor de código de este repo. NO cambies archivos.
Revisa este cambio para el issue #{numero} «{titulo}» contra:
- las reglas del repo (CLAUDE.md, AGENTS.md, REGLAS_ECOSISTEMA.md si existen),
- que el cambio resuelva el issue y nada más,
- que traiga pruebas del comportamiento nuevo,
- secretos, credenciales o datos personales en el código,
- cambios peligrosos (producción, borrar datos, puertos fijos repetidos).

La PRIMERA línea de tu respuesta debe ser exactamente APROBADO o CAMBIOS. Después, máximo 10 viñetas cortas.

Issue:
{cuerpo}

Diff:
{diff}"""


def interpretar_revision(salida: str) -> Revision:
    lineas = [l.strip() for l in (salida or "").strip().splitlines() if l.strip()]
    primera = lineas[0].strip("*#: ").upper() if lineas else ""
    resto = "\n".join(lineas[1:])[:1500]
    if primera.startswith("APROBADO"):
        return Revision(True, resto)
    if primera.startswith("CAMBIOS"):
        return Revision(False, resto)
    return Revision(None, "\n".join(lineas)[:1500] or "(sin respuesta)")


def revisor_por_agente(runner, agente: Optional[str] = None):
    """Revisor que usa un agente (claude -p / opencode run) en el worktree. HERMES_REVISOR elige cuál."""
    async def revisar(carpeta: str, issue: "Issue", diff: str) -> Revision:
        nombre = agente or os.environ.get("HERMES_REVISOR", "").strip().lower() or agente_configurado()
        if nombre not in AGENTES:
            nombre = agente_configurado()
        prompt = PROMPT_REVISOR.format(numero=issue.numero, titulo=issue.titulo, cuerpo=issue.cuerpo.strip()[:3000],
                                       diff=diff[:30000])
        code, out, err, vencido = await runner(REVISORES[nombre](prompt), carpeta, _env_int("HERMES_REVISOR_TIMEOUT_MIN", 15) * 60)
        if vencido or code != 0:
            return Revision(None, f"el revisor no pudo correr ({'tiempo vencido' if vencido else f'código {code}'})")
        return interpretar_revision(out)
    return revisar


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
                 hoy: Callable[[], str] = lambda: date.today().isoformat(), worktrees_dir: Optional[str] = None,
                 revisor="auto"):
        self.manager = manager
        if revisor == "auto":
            revisor = None if os.environ.get("HERMES_REVISOR", "") == "0" else revisor_por_agente(manager._runner)
        self.revisor = revisor
        self.registro_fn = registro_fn  # se relee projects.yaml en cada vuelta
        self.run = run
        self.estado = estado or EstadoCola()
        self.hoy = hoy
        self.worktrees_dir = os.path.expanduser(worktrees_dir or os.environ.get("HERMES_WORKTREES_DIR")
                                                or os.path.join(os.environ.get("HERMES_DATA_DIR", "~/.jarvis"), "worktrees"))
        self.max_fallas = _env_int("HERMES_COLA_MAX_FALLAS", 2)
        self.tope_dia = _env_int("HERMES_COLA_TOPE_DIA", 5)
        self.reintentos = _env_int("HERMES_COLA_REINTENTOS", 1)

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
        if proyecto.preparar:  # un worktree nuevo no trae node_modules ni dependencias
            import subprocess
            r = subprocess.run(proyecto.preparar, shell=True, cwd=destino, capture_output=True, text=True, timeout=900)
            if r.returncode != 0:
                raise RuntimeError(f"falló «{proyecto.preparar}»: {(r.stderr or r.stdout).strip()[-300:]}")
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

            # 1) Agente + pruebas, con reintento usando el error de las pruebas.
            prompt = prompt_para(issue)
            for intento in range(self.reintentos + 1):
                t, job_id = await self._trabajo(en_wt, prompt, notify)
                if t and t.estado == "ok":
                    break
                pruebas_fallaron = bool(t and t.pruebas in ("fallo", "timeout"))
                if pruebas_fallaron and intento < self.reintentos:
                    await notify(f"🔁 {etiqueta}: las pruebas fallaron; el agente lo intenta otra vez con el error")
                    prompt = (prompt_para(issue) + "\n\nEn el intento anterior las pruebas fallaron con esto. Corrígelo:\n"
                              + (t.error or "")[-2000:])
                    continue
                if pruebas_fallaron:
                    self.estado.pausar(f"las pruebas de {etiqueta} fallaron (trabajo #{job_id}). Revisa {carpeta} y usa /reanudar")
                    self._etiquetar(issue, ETQ_TRABAJANDO, ETQ_FALLO)
                    self._comentar(issue, f"Hermes: el agente terminó pero las pruebas fallaron (trabajo #{job_id}). No se subió nada.")
                    await notify(f"⏸️ Cola en pausa: {self.estado.motivo}")
                    return "pruebas fallaron"
                return await self._fallo(issue, notify, f"el agente no terminó bien (trabajo #{job_id}: {t.estado if t else '?'})", contar=True)

            # 2) Commit LOCAL (reversible). El push solo con aprobación.
            if not await self._commit(carpeta, f"feat: {issue.titulo} (#{issue.numero})"):
                return await self._fallo(issue, notify, "el agente no cambió ningún archivo", contar=True)

            # 3) Revisión automática; si pide cambios, una corrección y otra revisión.
            revision = await self._revisar(carpeta, issue, proyecto.rama_base)
            if revision and revision.aprobado is False:
                await notify(f"🧐 {etiqueta}: el revisor pidió cambios; el agente los corrige")
                t, job_id = await self._trabajo(en_wt, prompt_para(issue) + "\n\nEl revisor pidió estos cambios. Hazlos:\n" + revision.texto, notify)
                if t and t.estado == "ok":
                    await self._commit(carpeta, f"fix: ajustes de la revisión (#{issue.numero})")
                    revision = await self._revisar(carpeta, issue, proyecto.rama_base)
                else:
                    await asyncio.to_thread(self._cmd, ["git", "-C", carpeta, "checkout", "--", "."])
                    await asyncio.to_thread(self._cmd, ["git", "-C", carpeta, "clean", "-fdq"])
                    revision = Revision(False, revision.texto + "\n(la corrección falló; se dejó la versión anterior, con pruebas en verde)")

            code, stat, _ = await asyncio.to_thread(self._cmd, ["git", "-C", carpeta, "diff", "--stat", f"origin/{proyecto.rama_base}...HEAD"])
            self._etiquetar(issue, ETQ_TRABAJANDO, ETQ_ESPERANDO)
            self.estado.fallas_seguidas = 0
            self.estado.hechos_hoy += 1
            self.estado.guardar()

            resumen = stat.strip().splitlines()[-1] if code == 0 and stat.strip() else "sin resumen"

            # 4) Push de la rama y PR (una rama feature/* es reversible: no necesita permiso).
            try:
                await asyncio.to_thread(self._cmd_ok, ["git", "-C", carpeta, "push", "-u", "origin", rama], 300)
            except Exception as e:
                self.estado.pausar(f"no pude subir {etiqueta}: {e}")
                await notify(f"⏸️ Cola en pausa: {self.estado.motivo}")
                return "push falló"
            enlace = await asyncio.to_thread(self._abrir_pr, issue, proyecto.rama_base, rama, revision)
            self._comentar(issue, f"Hermes subió la rama `{rama}` con pruebas en verde: {enlace}")

            # 5) Johan prueba. Solo con su ✅ se hace el merge a la rama base (nunca a main).
            como = como_probar(getattr(t, "salida", "") or "")
            ok = await pedir_aprobacion(
                f"🧪 {etiqueta} listo para que lo pruebes.\n«{issue.titulo}»\nPR: {enlace}\nCambios: {resumen}\n"
                f"{self._texto_revision(revision)}\n\nCómo probarlo (en {carpeta}):\n{como}\n\n"
                f"¿Funciona? Con ✅ hago el merge a {proyecto.rama_base}.")
            if not ok:
                self._etiquetar(issue, ETQ_ESPERANDO, ETQ_RECHAZADO)
                self._comentar(issue, "Johan lo probó y no funciona todavía. El PR queda abierto.")
                await notify(f"🔧 {etiqueta}: el PR queda abierto ({enlace}). Dime qué falla con /pedir {issue.proyecto} <qué falla en #{issue.numero}>")
                return "no funciona"
            if os.environ.get("HERMES_MERGE", "1") == "0":
                self._etiquetar(issue, ETQ_ESPERANDO, ETQ_HECHO)
                await notify(f"👍 {etiqueta}: aprobado. El merge lo haces tú: {enlace}")
                return "aprobado"
            code, _, err = await asyncio.to_thread(self._cmd, ["gh", "pr", "merge", rama, "--repo", issue.repo, "--squash", "--delete-branch"], 120)
            if code != 0:
                await notify(f"⚠️ {etiqueta}: no pude hacer el merge ({(err or '').strip()[:200]}). Hazlo tú: {enlace}")
                return "merge falló"
            self._etiquetar(issue, ETQ_ESPERANDO, ETQ_HECHO)
            await asyncio.to_thread(self._cmd, ["git", "-C", proyecto.carpeta, "worktree", "remove", "--force", carpeta], 60)
            await notify(f"✅ {etiqueta}: merge a {proyecto.rama_base} hecho y worktree borrado. 🎉")
            return "integrado"
        finally:
            self.estado.actual = ""

    async def _trabajo(self, en_wt, prompt: str, notify: Notify):
        job_id = self.manager.iniciar(en_wt, prompt, notify)
        await self.manager.esperar(job_id)
        return self.manager.store.obtener(job_id), job_id

    async def _commit(self, carpeta: str, mensaje: str) -> bool:
        await asyncio.to_thread(self._cmd_ok, ["git", "-C", carpeta, "add", "-A"])
        code, cambios, _ = await asyncio.to_thread(self._cmd, ["git", "-C", carpeta, "status", "--porcelain"])
        if code == 0 and not cambios.strip():
            return False
        await asyncio.to_thread(self._cmd_ok, ["git", "-C", carpeta, "commit", "-q", "-m", mensaje])
        return True

    async def _revisar(self, carpeta: str, issue: Issue, rama_base: str) -> Optional[Revision]:
        if not self.revisor:
            return None
        try:
            code, diff, _ = await asyncio.to_thread(self._cmd, ["git", "-C", carpeta, "diff", f"origin/{rama_base}...HEAD"])
            return await self.revisor(carpeta, issue, diff if code == 0 else "")
        except Exception as e:
            return Revision(None, f"el revisor falló ({type(e).__name__})")

    @staticmethod
    def _texto_revision(r: Optional[Revision]) -> str:
        if r is None:
            return "Revisión automática: apagada"
        cabeza = {True: "✅ Revisión: APROBADO", False: "⚠️ Revisión: pide CAMBIOS", None: "⚪ Revisión: sin veredicto"}[r.aprobado]
        return cabeza + (f"\n{r.texto[:800]}" if r.texto else "")

    def _abrir_pr(self, issue: Issue, base: str, rama: str, revision: Optional[Revision]) -> str:
        """Abre el PR (sin merge). Si gh no puede, devuelve el enlace para abrirlo a mano."""
        cuerpo = (f"Closes #{issue.numero}\n\nHecho por Hermes con pruebas en verde.\n\n{self._texto_revision(revision)}\n\n"
                  "Revisar y hacer merge a mano.")
        code, out, _ = self._cmd(["gh", "pr", "create", "--repo", issue.repo, "--base", base, "--head", rama,
                                  "--title", f"{issue.titulo} (#{issue.numero})", "--body", cuerpo], 60)
        url = (out or "").strip().splitlines()[-1] if code == 0 and (out or "").strip() else ""
        return url or f"https://github.com/{issue.repo}/compare/{base}...{rama}?expand=1"

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

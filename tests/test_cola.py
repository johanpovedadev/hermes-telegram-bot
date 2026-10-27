"""Issue #9: la cola trabaja en un worktree, pide aprobación antes del push y se frena sola. Git real; GitHub y agente simulados."""
import asyncio
import json
import os
import subprocess

import pytest

from bot.core import cola as cl
from bot.core.estado import run_cmd
from bot.core.jobs import JobManager, JobStore
from bot.core.projects import Proyecto, Registro


def git(*a, cwd=None):
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def mundo(tmp_path, monkeypatch):
    for k in ["HERMES_COLA_MAX_FALLAS", "HERMES_COLA_TOPE_DIA", "HERMES_WORKTREES_DIR"]:
        monkeypatch.delenv(k, raising=False)
    for k, v in {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}.items():
        monkeypatch.setenv(k, v)
    origen = tmp_path / "origen.git"
    git("init", "-q", "--bare", "-b", "develop", str(origen))
    carpeta = tmp_path / "proyecto"
    git("clone", "-q", str(origen), str(carpeta))
    git("checkout", "-q", "-b", "develop", cwd=carpeta)
    (carpeta / "app.py").write_text("x = 1\n")
    git("add", ".", cwd=carpeta)
    git("commit", "-q", "-m", "inicio", cwd=carpeta)
    git("push", "-q", "origin", "develop", cwd=carpeta)

    p = Proyecto(nombre="demo", repo="johan/demo", carpeta=str(carpeta), pruebas="pruebas-demo", habilitado=True)
    otro = Proyecto(nombre="prod", repo="johan/prod", carpeta=str(carpeta), pruebas="x", habilitado=False)
    registro = Registro([p, otro], [], [])

    class GH:
        def __init__(self):
            self.issues = {("johan/demo", 7): {"title": "Agregar saludo", "body": "Que diga hola", "labels": {"hermes:listo"}}}
            self.llamadas = []
            self.comentarios = []
            self.prs = []
            self.pr_falla = False
            self.merges = []
            self.merge_falla = False

        def __call__(self, argv, timeout):
            if argv[0] != "gh":
                return run_cmd(argv, timeout)
            self.llamadas.append(argv)
            repo = argv[argv.index("--repo") + 1]
            if argv[1:3] == ["pr", "merge"]:
                self.merges.append(argv)
                return (1, "", "base branch policy prohibits the merge") if self.merge_falla else (0, "", "")
            if argv[1:3] == ["pr", "create"]:
                self.prs.append(argv)
                if self.pr_falla:
                    return 1, "", "GraphQL: no permitido"
                return 0, f"https://github.com/{repo}/pull/{len(self.prs)}\n", ""
            if argv[1:3] == ["issue", "list"]:
                assert repo != "johan/prod", "nunca mira proyectos deshabilitados"
                lista = [{"number": n, "title": d["title"], "body": d["body"]} for (r, n), d in self.issues.items()
                         if r == repo and "hermes:listo" in d["labels"]]
                return 0, json.dumps(lista), ""
            n = int(argv[3])
            if argv[1:3] == ["issue", "edit"]:
                labels = self.issues[(repo, n)]["labels"]
                if "--remove-label" in argv:
                    labels.discard(argv[argv.index("--remove-label") + 1])
                if "--add-label" in argv:
                    labels.add(argv[argv.index("--add-label") + 1])
                return 0, "", ""
            if argv[1:3] == ["issue", "comment"]:
                self.comentarios.append((n, argv[-1]))
                return 0, "", ""
            return 1, "", "no simulado"

    class Agente:
        def __init__(self):
            self.codigo, self.pruebas, self.escribe = 0, 0, True
            self.cwds = []
            self.prompts = []
            self.veredictos = ["APROBADO\n- todo bien"]
            self.revisiones = []
            self.pruebas_seq = None  # lista de códigos de prueba por intento
            self.nuevo_archivo = False  # cada llamada crea además un archivo nuevo

        async def __call__(self, argv, cwd, timeout, shell=False):
            if shell:
                code = self.pruebas_seq.pop(0) if self.pruebas_seq else self.pruebas
                return code, "", "AssertionError: 1 != 2" if code else "", False
            if argv[-1].startswith("REVISOR"):
                self.revisiones.append(argv[-1])
                v = self.veredictos.pop(0) if len(self.veredictos) > 1 else self.veredictos[0]
                return (1, "", "caído", False) if v == "ERROR" else (0, v, "", False)
            self.cwds.append(cwd)
            self.prompts.append(argv[-1])
            if self.escribe:
                with open(os.path.join(cwd, "saludo.py"), "a") as f:
                    f.write("print('hola')\n")
                if self.nuevo_archivo:
                    with open(os.path.join(cwd, f"paso{len(self.prompts)}.py"), "w") as f:
                        f.write("x = 1\n")
            return self.codigo, "listo\n\nCÓMO PROBAR:\n1. node index.js y abre el puerto 3000", "", False

    gh, agente = GH(), Agente()
    manager = JobManager(store=JobStore(str(tmp_path / "jobs.db")), runner=agente)
    estado = cl.EstadoCola(str(tmp_path / "cola.json"))
    c = cl.Cola(manager, lambda: registro, run=gh, estado=estado, hoy=lambda: "2026-10-17", worktrees_dir=str(tmp_path / "wt"))
    avisos = []

    async def notify(t):
        avisos.append(t)

    return dict(cola=c, gh=gh, agente=agente, origen=origen, carpeta=carpeta, avisos=avisos, notify=notify, tmp=tmp_path)


def si(respuesta, preguntas=None):
    async def pedir(texto):
        if preguntas is not None:
            preguntas.append(texto)
        return respuesta
    return pedir


def labels(m, n=7):
    return m["gh"].issues[("johan/demo", n)]["labels"]


def ramas_remotas(m):
    return git("branch", "--list", cwd=m["origen"])


def test_camino_feliz_worktree_aprobacion_y_push(mundo):
    m = mundo
    preguntas = []
    r = asyncio.run(m["cola"].procesar_uno(m["notify"], si(True, preguntas)))
    assert r == "integrado"
    wt = m["tmp"] / "wt" / "demo" / "issue-7"
    assert m["agente"].cwds and set(m["agente"].cwds) == {str(wt)}, "el agente trabaja en el worktree, nunca en la carpeta del proyecto"
    assert not (m["carpeta"] / "saludo.py").exists()
    assert git("rev-parse", "--abbrev-ref", "HEAD", cwd=m["carpeta"]).strip() == "develop"
    assert "feature/issue-7" in ramas_remotas(m)
    assert git("log", "-1", "--format=%s", "feature/issue-7", cwd=m["origen"]).strip() == "feat: Agregar saludo (#7)"
    assert "develop" in ramas_remotas(m) and git("log", "--oneline", "develop", cwd=m["origen"]).count("\n") == 1, "develop no se toca"
    assert labels(m) == {"hermes:hecho"}
    assert "¿Funciona?" in preguntas[0] and "1 file changed" in preguntas[0] and "pull/1" in preguntas[0]
    assert "abre el puerto" in preguntas[0], "los pasos de CÓMO PROBAR del agente llegan a Johan"
    mg = m["gh"].merges[0]
    assert mg[3] == "feature/issue-7" and "--squash" in mg and "--delete-branch" in mg
    assert not wt.exists(), "tras el merge se borra el worktree"
    assert "✅ Revisión: APROBADO" in preguntas[0]
    pr = m["gh"].prs[0]
    assert pr[pr.index("--base") + 1] == "develop" and pr[pr.index("--head") + 1] == "feature/issue-7"
    assert "Closes #7" in pr[pr.index("--body") + 1]
    assert any("merge a develop hecho" in a for a in m["avisos"])
    assert m["cola"].estado.hechos_hoy == 1


def test_no_funciona_deja_el_pr_abierto_sin_merge(mundo):
    m = mundo
    assert asyncio.run(m["cola"].procesar_uno(m["notify"], si(False))) == "no funciona"
    assert "feature/issue-7" in ramas_remotas(m), "la rama sí se sube para poder probarla"
    assert m["gh"].prs and m["gh"].merges == [], "sin el ✅ de Johan no hay merge"
    assert labels(m) == {"hermes:rechazado"}
    assert (m["tmp"] / "wt" / "demo" / "issue-7").exists(), "el worktree queda para corregir"
    assert any("/pedir demo" in a for a in m["avisos"])


def test_merge_que_falla_avisa_con_el_enlace(mundo):
    m = mundo
    m["gh"].merge_falla = True
    assert asyncio.run(m["cola"].procesar_uno(m["notify"], si(True))) == "merge falló"
    assert any("policy prohibits" in a and "pull/1" in a for a in m["avisos"])


def test_merge_apagado(mundo, monkeypatch):
    m = mundo
    monkeypatch.setenv("HERMES_MERGE", "0")
    assert asyncio.run(m["cola"].procesar_uno(m["notify"], si(True))) == "aprobado"
    assert m["gh"].merges == [] and labels(m) == {"hermes:hecho"}


def test_nunca_hace_merge_a_main(mundo):
    m = mundo
    asyncio.run(m["cola"].procesar_uno(m["notify"], si(True)))
    pr = m["gh"].prs[0]
    assert pr[pr.index("--base") + 1] == "develop"


@pytest.mark.parametrize("salida,esperado", [
    ("hice X\n\nCÓMO PROBAR:\n1. corre npm test", "1. corre npm test"), ("sin pasos", "• (el agente no dejó pasos; mira el PR)")])
def test_como_probar(salida, esperado):
    assert cl.como_probar(salida) == esperado


def test_pruebas_que_fallan_pausan_la_cola_sin_preguntar_ni_subir(mundo):
    m = mundo
    m["agente"].pruebas = 1  # falla también en el reintento
    preguntas = []
    assert asyncio.run(m["cola"].procesar_uno(m["notify"], si(True, preguntas))) == "pruebas fallaron"
    assert preguntas == [] and "feature/issue-7" not in ramas_remotas(m)
    assert m["cola"].estado.pausada and labels(m) == {"hermes:fallo"}
    assert m["gh"].comentarios and "No se subió nada" in m["gh"].comentarios[0][1]
    assert asyncio.run(m["cola"].procesar_uno(m["notify"], si(True))).startswith("⏸️")
    estado2 = cl.EstadoCola(m["cola"].estado.ruta)
    assert estado2.pausada, "la pausa sobrevive un reinicio del bot"


def test_dos_fallas_seguidas_pausan(mundo):
    m = mundo
    m["gh"].issues[("johan/demo", 8)] = {"title": "Otro", "body": "", "labels": {"hermes:listo"}}
    m["gh"].issues[("johan/demo", 9)] = {"title": "Tercero", "body": "", "labels": {"hermes:listo"}}
    m["agente"].codigo = 1
    asyncio.run(m["cola"].procesar_uno(m["notify"], si(True)))
    assert not m["cola"].estado.pausada and m["cola"].estado.fallas_seguidas == 1
    asyncio.run(m["cola"].procesar_uno(m["notify"], si(True)))
    assert m["cola"].estado.pausada and "2 fallas seguidas" in m["cola"].estado.motivo
    assert labels(m, 9) == {"hermes:listo"}, "el tercero no se toca"
    m["cola"].estado.reanudar()
    assert m["cola"].estado.fallas_seguidas == 0


def test_un_exito_reinicia_las_fallas(mundo):
    m = mundo
    m["gh"].issues[("johan/demo", 8)] = {"title": "Otro", "body": "", "labels": {"hermes:listo"}}
    m["agente"].codigo = 1
    asyncio.run(m["cola"].procesar_uno(m["notify"], si(True)))
    m["agente"].codigo = 0
    assert asyncio.run(m["cola"].procesar_uno(m["notify"], si(True))) == "integrado"
    assert m["cola"].estado.fallas_seguidas == 0


def test_agente_sin_cambios_es_falla(mundo):
    m = mundo
    m["agente"].escribe = False
    preguntas = []
    assert asyncio.run(m["cola"].procesar_uno(m["notify"], si(True, preguntas))) == "fallo"
    assert preguntas == [] and labels(m) == {"hermes:fallo"}


def test_tope_diario(mundo, monkeypatch):
    m = mundo
    m["cola"].tope_dia = 1
    m["gh"].issues[("johan/demo", 8)] = {"title": "Otro", "body": "", "labels": {"hermes:listo"}}
    assert asyncio.run(m["cola"].procesar_uno(m["notify"], si(True))) == "integrado"
    assert asyncio.run(m["cola"].procesar_uno(m["notify"], si(True))).startswith("🛑 Tope diario")
    m["cola"].hoy = lambda: "2026-10-18"
    assert asyncio.run(m["cola"].procesar_uno(m["notify"], si(True))) == "integrado", "al otro día sigue"


def test_worktree_ya_existe_no_pisa_nada(mundo):
    m = mundo
    wt = m["tmp"] / "wt" / "demo" / "issue-7"
    wt.mkdir(parents=True)
    (wt / "importante.txt").write_text("no borrar")
    assert asyncio.run(m["cola"].procesar_uno(m["notify"], si(True))) == "fallo"
    assert (wt / "importante.txt").read_text() == "no borrar"
    assert any("ya existe" in a for a in m["avisos"])


def test_sin_issues_y_pausa_manual(mundo):
    m = mundo
    m["gh"].issues.clear()
    assert asyncio.run(m["cola"].procesar_uno(m["notify"], si(True))) == "💤 No hay issues con hermes:listo"
    m["cola"].estado.pausar("pausada a mano con /pausar")
    assert "pausada a mano" in m["cola"].resumen()


def test_resumen_lista_pendientes(mundo):
    texto = mundo["cola"].resumen()
    assert "▶️ Activa" in texto and "demo #7 Agregar saludo" in texto and "Hoy: 0/5" in texto


def test_bucle_pausa_ante_error_inesperado(mundo):
    m = mundo

    async def explota(notify, pedir):
        raise RuntimeError("bum")

    m["cola"].procesar_uno = explota
    asyncio.run(cl.bucle_cola(m["cola"], m["notify"], si(True), cada_s=0, veces=1))
    assert m["cola"].estado.pausada and "bum" in m["cola"].estado.motivo


def test_botones_de_aprobacion():
    from bot.handlers import cola as hc

    class Bot:
        def __init__(self):
            self.markup = None

        async def send_message(self, chat_id, text, reply_markup=None):
            self.markup = reply_markup

    class Msg:
        text = "¿Lo subo?"

    class Query:
        def __init__(self, data):
            self.data, self.message, self.editado, self.respuesta = data, Msg(), None, None

        async def answer(self, *a, **k):
            self.respuesta = (a, k)

        async def edit_message_text(self, t):
            self.editado = t

    class Upd:
        def __init__(self, q):
            self.callback_query = q

    async def caso():
        bot = Bot()
        tarea = asyncio.create_task(hc.crear_pedir_aprobacion(bot, 1)("¿Lo subo?"))
        await asyncio.sleep(0)
        data = bot.markup.inline_keyboard[0][0].callback_data
        assert data.startswith("cola:si:")
        q = Query(data)
        await hc.responder_aprobacion(Upd(q), None)
        assert await tarea is True and q.editado.endswith("Haciendo el merge…")
        viejo = Query(data)
        await hc.responder_aprobacion(Upd(viejo), None)
        assert viejo.respuesta[1].get("show_alert"), "un botón viejo no hace nada"

        tarea = asyncio.create_task(hc.crear_pedir_aprobacion(bot, 1)("¿Lo subo?"))
        await asyncio.sleep(0)
        await hc.responder_aprobacion(Upd(Query(bot.markup.inline_keyboard[0][1].callback_data)), None)
        assert await tarea is False

    asyncio.run(caso())


def test_reintento_con_el_error_de_las_pruebas(mundo):
    m = mundo
    m["agente"].pruebas_seq = [1, 0]
    assert asyncio.run(m["cola"].procesar_uno(m["notify"], si(True))) == "integrado"
    assert len(m["agente"].prompts) == 2 and "AssertionError: 1 != 2" in m["agente"].prompts[1]
    assert any(a.startswith("🔁") for a in m["avisos"])


def test_sin_reintentos_pausa_al_primer_fallo(mundo):
    m = mundo
    m["cola"].reintentos = 0
    m["agente"].pruebas_seq = [1, 0]
    assert asyncio.run(m["cola"].procesar_uno(m["notify"], si(True))) == "pruebas fallaron"
    assert len(m["agente"].prompts) == 1


def test_revisor_pide_cambios_y_se_corrigen(mundo):
    m = mundo
    m["agente"].veredictos = ["CAMBIOS\n- falta la prueba del saludo", "APROBADO\n- listo"]
    preguntas = []
    assert asyncio.run(m["cola"].procesar_uno(m["notify"], si(True, preguntas))) == "integrado"
    assert len(m["agente"].revisiones) == 2 and "saludo.py" in m["agente"].revisiones[0], "el revisor ve el diff"
    assert "falta la prueba del saludo" in m["agente"].prompts[1]
    assert "✅ Revisión: APROBADO" in preguntas[0]
    log = git("log", "--format=%s", "develop..feature/issue-7", cwd=m["origen"])
    assert log.splitlines() == ["fix: ajustes de la revisión (#7)", "feat: Agregar saludo (#7)"]


def test_revisor_insiste_igual_se_pregunta_con_la_advertencia(mundo):
    m = mundo
    m["agente"].veredictos = ["CAMBIOS\n- usa un puerto fijo repetido"]
    preguntas = []
    asyncio.run(m["cola"].procesar_uno(m["notify"], si(False, preguntas)))
    assert "⚠️ Revisión: pide CAMBIOS" in preguntas[0] and "puerto fijo" in preguntas[0]
    assert len(m["agente"].revisiones) == 2, "una sola ronda de corrección, no un bucle"


def test_correccion_que_rompe_pruebas_se_descarta(mundo):
    m = mundo
    m["agente"].veredictos = ["CAMBIOS\n- renombra"]
    m["agente"].pruebas_seq = [0, 1]
    m["agente"].nuevo_archivo = True
    preguntas = []
    asyncio.run(m["cola"].procesar_uno(m["notify"], si(False, preguntas)))
    wt = m["tmp"] / "wt" / "demo" / "issue-7"
    assert git("status", "--porcelain", cwd=wt).strip() == "", "no quedan cambios rotos sin commit"
    assert git("log", "--format=%s", "origin/develop..HEAD", cwd=wt).splitlines() == ["feat: Agregar saludo (#7)"]
    assert "la corrección falló" in preguntas[0]


def test_revisor_caido_no_frena(mundo):
    m = mundo
    m["agente"].veredictos = ["ERROR"]
    preguntas = []
    assert asyncio.run(m["cola"].procesar_uno(m["notify"], si(True, preguntas))) == "integrado"
    assert "⚪ Revisión: sin veredicto" in preguntas[0] and "no pudo correr" in preguntas[0]


def test_revisor_apagado(mundo, monkeypatch):
    m = mundo
    monkeypatch.setenv("HERMES_REVISOR", "0")
    c = cl.Cola(m["cola"].manager, m["cola"].registro_fn, run=m["gh"], estado=m["cola"].estado,
                hoy=m["cola"].hoy, worktrees_dir=m["cola"].worktrees_dir)
    preguntas = []
    asyncio.run(c.procesar_uno(m["notify"], si(True, preguntas)))
    assert m["agente"].revisiones == [] and "Revisión automática: apagada" in preguntas[0]


def test_si_gh_no_abre_el_pr_queda_el_enlace(mundo):
    m = mundo
    m["gh"].pr_falla = True
    preguntas = []
    asyncio.run(m["cola"].procesar_uno(m["notify"], si(True, preguntas)))
    assert "compare/develop...feature/issue-7?expand=1" in preguntas[0]


@pytest.mark.parametrize("salida,esperado", [
    ("APROBADO\n- ok", True), ("**APROBADO**", True), ("CAMBIOS:\n- x", False), ("no sé", None), ("", None)])
def test_interpretar_revision(salida, esperado):
    assert cl.interpretar_revision(salida).aprobado is esperado


def test_preparar_corre_en_el_worktree_antes_del_agente(mundo):
    m = mundo
    p = m["cola"].registro_fn().obtener("demo")
    p.preparar = "python -c \"open('preparado.txt','w').write('ok')\""
    assert asyncio.run(m["cola"].procesar_uno(m["notify"], si(False))) == "no funciona"
    assert (m["tmp"] / "wt" / "demo" / "issue-7" / "preparado.txt").exists()
    assert not (m["carpeta"] / "preparado.txt").exists()


def test_preparar_que_falla_es_falla(mundo):
    m = mundo
    m["cola"].registro_fn().obtener("demo").preparar = "python -c \"import sys; sys.exit('sin red')\""
    assert asyncio.run(m["cola"].procesar_uno(m["notify"], si(True))) == "fallo"
    assert m["agente"].prompts == [] and any("sin red" in a for a in m["avisos"])


def test_pedir_crea_issue_con_etiqueta():
    from bot.handlers import cola as hc
    llamadas = []

    def run(argv, timeout):
        llamadas.append(argv)
        return 0, "Creating issue\nhttps://github.com/johan/demo/issues/50\n", ""

    p = Proyecto(nombre="demo", repo="johan/demo", carpeta="/x", pruebas="t", habilitado=True)
    url = hc.crear_issue(p, "que la heladería salude por el nombre. Y que sea corto", run=run)
    assert url == "https://github.com/johan/demo/issues/50"
    a = llamadas[0]
    assert a[a.index("--label") + 1] == "hermes:listo" and a[a.index("--repo") + 1] == "johan/demo"
    assert a[a.index("--title") + 1] == "Que la heladería salude por el nombre"


def test_pedir_falla_con_mensaje():
    from bot.handlers import cola as hc
    p = Proyecto(nombre="demo", repo="johan/demo", carpeta="/x", pruebas="t", habilitado=True)
    with pytest.raises(RuntimeError, match="not found"):
        hc.crear_issue(p, "algo", run=lambda a, t: (1, "", "could not add label: 'hermes:listo' not found"))


@pytest.mark.parametrize("pedido,titulo", [("x" * 100, "X" + "x" * 69), ("", "Pedido desde Telegram"), ("arregla el\nlogin", "Arregla el")])
def test_titulo_de(pedido, titulo):
    from bot.handlers import cola as hc
    assert hc.titulo_de(pedido) == titulo



def test_el_prompt_pide_cambio_primero_y_no_la_suite_completa():
    issue = cl.Issue("demo", "johan/demo", 7, "Agregar saludo", "Que diga hola")
    p = cl.prompt_para(issue)
    assert "NO corras la suite completa" in p and "Empieza por el cambio" in p and "CÓMO PROBAR:" in p

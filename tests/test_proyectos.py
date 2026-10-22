"""Issue #8: registro de proyectos (projects.yaml)."""
import pathlib

import pytest

from bot.core import projects

REPO = pathlib.Path(__file__).resolve().parents[1]


def _yaml(tmp_path, texto):
    f = tmp_path / "projects.yaml"
    f.write_text(texto, encoding="utf-8")
    return str(f)


def test_el_projects_yaml_del_repo_es_valido(tmp_path):
    # Las carpetas no existen en CI: para los deshabilitados es aviso; para los habilitados se crean aquí.
    reg = projects.cargar(str(REPO / "projects.yaml"), str(tmp_path))
    habilitados = [p for p in reg.proyectos if p.habilitado]
    for p in habilitados:
        pathlib.Path(p.carpeta).mkdir(parents=True, exist_ok=True)
    reg = projects.cargar(str(REPO / "projects.yaml"), str(tmp_path))
    assert reg.valido, reg.errores
    nombres = {p.nombre for p in reg.proyectos}
    assert {"saas-bot", "lion-platform-api", "agentvents", "hermes"} <= nombres
    assert all(p.pruebas for p in reg.proyectos)
    saas = reg.obtener("saas-bot")
    assert saas.solo_cola and saas.preparar, "producción solo por la cola, en worktree con dependencias instaladas"
    assert reg.para_trabajar("saas-bot")[0] is None, "/run nunca corre en la carpeta de producción"
    assert not reg.obtener("hermes").habilitado, "Hermes no se modifica a sí mismo mientras corre"


def test_validacion_con_mensajes_claros(tmp_path):
    (tmp_path / "a").mkdir()
    ruta = _yaml(tmp_path, """
proyectos:
  - nombre: a
    carpeta: a
    pruebas: ""
    puertos: [3000]
    habilitado: true
  - nombre: b
    carpeta: no-existe
    pruebas: npm test
    puertos: [3000, 70000]
    habilitado: true
  - nombre: A
    carpeta: a
    pruebas: x
  - carpeta: a
""")
    reg = projects.cargar(ruta, str(tmp_path))
    e = "\n".join(reg.errores)
    assert "a: falta el comando de 'pruebas'" in e
    assert "b: la carpeta no existe" in e
    assert "puerto 3000 repetido: a y b" in e
    assert "b: puerto inválido 70000" in e
    assert "A: nombre repetido" in e
    assert "proyecto #4: falta 'nombre'" in e
    assert not reg.valido


def test_carpeta_faltante_de_un_deshabilitado_es_solo_aviso(tmp_path):
    reg = projects.cargar(_yaml(tmp_path, "proyectos:\n  - nombre: x\n    carpeta: nada\n    pruebas: t\n"), str(tmp_path))
    assert reg.valido and reg.avisos and "x: la carpeta no existe" in reg.avisos[0]


@pytest.mark.parametrize("contenido,error", [
    (None, "No existe"),
    ("proyectos: [", "no es YAML válido"),
    ("otra_cosa: 1", "lista 'proyectos:'"),
])
def test_archivo_ausente_o_roto(tmp_path, contenido, error):
    ruta = str(tmp_path / "projects.yaml") if contenido is None else _yaml(tmp_path, contenido)
    reg = projects.cargar(ruta, str(tmp_path))
    assert not reg.valido and error in reg.errores[0]


def test_para_trabajar(tmp_path):
    (tmp_path / "si").mkdir()
    reg = projects.cargar(_yaml(tmp_path, """
proyectos:
  - {nombre: si, carpeta: si, pruebas: t, habilitado: true}
  - {nombre: prod, carpeta: si, pruebas: t, habilitado: false, nota: produccion}
"""), str(tmp_path))
    p, motivo = reg.para_trabajar("SI")
    assert p and p.nombre == "si" and motivo is None and p.carpeta == str(tmp_path / "si")
    p, motivo = reg.para_trabajar("prod")
    assert p is None and "deshabilitado" in motivo and "produccion" in motivo
    p, motivo = reg.para_trabajar("otro")
    assert p is None and "no está en projects.yaml" in motivo and "si" in motivo


def test_carpeta_absoluta_se_respeta(tmp_path):
    abs_dir = tmp_path / "abs"
    abs_dir.mkdir()
    reg = projects.cargar(_yaml(tmp_path, f"proyectos:\n  - nombre: z\n    carpeta: '{abs_dir}'\n    pruebas: t\n    habilitado: true\n"), "/otra/parte")
    assert reg.obtener("z").carpeta == str(abs_dir)


@pytest.mark.asyncio
async def test_comando_proyectos_lista_desde_el_archivo(mock_update, mock_context, monkeypatch, tmp_path):
    (tmp_path / "si").mkdir()
    ruta = _yaml(tmp_path, "proyectos:\n  - {nombre: si, repo: o/si, carpeta: si, pruebas: t, habilitado: true}\n  - {nombre: viejo, carpeta: nada, pruebas: t}\n")
    real = projects.cargar
    monkeypatch.setattr("bot.handlers.commands.projects.cargar", lambda *a, **k: real(ruta, str(tmp_path)))
    from bot.handlers.commands import listar_proyectos
    await listar_proyectos(mock_update, mock_context)
    texto = mock_update.message.reply_text.call_args[0][0]
    assert "✅ `si` — o/si" in texto and "⛔ `viejo`" in texto


@pytest.mark.asyncio
async def test_run_rechaza_deshabilitado(mock_update, mock_context, monkeypatch, tmp_path):
    (tmp_path / "prod").mkdir()
    ruta = _yaml(tmp_path, "proyectos:\n  - {nombre: prod, carpeta: prod, pruebas: t, habilitado: false}\n")
    real = projects.cargar
    monkeypatch.setattr("bot.handlers.run.projects.cargar", lambda *a, **k: real(ruta, str(tmp_path)))
    from unittest.mock import AsyncMock, patch
    from bot.handlers.run import ejecutar_issue
    mock_context.args = ["prod", "borra todo"]
    with patch("bot.handlers.run.get_manager") as manager:
        await ejecutar_issue(mock_update, mock_context)
    manager.assert_not_called()
    assert "deshabilitado" in mock_update.message.reply_text.call_args[0][0]


def test_nombre_que_yaml_lee_como_si_no(tmp_path):
    reg = projects.cargar(_yaml(tmp_path, "proyectos:\n  - {nombre: no, carpeta: x, pruebas: t}\n"), str(tmp_path))
    assert not reg.valido and "entre comillas" in reg.errores[0]


def test_solo_cola_bloquea_run(tmp_path):
    (tmp_path / "prod").mkdir()
    f = tmp_path / "p.yaml"
    f.write_text("proyectos:\n  - nombre: saas-bot\n    repo: a/b\n    carpeta: prod\n    pruebas: npm test\n"
                 "    habilitado: true\n    solo_cola: true\n    preparar: npm ci\n")
    reg = projects.cargar(str(f), str(tmp_path))
    p = reg.obtener("saas-bot")
    assert p.solo_cola and p.preparar == "npm ci"
    info, motivo = reg.para_trabajar("saas-bot")
    assert info is None and "solo para la cola" in motivo

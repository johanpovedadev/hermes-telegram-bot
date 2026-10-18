"""Issue #8: registro de proyectos (projects.yaml). Hermes solo trabaja en lo que está aquí.

Cada proyecto: nombre, repo de GitHub, carpeta en el PC, rama base, comando de pruebas, apps de PM2 y puertos que le
pertenecen, y si Hermes puede trabajar en él. Sin secretos: el archivo va versionado.

Ubicación: HERMES_PROJECTS_FILE o, por defecto, projects.yaml en la raíz del repo. Una carpeta relativa se resuelve
contra HERMES_DOCUMENTS_PATH (~/Documents).
"""
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import yaml

from bot.core.config import BASE_DIR, DOCUMENTS_PATH


@dataclass
class Proyecto:
    nombre: str
    repo: str
    carpeta: str
    pruebas: str
    rama_base: str = "develop"
    pm2: List[str] = field(default_factory=list)
    puertos: List[int] = field(default_factory=list)
    habilitado: bool = False
    nota: str = ""


def ruta_por_defecto() -> str:
    return os.environ.get("HERMES_PROJECTS_FILE") or os.path.join(BASE_DIR, "projects.yaml")


def _resolver_carpeta(carpeta: str, documentos: str) -> str:
    c = os.path.expanduser(str(carpeta or "").strip())
    if not c:
        return ""
    return c if os.path.isabs(c) else os.path.join(documentos, c)


class Registro:
    def __init__(self, proyectos: List[Proyecto], errores: List[str], avisos: List[str]):
        self.proyectos = proyectos
        self.errores = errores
        self.avisos = avisos
        self._por_nombre: Dict[str, Proyecto] = {p.nombre.lower(): p for p in proyectos}

    @property
    def valido(self) -> bool:
        return not self.errores

    def obtener(self, nombre: str) -> Optional[Proyecto]:
        return self._por_nombre.get(str(nombre or "").strip().lower())

    def para_trabajar(self, nombre: str) -> Tuple[Optional[Proyecto], Optional[str]]:
        """(proyecto, None) si Hermes puede trabajar en él; (None, motivo) si no."""
        p = self.obtener(nombre)
        if not p:
            disponibles = ", ".join(x.nombre for x in self.proyectos if x.habilitado) or "ninguno"
            return None, f"❌ `{nombre}` no está en projects.yaml. Habilitados: {disponibles}"
        if not p.habilitado:
            return None, f"⛔ `{p.nombre}` está deshabilitado para Hermes en projects.yaml{f' ({p.nota})' if p.nota else ''}."
        if not os.path.isdir(p.carpeta):
            return None, f"❌ La carpeta de `{p.nombre}` no existe: {p.carpeta}"
        return p, None


def cargar(ruta: Optional[str] = None, documentos: Optional[str] = None) -> Registro:
    """Lee y valida el archivo. Nunca lanza: los problemas quedan en registro.errores (bloquean) o .avisos."""
    ruta = ruta or ruta_por_defecto()
    documentos = documentos or DOCUMENTS_PATH
    errores: List[str] = []
    avisos: List[str] = []
    try:
        with open(ruta, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return Registro([], [f"No existe {ruta}"], [])
    except yaml.YAMLError as e:
        return Registro([], [f"projects.yaml no es YAML válido: {e}"], [])

    crudos = data.get("proyectos") if isinstance(data, dict) else None
    if not isinstance(crudos, list):
        return Registro([], ["projects.yaml debe tener una lista 'proyectos:'"], [])

    proyectos: List[Proyecto] = []
    vistos = set()
    dueños_puerto: Dict[int, str] = {}
    for i, c in enumerate(crudos, 1):
        if not isinstance(c, dict):
            errores.append(f"proyecto #{i}: debe ser un objeto")
            continue
        if isinstance(c.get("nombre"), bool):
            # YAML lee no/yes/on/off como sí/no: el nombre se perdería en silencio.
            errores.append(f"proyecto #{i}: el nombre se leyó como sí/no; ponlo entre comillas (ej. nombre: \"no\")")
            continue
        nombre = str(c.get("nombre") or "").strip()
        if not nombre:
            errores.append(f"proyecto #{i}: falta 'nombre'")
            continue
        if nombre.lower() in vistos:
            errores.append(f"{nombre}: nombre repetido")
            continue
        vistos.add(nombre.lower())
        pruebas = str(c.get("pruebas") or "").strip()
        habilitado = bool(c.get("habilitado", False))
        if not pruebas:
            errores.append(f"{nombre}: falta el comando de 'pruebas' (sin pruebas, Hermes no puede saber si terminó bien)")
        carpeta = _resolver_carpeta(c.get("carpeta"), documentos)
        if not carpeta:
            errores.append(f"{nombre}: falta 'carpeta'")
        elif not os.path.isdir(carpeta):
            (errores if habilitado else avisos).append(f"{nombre}: la carpeta no existe ({carpeta})")
        puertos = []
        for p in c.get("puertos") or []:
            if not isinstance(p, int) or not (1 <= p <= 65535):
                errores.append(f"{nombre}: puerto inválido {p!r}")
                continue
            if p in dueños_puerto:
                errores.append(f"puerto {p} repetido: {dueños_puerto[p]} y {nombre}")
                continue
            dueños_puerto[p] = nombre
            puertos.append(p)
        proyectos.append(Proyecto(
            nombre=nombre, repo=str(c.get("repo") or "").strip(), carpeta=carpeta, pruebas=pruebas,
            rama_base=str(c.get("rama_base") or "develop").strip(), pm2=[str(x) for x in (c.get("pm2") or [])],
            puertos=puertos, habilitado=habilitado, nota=str(c.get("nota") or "").strip(),
        ))
    return Registro(proyectos, errores, avisos)

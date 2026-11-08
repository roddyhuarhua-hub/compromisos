"""Venta por modulos: cada cliente ve solo las herramientas que contrato.

Lo pidieron las tres entrevistas (docs/research/): un proyecto en etapa temprana, sin acuerdos, solo necesita el
mapa de actores y el seguimiento de lideres; uno en exploracion suma compromisos y riesgos; una operacion o un
corporativo con varios proyectos usa todo.

Los modulos de un cliente se fijan con la variable MODULOS (Secrets de Streamlit o .env): el nombre de un paquete
("temprana", "exploracion", "operacion", "corporativo") o una lista separada por comas ("actores,riesgos").
Sin esa variable, la demo deja elegirlos en la barra lateral. Tambien se puede probar con ?modulos=temprana.
"""
from __future__ import annotations

# clave -> (nombre en pantalla, para que sirve)
MODULOS = {
    "reunion": ("🎙️ Registro de campo", "Subir audio, foto del acta o texto; la IA extrae compromisos y actores"),
    "actores": ("🕸️ Grupos de interés", "Quién es quién, postura pública y privada, red y seguimiento de líderes"),
    "compromisos": ("📊 Gestión de compromisos", "Panel ejecutivo de compromisos, vencidos por prioridad, registro y descargas"),
    "conflictividad": ("🔥 Conflictividad social", "Historia de paros, bloqueos y tomas en el territorio"),
    "riesgos": ("🎯 Riesgo social y escenarios", "Riesgo de paralización por proceso, 'si haces esto, pasa esto'"),
    "portafolio": ("🏢 Vista corporativa", "Varios proyectos o unidades en una sola mirada corporativa"),
}
SIEMPRE = ["reunion"]  # la captura de reuniones alimenta a todos los demas modulos

PAQUETES = {
    "temprana": ("🌱 Etapa temprana", ["reunion", "actores"],
                 "Proyecto sin acuerdos todavía: mapa de actores y seguimiento de líderes"),
    "exploracion": ("⛏️ Exploración", ["reunion", "actores", "compromisos", "riesgos"],
                    "Acuerdos de acceso y uso superficial: suma compromisos y riesgos de cada proceso"),
    "operacion": ("🏭 Operación", ["reunion", "actores", "compromisos", "conflictividad", "riesgos"],
                  "Unidad en operación con convenios y conflictividad histórica"),
    "corporativo": ("🏢 Corporativo (todo)", list(MODULOS),
                    "Varios proyectos o unidades, con la vista de portafolio"),
}


def leer(valor: str | None) -> list[str] | None:
    """Convierte el texto de MODULOS (paquete o lista) en la lista de modulos activos. None si no hay valor."""
    if not valor or not str(valor).strip():
        return None
    v = str(valor).strip().lower()
    if v in PAQUETES:
        mods = PAQUETES[v][1]
    else:
        mods = [m.strip() for m in v.replace(";", ",").split(",") if m.strip() in MODULOS]
    return ordenar(mods)


def ordenar(mods) -> list[str]:
    elegidos = set(mods) | set(SIEMPRE)
    return [m for m in MODULOS if m in elegidos]


def paquete_de(mods) -> str | None:
    for clave, (_, lista, _) in PAQUETES.items():
        if set(lista) == set(ordenar(mods)):
            return clave
    return None

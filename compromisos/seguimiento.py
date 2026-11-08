"""Temas que seguimos: asuntos nacionales que pueden mover a los dirigentes locales.

El primero es la Ley MAPE (pequeña minería y minería artesanal), el REINFO y la minería informal e ilegal: cómo
avanza en el Congreso y qué movilizaciones hacen los mineros y sus dirigentes. Para el relacionamiento importa
sobre todo si la movilización llega a nuestra región y si en la noticia aparece algún dirigente de nuestro mapa
de grupos de interés.

Cada tema es una lista de búsquedas para Google Noticias; el equipo puede agregar los suyos desde la app.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from . import noticias as nt

TEMAS_BASE = {
    "Ley MAPE, REINFO y minería artesanal": [
        '"Ley MAPE"', '"ley de la pequeña minería" Congreso', "REINFO ampliación Congreso",
        "mineros artesanales paro", "mineros informales movilización", "minería ilegal dirigentes",
        "Confemin paro", "mineros artesanales Lima marcha"],
}
ETAPAS = {
    "En el Congreso": ["congreso", "comision", "pleno", "dictamen", "aprob", "proyecto de ley", "ley mape",
                       "predictamen", "votacion", "legislativ", "ejecutivo", "minem", "decreto"],
    "Movilización": ["paro", "bloqueo", "marcha", "movilizaci", "huelga", "protesta", "plantón", "planton",
                     "toma de", "enfrentamiento"],
}
COLUMNAS = ["fecha", "tema_seguido", "titulo", "medio", "enlace", "etapa", "alerta", "en_region", "menciona"]


def etapa(texto: str) -> str:
    t = nt._plano(texto)
    mov = sum(t.count(k) for k in ETAPAS["Movilización"])
    con = sum(t.count(k) for k in ETAPAS["En el Congreso"])
    return "Movilización" if mov and mov >= con else "En el Congreso" if con else "Otro"


def seguir(tema: str, busquedas: list[str], regiones: list[str], actores: list[str], hoy: date | None = None,
           dias: int = 14, bajar=nt.descargar) -> pd.DataFrame:
    """Noticias del tema, marcando las que tocan nuestra region o mencionan a nuestros actores."""
    hoy = hoy or date.today()
    from concurrent.futures import ThreadPoolExecutor
    urls = [nt.url_google(q, dias) for q in busquedas]
    with ThreadPoolExecutor(max_workers=8) as ex:
        contenidos = list(ex.map(bajar, urls))
    regs = [nt._plano(r) for r in regiones if r]
    nombres = {nt._plano(a): a for a in actores if a and len(a) > 5}
    vistas, filas = set(), []
    for contenido in contenidos:
        for n in nt.leer_rss(contenido or b""):
            clave = nt._plano(n["titulo"])[:90]
            if clave in vistas or (n["fecha"] and n["fecha"] < hoy - timedelta(days=dias)):
                continue
            vistas.add(clave)
            texto = f"{n['titulo']} {n['resumen']}"
            tp = nt._plano(texto)
            _, alerta = nt.clasificar(texto)
            filas.append(dict(fecha=n["fecha"] or hoy, tema_seguido=tema, titulo=n["titulo"], medio=n["medio"],
                              enlace=n["enlace"], etapa=etapa(texto), alerta=alerta,
                              en_region=any(r in tp for r in regs),
                              menciona=", ".join(v for k, v in nombres.items() if k in tp)))
    df = pd.DataFrame(filas, columns=COLUMNAS)
    return df.sort_values(["en_region", "alerta", "fecha"], ascending=[False, False, False]).reset_index(drop=True)


def a_contexto(df: pd.DataFrame, proyecto: str) -> pd.DataFrame:
    """Noticias elegidas como factores externos del proyecto, por validar."""
    return pd.DataFrame([dict(fecha=r["fecha"], proyecto=proyecto, comunidad="",
                              tipo="Norma o política en debate" if r["etapa"] == "En el Congreso" else "Otro detonante",
                              descripcion=f"{r['tema_seguido']}: {r['titulo']}",
                              intensidad=3 if r["en_region"] and r["etapa"] == "Movilización" else 2 if r["en_region"]
                              else 1, fuente=r["medio"] or "Noticia", enlace=r["enlace"], validado=False)
                         for _, r in df.iterrows()])

"""Contexto del dia: noticias nacionales, regionales y locales sobre el ambito del proyecto.

Lo pidio la entrevista 3: lo que pasa en la region (un paro, una denuncia ambiental, el precio de los metales,
las elecciones municipales, regionales o comunales) afecta el relacionamiento aunque no ocurra en la comunidad.

Fuente: Google Noticias por RSS (agrupa diarios nacionales como El Comercio, La Republica, RPP o Andina, y medios
regionales y locales), mas los RSS que el cliente agregue en la variable NOTICIAS_RSS (separados por comas).
No necesita clave. Cada noticia se clasifica por tema (social, ambiental, economico, politico), por alcance
(local, regional, nacional) y por su señal de alerta; las que importan pasan a *Factores externos de riesgo*
como "por validar", para que el equipo las confirme antes de que suban el riesgo.

Uso diario sin abrir la app: python scripts/noticias_del_dia.py (escribe datos/noticias.csv).
"""
from __future__ import annotations

import html
import os
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import pandas as pd

COLUMNAS = ["fecha", "proyecto", "titulo", "medio", "enlace", "tema", "alcance", "alerta", "tipo_contexto",
            "lugar"]
TEMAS = {
    "Político y electoral": ["elecci", "candidat", "alcalde", "gobernador", "consejo regional", "jne", "onpe",
                             "vacancia", "revocatoria", "congreso", "ministr", "premier", "proyecto de ley",
                             "directiva comunal", "junta directiva", "presidente comunal", "asamblea comunal"],
    "Social y conflictos": ["paro", "bloqueo", "protesta", "movilizaci", "huelga", "conflicto", "defensoria",
                            "dialogo", "mesa de", "comuner", "ronda", "toma de", "enfrentamiento", "marcha"],
    "Ambiental": ["contamina", "derrame", "relave", "oefa", "agua", "laguna", "rio ", "bofedal", "ambiental",
                  "eia", "dia ", "ana ", "metales pesados", "glaciar", "sequia", "helada", "huaico", "lluvia"],
    "Económico": ["precio del cobre", "precio del oro", "cobre", "oro", "canon", "regalia", "inversion",
                  "exportacion", "empleo", "economia", "presupuesto", "obras por impuestos", "mineria ilegal",
                  "mineros informales", "reinfo"],
}
# palabras que vuelven una noticia una señal de alerta para el relacionamiento (mas puntos = mas fuerte)
ALERTA = {3: ["paro", "bloqueo", "toma de", "enfrentamiento", "muerto", "herido", "derrame", "estado de emergencia",
              "vacancia", "huelga indefinida"],
          2: ["denuncia", "protesta", "movilizaci", "contamina", "conflicto", "elecciones", "revocatoria",
              "suspend", "rechaz", "ultimatum", "mineria ilegal"],
          1: ["reclamo", "exige", "pide", "reunion", "mesa de dialogo", "proyecto de ley", "canon"]}


def _plano(t: str) -> str:
    t = unicodedata.normalize("NFKD", str(t).lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def clasificar(texto: str) -> tuple[str, int]:
    """Tema principal y señal de alerta (0 a 3) de una noticia."""
    t = f" {_plano(texto)} "
    puntos = {tema: sum(t.count(k) for k in claves) for tema, claves in TEMAS.items()}
    tema = max(puntos, key=puntos.get) if max(puntos.values()) > 0 else "Otro"
    alerta = next((n for n in (3, 2, 1) if any(k in t for k in ALERTA[n])), 0)
    return tema, alerta


def tipo_contexto(tema: str, texto: str) -> str:
    """El tipo de *factor externo de riesgo* que corresponde a la noticia."""
    t = _plano(texto)
    if tema == "Político y electoral":
        if any(k in t for k in ("directiva comunal", "junta directiva", "presidente comunal", "elecci")):
            return "Elecciones o cambio de autoridades"
        return "Norma o política en debate"
    if tema == "Ambiental":
        return "Denuncia ambiental" if "denuncia" in t or "oefa" in t else "Otro detonante"
    if "policia" in t or "fiscal" in t:
        return "Denuncia policial"
    if any(k in t for k in ("asalto", "inseguridad", "emboscada", "secuestro")):
        return "Riesgo de seguridad"
    return "Otro detonante"


# ------------------------------------------------------------------ consultas y lectura
def lugares(proyecto: str, comunidades: pd.DataFrame, proyectos: pd.DataFrame | None = None) -> dict[str, list[str]]:
    """Region, distritos y comunidades del proyecto, para buscar y para saber si una noticia es local."""
    c = comunidades[comunidades["proyecto"] == proyecto] if "proyecto" in comunidades else comunidades
    region = ""
    if proyectos is not None and not proyectos.empty and "region" in proyectos:
        r = proyectos.loc[proyectos["proyecto"] == proyecto, "region"]
        region = str(r.iloc[0]) if not r.empty else ""
    if not region and "region" in c and not c.empty:
        region = str(c["region"].mode().iloc[0])
    distritos = sorted({str(d) for d in c.get("distrito", pd.Series(dtype=str)).dropna() if str(d).strip()})
    coms = sorted({re.sub(r"^C\.C\.\s*", "", str(x)) for x in c["comunidad"]})
    return {"region": [region] if region else [], "distritos": distritos, "comunidades": coms}


def consultas(lug: dict[str, list[str]]) -> list[str]:
    """Busquedas para Google Noticias: la region con cada tema, y los distritos y comunidades por su nombre."""
    q = []
    for reg in lug["region"]:
        q += [f'"{reg}" (minería OR minera OR paro OR bloqueo OR conflicto OR comunidad)',
              f'"{reg}" (elecciones OR alcalde OR gobernador OR "consejo regional" OR revocatoria)',
              f'"{reg}" (contaminación OR agua OR OEFA OR ambiental OR derrame)',
              f'"{reg}" (canon OR inversión OR "minería ilegal" OR empleo)']
    for d in lug["distritos"][:6]:
        q.append(f'"{d}" {lug["region"][0] if lug["region"] else ""}'.strip())
    for c in lug["comunidades"][:6]:
        q.append(f'"comunidad {c}"')
    return q


def url_google(q: str, dias: int = 7) -> str:
    return (f"https://news.google.com/rss/search?q={quote_plus(q + f' when:{dias}d')}"
            "&hl=es-419&gl=PE&ceid=PE:es-419")


def fuentes_extra() -> list[str]:
    return [u.strip() for u in os.getenv("NOTICIAS_RSS", "").split(",") if u.strip()]


def leer_rss(xml: bytes | str) -> list[dict]:
    """Noticias de un RSS: titulo, enlace, fecha, medio y resumen."""
    try:
        raiz = ET.fromstring(xml)
    except ET.ParseError:
        return []
    out = []
    for it in raiz.iter("item"):
        titulo = html.unescape(it.findtext("title") or "").strip()
        medio = (it.findtext("source") or "").strip()
        if medio and titulo.endswith(f" - {medio}"):  # Google Noticias agrega el medio al final del titulo
            titulo = titulo[: -len(medio) - 3].strip()
        try:
            fecha = parsedate_to_datetime(it.findtext("pubDate") or "").date()
        except (TypeError, ValueError):
            fecha = None
        resumen = re.sub(r"<[^>]+>", " ", html.unescape(it.findtext("description") or ""))
        out.append(dict(titulo=titulo, enlace=(it.findtext("link") or "").strip(), fecha=fecha, medio=medio,
                        resumen=re.sub(r"\s+", " ", resumen).strip()))
    return [n for n in out if n["titulo"]]


def descargar(url: str, timeout: int = 12) -> bytes | None:
    try:
        import requests
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 (Compromisos; noticias)"})
        return r.content if r.ok else None
    except Exception:
        return None


def buscar(proyecto: str, comunidades: pd.DataFrame, proyectos: pd.DataFrame | None = None, hoy: date | None = None,
           dias: int = 7, bajar=descargar) -> pd.DataFrame:
    """Noticias de los ultimos dias sobre el ambito del proyecto, sin repetidas y ordenadas por alerta."""
    hoy = hoy or date.today()
    lug = lugares(proyecto, comunidades, proyectos)
    urls = [url_google(q, dias) for q in consultas(lug)] + fuentes_extra()
    vistas, filas = set(), []
    locales = [_plano(x) for x in lug["distritos"] + lug["comunidades"]]
    regionales = [_plano(x) for x in lug["region"]]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as ex:  # todas las busquedas a la vez: unos segundos en total
        contenidos = list(ex.map(bajar, urls))
    for u, contenido in zip(urls, contenidos):
        if not contenido:
            continue
        for n in leer_rss(contenido):
            clave = _plano(n["titulo"])[:90]
            if clave in vistas or (n["fecha"] and n["fecha"] < hoy - timedelta(days=dias)):
                continue
            vistas.add(clave)
            texto = f"{n['titulo']} {n['resumen']}"
            tp = _plano(texto)
            if u in fuentes_extra() and not any(x in tp for x in locales + regionales):
                continue  # de un RSS general, solo lo que menciona el ambito
            tema, alerta = clasificar(texto)
            lugar = next((x for x in lug["distritos"] + lug["comunidades"] if _plano(x) in tp), "")
            alcance = "Local" if lugar else "Regional" if any(r in tp for r in regionales) else "Nacional"
            filas.append(dict(fecha=n["fecha"] or hoy, proyecto=proyecto, titulo=n["titulo"], medio=n["medio"],
                              enlace=n["enlace"], tema=tema, alcance=alcance, alerta=alerta,
                              tipo_contexto=tipo_contexto(tema, texto), lugar=lugar))
    df = pd.DataFrame(filas, columns=COLUMNAS)
    orden = {"Local": 0, "Regional": 1, "Nacional": 2}
    return df.assign(_a=df["alcance"].map(orden)).sort_values(["alerta", "_a", "fecha"], ascending=[False, True, False]) \
        .drop(columns="_a").reset_index(drop=True)


def a_contexto(nots: pd.DataFrame, comunidades: pd.DataFrame) -> pd.DataFrame:
    """Convierte noticias elegidas en factores externos de riesgo, por validar."""
    com_de = {re.sub(r"^C\.C\.\s*", "", c): c for c in comunidades["comunidad"]}
    return pd.DataFrame([dict(fecha=r["fecha"], proyecto=r["proyecto"] if r["lugar"] not in com_de else "",
                              comunidad=com_de.get(r["lugar"], ""), tipo=r["tipo_contexto"],
                              descripcion=r["titulo"], intensidad=max(1, int(r["alerta"])),
                              fuente=r["medio"] or "Noticia", enlace=r["enlace"], validado=False)
                         for _, r in nots.iterrows()])


def guardar(df: pd.DataFrame, ruta) -> None:
    """Agrega las noticias nuevas a un CSV historico (sin repetir titulos)."""
    from pathlib import Path
    ruta = Path(ruta)
    if ruta.exists():
        viejo = pd.read_csv(ruta)
        df = pd.concat([viejo, df], ignore_index=True)
    df.drop_duplicates(subset=["proyecto", "titulo"], keep="last").to_csv(ruta, index=False)


def cuando(fecha) -> str:
    try:
        d = (date.today() - fecha).days
    except TypeError:
        return ""
    return "hoy" if d <= 0 else "ayer" if d == 1 else f"hace {d} días"


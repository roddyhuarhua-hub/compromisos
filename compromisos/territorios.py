"""Territorios comunales: los limites de propiedad de cada comunidad, como poligonos en el mapa.

Tres fuentes, de la mejor a la de ejemplo:

1. **Los poligonos del cliente** (GeoJSON en WGS84, o un shapefile .zip en WGS84). Son los limites que la empresa
   ya tiene: del catastro rural del MIDAGRI, del plano inscrito en SUNARP, del SICCAM (IBC-CEPES) o de su propio
   levantamiento topografico. Se cruzan por nombre con las comunidades del registro.
2. **La capa oficial del MIDAGRI** (catastro rural, capa *Comunidades campesinas*), que el navegador dibuja
   directamente desde el geoservidor del Estado (WMS). No se descarga nada; si el servicio no responde, no se ve.
3. **Territorios de ejemplo**: para la demo, poligonos aproximados alrededor de cada comunidad ficticia (como un
   diagrama de Voronoi recortado e irregular). No representan limites reales.
"""
from __future__ import annotations

import io
import json
import math
import os
import re
import unicodedata
import zipfile

import numpy as np
import pandas as pd

# geoservidores del MIDAGRI (catastro rural en WGS84); se prueba en orden
WMS_MIDAGRI = [
    "https://georural.midagri.gob.pe/geoservicios/services/public/WGS84_Catastro_Rural/MapServer/WMSServer",
    "https://georural.minagri.gob.pe/geoservicios/services/public/WGS84_Catastro_Rural/MapServer/WMSServer",
    "https://georural.midagri.gob.pe/geoservicios/services/servicios_ogc/Catastro_Rural/MapServer/WMSServer",
]
CAMPOS_NOMBRE = ["comunidad", "nombre", "nom_comuni", "nom_comun", "nomb_comun", "nombre_cc", "nom_cc", "name",
                 "denominaci", "denominacion", "nom_ccpp", "nombre_com"]


def plano(t: str) -> str:
    """Nombre comparable: sin tildes, sin 'C.C.' ni 'comunidad campesina', en minusculas."""
    t = unicodedata.normalize("NFKD", str(t).lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"\b(c\.?\s?c\.?|comunidad campesina( de)?|comunidad( de)?)\b", " ", t)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


# ------------------------------------------------------------------ territorios de ejemplo
def ejemplo(comunidades: pd.DataFrame, radio_km: float = 7.5, lados: int = 56, semilla: int = 11) -> dict:
    """Poligonos aproximados para la demo: la celda de Voronoi de cada comunidad, recortada a un radio que
    crece con el numero de familias, con borde irregular. Devuelve un GeoJSON (FeatureCollection)."""
    c = comunidades.dropna(subset=["lat", "lon"]).reset_index(drop=True)
    rng = np.random.default_rng(semilla)
    feats = []
    if c.empty:
        return dict(type="FeatureCollection", features=feats)
    lat0 = float(c["lat"].mean())
    kx = 111.32 * math.cos(math.radians(lat0))  # km por grado de longitud
    ky = 110.57                                  # km por grado de latitud
    xy = np.c_[c["lon"].to_numpy() * kx, c["lat"].to_numpy() * ky]
    fam = c["familias"].fillna(c["familias"].median() if "familias" in c else 120) if "familias" in c \
        else pd.Series(120, index=c.index)
    ang = np.linspace(0, 2 * np.pi, lados, endpoint=False)
    u = np.c_[np.cos(ang), np.sin(ang)]
    for i, row in c.iterrows():
        rmax = radio_km * float(np.clip(np.sqrt(fam.iloc[i] / 130), 0.7, 1.35))
        r = np.full(lados, rmax)
        for j in range(len(c)):
            if j == i:
                continue
            d = xy[j] - xy[i]
            dist = float(np.hypot(*d))
            if dist == 0:
                continue
            proy = u @ (d / dist)                     # cos del angulo entre el rayo y la direccion al vecino
            lim = np.where(proy > 1e-6, (dist / 2) / np.maximum(proy, 1e-6), np.inf)
            r = np.minimum(r, lim * 0.94)              # un poco antes de la mediatriz: queda un borde entre vecinos
        # borde irregular, suave (como un limite que sigue quebradas y cumbres)
        ruido = np.zeros(lados)
        for k, amp in ((2, 0.09), (3, 0.07), (5, 0.05), (9, 0.03)):
            ruido += amp * np.cos(k * ang + rng.uniform(0, 2 * np.pi))
        r = r * (1 + ruido)
        px = xy[i, 0] + r * u[:, 0]
        py = xy[i, 1] + r * u[:, 1]
        anillo = [[round(x / kx, 6), round(y / ky, 6)] for x, y in zip(px, py)]
        anillo.append(anillo[0])
        area = 0.5 * abs(np.dot(px, np.roll(py, 1)) - np.dot(py, np.roll(px, 1)))  # km2
        feats.append(dict(type="Feature", id=str(row["comunidad"]),
                          properties=dict(comunidad=str(row["comunidad"]), area_ha=round(area * 100),
                                          fuente="Ejemplo (no es un límite real)"),
                          geometry=dict(type="Polygon", coordinates=[anillo])))
    return dict(type="FeatureCollection", features=feats)


# ------------------------------------------------------------------ poligonos del cliente
def _campo_nombre(props: dict) -> str | None:
    low = {k.lower(): k for k in props}
    for c in CAMPOS_NOMBRE:
        if c in low:
            return low[c]
    return next((k for k, v in props.items() if isinstance(v, str) and len(v) > 3), None)


def _desde_shapefile(contenido: bytes) -> dict:
    import shapefile  # pyshp

    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        nombres = z.namelist()
        base = next(n[:-4] for n in nombres if n.lower().endswith(".shp"))
        prj = next((n for n in nombres if n.lower().endswith(".prj")), None)
        if prj:
            txt = z.read(prj).decode("latin-1", "ignore").upper()
            if "PROJCS" in txt:
                raise ValueError("El shapefile está en coordenadas proyectadas (UTM). Expórtalo en WGS84 "
                                 "(EPSG:4326) desde QGIS o mapshaper.org y vuelve a subirlo.")
        ext = {n[-4:].lower(): n for n in nombres if n.startswith(base)}
        lector = shapefile.Reader(shp=io.BytesIO(z.read(ext[".shp"])), dbf=io.BytesIO(z.read(ext[".dbf"])),
                                  shx=io.BytesIO(z.read(ext[".shx"])) if ".shx" in ext else None,
                                  encoding="latin-1")
        return lector.__geo_interface__


def leer(nombre_archivo: str, contenido: bytes) -> dict:
    """GeoJSON o shapefile (.zip) -> FeatureCollection en WGS84."""
    if nombre_archivo.lower().endswith(".zip"):
        gj = _desde_shapefile(contenido)
    else:
        gj = json.loads(contenido.decode("utf-8-sig"))
    if gj.get("type") == "Feature":
        gj = dict(type="FeatureCollection", features=[gj])
    feats = [f for f in gj.get("features", []) if f.get("geometry", {}) and
             f["geometry"].get("type") in ("Polygon", "MultiPolygon")]
    if not feats:
        raise ValueError("El archivo no tiene polígonos.")
    x = _primera_coord(feats[0]["geometry"])
    if not (-180 <= x[0] <= 180 and -90 <= x[1] <= 90):
        raise ValueError("Las coordenadas no están en grados (WGS84). Exporta el archivo en EPSG:4326.")
    return dict(type="FeatureCollection", features=feats)


def _primera_coord(g: dict) -> list[float]:
    c = g["coordinates"]
    while isinstance(c[0], list):
        c = c[0]
    return c


def cruzar(gj: dict, comunidades: pd.DataFrame) -> tuple[dict, list[str]]:
    """Deja en cada poligono el nombre de la comunidad del registro (cruce por nombre, sin tildes ni 'C.C.').
    Devuelve el GeoJSON cruzado y la lista de comunidades del registro que no encontraron poligono."""
    mapa = {plano(c): c for c in comunidades["comunidad"]}
    out, vistos = [], set()
    for f in gj["features"]:
        props = dict(f.get("properties") or {})
        campo = _campo_nombre(props)
        nom = plano(props.get(campo, "")) if campo else ""
        com = mapa.get(nom) or next((v for k, v in mapa.items() if k and nom and (k in nom or nom in k)), None)
        if not com:
            continue
        vistos.add(com)
        props.update(comunidad=com, fuente=props.get("fuente", "Límites del cliente"))
        out.append(dict(type="Feature", id=com, properties=props, geometry=f["geometry"]))
    faltan = [c for c in comunidades["comunidad"] if c not in vistos]
    return dict(type="FeatureCollection", features=out), faltan


def centroides(gj: dict) -> pd.DataFrame:
    """Centro aproximado de cada poligono (promedio del anillo exterior mas grande)."""
    filas = []
    for f in gj["features"]:
        g = f["geometry"]
        anillos = [g["coordinates"][0]] if g["type"] == "Polygon" else [p[0] for p in g["coordinates"]]
        a = max(anillos, key=len)
        filas.append(dict(comunidad=f["properties"]["comunidad"], lon=float(np.mean([p[0] for p in a])),
                          lat=float(np.mean([p[1] for p in a]))))
    return pd.DataFrame(filas, columns=["comunidad", "lon", "lat"])


# ------------------------------------------------------------------ capa oficial del MIDAGRI (WMS)
def _capas_wms(xml: bytes) -> list[tuple[str, str]]:
    import xml.etree.ElementTree as ET

    raiz = ET.fromstring(xml)
    out = []
    for capa in raiz.iter():
        if not capa.tag.endswith("Layer"):
            continue
        nom = tit = None
        for h in capa:
            if h.tag.endswith("Name"):
                nom = (h.text or "").strip()
            elif h.tag.endswith("Title"):
                tit = (h.text or "").strip()
        if nom:
            out.append((nom, tit or nom))
    return out


def capa_oficial(bajar=None, urls: list[str] | None = None) -> dict | None:
    """Busca en el geoservidor del MIDAGRI la capa de comunidades campesinas y arma la plantilla de mosaicos
    WMS que el mapa pide directamente. None si el servicio no responde."""
    plantilla = os.getenv("WMS_COMUNIDADES")  # el cliente puede fijar su propia capa (URL con {bbox-epsg-3857})
    if plantilla:
        return dict(url=plantilla, titulo="Comunidades campesinas", fuente="Capa configurada por el cliente")
    if bajar is None:
        def bajar(u):
            import requests
            try:
                r = requests.get(u, timeout=10, headers={"User-Agent": "Mozilla/5.0 (Compromisos)"})
                return r.content if r.ok else None
            except Exception:  # noqa: BLE001
                return None
    for base in urls or WMS_MIDAGRI:
        xml = bajar(f"{base}?service=WMS&request=GetCapabilities&version=1.1.1")
        if not xml:
            continue
        try:
            capas = _capas_wms(xml)
        except Exception:  # noqa: BLE001
            continue
        elegidas = [n for n, t in capas if "campesin" in plano(t) or "campesin" in plano(n)]
        if not elegidas:
            continue
        url = (f"{base}?service=WMS&request=GetMap&version=1.1.1&layers={','.join(elegidas)}&styles="
               "&format=image/png&transparent=true&srs=EPSG:3857&width=256&height=256&bbox={bbox-epsg-3857}")
        return dict(url=url, titulo="Comunidades campesinas (MIDAGRI)",
                    fuente="Catastro rural © MIDAGRI")
    return None


# ------------------------------------------------------------------ dibujo
def trazas(gj: dict, ind: pd.DataFrame, colores: dict[str, str], satelite: bool = True) -> list:
    """Poligonos rellenos por semaforo (Choroplethmap) + su borde. ind: comunidad, semaforo, indice."""
    import plotly.graph_objects as go

    if not gj or not gj.get("features"):
        return []
    sem = ind.set_index("comunidad")
    ids = [f["properties"]["comunidad"] for f in gj["features"] if f["properties"]["comunidad"] in sem.index]
    if not ids:
        return []
    out = []
    for nivel, color in colores.items():
        s = [i for i in ids if sem.loc[i, "semaforo"] == nivel]
        if not s:
            continue
        sub = dict(type="FeatureCollection",
                   features=[f for f in gj["features"] if f["properties"]["comunidad"] in s])
        area = {f["properties"]["comunidad"]: f["properties"].get("area_ha", "") for f in sub["features"]}
        fuente = {f["properties"]["comunidad"]: f["properties"].get("fuente", "") for f in sub["features"]}
        out.append(go.Choroplethmap(
            geojson=sub, locations=s, featureidkey="properties.comunidad", z=[1] * len(s),
            colorscale=[[0, color], [1, color]], showscale=False,
            marker=dict(opacity=0.30 if satelite else 0.22,
                        line=dict(color="#ffffff" if satelite else color, width=2.2)),
            name=f"Territorio · {nivel}", showlegend=False,
            customdata=[[i, sem.loc[i, "indice"], area[i], fuente[i]] for i in s],
            hovertemplate=("<b>%{customdata[0]}</b><br>Índice de riesgo: %{customdata[1]:.0f}/100"
                           "<br>Superficie: %{customdata[2]:,} ha<br><i>%{customdata[3]}</i><extra></extra>"),
        ))
    return out


def contornos(gj: dict | None, comunidades, satelite: bool = True) -> list:
    """Territorios sin semaforo: relleno tenue y borde, para mapas donde el color lo llevan otros datos."""
    import plotly.graph_objects as go

    if not gj or not gj.get("features"):
        return []
    quiero = set(comunidades)
    sub = dict(type="FeatureCollection", features=[f for f in gj["features"]
                                                    if f["properties"]["comunidad"] in quiero])
    if not sub["features"]:
        return []
    ids = [f["properties"]["comunidad"] for f in sub["features"]]
    color = "#ffffff" if satelite else "#2d4a33"
    return [go.Choroplethmap(
        geojson=sub, locations=ids, featureidkey="properties.comunidad", z=[1] * len(ids),
        colorscale=[[0, color], [1, color]], showscale=False, name="Territorio comunal", showlegend=False,
        marker=dict(opacity=0.10 if satelite else 0.08, line=dict(color=color, width=1.8)),
        hovertemplate="<b>%{location}</b><extra>Territorio comunal</extra>")]


def dibujar_mpl(ax, gj: dict | None, color_de: dict[str, str] | None = None, satelite: bool = True,
                zorder: int = 1) -> None:
    """Territorios en un grafico de matplotlib (laminas): relleno tenue por semaforo y borde."""
    from matplotlib.patches import Polygon

    if not gj or not gj.get("features"):
        return
    for f in gj["features"]:
        com = f["properties"]["comunidad"]
        if color_de is not None and com not in color_de:
            continue
        color = (color_de or {}).get(com, "#ffffff" if satelite else "#2d4a33")
        g = f["geometry"]
        polis = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        for poli in polis:
            xy = np.asarray(poli[0], dtype=float)
            ax.add_patch(Polygon(xy, closed=True, fc=color, alpha=0.30 if satelite else 0.22, lw=0, zorder=zorder))
            ax.add_patch(Polygon(xy, closed=True, fill=False, ec="white" if satelite else color, lw=2.0,
                                 alpha=0.95, zorder=zorder + 0.1))

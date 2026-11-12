"""Fondo de mapa (satelite con nombres de lugares) para las laminas de alta resolucion.

Descarga los mosaicos (tiles) de Esri del area que se va a dibujar, los une y los pone debajo de los
graficos de matplotlib. Si no hay internet, la lamina se dibuja igual, sin fondo.
"""
from __future__ import annotations

import io
import math
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import numpy as np
from PIL import Image

ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services"
CLARITY = "https://clarity.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
ESTILOS = {
    # capas de abajo hacia arriba, atribucion
    "satelite": ([f"{ESRI}/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}",
                    CLARITY,  # imagen mas nitida y de color natural (si no carga, queda la de abajo)
                    f"{ESRI}/Reference/World_Transportation/MapServer/tile/{{z}}/{{y}}/{{x}}",
                  f"{ESRI}/Reference/World_Boundaries_and_Places/MapServer/tile/{{z}}/{{y}}/{{x}}"],
                 "Imágenes © Esri, Maxar, Earthstar Geographics"),
    "relieve": ([f"{ESRI}/World_Topo_Map/MapServer/tile/{{z}}/{{y}}/{{x}}"],
                "Mapa topográfico © Esri, HERE, Garmin, USGS"),
}
AGENTE = "Compromisos/1.0 (reportes de gestion social)"


def _capas(estilo: str) -> tuple[list[str], str]:
    propio = os.getenv("MAPA_TILES_URL")  # para pruebas o para usar otro proveedor de mosaicos
    if propio:
        return propio.split("|"), "Mapa base"
    return ESTILOS.get(estilo, ESTILOS["satelite"])


def _a_tile(lat: float, lon: float, z: int) -> tuple[float, float]:
    """Coordenadas (fraccionarias) del tile que contiene el punto, en Web Mercator."""
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def _a_latlon(x: float, y: float, z: int) -> tuple[float, float]:
    n = 2 ** z
    lon = x / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lat, lon


@lru_cache(maxsize=512)
def _descargar(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.read()
    except Exception:  # noqa: BLE001  sin internet o tile inexistente
        return None


def mosaico(lon0: float, lon1: float, lat0: float, lat1: float, estilo: str = "satelite",
            max_tiles: int = 80) -> tuple[np.ndarray, tuple[float, float, float, float], str] | None:
    """Imagen del area (lon0..lon1, lat0..lat1) reproyectada a grilla lon/lat regular.
    Devuelve (imagen RGB, extent=(lon0, lon1, lat0, lat1), atribucion) o None si no se pudo descargar."""
    capas, atribucion = _capas(estilo)
    for z in range(15, 4, -1):  # el mayor zoom que no pase de max_tiles (mas tiles = mas nitidez)
        x0, y0 = _a_tile(lat1, lon0, z)
        x1, y1 = _a_tile(lat0, lon1, z)
        tx = range(int(x0), int(x1) + 1)
        ty = range(int(y0), int(y1) + 1)
        if len(tx) * len(ty) <= max_tiles:
            break
    pedidos = [(i, j, k, url.format(z=z, x=x, y=y)) for i, x in enumerate(tx) for j, y in enumerate(ty)
               for k, url in enumerate(capas)]
    with ThreadPoolExecutor(max_workers=12) as ex:
        datos = list(ex.map(lambda p: _descargar(p[3]), pedidos))
    base_ok = [d for (_, _, k, _), d in zip(pedidos, datos) if k == 0]
    if not base_ok or sum(d is not None for d in base_ok) < 0.7 * len(base_ok):
        return None
    lienzo = Image.new("RGBA", (256 * len(tx), 256 * len(ty)), (238, 243, 238, 255))
    for (i, j, _, _), d in sorted(zip(pedidos, datos), key=lambda t: t[0][2]):  # capas en orden
        if d is None:
            continue
        try:
            t = Image.open(io.BytesIO(d)).convert("RGBA").resize((256, 256))
        except Exception:  # noqa: BLE001
            continue
        lienzo.alpha_composite(t, (256 * i, 256 * j))
    from PIL import ImageEnhance
    rgb = lienzo.convert("RGB")
    if estilo == "satelite":  # mas luz y color natural: la imagen de los Andes sale oscura a poco zoom
        rgb = ImageEnhance.Contrast(ImageEnhance.Color(ImageEnhance.Brightness(rgb).enhance(1.12)).enhance(1.18))\
            .enhance(1.06)
    img = np.asarray(rgb)
    # recorte exacto y paso de Mercator a grilla regular de latitud (para dibujar en grados)
    # a la resolucion nativa de los tiles (antes 600 px fijos: el mapa salia borroso en las laminas 4K)
    alto_nat = (_a_tile(lat0, lon0, z)[1] - _a_tile(lat1, lon0, z)[1]) * 256
    alto_px = int(min(2600, max(900, alto_nat)))
    ancho_px = max(300, int(alto_px * (lon1 - lon0) / (lat1 - lat0) * math.cos(math.radians((lat0 + lat1) / 2))))
    lons = np.linspace(lon0, lon1, ancho_px)
    lats = np.linspace(lat1, lat0, alto_px)
    px = ((np.array([_a_tile(lat1, lo, z)[0] for lo in lons]) - tx[0]) * 256).clip(0, img.shape[1] - 1)
    py = ((np.array([_a_tile(la, lon0, z)[1] for la in lats]) - ty[0]) * 256).clip(0, img.shape[0] - 1)
    escalado = img[py.astype(int)][:, px.astype(int)]
    return escalado, (lon0, lon1, lat0, lat1), atribucion


def poner_fondo(ax, estilo: str = "satelite") -> bool:
    """Pone el mapa base bajo lo ya dibujado en ax (usa los limites actuales). Devuelve True si pudo."""
    lon0, lon1 = ax.get_xlim()
    lat0, lat1 = ax.get_ylim()
    m = mosaico(lon0, lon1, lat0, lat1, estilo)
    if m is None and estilo != "relieve":  # si falla el satelite, intenta el relieve
        m = mosaico(lon0, lon1, lat0, lat1, "relieve")
    if m is None:
        return False
    img, extent, atribucion = m
    ax.imshow(img, extent=extent, origin="upper", zorder=0, interpolation="bilinear", aspect="auto")
    ax.set_xlim(lon0, lon1)
    ax.set_ylim(lat0, lat1)
    ax.text(0.995, 0.005, atribucion, transform=ax.transAxes, ha="right", va="bottom", fontsize=8,
            color="white", bbox=dict(boxstyle="square,pad=0.2", fc="black", ec="none", alpha=0.45), zorder=10)
    return True

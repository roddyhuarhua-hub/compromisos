"""Centro y zoom de los mapas (una zona o varias regiones del pais)."""
from __future__ import annotations

import math

import pandas as pd


def encuadre(lat: pd.Series, lon: pd.Series, ancho_px: int = 900, alto_px: int = 470) -> tuple[dict, float]:
    """Centro y zoom para que entren todos los puntos (una zona o varias regiones del pais)."""
    lat, lon = lat.dropna(), lon.dropna()
    if lat.empty:
        return dict(lat=-14.15, lon=-72.8), 8.6
    d_lon = max(lon.max() - lon.min(), 0.25) * 1.5
    d_lat = max(lat.max() - lat.min(), 0.25) * 1.5
    z = min(math.log2(360 * ancho_px / 256 / d_lon), math.log2(170 * alto_px / 256 / d_lat)) - 0.3
    return dict(lat=float((lat.max() + lat.min()) / 2), lon=float((lon.max() + lon.min()) / 2)), \
        max(4.3, min(9.0, z))

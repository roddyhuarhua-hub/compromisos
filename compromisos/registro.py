"""Registro de compromisos: tabla con estados, alertas y exportacion."""
from __future__ import annotations

import uuid
from datetime import date

import pandas as pd

from .modelos import ExtraccionReunion

COLUMNAS = [
    "id", "reunion", "fecha_reunion", "comunidad", "distrito", "region",
    "descripcion", "responsable", "responsable_detalle", "beneficiario", "tema",
    "fecha_limite", "riesgo_conflicto", "cumplido", "fecha_cumplimiento",
    "cita_textual", "fuente",
    "depende_de",  # si el compromiso espera una entrega de la otra parte (estudio, permiso, padron)
]

DIAS_ALERTA = 30
ORDEN_ESTADO = ["Vencido", "Por vencer", "En plazo", "Sin plazo", "Cumplido"]


def vacio() -> pd.DataFrame:
    return normalizar(pd.DataFrame(columns=COLUMNAS))


def normalizar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in COLUMNAS:
        if c not in df.columns:
            df[c] = None
    for c in ["fecha_reunion", "fecha_limite", "fecha_cumplimiento"]:
        df[c] = pd.to_datetime(df[c], errors="coerce").dt.date
    df["cumplido"] = (
        df["cumplido"].astype(str).str.lower().isin(["true", "1", "si", "sí", "yes"])
    )
    texto = [c for c in COLUMNAS if c not in
             ("fecha_reunion", "fecha_limite", "fecha_cumplimiento", "cumplido")]
    df[texto] = df[texto].fillna("").astype(str)
    return df[COLUMNAS]


def cargar(ruta_o_archivo) -> pd.DataFrame:
    return normalizar(pd.read_csv(ruta_o_archivo, dtype=str, keep_default_na=False))


def estado(fila, hoy: date) -> str:
    if fila["cumplido"]:
        return "Cumplido"
    limite = fila["fecha_limite"]
    if limite is None or pd.isna(limite):
        return "Sin plazo"
    dias = (limite - hoy).days
    if dias < 0:
        return "Vencido"
    if dias <= DIAS_ALERTA:
        return "Por vencer"
    return "En plazo"


def con_estado(df: pd.DataFrame, hoy: date | None = None) -> pd.DataFrame:
    hoy = hoy or date.today()
    df = df.copy()
    if df.empty:
        df["estado"] = pd.Series(dtype=str)
        df["dias_restantes"] = pd.Series(dtype="Int64")
        return df
    df["estado"] = df.apply(lambda f: estado(f, hoy), axis=1)
    df["dias_restantes"] = df["fecha_limite"].apply(
        lambda d: (d - hoy).days if d is not None and not pd.isna(d) else None
    ).astype("Int64")
    return df


def desde_extraccion(
    ext: ExtraccionReunion,
    reunion: str,
    fecha_reunion: date,
    comunidad: str = "",
    distrito: str = "",
    region: str = "",
    fuente: str = "",
) -> pd.DataFrame:
    filas = []
    for c in ext.compromisos:
        filas.append({
            "id": uuid.uuid4().hex[:8],
            "reunion": reunion,
            "fecha_reunion": fecha_reunion,
            "comunidad": comunidad,
            "distrito": distrito,
            "region": region,
            "descripcion": c.descripcion,
            "responsable": c.responsable,
            "responsable_detalle": c.responsable_detalle,
            "beneficiario": c.beneficiario,
            "tema": c.tema,
            "fecha_limite": c.fecha_limite,
            "riesgo_conflicto": c.riesgo_conflicto,
            "cumplido": False,
            "fecha_cumplimiento": None,
            "cita_textual": c.cita_textual,
            "fuente": fuente,
        })
    return normalizar(pd.DataFrame(filas, columns=COLUMNAS))


def indicadores(df: pd.DataFrame) -> dict:
    total = len(df)
    cuenta = df["estado"].value_counts() if total else pd.Series(dtype=int)
    cumplidos = int(cuenta.get("Cumplido", 0))
    vencidos = int(cuenta.get("Vencido", 0))
    exigibles = int(((df["estado"] == "Cumplido") | (df["estado"] == "Vencido")).sum()) if total else 0
    return {
        "total": total,
        "vencidos": vencidos,
        "por_vencer": int(cuenta.get("Por vencer", 0)),
        "cumplidos": cumplidos,
        "sin_plazo": int(cuenta.get("Sin plazo", 0)),
        "tasa_cumplimiento": cumplidos / exigibles if exigibles else None,
        "alto_riesgo_abiertos": int(
            ((df["riesgo_conflicto"] == "alto") & (df["estado"] != "Cumplido")).sum()
        ) if total else 0,
    }


def acta_markdown(ext: ExtraccionReunion, reunion: str, fecha_reunion: date, comunidad: str) -> str:
    """Ficha de la reunion lista para descargar y compartir con la comunidad."""
    lineas = [
        f"# Ficha de reunion: {reunion}",
        f"**Fecha:** {fecha_reunion:%d/%m/%Y}  ",
        f"**Comunidad:** {comunidad or '-'}  ",
        f"**Participantes:** {', '.join(ext.participantes) or '-'}",
        "",
        "## Resumen",
        ext.resumen,
        "",
        "## Compromisos",
        "| # | Compromiso | Responsable | Plazo | Riesgo |",
        "|---|---|---|---|---|",
    ]
    for i, c in enumerate(ext.compromisos, 1):
        plazo = c.fecha_limite.strftime("%d/%m/%Y") if c.fecha_limite else "sin plazo"
        resp = c.responsable + (f" ({c.responsable_detalle})" if c.responsable_detalle else "")
        lineas.append(f"| {i} | {c.descripcion} | {resp} | {plazo} | {c.riesgo_conflicto} |")
    if ext.temas_pendientes:
        lineas += ["", "## Temas sin acuerdo"] + [f"- {t}" for t in ext.temas_pendientes]
    lineas += ["", "_Generado con Compromisos. Revisar y validar con las partes antes de firmar._"]
    return "\n".join(lineas)

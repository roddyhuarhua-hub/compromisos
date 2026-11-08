"""Anticipar: lo que pidieron los gerentes entrevistados (docs/research/entrevista_1.md y entrevista_2.md).

- Detonantes y contexto: hechos que no son "sociales" pero frenan el dialogo (una denuncia ambiental,
  comercial o policial contra un comunero), el cambio de directiva que se viene, una norma en debate o
  un riesgo de seguridad para el personal.
- Mejores jugadas: "si haces esto, pasa esto". Prueba, actor por actor, cuanto bajaria el riesgo del
  proceso si se atiende lo que le preocupa, y ordena las acciones por su efecto.
- Tendencia: como evoluciono el riesgo mes a mes, para ver si el plan esta funcionando.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go

from . import actores as ac
from . import registro

COL_CONTEXTO = ["fecha", "proyecto", "comunidad", "tipo", "descripcion", "intensidad", "fuente"]
# tipo -> (icono, dias hacia atras en que cuenta, dias hacia adelante en que cuenta)
TIPOS_CONTEXTO = {
    "Denuncia ambiental": ("🌊", 90, 0),
    "Denuncia comercial": ("💼", 90, 0),
    "Denuncia policial": ("🚓", 90, 0),
    "Cambio de directiva": ("🗳️", 30, 150),
    "Norma o política en debate": ("📜", 180, 120),
    "Riesgo de seguridad": ("⚠️", 180, 0),
    "Otro detonante": ("📌", 90, 0),
}
INTENSIDAD_TXT = {1: "baja", 2: "media", 3: "alta"}


# ------------------------------------------------------------------ detonantes y contexto
def normalizar_contexto(df: pd.DataFrame, comunidades: pd.DataFrame | None = None) -> pd.DataFrame:
    df = df.copy()
    for c in COL_CONTEXTO:
        if c not in df:
            df[c] = None
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").dt.date
    df["intensidad"] = pd.to_numeric(df["intensidad"], errors="coerce").fillna(2).clip(1, 3).astype(int)
    for c in ("proyecto", "comunidad", "tipo", "descripcion", "fuente"):
        df[c] = df[c].fillna("").astype(str).str.strip()
    df.loc[~df["tipo"].isin(TIPOS_CONTEXTO), "tipo"] = "Otro detonante"
    if comunidades is not None and not comunidades.empty and "proyecto" in comunidades:
        de_com = dict(zip(comunidades["comunidad"], comunidades["proyecto"]))
        falta = (df["proyecto"] == "") & df["comunidad"].isin(de_com)
        df.loc[falta, "proyecto"] = df.loc[falta, "comunidad"].map(de_com)
    df = df.dropna(subset=["fecha"])
    return df[df["descripcion"] != ""][COL_CONTEXTO].sort_values("fecha", ascending=False).reset_index(drop=True)


def vigentes(contexto: pd.DataFrame | None, comunidad: str, proyecto: str, hoy: date) -> pd.DataFrame:
    """Hechos que hoy pesan sobre un proceso: los de su comunidad y los de todo su proyecto, dentro de
    la ventana de cada tipo (una denuncia pesa 3 meses; un cambio de directiva pesa desde 5 meses antes)."""
    if contexto is None or contexto.empty:
        return pd.DataFrame(columns=COL_CONTEXTO)
    if not proyecto:  # el proyecto del proceso se deduce de los hechos registrados en su comunidad
        de_com = contexto.loc[(contexto["comunidad"] == comunidad) & (contexto["proyecto"] != ""), "proyecto"]
        proyecto = de_com.iloc[0] if not de_com.empty else ""
    c = contexto[(contexto["comunidad"] == comunidad) |
                 ((contexto["comunidad"] == "") & (contexto["proyecto"] == proyecto) & (proyecto != ""))]
    if c.empty:
        return c

    def cuenta(r) -> bool:
        _, atras, adelante = TIPOS_CONTEXTO.get(r["tipo"], TIPOS_CONTEXTO["Otro detonante"])
        return hoy - timedelta(days=atras) <= r["fecha"] <= hoy + timedelta(days=adelante) and \
            (adelante > 0 or r["fecha"] <= hoy)
    return c[c.apply(cuenta, axis=1)]


def factor_contexto(contexto: pd.DataFrame | None, comunidad: str, proyecto: str, hoy: date,
                    maximo: float) -> tuple[float, str]:
    v = vigentes(contexto, comunidad, proyecto, hoy)
    if v.empty:
        return 0.0, "Sin denuncias, cambios de directiva ni hechos de contexto registrados en los últimos meses"
    pts = maximo * min(1, v["intensidad"].sum() / 6)
    partes = []
    for _, r in v.sort_values("intensidad", ascending=False).head(3).iterrows():
        cuando = (f"en {(r['fecha'] - hoy).days} días" if r["fecha"] > hoy else f"el {r['fecha']:%d/%m}")
        partes.append(f"{r['tipo'].lower()} {cuando}")
    return pts, f"{len(v)} hecho{'s' * (len(v) != 1)} que pueden frenar el diálogo: " + "; ".join(partes)


# ------------------------------------------------------------------ si haces esto, pasa esto
def mejores_jugadas(evaluar, proceso: pd.Series, p: pd.DataFrame, base: int, n: int = 3, **kw) -> tuple[pd.DataFrame, int | None]:
    """Prueba una accion por actor del proceso y la ordena por cuanto baja el riesgo.

    evaluar: funcion riesgos.evaluar con sus datos ya fijados (kw: partes, A, H, conf, reg, hoy, contexto).
    p: actores del proceso (riesgos.partes_con_postura). Si un actor dice en publico algo distinto de lo
    que dice en privado, la jugada es que lo exprese en publico; si no, que mejore un paso su postura."""
    filas = []
    for _, a in p.iterrows():
        privada = int(a.get("postura_privada", a["postura"]))
        doble = bool(a.get("doble_discurso", False)) and privada > a["postura"]
        if a["postura"] >= 2 or (a["influencia"] < 3 and a["rol"] not in ("Decide", "Puede vetar") and not doble):
            continue
        nueva = privada if doble else min(2, int(a["postura"]) + 1)
        r = evaluar(proceso, cambios_postura={a["nombre"]: nueva}, **kw)
        baja = base - r["puntos"]
        if baja <= 0:
            continue
        if doble:
            accion = "Crear condiciones para que exprese en público el apoyo que da en privado"
        elif a.get("preocupacion"):
            accion = f"Atender lo que le preocupa: {str(a['preocupacion']).rstrip('.').lower()}"
        else:
            accion = "Reunión directa para escuchar y acordar un siguiente paso"
        filas.append(dict(nombre=a["nombre"], rol=a["rol"], de=int(a["postura"]), a=nueva, accion=accion,
                          fondo=a.get("interes_fondo", "") or "", antes=base, despues=r["puntos"], baja=baja))
    jug = pd.DataFrame(filas, columns=["nombre", "rol", "de", "a", "accion", "fondo", "antes", "despues", "baja"])
    jug = jug.sort_values(["baja", "nombre"], ascending=[False, True]).head(n).reset_index(drop=True)
    combinado = evaluar(proceso, cambios_postura=dict(zip(jug["nombre"], jug["a"])), **kw)["puntos"] \
        if len(jug) > 1 else None
    return jug, combinado


def probabilidad(puntos: int) -> str:
    """Lectura en palabras del puntaje (no es una probabilidad estadistica)."""
    return ("muy probable" if puntos >= 75 else "probable" if puntos >= 60 else "posible" if puntos >= 35
            else "poco probable")


# ------------------------------------------------------------------ esta funcionando el plan?
def tendencia(evaluar, proceso: pd.Series, partes: pd.DataFrame, A: pd.DataFrame, H: pd.DataFrame,
              conf: pd.DataFrame, registro_bruto: pd.DataFrame, hoy: date, contexto: pd.DataFrame | None = None,
              meses: int = 6) -> pd.DataFrame:
    """Riesgo del proceso a fin de cada mes (y hoy), con lo que se sabia en esa fecha."""
    fechas = sorted({(pd.Timestamp(hoy) - pd.DateOffset(months=k) + pd.offsets.MonthEnd(0)).date()
                     for k in range(1, meses + 1)} | {hoy})
    filas = []
    for f in fechas:
        if f > hoy:
            continue
        h_f = H[H["fecha"] <= f] if not H.empty else H
        a_f = ac.al_corte(A, H, f) if not H.empty else A
        reg_f = registro_bruto[registro_bruto["fecha_reunion"].map(lambda d: pd.notna(d) and d <= f)]
        reg_f = registro.con_estado(reg_f, f)
        conf_f = conf[conf["fecha"] <= f] if not conf.empty else conf
        ctx_f = contexto[contexto["fecha"] <= f + timedelta(days=150)] if contexto is not None and \
            not contexto.empty else contexto
        r = evaluar(proceso, partes, a_f, h_f, conf_f, reg_f, f, contexto=ctx_f)
        filas.append(dict(fecha=f, puntos=r["puntos"], nivel=r["nivel"]))
    return pd.DataFrame(filas)


def figura_tendencia(t: pd.DataFrame, alto: int = 260) -> go.Figure:
    fig = go.Figure()
    # sin etiqueta en un punto pegado al siguiente (fin de mes y hoy), para que no se encimen
    fechas = list(pd.to_datetime(t["fecha"]))
    texto = [("" if i + 1 < len(fechas) and (fechas[i + 1] - f).days < 12 else str(v))
             for i, (f, v) in enumerate(zip(fechas, t["puntos"]))]
    for y0, y1, color in ((0, 35, "rgba(27,175,122,0.08)"), (35, 60, "rgba(237,161,0,0.10)"),
                          (60, 100, "rgba(208,59,59,0.08)")):
        fig.add_hrect(y0=y0, y1=y1, fillcolor=color, line_width=0, layer="below")
    fig.add_scatter(x=t["fecha"], y=t["puntos"], mode="lines+markers+text", text=texto,
                    textposition="top center", line=dict(color="#1f2a37", width=2.5),
                    marker=dict(size=9, color=["#d03b3b" if v >= 60 else "#eda100" if v >= 35 else "#1baf7a"
                                               for v in t["puntos"]], line=dict(color="white", width=1.5)),
                    hovertemplate="%{x|%d/%m/%Y}: %{y}/100<extra></extra>", showlegend=False)
    fig.update_yaxes(range=[0, 105], tickvals=[0, 35, 60, 100], gridcolor="#eef1f5", title="Riesgo")
    fig.update_xaxes(tickformat="%b %Y", gridcolor="#eef1f5")
    fig.update_layout(height=alto, margin=dict(l=10, r=10, t=20, b=10), plot_bgcolor="white",
                      paper_bgcolor="white", font=dict(family="Inter, Segoe UI, sans-serif", color="#5b6675"))
    return fig

"""Conflictividad historica del territorio: registro de eventos (bloqueos, paros, tomas, marchas...),
indicadores y graficos (mapa, cronologia, dias de paralizacion, motivos y relacion con los
compromisos incumplidos).

La estructura sigue los campos de los reportes de conflictos sociales de la Defensoria del Pueblo.
"""
from __future__ import annotations

import os
from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .actores import clave
from .modelos import ExtraccionEventos
from .visual import FONDOS, SEMAFORO, TINTA, TINTA_2, base
from .zoom import encuadre

COLUMNAS = ["fecha", "tipo", "titulo", "lugar", "comunidad", "lat", "lon", "convocantes", "demanda", "tema",
            "duracion_dias", "participantes", "intensidad", "hubo_violencia", "desenlace", "fuente"]
TIPO_COLOR = {
    "Bloqueo de vía": "#c2410c", "Paralización / paro": "#a32424", "Toma de instalaciones": "#7c3aed",
    "Enfrentamiento": "#111827", "Movilización / marcha": "#eda100", "Plantón": "#2a78d6",
    "Pronunciamiento / ultimátum": "#1baf7a", "Denuncia o queja formal": "#8a8984", "Otro": "#b8b8b4",
}
# medidas que paralizan la operacion o el transito
DE_FUERZA = ["Bloqueo de vía", "Paralización / paro", "Toma de instalaciones", "Enfrentamiento"]
TINTA_CLARA = "rgba(31,42,55,0.08)"


def normalizar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in COLUMNAS:
        if c not in df.columns:
            df[c] = None
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").dt.date
    for c in ("lat", "lon"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["duracion_dias"] = pd.to_numeric(df["duracion_dias"], errors="coerce").fillna(1).clip(lower=0).astype(int)
    df["participantes"] = pd.to_numeric(df["participantes"], errors="coerce")
    df["hubo_violencia"] = df["hubo_violencia"].astype(str).str.lower().isin(["true", "1", "sí", "si", "yes"])
    texto = ["tipo", "titulo", "lugar", "comunidad", "convocantes", "demanda", "tema", "intensidad", "desenlace",
             "fuente"]
    df[texto] = df[texto].fillna("").astype(str)
    df.loc[df["tipo"] == "", "tipo"] = "Otro"
    df = df.dropna(subset=["fecha"])
    return df[COLUMNAS].sort_values("fecha", ascending=False).reset_index(drop=True)


def desde_extraccion(ext: ExtraccionEventos, comunidades: pd.DataFrame, comunidad_def: str = "",
                     fuente: str = "IA (revisado)") -> pd.DataFrame:
    """Convierte lo que extrajo la IA en filas del registro. Ubica cada evento en su comunidad
    (o en la comunidad elegida) con un pequeño desplazamiento; la ubicacion exacta se corrige en la tabla."""
    coords = comunidades.set_index("comunidad")[["lat", "lon"]]
    filas = []
    rng = np.random.default_rng(len(ext.eventos))
    for e in ext.eventos:
        com = e.comunidad
        if com not in coords.index:  # nombre parecido: 'Pucara Alto' -> 'C.C. Pucará Alto'
            buscado = clave(com).replace("c.c. ", "")
            com = next((c for c in coords.index if buscado and buscado in clave(c)), comunidad_def)
        lat, lon = (coords.loc[com].values + rng.normal(0, 0.008, 2)) if com in coords.index else (None, None)
        filas.append({**e.model_dump(), "comunidad": com, "lat": lat, "lon": lon, "fuente": fuente})
    return normalizar(pd.DataFrame(filas, columns=COLUMNAS)) if filas else pd.DataFrame(columns=COLUMNAS)


def indicadores(df: pd.DataFrame, hoy: date) -> dict:
    fuerza = df[df["tipo"].isin(DE_FUERZA)]
    ultimo = df["fecha"].max() if not df.empty else None
    return {
        "eventos": len(df),
        "medidas_fuerza": len(fuerza),
        "dias_paralizacion": int(fuerza["duracion_dias"].sum()),
        "bloqueos": int((df["tipo"] == "Bloqueo de vía").sum()),
        "con_violencia": int(df["hubo_violencia"].sum()),
        "ultimo": ultimo,
        "dias_desde_ultimo": (hoy - ultimo).days if ultimo else None,
        "en_curso": int((df["desenlace"] == "En curso").sum()),
        "max_participantes": int(df["participantes"].max()) if df["participantes"].notna().any() else 0,
    }


def _tam(d: pd.DataFrame) -> pd.Series:
    return 11 + 6 * np.sqrt(d["duracion_dias"].clip(lower=0.5)) + 6 * d["hubo_violencia"]


# ------------------------------------------------------------------ graficos
def mapa(df: pd.DataFrame, comunidades: pd.DataFrame, fondo: str = "🛰️ Satélite", alto: int = 520) -> go.Figure:
    """Lugares donde ocurrieron los hechos: calor ponderado por dias de paralizacion + un punto por evento."""
    capas, atribucion, texto_oscuro = FONDOS.get(fondo, FONDOS["🛰️ Satélite"])
    d = df.dropna(subset=["lat", "lon"])
    fig = go.Figure()
    if not d.empty:
        fig.add_trace(go.Densitymap(
            lat=d["lat"], lon=d["lon"], z=1 + d["duracion_dias"], radius=38, opacity=0.65, showscale=False,
            colorscale=[[0, "rgba(250,178,25,0)"], [0.35, "#fab219"], [0.7, "#eb6834"], [1, "#a32424"]],
            hoverinfo="skip", name="Intensidad"))
    c = comunidades.dropna(subset=["lat", "lon"])
    fig.add_trace(go.Scattermap(
        lat=c["lat"], lon=c["lon"], mode="markers+text", name="Comunidad",
        marker=dict(size=9, color="#ffffff" if not texto_oscuro else TINTA, opacity=0.9),
        text=c["comunidad"].str.replace("C.C. ", "", regex=False), textposition="top center",
        textfont=dict(size=12, color="#ffffff" if not texto_oscuro else TINTA), hoverinfo="skip"))
    for tipo, color in TIPO_COLOR.items():
        s = d[d["tipo"] == tipo]
        if s.empty:
            continue
        fig.add_trace(go.Scattermap(
            lat=s["lat"], lon=s["lon"], mode="markers", name=tipo,
            marker=dict(size=_tam(s), color=color, opacity=0.92),
            customdata=np.stack([s["titulo"], s["fecha"].astype(str), s["lugar"], s["convocantes"], s["demanda"],
                                 s["duracion_dias"], s["desenlace"],
                                 np.where(s["hubo_violencia"], "Sí", "No")], axis=-1),
            hovertemplate=("<b>%{customdata[0]}</b><br>%{customdata[1]} · %{customdata[2]}"
                           "<br>Convocan: %{customdata[3]}<br>Demanda: %{customdata[4]}"
                           "<br>Duración: %{customdata[5]} días · Violencia: %{customdata[7]}"
                           "<br>Desenlace: %{customdata[6]}<extra></extra>")))
    ref = c if not c.empty else d
    centro, zoom = encuadre(ref["lat"], ref["lon"], alto_px=alto) if not ref.empty \
        else (dict(lat=-14.15, lon=-72.8), 8.6)
    fig.update_layout(
        map=dict(style=os.getenv("ESTILO_MAPA") or ("carto-positron" if not capas else "white-bg"),
                 center=centro, zoom=zoom,
                 layers=[dict(sourcetype="raster", source=[u], below="traces", sourceattribution=atribucion)
                         for u in capas]),
        height=alto, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=0.01, x=0.01, bgcolor="rgba(255,255,255,0.88)",
                    font=dict(size=11)))
    return fig


def cronologia(df: pd.DataFrame, hitos: pd.DataFrame | None = None, alto: int = 420) -> go.Figure:
    """La historia del territorio: cada evento en su fecha y comunidad (tamaño = dias, borde negro = violencia)."""
    d = df.copy()
    d["com"] = d["comunidad"].replace("", "Sin comunidad").str.replace("C.C. ", "", regex=False)
    orden = d.groupby("com").size().sort_values().index.tolist()
    fig = go.Figure()
    for tipo, color in TIPO_COLOR.items():
        s = d[d["tipo"] == tipo]
        if s.empty:
            continue
        fig.add_trace(go.Scatter(
            x=pd.to_datetime(s["fecha"]), y=s["com"], mode="markers", name=tipo,
            marker=dict(size=_tam(s), color=color, opacity=0.88,
                        line=dict(color=np.where(s["hubo_violencia"], "#111827", "white"),
                                  width=np.where(s["hubo_violencia"], 2.5, 1.2))),
            customdata=np.stack([s["titulo"], s["lugar"], s["duracion_dias"], s["desenlace"]], axis=-1),
            hovertemplate="<b>%{customdata[0]}</b><br>%{x|%d/%m/%Y} · %{customdata[1]}"
                          "<br>%{customdata[2]} días · %{customdata[3]}<extra></extra>"))
    fig.update_yaxes(categoryorder="array", categoryarray=orden, showgrid=True, gridcolor=TINTA_CLARA)
    fig.update_xaxes(showgrid=False)
    fig = base(fig, alto)
    fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.16, x=0), margin=dict(b=90))
    return fig


def por_anio(df: pd.DataFrame) -> go.Figure:
    d = df.assign(anio=pd.to_datetime(df["fecha"]).dt.year)
    t = d.pivot_table(index="anio", columns="tipo", values="titulo", aggfunc="count", fill_value=0)
    fig = go.Figure()
    for tipo, color in TIPO_COLOR.items():
        if tipo in t.columns:
            fig.add_trace(go.Bar(x=t.index.astype(str), y=t[tipo], name=tipo, marker_color=color,
                                 marker_line=dict(color="white", width=1.5),
                                 hovertemplate="%{x}: %{y} · " + tipo + "<extra></extra>"))
    dias = d[d["tipo"].isin(DE_FUERZA)].groupby("anio")["duracion_dias"].sum().reindex(t.index, fill_value=0)
    fig.add_trace(go.Scatter(x=t.index.astype(str), y=t.sum(axis=1), mode="text", showlegend=False,
                             text=[f"{n}" for n in t.sum(axis=1)], textposition="top center",
                             textfont=dict(size=12, color=TINTA), hoverinfo="skip"))
    fig.update_layout(barmode="stack", showlegend=False)
    fig.update_yaxes(showgrid=True, gridcolor=TINTA_CLARA, title=None, range=[0, t.sum(axis=1).max() * 1.18])
    fig.update_xaxes(showgrid=False, type="category",
                     ticktext=[f"{a}<br><span style='font-size:10px'>{v} días</span>" if v else str(a)
                               for a, v in dias.items()], tickvals=[str(a) for a in t.index])
    return base(fig, 320)


def dias_por_comunidad(df: pd.DataFrame) -> go.Figure:
    d = df[df["tipo"].isin(DE_FUERZA)].copy()
    d["com"] = d["comunidad"].replace("", "Sin comunidad").str.replace("C.C. ", "", regex=False)
    g = d.groupby("com").agg(dias=("duracion_dias", "sum"), medidas=("tipo", "count"),
                             violencia=("hubo_violencia", "sum")).sort_values("dias")
    fig = go.Figure(go.Bar(
        y=g.index, x=g["dias"], orientation="h", marker_color="#c2410c",
        text=[f"{dd} días · {m} medida{'s' * (m != 1)}" + (f" · {v} con violencia" if v else "")
              for dd, m, v in zip(g["dias"], g["medidas"], g["violencia"])],
        textposition="outside", cliponaxis=False, hovertemplate="%{y}: %{x} días<extra></extra>"))
    fig.update_xaxes(showgrid=True, gridcolor=TINTA_CLARA, range=[0, max(1, g["dias"].max()) * 2.7])
    return base(fig, 320)


def motivos(df: pd.DataFrame) -> go.Figure:
    g = df["tema"].replace("", "Otro").value_counts().sort_values()
    fig = go.Figure(go.Bar(y=g.index, x=g.values, orientation="h", marker_color="#2d4a33",
                           text=g.values, textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: %{x} eventos<extra></extra>"))
    fig.update_xaxes(showgrid=True, gridcolor=TINTA_CLARA, range=[0, g.max() * 1.12])
    return base(fig, 320)


def _ubicar_etiquetas(puntos: list[dict], x_rango, y_rango, ancho_px: int, alto_px: int) -> list[dict]:
    """Coloca cada etiqueta donde no choque con otras etiquetas ni con los puntos.

    Prueba posiciones alrededor del punto (arriba, abajo, a los lados y en diagonal, cada vez mas lejos)
    y se queda con la primera libre. Devuelve los desplazamientos en pixeles (ax, ay) para annotations."""
    def px(x, y):
        return ((x - x_rango[0]) / (x_rango[1] - x_rango[0]) * ancho_px,
                (y_rango[1] - y) / (y_rango[1] - y_rango[0]) * alto_px)

    ocupado = []  # cajas (x0, y0, x1, y1) en pixeles
    for p in puntos:
        cx, cy = px(p["x"], p["y"])
        r = p["r"] + 2
        ocupado.append((cx - r, cy - r, cx + r, cy + r))

    def choca(c):
        return any(not (c[2] < o[0] or c[0] > o[2] or c[3] < o[1] or c[1] > o[3]) for o in ocupado)

    salida = []
    for p in sorted(puntos, key=lambda q: (-q["y"], q["x"])):
        cx, cy = px(p["x"], p["y"])
        lineas = p["texto"].split("<br>")
        w = max(len(t) for t in lineas) * 7.0 + 8
        h = 15 * len(lineas) + 2
        r = p["r"]
        elegido = None
        for paso in (1, 1.6, 2.3, 3.1, 4.0):
            d = (r + 6) * paso
            for ax, ay in ((0, -(d + h / 2)), (0, d + h / 2), (d + w / 2, 0), (-(d + w / 2), 0),
                           (d * .8 + w / 2, -(d * .8 + h / 2)), (-(d * .8 + w / 2), -(d * .8 + h / 2)),
                           (d * .8 + w / 2, d * .8 + h / 2), (-(d * .8 + w / 2), d * .8 + h / 2)):
                bx, by = cx + ax, cy + ay
                caja = (bx - w / 2, by - h / 2, bx + w / 2, by + h / 2)
                if caja[0] < -20 or caja[2] > ancho_px + 20 or caja[1] < -10 or caja[3] > alto_px + 30:
                    continue
                if not choca(caja):
                    elegido = (ax, ay, caja)
                    break
            if elegido:
                break
        if elegido is None:  # sin espacio libre: arriba y que se note la flecha
            elegido = (0, -(r + 30 + h / 2), (cx - w / 2, cy - r - 30 - h, cx + w / 2, cy - r - 30))
        ax, ay, caja = elegido
        ocupado.append(caja)
        salida.append(dict(p, ax=ax, ay=ay, flecha=abs(ax) + abs(ay) > r + h / 2 + 14 + w / 2 * (ax != 0)))
    return salida


def relacion_compromisos(conf: pd.DataFrame, ind: pd.DataFrame, desde: date, alto: int = 470,
                         ancho_px: int = 900, proyectos: dict | None = None,
                         colores: dict | None = None) -> go.Figure:
    """¿Donde se incumple mas hay mas conflicto? Vencidos (x) vs medidas de protesta recientes (y).

    Las comunidades con los mismos valores comparten una sola etiqueta (nombres uno debajo de otro)
    y cada etiqueta se ubica donde no tape a otra. Si hay comunidades de varios proyectos (proyectos:
    comunidad -> proyecto), los puntos se pintan por proyecto o unidad, con su leyenda, para ubicar el ambito."""
    rec = conf[conf["fecha"] >= desde]
    g = rec.groupby("comunidad").agg(eventos=("tipo", "count"),
                                      dias=("duracion_dias", lambda s: int(s[rec.loc[s.index, "tipo"]
                                                                            .isin(DE_FUERZA)].sum())))
    d = ind.merge(g, left_on="comunidad", right_index=True, how="left").fillna({"eventos": 0, "dias": 0})
    d["corto"] = d["comunidad"].str.replace("C.C. ", "", regex=False)
    d["tam"] = 16 + 3 * np.sqrt(d["dias"])
    proyectos = proyectos or {}
    d["proyecto"] = d["comunidad"].map(proyectos).fillna("")
    por_proyecto = d["proyecto"].nunique() > 1
    if por_proyecto:
        orden = list(dict.fromkeys(list(colores or {}) + sorted(d["proyecto"].unique())))
        grupos = [(p, (colores or {}).get(p, TINTA_2), d[d["proyecto"] == p]) for p in orden]
    else:
        grupos = [(nivel, color, d[d["semaforo"] == nivel]) for nivel, color in SEMAFORO.items()]
    fig = go.Figure()
    for nombre, color, s in grupos:
        if s.empty:
            continue
        fig.add_trace(go.Scatter(
            x=s["vencidos"], y=s["eventos"], mode="markers", name=nombre,
            marker=dict(size=s["tam"], color=color, opacity=0.85, line=dict(color="white", width=2)),
            text=s["corto"], cliponaxis=False,
            customdata=np.stack([s["dias"], s["indice"], s["proyecto"], s["semaforo"]], axis=-1),
            hovertemplate="<b>%{text}</b> · %{customdata[2]}<br>Vencidos: %{x} · Eventos: %{y}<br>"
                          "Días de paralización: %{customdata[0]} · Índice: %{customdata[1]:.0f} "
                          "(%{customdata[3]})<extra></extra>"))
    color_de = {p: c for p, c, _ in grupos} if por_proyecto else {}
    x_max, y_max = max(1, d["vencidos"].max()), max(1, d["eventos"].max())
    x_rango = [-0.06 * x_max - 0.6, x_max * 1.12 + 0.6]
    y_rango = [-0.75, y_max * 1.18 + 0.6]
    if len(d) >= 3 and d["vencidos"].std() > 0:
        m, b = np.polyfit(d["vencidos"], d["eventos"], 1)
        xs = np.array([0, d["vencidos"].max()])
        fig.add_trace(go.Scatter(x=xs, y=m * xs + b, mode="lines", showlegend=False, hoverinfo="skip",
                                 line=dict(color=TINTA_2, dash="dot", width=1.5)))
        r = np.corrcoef(d["vencidos"], d["eventos"])[0, 1]
        fig.add_annotation(x=0.99, y=0.99, xref="paper", yref="paper", showarrow=False, xanchor="right",
                           yanchor="top", text=f"Correlación: <b>{r:.2f}</b>", font=dict(size=12, color=TINTA),
                           bgcolor="rgba(255,255,255,0.85)")
    # Una etiqueta por posicion: si varias comunidades caen en el mismo punto, sus nombres van juntos.
    puntos = []
    for (x, y), grupo in d.groupby(["vencidos", "eventos"]):
        nombres = sorted(grupo["corto"])
        texto = "<br>".join(nombres) if len(nombres) <= 3 else \
            "<br>".join(nombres[:2]) + f"<br>+{len(nombres) - 2} más"
        puntos.append(dict(x=float(x), y=float(y), texto=texto, r=float(grupo["tam"].max()) / 2,
                           color=color_de.get(grupo["proyecto"].iloc[0], TINTA)
                           if grupo["proyecto"].nunique() == 1 else TINTA))
    area_w, area_h = ancho_px - 80, alto - 70
    for p in _ubicar_etiquetas(puntos, x_rango, y_rango, area_w, area_h):
        fig.add_annotation(x=p["x"], y=p["y"], text=p["texto"], ax=p["ax"], ay=p["ay"], axref="pixel",
                           ayref="pixel", showarrow=True, arrowhead=0, arrowwidth=1,
                           arrowcolor="rgba(71,85,105,0.55)" if p["flecha"] else "rgba(0,0,0,0)",
                           standoff=p["r"] if p["flecha"] else 0, font=dict(size=11, color=p["color"]),
                           bgcolor="rgba(255,255,255,0.75)", borderpad=1, align="center")
    fig.update_xaxes(title="Compromisos vencidos sin cumplir", showgrid=True, gridcolor=TINTA_CLARA,
                     range=x_rango)
    fig.update_yaxes(title=f"Eventos de conflicto desde {desde:%Y}", showgrid=True, gridcolor=TINTA_CLARA,
                     range=y_rango, dtick=1)
    fig = base(fig, alto)
    if por_proyecto:  # leyenda arriba: un color por unidad o proyecto
        fig.update_layout(showlegend=True, margin=dict(t=46),
                          legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None,
                                      font=dict(size=12, color=TINTA), itemsizing="constant"))
    else:
        fig.update_layout(showlegend=False)
    return fig

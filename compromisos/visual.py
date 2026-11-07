"""Graficos y componentes visuales del panel ejecutivo (Plotly + HTML)."""
from __future__ import annotations

import os
import textwrap
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Paleta de ESTADO (fija, nunca se reutiliza para series): verde / ambar / rojo + azul y gris
COLOR_ESTADO = {
    "Vencido": "#d03b3b",
    "Por vencer": "#fab219",
    "En plazo": "#2a78d6",
    "Sin plazo": "#8a8984",
    "Cumplido": "#0ca30c",
}
ICONO_ESTADO = {"Vencido": "🔴", "Por vencer": "🟡", "En plazo": "🔵", "Sin plazo": "⚪", "Cumplido": "🟢"}
# Paleta categorica (orden fijo) para las partes
COLOR_PARTE = {"Empresa": "#2a78d6", "Estado": "#eb6834", "Comunidad": "#1baf7a", "Otro": "#8a8984"}
SEMAFORO = {"Crítico": "#d03b3b", "Atención": "#fab219", "Estable": "#0ca30c"}
TINTA = "#1f2a37"
TINTA_2 = "#5b6675"
GRID = "rgba(31,42,55,0.08)"

PESO_RIESGO = {"alto": 3, "medio": 2, "bajo": 1}
PESO_ESTADO = {"Vencido": 2.0, "Por vencer": 1.0, "En plazo": 0.3, "Sin plazo": 0.6, "Cumplido": 0.0}


def base(fig: go.Figure, alto: int = 340, titulo: str | None = None) -> go.Figure:
    fig.update_layout(
        height=alto,
        title=dict(text=titulo, x=0, xanchor="left", font=dict(size=15, color=TINTA)) if titulo else None,
        margin=dict(l=8, r=8, t=48 if titulo else 8, b=8),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, sans-serif", size=12, color=TINTA_2),
        legend=dict(orientation="h", yanchor="top", y=-0.1, x=0, title=None),
        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Inter, Segoe UI, sans-serif"),
    )
    fig.update_xaxes(showgrid=True, gridcolor=GRID, zeroline=False, linecolor=GRID)
    fig.update_yaxes(showgrid=False, zeroline=False, linecolor=GRID)
    return fig


# ------------------------------------------------------------------ indices
def indice_comunidades(df: pd.DataFrame, comunidades: pd.DataFrame) -> pd.DataFrame:
    """Indice de riesgo social 0-100 por comunidad: promedio de (peso del riesgo x peso del
    estado) de sus compromisos. Riesgo alto=3, medio=2, bajo=1; vencido=2, por vencer=1,
    sin plazo=0.6, en plazo=0.3, cumplido=0. Critico >40, atencion 25-40, estable <25."""
    d = df.copy()
    d["puntos"] = d["riesgo_conflicto"].map(PESO_RIESGO).fillna(2) * d["estado"].map(PESO_ESTADO).fillna(0)
    g = d.groupby("comunidad").agg(
        compromisos=("id", "count"),
        vencidos=("estado", lambda s: (s == "Vencido").sum()),
        por_vencer=("estado", lambda s: (s == "Por vencer").sum()),
        cumplidos=("estado", lambda s: (s == "Cumplido").sum()),
        reuniones=("reunion", "nunique"),
        ultima_reunion=("fecha_reunion", "max"),
        puntos=("puntos", "sum"),
    ).reset_index()
    exig = g["cumplidos"] + g["vencidos"]
    g["cumplimiento"] = (g["cumplidos"] / exig.where(exig > 0)).fillna(0)
    # 100 = todos sus compromisos son de riesgo alto y estan vencidos (3 x 2 = 6 puntos c/u)
    g["indice"] = (100 * g["puntos"] / (6 * g["compromisos"])).clip(upper=100).round(0)
    g["semaforo"] = pd.cut(g["indice"], [-1, 25, 40, 101], labels=["Estable", "Atención", "Crítico"]).astype(str)
    out = g.merge(comunidades, on="comunidad", how="left", suffixes=("", "_c"))
    return out.sort_values("indice", ascending=False)


# ------------------------------------------------------------------ mapa
ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services"
FONDOS = {
    # nombre: (capas raster de abajo hacia arriba, atribucion, texto oscuro?)
    "🛰️ Satélite": ([f"{ESRI}/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}",
                    f"{ESRI}/Reference/World_Boundaries_and_Places/MapServer/tile/{{z}}/{{y}}/{{x}}"],
                   "Imágenes © Esri, Maxar, Earthstar Geographics", False),
    "⛰️ Relieve": ([f"{ESRI}/World_Topo_Map/MapServer/tile/{{z}}/{{y}}/{{x}}"],
                  "Mapa topográfico © Esri, HERE, Garmin, USGS", True),
    "🗺️ Calles": ([], "© CARTO, © OpenStreetMap", True),
}


def mapa(ind: pd.DataFrame, reuniones: pd.DataFrame, alto: int = 470,
         fondo: str = "🛰️ Satélite") -> go.Figure:
    """Mapa de calor de reuniones + burbujas por comunidad coloreadas por semaforo,
    sobre imagen satelital, relieve o calles."""
    capas, atribucion, texto_oscuro = FONDOS.get(fondo, FONDOS["🛰️ Satélite"])
    satelite = not texto_oscuro
    fig = go.Figure()
    r = reuniones.dropna(subset=["lat", "lon"])
    if not r.empty:
        fig.add_trace(go.Densitymap(
            lat=r["lat"], lon=r["lon"], z=r["compromisos"], radius=45, opacity=0.7,
            colorscale=([[0, "rgba(134,182,239,0)"], [0.3, "#86b6ef"], [0.6, "#cde2fb"], [1, "#ffffff"]]
                        if satelite else
                        [[0, "rgba(42,120,214,0)"], [0.3, "#86b6ef"], [0.6, "#2a78d6"], [1, "#0d366b"]]),
            showscale=False, hoverinfo="skip", name="Intensidad de reuniones",
        ))
    c = ind.dropna(subset=["lat", "lon"])
    for nivel in ["Estable", "Atención", "Crítico"]:
        s = c[c["semaforo"] == nivel]
        if s.empty:
            continue
        fig.add_trace(go.Scattermap(
            lat=s["lat"], lon=s["lon"], mode="markers+text",
            marker=dict(size=14 + s["vencidos"].clip(upper=15) * 2.2, color=SEMAFORO[nivel], opacity=0.95),
            text=s["comunidad"].str.replace("C.C. ", "", regex=False), textposition="top center",
            textfont=dict(size=13, color=TINTA if texto_oscuro else "#ffffff",
                          weight=700 if satelite else 500),
            name=f"{nivel}",
            customdata=s[["comunidad", "indice", "vencidos", "por_vencer", "reuniones", "familias"]].values,
            hovertemplate=("<b>%{customdata[0]}</b><br>Índice de riesgo: %{customdata[1]:.0f}/100"
                           "<br>Vencidos: %{customdata[2]} · Por vencer: %{customdata[3]}"
                           "<br>Reuniones: %{customdata[4]} · Familias: %{customdata[5]}<extra></extra>"),
        ))
    centro = dict(lat=float(c["lat"].mean()), lon=float(c["lon"].mean())) if not c.empty else dict(lat=-14.15, lon=-72.8)
    fig.update_layout(
        map=dict(
            style=os.getenv("ESTILO_MAPA") or ("carto-positron" if not capas else "white-bg"),
            center=centro, zoom=8.6,
            layers=[dict(sourcetype="raster", source=[url], below="traces",
                         sourceattribution=atribucion) for url in capas],
        ),
        height=alto, margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=0.01, x=0.01, bgcolor="rgba(255,255,255,0.85)",
                    title=dict(text="Semáforo  ")),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ------------------------------------------------------------------ indicadores
def gauge(valor: float | None, alto: int = 230) -> go.Figure:
    v = 0 if valor is None else valor * 100
    color = SEMAFORO["Estable"] if v >= 75 else SEMAFORO["Atención"] if v >= 50 else SEMAFORO["Crítico"]
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=v, number=dict(suffix="%", valueformat=".0f", font=dict(size=40, color=TINTA)),
        gauge=dict(
            axis=dict(range=[0, 100], tickwidth=0, tickcolor="rgba(0,0,0,0)", tickfont=dict(size=10)),
            bar=dict(color=color, thickness=0.32), bgcolor="rgba(31,42,55,0.06)", borderwidth=0,
            steps=[dict(range=[0, 50], color="rgba(208,59,59,0.10)"),
                   dict(range=[50, 75], color="rgba(250,178,25,0.12)"),
                   dict(range=[75, 100], color="rgba(12,163,12,0.10)")],
            threshold=dict(line=dict(color=TINTA, width=2), thickness=0.8, value=80),
        ),
    ))
    fig.update_layout(height=alto, margin=dict(l=20, r=20, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Inter, Segoe UI, sans-serif"))
    return fig


def dona_estados(df: pd.DataFrame, orden: list[str], alto: int = 260) -> go.Figure:
    cuenta = df["estado"].value_counts().reindex(orden).dropna()
    fig = go.Figure(go.Pie(
        labels=cuenta.index, values=cuenta.values, hole=0.62, sort=False,
        marker=dict(colors=[COLOR_ESTADO[e] for e in cuenta.index], line=dict(color="white", width=2)),
        textinfo="value", textfont=dict(size=12, color="white"),
        hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
    ))
    fig.update_layout(
        height=alto, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
        showlegend=True, legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.05, font=dict(size=12)),
        annotations=[dict(text=f"<b>{int(cuenta.sum())}</b><br>total", showarrow=False,
                          font=dict(size=16, color=TINTA))],
        font=dict(family="Inter, Segoe UI, sans-serif"),
    )
    return fig


def quien_incumple(df: pd.DataFrame, orden: list[str]) -> go.Figure:
    g = df.groupby(["responsable", "estado"]).size().reset_index(name="n")
    tot = df.groupby("responsable").size()
    venc = df[df["estado"] == "Vencido"].groupby("responsable").size().reindex(tot.index, fill_value=0)
    orden_r = (venc / tot).sort_values().index.tolist()  # el que mas incumple, arriba
    fig = px.bar(g, y="responsable", x="n", color="estado", orientation="h", text="n",
                 color_discrete_map=COLOR_ESTADO, category_orders={"estado": orden, "responsable": orden_r[::-1]},
                 labels={"n": "Compromisos", "responsable": "", "estado": "Estado"})
    fig.update_traces(marker_line_width=2, marker_line_color="white", textposition="inside",
                      insidetextanchor="middle", textfont=dict(color="white", size=13))
    for r in orden_r:
        fig.add_annotation(x=tot[r], y=r, text=f"<b>{venc[r] / tot[r]:.0%}</b> vencido", showarrow=False,
                           xanchor="left", xshift=8, font=dict(size=13, color=COLOR_ESTADO["Vencido"]))
    fig = base(fig, 330, "¿Quién está incumpliendo?")
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, title=None),
                      margin=dict(l=8, r=110, t=80, b=8), bargap=0.35)
    fig.update_yaxes(tickfont=dict(size=14, color=TINTA))
    return fig


def calendario(df: pd.DataFrame, hoy: date, dias: int = 120) -> go.Figure:
    """Linea de tiempo: compromisos abiertos de los ultimos y proximos meses, por comunidad."""
    d = df[(df["estado"] != "Cumplido") & df["fecha_limite"].notna()].copy()
    d = d[(d["fecha_limite"] >= hoy - timedelta(days=240)) & (d["fecha_limite"] <= hoy + timedelta(days=dias))]
    d["fecha_limite"] = pd.to_datetime(d["fecha_limite"])
    d["comunidad_c"] = d["comunidad"].str.replace("C.C. ", "", regex=False)
    d["tam"] = d["riesgo_conflicto"].map({"alto": 16, "medio": 11, "bajo": 8})
    fig = px.scatter(d, x="fecha_limite", y="comunidad_c", color="estado", size="tam", size_max=16,
                     color_discrete_map=COLOR_ESTADO, category_orders={"estado": ["Vencido", "Por vencer", "En plazo"]},
                     hover_data={"descripcion": True, "responsable": True, "riesgo_conflicto": True,
                                 "tam": False, "comunidad_c": False, "fecha_limite": "|%d/%m/%Y"},
                     labels={"fecha_limite": "", "comunidad_c": "", "estado": "Estado",
                             "descripcion": "Compromiso", "responsable": "Responsable",
                             "riesgo_conflicto": "Riesgo"})
    fig.update_traces(marker=dict(line=dict(width=2, color="white"), opacity=0.9))
    fig.add_vline(x=pd.Timestamp(hoy).timestamp() * 1000, line_width=2, line_dash="dot", line_color=TINTA)
    fig.add_annotation(x=pd.Timestamp(hoy), y=1.02, yref="paper", text="Hoy", showarrow=False,
                       font=dict(color=TINTA, size=12))
    fig.update_yaxes(showgrid=True, gridcolor=GRID)
    return base(fig, 360, "Calendario de vencimientos (tamaño = riesgo)")


def calor_tema(df: pd.DataFrame) -> go.Figure:
    """Mapa de calor tema x comunidad de compromisos vencidos sin cumplir."""
    d = df[df["estado"] == "Vencido"].copy()
    d["comunidad_c"] = d["comunidad"].str.replace("C.C. ", "", regex=False)
    t = d.pivot_table(index="tema", columns="comunidad_c", values="id", aggfunc="count", fill_value=0)
    if t.empty:
        return base(go.Figure(), 300, "Sin compromisos vencidos")
    t = t.loc[t.sum(axis=1).sort_values().index]
    t = t[t.sum().sort_values(ascending=False).index]
    xs = [f"{'<br>'.join(textwrap.wrap(c, 14))}<br><b>{int(t[c].sum())}</b>" for c in t.columns]
    ys = [f"{i}  <b>{int(t.loc[i].sum())}</b>" for i in t.index]
    fig = go.Figure(go.Heatmap(
        z=t.values, x=xs, y=ys, xgap=4, ygap=4,
        colorscale=[[0, "#fbfbfa"], [0.01, "#fde2e1"], [0.5, "#ec835a"], [1, "#a32424"]],
        text=[[str(v) if v else "" for v in fila] for fila in t.values], texttemplate="%{text}",
        textfont=dict(size=14), customdata=[[[i, c] for c in t.columns] for i in t.index],
        hovertemplate="%{customdata[0]} · %{customdata[1]}: %{z} vencidos<extra></extra>", showscale=False,
    ))
    fig.update_xaxes(showgrid=False, tickangle=0, side="top", tickfont=dict(size=12, color=TINTA))
    fig.update_yaxes(tickfont=dict(size=13, color=TINTA))
    fig = base(fig, 120 + 38 * len(t), "¿Dónde y en qué temas se acumulan los incumplimientos?")
    fig.update_layout(margin=dict(l=8, r=8, t=120, b=30))
    fig.add_annotation(x=0.97, y=0, xref="paper", yref="paper", yanchor="top", yshift=-6, xanchor="right",
                       showarrow=False,
                       text="Compromisos vencidos. En negrita, el total por tema y por comunidad.",
                       font=dict(size=11, color=TINTA_2))
    return fig


def brecha(df: pd.DataFrame, hoy: date) -> go.Figure:
    """Acumulado mensual: compromisos que vencieron vs cumplidos (misma escala)."""
    d = df.copy()
    venc = pd.to_datetime(d.loc[d["fecha_limite"].notna() & (d["fecha_limite"] <= hoy), "fecha_limite"])
    cump = pd.to_datetime(d.loc[d["cumplido"] & d["fecha_cumplimiento"].notna(), "fecha_cumplimiento"])
    if venc.empty:
        return base(go.Figure(), 300)
    meses = pd.period_range(venc.min().to_period("M"), pd.Timestamp(hoy).to_period("M"), freq="M")
    a = venc.dt.to_period("M").value_counts().reindex(meses, fill_value=0).cumsum()
    b = cump.dt.to_period("M").value_counts().reindex(meses, fill_value=0).cumsum()
    x = meses.to_timestamp()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=a.values, name="Debían cumplirse", mode="lines",
                             line=dict(color="#8a8984", width=2, dash="dot")))
    fig.add_trace(go.Scatter(x=x, y=b.values, name="Cumplidos", mode="lines", fill="tonexty",
                             fillcolor="rgba(208,59,59,0.10)", line=dict(color=COLOR_ESTADO["Cumplido"], width=2)))
    fig.add_annotation(x=0.97, xref="paper", y=a.values[-1], text=f"<b>Brecha: {a.values[-1] - b.values[-1]}</b>",
                       showarrow=False, xanchor="right", xshift=-4, yshift=16,
                       font=dict(color=COLOR_ESTADO["Vencido"], size=12))
    fig.update_yaxes(showgrid=True, gridcolor=GRID, title=None)
    fig.update_layout(hovermode="x unified")
    return base(fig, 300, "Brecha de cumplimiento acumulada")

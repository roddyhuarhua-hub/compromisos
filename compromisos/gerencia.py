"""Lo que pidio la entrevista 3 (docs/research/entrevista_3.md).

- Vencidos por prioridad: "el que ya esta vencido es el que te va a venir a rondar". Cada vencido recibe una
  prioridad de atencion (1, 2 o 3), con un color fijo que se repite en las alertas, la tabla y el grafico, y un
  plazo sugerido para atenderlo.
- Glosario: los terminos de la app definidos en un solo lugar, en lenguaje de gerencia.
"""
from __future__ import annotations

from datetime import date, timedelta
from html import escape

import pandas as pd
import plotly.graph_objects as go

PRIORIDAD_COLOR = {1: "#d03b3b", 2: "#ef7d22", 3: "#d9a800"}
PRIORIDAD_TXT = {1: "Prioridad 1 · puede parar el proyecto", 2: "Prioridad 2 · atender pronto",
                 3: "Prioridad 3 · programar"}
PLAZO_DIAS = {1: 7, 2: 15, 3: 30}  # plazo sugerido para atender un vencido, segun su prioridad
ATRASO_LARGO = 90  # un vencido de riesgo bajo con mas de 3 meses sube a prioridad 2: la comunidad ya lo recuerda


def prioridad(riesgo: str, dias_atraso: int) -> int:
    """P1 = riesgo alto (agua, tierras, salud, empleo local): puede parar el proyecto. P2 = riesgo medio.
    P3 = riesgo bajo, salvo que lleve mas de 3 meses vencido. La prioridad 1 queda solo para lo critico."""
    base = {"alto": 1, "medio": 2}.get(str(riesgo).lower(), 3)
    return 2 if base == 3 and dias_atraso > ATRASO_LARGO else base


def priorizar(df: pd.DataFrame, hoy: date) -> pd.DataFrame:
    """Solo los vencidos, con su prioridad, dias de atraso y fecha sugerida para atenderlos."""
    v = df[df["estado"] == "Vencido"].copy()
    if v.empty:
        return v.assign(prioridad=pd.Series(dtype=int), dias_atraso=pd.Series(dtype=int),
                        atender_antes=pd.Series(dtype=object))
    v["dias_atraso"] = (-pd.to_numeric(v["dias_restantes"], errors="coerce").fillna(0)).astype(int)
    v["prioridad"] = [prioridad(r, d) for r, d in zip(v["riesgo_conflicto"], v["dias_atraso"])]
    v["atender_antes"] = v["prioridad"].map(lambda p: hoy + timedelta(days=PLAZO_DIAS[p]))
    return v.sort_values(["prioridad", "dias_atraso"], ascending=[True, False]).reset_index(drop=True)


def tabla_html(pr: pd.DataFrame) -> str:
    """Tabla comunidad x prioridad, con los mismos colores que las alertas."""
    if pr.empty:
        return ""
    t = pd.crosstab(pr["comunidad"].str.replace("C.C. ", "", regex=False), pr["prioridad"])
    t = t.reindex(columns=[1, 2, 3], fill_value=0)
    t = t.sort_values([1, 2, 3], ascending=False)
    cab = "".join(f'<th style="background:{PRIORIDAD_COLOR[p]};color:#fff;padding:5px 8px;font-weight:600">P{p}</th>'
                  for p in (1, 2, 3))
    filas = []
    for com, r in t.iterrows():
        celdas = "".join(
            f'<td style="text-align:center;padding:5px 8px;font-weight:{700 if r[p] else 400};'
            f'background:{PRIORIDAD_COLOR[p] + "26" if r[p] else "#fff"};color:{"#1f2a37" if r[p] else "#b7bfca"}">'
            f'{int(r[p])}</td>' for p in (1, 2, 3))
        filas.append(f'<tr><td style="padding:5px 8px">{escape(com)}</td>{celdas}</tr>')
    return ('<table style="width:100%;border-collapse:collapse;font-size:13px;background:#fff;border-radius:10px;'
            'overflow:hidden"><tr><th style="text-align:left;padding:5px 8px;color:#5b6675">Comunidad</th>'
            f'{cab}</tr>{"".join(filas)}</table>')


def figura_vencidos(pr: pd.DataFrame, hoy: date, alto: int = 340) -> go.Figure:
    """Cada vencido segun cuanto lleva de atraso, por comunidad y con el color de su prioridad."""
    fig = go.Figure()
    d = pr.copy()
    d["com"] = d["comunidad"].str.replace("C.C. ", "", regex=False)
    for p in (3, 2, 1):  # la prioridad 1 encima
        s = d[d["prioridad"] == p]
        if s.empty:
            continue
        fig.add_scatter(x=s["dias_atraso"], y=s["com"], mode="markers", name=f"Prioridad {p}",
                        marker=dict(size=15 if p == 1 else 12, color=PRIORIDAD_COLOR[p], opacity=0.92,
                                    line=dict(color="white", width=1.5)),
                        customdata=list(zip(s["descripcion"], s["atender_antes"].map(lambda f: f"{f:%d/%m}"))),
                        hovertemplate="%{customdata[0]}<br>%{x} días de atraso · atender antes del "
                                      "%{customdata[1]}<extra></extra>")
    fig.add_vline(x=ATRASO_LARGO, line_dash="dot", line_color="#9aa4b1")
    fig.add_annotation(x=ATRASO_LARGO, y=1.0, yref="paper", text="3 meses", showarrow=False, yshift=8,
                       font=dict(size=11, color="#5b6675"))
    fig.update_xaxes(title="Días de atraso", rangemode="tozero", gridcolor="#eef1f5")
    fig.update_yaxes(gridcolor="#eef1f5", categoryorder="category descending")
    fig.update_layout(height=alto, margin=dict(l=10, r=10, t=50, b=75), plot_bgcolor="white", paper_bgcolor="white",
                      title=dict(text="Vencidos por prioridad y días de atraso", x=0, font_size=15),
                      legend=dict(orientation="h", y=-0.3, yanchor="top", x=0, traceorder="reversed"),
                      font=dict(family="Inter, Segoe UI, sans-serif", color="#5b6675"))
    return fig


GLOSARIO = {
    "Compromiso": "Lo que una parte (empresa, Estado o comunidad) se obligó a hacer en una reunión o acta, "
                  "con un plazo.",
    "Vencido": "Compromiso cuyo plazo ya pasó y no se cumplió. Es el que la comunidad recordará cuando la "
               "empresa pida algo.",
    "Por vencer": "Compromiso que vence en los próximos 30 días. Todavía está dentro de la programación.",
    "Prioridad de atención (P1, P2, P3)": "Orden para atender los vencidos. P1 = riesgo alto, puede parar el "
                                          "proyecto: atender en 7 días. P2 = riesgo medio, 15 días. P3 = riesgo "
                                          "bajo, 30 días (sube a P2 si lleva más de 3 meses vencido).",
    "Riesgo de conflicto (de un compromiso)": "Alto si toca agua, tierras, salud o empleo local; medio o bajo en "
                                              "los demás temas.",
    "Semáforo de la comunidad": "Índice de 0 a 100 que suma los vencidos (pesados por su riesgo) de la comunidad.",
    "Postura": "Qué tan a favor o en contra de la empresa está un actor: −2 opositor, −1 crítico, 0 neutral, "
               "+1 favorable, +2 aliado. Se registra la que dice en público y la que dice en privado.",
    "Influencia": "Capacidad de un actor de mover a otros o de decidir, de 1 (poca) a 5 (mucha).",
    "Interés de fondo": "El motivo real de un actor que no está escrito (un agravio antiguo, una elección "
                        "próxima). Información reservada del equipo.",
    "Proceso clave": "Un hito que la empresa necesita sacar adelante: una servidumbre, un convenio, un monitoreo.",
    "Riesgo de paralización": "Puntaje de 0 a 100 de qué tan probable es que un proceso clave se frene. Bajo hasta "
                              "35, medio hasta 60, alto desde 60. Es una guía para conversar, no una predicción.",
    "Detonante": "Hecho no social que puede frenar el diálogo: una denuncia ambiental, comercial o policial, "
                 "un cambio de directiva, una norma en debate o un riesgo de seguridad.",
    "Validado": "Hecho confirmado por el equipo. Lo que llega por rumor o por una sola fuente no sube el riesgo "
                "hasta validarlo.",
    "Jugada": "Acción sobre un actor que la app prueba antes de hacerla: cuánto bajaría el riesgo si se logra.",
}

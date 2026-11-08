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
ATRASO_LARGO = 90  # un vencido con mas de 3 meses suma: ya es una deuda que la comunidad recuerda
DE_FUERZA = ["Bloqueo de vía", "Paralización / paro", "Toma de instalaciones", "Enfrentamiento"]
PUNTOS_RIESGO = {"alto": 3, "medio": 2, "bajo": 1}


# ------------------------------------------------------------------ poder de cada comunidad para paralizar
def poder_comunidades(A: pd.DataFrame | None, conf: pd.DataFrame | None, hoy: date, anios: int = 5) -> pd.DataFrame:
    """Que tan capaz es cada comunidad de paralizar si se le incumple (0 a 1).

    Mitad por sus actores: opositores o criticos con influencia (se usa lo que dicen en publico, porque eso es
    lo que convoca). Mitad por su historia: medidas de fuerza y dias de paralizacion de los ultimos 5 anios.
    Un mismo vencido pesa mas donde hay dirigentes con poder de convocatoria y antecedentes de paro."""
    filas = {}
    if A is not None and not A.empty:
        a = A.copy()
        pub = pd.to_numeric(a.get("postura_publica", pd.Series("", index=a.index)), errors="coerce")
        a["post"] = pub.fillna(pd.to_numeric(a["postura"], errors="coerce")).fillna(0)
        a["influencia"] = pd.to_numeric(a["influencia"], errors="coerce").fillna(1)
        op = a[(a["post"] < 0) & (a["comunidad"].fillna("") != "")]
        for com, g in op.groupby("comunidad"):
            g = g.assign(fuerza=g["influencia"] * -g["post"]).sort_values("fuerza", ascending=False)
            filas.setdefault(com, {})["fuerza_op"] = g["fuerza"].sum()
            filas[com]["opositores"] = list(g.loc[g["influencia"] >= 3, "nombre"])
    if conf is not None and not conf.empty:
        c = conf[(conf["tipo"].isin(DE_FUERZA)) & (conf["fecha"] >= hoy - timedelta(days=365 * anios)) &
                 (conf["fecha"] <= hoy)]
        for com, g in c.groupby("comunidad"):
            filas.setdefault(com, {}).update(medidas=len(g), dias=int(g["duracion_dias"].sum()))
    res = []
    for com, f in filas.items():
        actores_ = min(1.0, f.get("fuerza_op", 0) / 15)
        historia = min(1.0, (f.get("medidas", 0) + f.get("dias", 0) / 5) / 4)
        res.append(dict(comunidad=com, poder=round(0.5 * actores_ + 0.5 * historia, 2),
                        opositores=f.get("opositores", []), medidas=f.get("medidas", 0), dias=f.get("dias", 0)))
    out = pd.DataFrame(res, columns=["comunidad", "poder", "opositores", "medidas", "dias"])
    out["nivel_poder"] = out["poder"].map(nivel_poder)
    out["motivo"] = out.apply(_motivo, axis=1)
    return out.sort_values("poder", ascending=False).reset_index(drop=True)


def nivel_poder(p: float) -> str:
    return "alto" if p >= 0.6 else "medio" if p >= 0.3 else "bajo"


def _motivo(r) -> str:
    partes = []
    n = len(r["opositores"])
    if n:
        nombres = ", ".join(r["opositores"][:2]) + (" y otros" if n > 2 else "")
        partes.append(f"{n} opositor{'es' * (n != 1)} influyente{'s' * (n != 1)} ({nombres})")
    if r["medidas"]:
        partes.append(f"{r['medidas']} medida{'s' * (r['medidas'] != 1)} de fuerza y {r['dias']} "
                      f"día{'s' * (r['dias'] != 1)} de paralización en 5 años")
    return " · ".join(partes) or "sin opositores influyentes ni paralizaciones recientes"


# ------------------------------------------------------------------ prioridad de cada vencido
def puntaje(riesgo: str, dias_atraso: int, poder: float = 0.5) -> float:
    """Riesgo del tema (1 a 3) + poder de la comunidad para paralizar (0 a 2) + 0,5 si lleva mas de 3 meses."""
    return PUNTOS_RIESGO.get(str(riesgo).lower(), 1) + 2 * poder + (0.5 if dias_atraso > ATRASO_LARGO else 0)


def prioridad(riesgo: str, dias_atraso: int, poder: float = 0.5) -> int:
    """P1 desde 4 puntos, P2 desde 2,75. Un tema de riesgo alto en una comunidad sin poder de convocatoria ni
    historia de paro queda en P2; un tema medio donde hay dirigentes que ya paralizaron sube a P1."""
    p = puntaje(riesgo, dias_atraso, poder)
    return 1 if p >= 4 else 2 if p >= 2.75 else 3


def priorizar(df: pd.DataFrame, hoy: date, poder: pd.DataFrame | None = None) -> pd.DataFrame:
    """Solo los vencidos, con su prioridad, dias de atraso, el poder de su comunidad y fecha para atenderlos.
    Sin datos de poder, cada comunidad cuenta como de poder medio."""
    v = df[df["estado"] == "Vencido"].copy()
    if v.empty:
        return v.assign(prioridad=pd.Series(dtype=int), dias_atraso=pd.Series(dtype=int), poder=pd.Series(dtype=float),
                        puntaje=pd.Series(dtype=float), motivo_poder="", atender_antes=pd.Series(dtype=object))
    v["dias_atraso"] = (-pd.to_numeric(v["dias_restantes"], errors="coerce").fillna(0)).astype(int)
    if poder is not None and not poder.empty:
        pw = poder.set_index("comunidad")
        v["poder"] = v["comunidad"].map(pw["poder"]).fillna(0.0)
        v["motivo_poder"] = v["comunidad"].map(pw["motivo"]).fillna(
            "sin opositores influyentes ni paralizaciones recientes")
    else:
        v["poder"], v["motivo_poder"] = 0.5, ""
    v["puntaje"] = [puntaje(r, d, p) for r, d, p in zip(v["riesgo_conflicto"], v["dias_atraso"], v["poder"])]
    v["prioridad"] = [prioridad(r, d, p) for r, d, p in zip(v["riesgo_conflicto"], v["dias_atraso"], v["poder"])]
    v["atender_antes"] = v["prioridad"].map(lambda p: hoy + timedelta(days=PLAZO_DIAS[p]))
    return v.sort_values(["prioridad", "puntaje", "dias_atraso"], ascending=[True, False, False]).reset_index(drop=True)


def tabla_html(pr: pd.DataFrame) -> str:
    """Tabla comunidad x prioridad, con los mismos colores que las alertas y el poder de cada comunidad."""
    if pr.empty:
        return ""
    t = pd.crosstab(pr["comunidad"], pr["prioridad"]).reindex(columns=[1, 2, 3], fill_value=0)
    poder = pr.groupby("comunidad")["poder"].first() if "poder" in pr else pd.Series(0.5, index=t.index)
    t["poder"] = poder.reindex(t.index).fillna(0)
    t = t.sort_values([1, "poder", 2, 3], ascending=False)
    color_poder = {"alto": "#d03b3b", "medio": "#ef7d22", "bajo": "#1baf7a"}
    cab = "".join(f'<th style="background:{PRIORIDAD_COLOR[p]};color:#fff;padding:5px 8px;font-weight:600">P{p}</th>'
                  for p in (1, 2, 3))
    filas = []
    for com, r in t.iterrows():
        celdas = "".join(
            f'<td style="text-align:center;padding:5px 8px;font-weight:{700 if r[p] else 400};'
            f'background:{PRIORIDAD_COLOR[p] + "26" if r[p] else "#fff"};color:{"#1f2a37" if r[p] else "#b7bfca"}">'
            f'{int(r[p])}</td>' for p in (1, 2, 3))
        nv = nivel_poder(r["poder"])
        filas.append(f'<tr><td style="padding:5px 8px">{escape(com.replace("C.C. ", ""))}</td>'
                     f'<td style="padding:5px 8px;color:{color_poder[nv]};font-weight:600">{nv}</td>{celdas}</tr>')
    return ('<table style="width:100%;border-collapse:collapse;font-size:13px;background:#fff;border-radius:10px;'
            'overflow:hidden"><tr><th style="text-align:left;padding:5px 8px;color:#5b6675">Comunidad</th>'
            f'<th style="text-align:left;padding:5px 8px;color:#5b6675">Poder</th>{cab}</tr>{"".join(filas)}</table>')


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
                        customdata=list(zip(s["descripcion"], s["atender_antes"].map(lambda f: f"{f:%d/%m}"),
                                            s["riesgo_conflicto"],
                                            s.get("poder", pd.Series(0.5, index=s.index)).map(nivel_poder))),
                        hovertemplate="%{customdata[0]}<br>%{x} días de atraso · tema de riesgo %{customdata[2]} · "
                                      "poder de la comunidad %{customdata[3]}<br>Atender antes del "
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
    "Prioridad de atención (P1, P2, P3)": "Orden para atender los vencidos. No basta el tiempo de atraso: pesa "
                                          "el tema (agua, tierras, salud y empleo son riesgo alto) y el poder de la "
                                          "comunidad para paralizar. P1: atender en 7 días. P2: 15 días. P3: 30 días.",
    "Poder de la comunidad": "Qué tan capaz es una comunidad de paralizar si se le incumple: la mitad por sus "
                             "dirigentes opositores con influencia (lo que dicen en público) y la mitad por sus "
                             "medidas de fuerza y días de paralización de los últimos 5 años.",
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

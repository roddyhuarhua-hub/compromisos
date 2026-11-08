"""Ruta para bajar el riesgo: que actor abordar primero, como, y en cuanto tiempo puede cambiar el escenario.

Es el valor en el que coincidieron los entrevistados: no basta saber que el riesgo es alto, hay que saber que
camino tomar. La ruta prueba, paso a paso, la accion que mas baja el riesgo dado lo ya logrado (un actor puede
aparecer dos veces: primero de opositor a critico y luego a neutral), y suma el tiempo que suele tomar cada paso.

Los tiempos son una referencia de campo, no una prediccion (entrevista 1: un opositor que asume un cargo cambia
de opinion en 6 a 8 meses, es decir unos 3 meses por paso de postura). El equipo los ajusta con su criterio.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

# meses que suele tomar mover un paso de postura publica, segun desde donde parte el actor
MESES_PASO = {-2: 3.0, -1: 2.0, 0: 2.0, 1: 2.0}
MESES_DOBLE = 1.0  # que diga en publico lo que ya dice en privado
OBJETIVO = 35  # bajo este puntaje el riesgo es bajo


def meses_paso(postura: int, doble: bool, interes_fondo: str = "") -> float:
    m = MESES_DOBLE if doble else MESES_PASO.get(int(postura), 2.0)
    if not doble and any(k in str(interes_fondo).lower() for k in ("agravio", "orgullo", "reconocimiento")):
        m += 1.0  # un agravio antiguo se resuelve con reconocimiento, y eso toma tiempo
    return m


def como_abordar(a: pd.Series, puentes: list[str], doble: bool) -> str:
    """Guia corta para el relacionista: por quien entrar, que atender y que evitar."""
    partes = []
    if puentes:
        partes.append(f"Entrar a través de {', '.join(puentes[:2])}")
    else:
        partes.append("Reunión directa, sin intermediarios, primero en privado")
    if doble:
        partes.append("no exponerlo en asamblea antes de que tenga algo que mostrar a su base")
    elif a.get("preocupacion"):
        partes.append(f"atender: {str(a['preocupacion']).rstrip('.').lower()}")
    fondo = str(a.get("interes_fondo", "") or "")
    if any(k in fondo.lower() for k in ("agravio", "orgullo", "reconocimiento")):
        partes.append("reconocer el agravio en público antes de ofrecer algo material")
    elif fondo:
        partes.append(f"de fondo: {fondo[0].lower() + fondo[1:]}")
    return "; ".join(partes) + "."


def ruta(evaluar, proceso: pd.Series, p: pd.DataFrame, base: int, puentes_de=None, pasos: int = 5,
         **kw) -> pd.DataFrame:
    """Secuencia de pasos que mas baja el riesgo, con el tiempo acumulado.

    evaluar: riesgos.evaluar con sus datos fijados en kw (partes, A, H, conf, reg, hoy, contexto).
    p: actores del proceso (riesgos.partes_con_postura). puentes_de: funcion nombre -> lista de actores puente."""
    cambios: dict[str, int] = {}
    actual = {a["nombre"]: int(a["postura"]) for _, a in p.iterrows()}
    privada = {a["nombre"]: int(a.get("postura_privada", a["postura"])) for _, a in p.iterrows()}
    info = p.set_index("nombre")
    filas, riesgo, meses = [], base, 0.0
    for _ in range(pasos):
        if riesgo < OBJETIVO:
            break
        mejor = None
        for nombre, post in actual.items():
            a = info.loc[nombre]
            if post >= 2 or (a["influencia"] < 3 and a["rol"] not in ("Decide", "Puede vetar")):
                continue
            doble = bool(a.get("doble_discurso", False)) and privada[nombre] > post and nombre not in cambios
            nueva = privada[nombre] if doble else post + 1
            r = evaluar(proceso, cambios_postura={**cambios, nombre: nueva}, **kw)["puntos"]
            baja = riesgo - r
            m = meses_paso(post, doble, a.get("interes_fondo", ""))
            # la mejor relacion entre lo que baja y lo que demora
            if baja > 0 and (mejor is None or baja / m > mejor[0]):
                mejor = (baja / m, nombre, post, nueva, r, baja, m, doble)
        if mejor is None:
            break
        _, nombre, post, nueva, r, baja, m, doble = mejor
        a = info.loc[nombre]
        meses += m
        cambios[nombre] = nueva
        actual[nombre] = nueva
        filas.append(dict(paso=len(filas) + 1, nombre=nombre, rol=a["rol"], de=post, a=nueva, doble=doble,
                          como=como_abordar(a, puentes_de(nombre) if puentes_de else [], doble),
                          meses=m, mes_acum=meses, riesgo_antes=riesgo, riesgo=r, baja=baja))
        riesgo = r
    return pd.DataFrame(filas, columns=["paso", "nombre", "rol", "de", "a", "doble", "como", "meses", "mes_acum",
                                        "riesgo_antes", "riesgo", "baja"])


def meses_a_objetivo(rt: pd.DataFrame, base: int, umbral: int = 60) -> float | None:
    """Meses hasta salir de riesgo alto (o del umbral pedido) siguiendo la ruta."""
    if base < umbral:
        return 0.0
    ok = rt[rt["riesgo"] < umbral]
    return float(ok.iloc[0]["mes_acum"]) if not ok.empty else None


def figura_ruta(rt: pd.DataFrame, base: int, alto: int = 300) -> go.Figure:
    """Escalera del riesgo: cuanto baja con cada paso y en que mes."""
    xs = [0] + list(rt["mes_acum"])
    ys = [base] + list(rt["riesgo"])
    fig = go.Figure()
    for y0, y1, color in ((0, 35, "rgba(27,175,122,0.08)"), (35, 60, "rgba(237,161,0,0.10)"),
                          (60, 100, "rgba(208,59,59,0.08)")):
        fig.add_hrect(y0=y0, y1=y1, fillcolor=color, line_width=0, layer="below")
    fig.add_scatter(x=xs, y=ys, mode="lines+markers+text", line=dict(color="#1f2a37", width=2.5, shape="hv"),
                    text=[str(v) for v in ys], textposition="top right",
                    marker=dict(size=10, color=["#d03b3b" if v >= 60 else "#eda100" if v >= 35 else "#1baf7a"
                                                for v in ys], line=dict(color="white", width=1.5)),
                    customdata=["Hoy"] + [f"Paso {int(r.paso)}: {r.nombre}" for r in rt.itertuples()],
                    hovertemplate="%{customdata}<br>Mes %{x:.0f}: riesgo %{y}<extra></extra>", showlegend=False)
    fig.update_yaxes(range=[0, 105], tickvals=[0, 35, 60, 100], gridcolor="#eef1f5", title="Riesgo")
    fig.update_xaxes(title="Meses desde hoy", gridcolor="#eef1f5", dtick=2, range=[-0.5, max(xs) + 2])
    fig.update_layout(height=alto, margin=dict(l=10, r=10, t=20, b=10), plot_bgcolor="white", paper_bgcolor="white",
                      font=dict(family="Inter, Segoe UI, sans-serif", color="#5b6675"))
    return fig

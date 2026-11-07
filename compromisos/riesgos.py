"""Riesgos y decisiones: para cada proceso clave (una servidumbre, un contrato local, un monitoreo...)
estima el riesgo de paralizacion a partir de lo que la herramienta ya sabe (actores, conflictos y
compromisos), identifica a quien puede frenarlo y simula escenarios antes de decidir.

El puntaje es una guia transparente para conversar en el equipo, no una prediccion: cada punto se
explica con un dato que se puede revisar.
"""
from __future__ import annotations

import textwrap
from datetime import date

import networkx as nx
import pandas as pd
import plotly.graph_objects as go

from . import actores as ac
from .conflictos import DE_FUERZA

COL_PROCESOS = ["id", "proceso", "tipo", "comunidad", "hito", "fecha_limite", "impacto", "si_se_paraliza",
                "responsable", "estado", "fuente"]
COL_PARTES = ["proceso_id", "nombre", "rol", "interes", "preocupacion"]
COL_ESCENARIOS = ["proceso_id", "escenario", "nombre", "postura_nueva", "motivo"]
COL_ACCIONES = ["proceso_id", "nombre", "estrategia", "accion", "responsable", "fecha", "estado"]
ROLES = ["Decide", "Puede vetar", "Influye", "Afectado"]
PESO_ROL = {"Decide": 1.5, "Puede vetar": 1.5, "Influye": 1.0, "Afectado": 0.7}
ESTRATEGIAS = ["Atender sus preocupaciones de cerca", "Involucrar y consultar", "Colaborar", "Informar y escuchar",
               "Mantener informado"]
ESTADOS_ACCION = ["Pendiente", "En curso", "Hecha"]
NIVEL_COLOR = {"Alto": "#d03b3b", "Medio": "#eda100", "Bajo": "#1baf7a"}
TINTA, TINTA_2, BORDE = "#1f2a37", "#5b6675", "#e3e7eb"
# puntaje maximo de cada componente (suman 100)
MAXIMOS = {"Oposición con poder": 40, "Precedentes de conflicto": 20, "Compromisos vencidos": 20,
           "Posturas que empeoran": 20}


# ------------------------------------------------------------------ datos
def _texto(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        if c not in df:
            df[c] = ""
    return df


def normalizar_procesos(df: pd.DataFrame) -> pd.DataFrame:
    df = _texto(df, COL_PROCESOS)[COL_PROCESOS]
    df = df.dropna(subset=["proceso"])
    for c in COL_PROCESOS:
        if c not in ("fecha_limite", "impacto"):
            df[c] = df[c].fillna("").astype(str).str.strip()
    df["fecha_limite"] = pd.to_datetime(df["fecha_limite"], errors="coerce").dt.date
    df["impacto"] = pd.to_numeric(df["impacto"], errors="coerce").fillna(3).clip(1, 5).astype(int)
    vacios = df["id"] == ""
    df.loc[vacios, "id"] = [f"P{i}" for i in range(100, 100 + int(vacios.sum()))]
    return df[df["proceso"] != ""].reset_index(drop=True)


def normalizar_partes(df: pd.DataFrame) -> pd.DataFrame:
    df = _texto(df, COL_PARTES)[COL_PARTES].fillna("").astype(str)
    df = df.apply(lambda s: s.str.strip())
    df.loc[~df["rol"].isin(ROLES), "rol"] = "Influye"
    return df[(df["nombre"] != "") & (df["proceso_id"] != "")].drop_duplicates(["proceso_id", "nombre"])\
        .reset_index(drop=True)


def normalizar_escenarios(df: pd.DataFrame) -> pd.DataFrame:
    df = _texto(df, COL_ESCENARIOS)[COL_ESCENARIOS]
    for c in ("proceso_id", "escenario", "nombre", "motivo"):
        df[c] = df[c].fillna("").astype(str).str.strip()
    df["postura_nueva"] = pd.to_numeric(df["postura_nueva"], errors="coerce").fillna(0).clip(-2, 2).astype(int)
    return df[(df["escenario"] != "") & (df["nombre"] != "")].reset_index(drop=True)


def normalizar_acciones(df: pd.DataFrame) -> pd.DataFrame:
    df = _texto(df, COL_ACCIONES)[COL_ACCIONES]
    for c in COL_ACCIONES:
        if c != "fecha":
            df[c] = df[c].fillna("").astype(str).str.strip()
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").dt.date
    df.loc[~df["estado"].isin(ESTADOS_ACCION), "estado"] = "Pendiente"
    return df[(df["accion"] != "") | (df["nombre"] != "")].reset_index(drop=True)


# ------------------------------------------------------------------ calculo
def partes_con_postura(partes: pd.DataFrame, A: pd.DataFrame, cambios_postura: dict | None = None) -> pd.DataFrame:
    """Une los actores del proceso con su postura e influencia actuales (del mapa de actores)."""
    p = partes.copy()
    info = A.set_index(A["nombre"].map(ac.clave))[["postura", "influencia", "cargo", "tipo", "comunidad"]]
    p = p.join(info, on=p["nombre"].map(ac.clave).rename("_k")) if not p.empty else p
    for c, v in (("postura", 0), ("influencia", 2), ("cargo", ""), ("tipo", ""), ("comunidad", "")):
        if c not in p:
            p[c] = v
        p[c] = p[c].fillna(v)
    p["postura"] = p["postura"].astype(int)
    p["influencia"] = p["influencia"].astype(int)
    p["postura_antes"] = p["postura"]
    if cambios_postura:
        nuevo = p["nombre"].map(cambios_postura)
        p["postura"] = nuevo.fillna(p["postura"]).astype(int)
    p["peso"] = p["rol"].map(PESO_ROL).fillna(1.0)
    p["presion"] = (p["peso"] * (-p["postura"]).clip(lower=0) * p["influencia"]).round(1)
    p["apoyo"] = (p["peso"] * p["postura"].clip(lower=0) * p["influencia"]).round(1)
    p["estrategia"] = [estrategia(a, b) for a, b in zip(p["postura"], p["influencia"])]
    return p.sort_values(["presion", "influencia"], ascending=False).reset_index(drop=True)


def estrategia(postura: int, influencia: int) -> str:
    """Estrategia sugerida segun poder y postura (matriz clasica de grupos de interes)."""
    if influencia >= 4:
        if postura < 0:
            return "Atender sus preocupaciones de cerca"
        if postura == 0:
            return "Involucrar y consultar"
        return "Colaborar"
    if postura < 0:
        return "Informar y escuchar"
    return "Mantener informado"


def nivel(puntos: float) -> str:
    return "Alto" if puntos >= 60 else "Medio" if puntos >= 35 else "Bajo"


def evaluar(proceso: pd.Series, partes: pd.DataFrame, A: pd.DataFrame, H: pd.DataFrame, conf: pd.DataFrame,
            reg: pd.DataFrame, hoy: date, cambios_postura: dict | None = None, meses: int = 6) -> dict:
    """Riesgo de paralizacion (0-100) del proceso con sus cuatro componentes y el porque de cada uno.
    reg debe venir con la columna 'estado' (registro.con_estado)."""
    com = proceso["comunidad"]
    p = partes_con_postura(partes[partes["proceso_id"] == proceso["id"]], A, cambios_postura)

    # 1. oposicion con poder entre quienes deciden, pueden vetar o influyen
    tope = (p["peso"] * 2 * p["influencia"]).sum()
    ratio = p["presion"].sum() / tope if tope else 0
    pts_op = MAXIMOS["Oposición con poder"] * min(1, 1.4 * ratio)
    veto = p[(p["rol"].isin(["Decide", "Puede vetar"])) & (p["postura"] < 0)]
    txt_op = (f"{len(veto)} de {int(p['rol'].isin(['Decide', 'Puede vetar']).sum())} actores que deciden o pueden "
              f"vetar están en contra" + (f" ({', '.join(veto['nombre'].head(2))}{' y otros' if len(veto) > 2 else ''})" if len(veto) else ""))

    # 2. precedentes: medidas de fuerza en la comunidad en los ultimos 3 anios
    desde = date(hoy.year - 3, hoy.month, 1)
    c = conf[(conf["comunidad"] == com) & (conf["fecha"] >= desde)] if not conf.empty else conf
    fuerza = c[c["tipo"].isin(DE_FUERZA)] if not c.empty else c
    dias = int(fuerza["duracion_dias"].sum()) if not fuerza.empty else 0
    pts_pre = MAXIMOS["Precedentes de conflicto"] * min(1, 0.2 * len(fuerza) + dias / 50)
    txt_pre = (f"{len(fuerza)} medidas de fuerza y {dias} días de paralización en {com.replace('C.C. ', '')} "
               f"desde {desde.year}" if len(fuerza) else f"Sin medidas de fuerza en {com.replace('C.C. ', '')} "
               f"desde {desde.year}")

    # 3. compromisos vencidos que pueden usarse como bandera
    v = reg[(reg["comunidad"] == com) & (reg["estado"] == "Vencido")] if not reg.empty else reg
    altos = int((v["riesgo_conflicto"] == "alto").sum()) if not v.empty else 0
    pts_comp = MAXIMOS["Compromisos vencidos"] * min(1, (len(v) + altos) / 25)
    txt_comp = f"{len(v)} compromisos vencidos con la comunidad ({altos} de riesgo alto)"

    # 4. actores del proceso cuya postura empeoro en los ultimos meses (o en el escenario)
    ini = (pd.Timestamp(hoy) - pd.DateOffset(months=meses)).date()
    cam = ac.cambios(H[H["nombre"].isin(p["nombre"])], ini, hoy) if not H.empty else pd.DataFrame()
    bajan = set(cam.loc[cam["delta"] < 0, "nombre"]) if not cam.empty else set()
    if cambios_postura:
        bajan |= set(p.loc[p["postura"] < p["postura_antes"], "nombre"])
        bajan -= set(p.loc[p["postura"] > p["postura_antes"], "nombre"])
    infl_bajan = int(p.loc[p["nombre"].isin(bajan), "influencia"].sum())
    pts_ten = MAXIMOS["Posturas que empeoran"] * min(1, infl_bajan / 16)
    txt_ten = (f"{len(bajan)} actores del proceso se alejaron en los últimos {meses} meses"
               + (f" ({', '.join(sorted(bajan)[:2])}{' y otros' if len(bajan) > 2 else ''})" if bajan else ""))

    comp = {"Oposición con poder": (pts_op, txt_op), "Precedentes de conflicto": (pts_pre, txt_pre),
            "Compromisos vencidos": (pts_comp, txt_comp), "Posturas que empeoran": (pts_ten, txt_ten)}
    total = round(sum(x for x, _ in comp.values()))
    dias_plazo = (proceso["fecha_limite"] - hoy).days if pd.notna(proceso["fecha_limite"]) else None
    return dict(puntos=total, nivel=nivel(total), componentes=comp, partes=p, dias_plazo=dias_plazo,
                prioridad=round(total * proceso["impacto"] / 5), vencidos=v, precedentes=c)


def cartera(procesos: pd.DataFrame, partes, A, H, conf, reg, hoy) -> pd.DataFrame:
    """Resumen de todos los procesos: riesgo, impacto y plazo."""
    filas = []
    for _, pr in procesos.iterrows():
        r = evaluar(pr, partes, A, H, conf, reg, hoy)
        filas.append(dict(id=pr["id"], proceso=pr["proceso"], comunidad=pr["comunidad"], tipo=pr["tipo"],
                          riesgo=r["puntos"], nivel=r["nivel"], impacto=pr["impacto"], prioridad=r["prioridad"],
                          dias_plazo=r["dias_plazo"], fecha_limite=pr["fecha_limite"], estado=pr["estado"],
                          responsable=pr["responsable"]))
    return pd.DataFrame(filas).sort_values("prioridad", ascending=False).reset_index(drop=True) if filas else \
        pd.DataFrame(columns=["id", "proceso", "riesgo", "nivel", "impacto", "prioridad", "dias_plazo"])


def puentes(nombre: str, A: pd.DataFrame, R: pd.DataFrame) -> list[str]:
    """Actores conectados con 'nombre' que no estan en contra y pueden abrir el dialogo (primero los que
    ya tienen relacion con la empresa)."""
    g = ac.red(A, R)
    if nombre not in g:
        return []
    empresa = {n for n, d in g.nodes(data=True) if d.get("tipo") == "Empresa"}
    cand = []
    for v in g.neighbors(nombre):
        d = g.nodes[v]
        if d.get("tipo") == "Empresa" or int(d.get("postura", 0)) < 0 or g.edges[nombre, v]["tipo"] == "Conflicto":
            continue
        con_empresa = any(u in empresa for u in g.neighbors(v))
        cand.append((not con_empresa, -int(d.get("postura", 0)), -int(d.get("influencia", 0)), v))
    return [c[-1] for c in sorted(cand)]


def distancia_empresa(nombre: str, A: pd.DataFrame, R: pd.DataFrame) -> int | None:
    g = ac.red(A, R)
    empresa = [n for n, d in g.nodes(data=True) if d.get("tipo") == "Empresa"]
    if nombre not in g or not empresa:
        return None
    largos = [nx.shortest_path_length(g, e, nombre) for e in empresa if nx.has_path(g, e, nombre)]
    return min(largos) if largos else None


def tensiones(nombres: list[str], R: pd.DataFrame) -> pd.DataFrame:
    """Relaciones de conflicto en las que participan los actores que cambian en un escenario."""
    if not nombres:
        return R.iloc[0:0]
    return R[(R["tipo"] == "Conflicto") & (R["origen"].isin(nombres) | R["destino"].isin(nombres))]


def sugerir_acciones(proceso_id: str, p: pd.DataFrame, acciones: pd.DataFrame, responsable: str) -> pd.DataFrame:
    """Una accion sugerida para cada actor relevante del proceso que todavia no tiene ninguna."""
    con = set(acciones.loc[acciones["proceso_id"] == proceso_id, "nombre"])
    falta = p[~p["nombre"].isin(con) & ((p["influencia"] >= 3) | (p["postura"] < 0))]
    texto = {"Atender sus preocupaciones de cerca": "Reunión directa para escuchar y responder: {preo}",
             "Involucrar y consultar": "Invitar a la mesa de trabajo del proceso",
             "Colaborar": "Pedir su apoyo para abrir el diálogo con los actores críticos",
             "Informar y escuchar": "Visita informativa y recojo de dudas: {preo}",
             "Mantener informado": "Enviar información periódica del avance"}
    filas = [dict(proceso_id=proceso_id, nombre=r["nombre"], estrategia=r["estrategia"],
                  accion=texto[r["estrategia"]].format(preo=(r["preocupacion"] or "sus preocupaciones").lower()),
                  responsable=responsable, fecha=None, estado="Pendiente") for _, r in falta.iterrows()]
    return pd.DataFrame(filas, columns=COL_ACCIONES)


# ------------------------------------------------------------------ graficos
def _base(fig: go.Figure, alto: int) -> go.Figure:
    fig.update_layout(height=alto, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white", paper_bgcolor="white",
                      font=dict(family="Inter, Segoe UI, sans-serif", color=TINTA_2),
                      hoverlabel=dict(bgcolor="white", font_size=12))
    return fig


def figura_medidor(puntos: int, antes: int | None = None, alto: int = 230) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number" + ("+delta" if antes is not None else ""), value=puntos,
        number=dict(suffix=" /100", font=dict(size=34, color=TINTA)),
        delta=dict(reference=antes, increasing=dict(color="#d03b3b"), decreasing=dict(color="#1baf7a"))
        if antes is not None else None,
        gauge=dict(axis=dict(range=[0, 100], tickvals=[0, 35, 60, 100], tickcolor=BORDE),
                   bar=dict(color=TINTA, thickness=0.28),
                   steps=[dict(range=[0, 35], color="#c8ecd9"), dict(range=[35, 60], color="#fbe3a6"),
                          dict(range=[60, 100], color="#f6c4c4")],
                   threshold=dict(line=dict(color=NIVEL_COLOR[nivel(puntos)], width=4), value=puntos))))
    return _base(fig, alto).update_layout(margin=dict(l=25, r=25, t=20, b=0))


def figura_componentes(r: dict, alto: int = 230) -> go.Figure:
    nombres = list(MAXIMOS)[::-1]
    pts = [r["componentes"][n][0] for n in nombres]
    fig = go.Figure()
    fig.add_bar(y=nombres, x=[MAXIMOS[n] for n in nombres], orientation="h", marker_color="#eef1f4",
                hoverinfo="skip", showlegend=False)
    fig.add_bar(y=nombres, x=pts, orientation="h", marker_color=[NIVEL_COLOR[nivel(100 * p / MAXIMOS[n])]
                                                                for p, n in zip(pts, nombres)],
                text=[f"{p:.0f} de {MAXIMOS[n]}" for p, n in zip(pts, nombres)], textposition="outside",
                cliponaxis=False, customdata=[r["componentes"][n][1] for n in nombres],
                hovertemplate="<b>%{y}</b><br>%{customdata}<extra></extra>", showlegend=False)
    fig.update_layout(barmode="overlay", bargap=0.35)
    fig.update_xaxes(visible=False, range=[0, 56])
    fig.update_yaxes(tickfont=dict(size=13, color=TINTA))
    return _base(fig, alto)


def figura_actores(p: pd.DataFrame, alto: int = 430) -> go.Figure:
    """Postura vs influencia de los actores del proceso; el simbolo indica su rol."""
    simbolo = {"Decide": "star", "Puede vetar": "diamond", "Influye": "circle", "Afectado": "square"}
    fig = go.Figure()
    fig.add_shape(type="rect", x0=-2.5, x1=-0.5, y0=3.5, y1=6.15, fillcolor="rgba(208,59,59,0.07)", line_width=0,
                  layer="below")
    fig.add_annotation(x=-2.45, y=6.0, text="Pueden frenar el proceso", showarrow=False, xanchor="left",
                       font=dict(size=12, color="#a32424"))
    fig.add_shape(type="rect", x0=0.5, x1=2.5, y0=3.5, y1=6.15, fillcolor="rgba(28,92,171,0.06)", line_width=0,
                  layer="below")
    fig.add_annotation(x=2.45, y=6.0, text="Aliados con poder", showarrow=False, xanchor="right",
                       font=dict(size=12, color="#1c5cab"))
    d = p.copy()
    d["_n"] = d.groupby(["postura", "influencia"]).cumcount()
    d["x"] = d["postura"] + (d["_n"] % 3 - 1 + (d.groupby(["postura", "influencia"])["_n"].transform("max") == 0))\
        * 0.3
    d["y"] = d["influencia"] - (d["_n"] // 3) * 0.28
    for rol, s in d.groupby("rol"):
        fig.add_scatter(x=s["x"], y=s["y"], mode="markers+text", name=rol,
                        marker=dict(symbol=simbolo.get(rol, "circle"), size=8 + 4 * s["influencia"],
                                    color=[ac.POSTURA_COLOR[int(v)] for v in s["postura"]],
                                    line=dict(color="white", width=1.5)),
                        text=s["nombre"].str.slice(0, 26),
                        textposition=["top center" if n % 2 == 0 else "bottom center" for n in s["_n"]],
                        textfont=dict(size=11, color=TINTA),
                        customdata=s[["rol", "preocupacion"]].to_numpy(),
                        hovertemplate="<b>%{text}</b><br>%{customdata[0]}<br>Preocupación: %{customdata[1]}"
                                      "<extra></extra>")
    fig.update_xaxes(range=[-2.9, 2.75], tickvals=list(ac.POSTURA_TXT), ticktext=list(ac.POSTURA_TXT.values()),
                     zeroline=False, gridcolor="#f1f3f5", title="Postura hacia la empresa")
    fig.update_yaxes(range=[0.4, 6.25], tickvals=[1, 2, 3, 4, 5], gridcolor="#f1f3f5", title="Influencia")
    fig.update_layout(legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center", title_text="Rol: "))
    return _base(fig, alto).update_layout(margin=dict(l=10, r=10, t=10, b=70))


def figura_escenarios(resultados: list[tuple[str, int]], base: int, alto: int = 300) -> go.Figure:
    """Riesgo de cada escenario frente a la situacion actual."""
    nombres = ["Situación actual"] + [n for n, _ in resultados]
    valores = [base] + [v for _, v in resultados]
    corto = ["<br>".join(textwrap.wrap(n, 60)) for n in nombres]
    fig = go.Figure(go.Bar(y=corto[::-1], x=valores[::-1], orientation="h",
                           marker_color=[NIVEL_COLOR[nivel(v)] for v in valores[::-1]],
                           marker_line=dict(color=[TINTA if i == len(valores) - 1 else "white"
                                                   for i in range(len(valores))], width=2),
                           text=[f"{v}" + ("" if i == len(valores) - 1 else f"  ({v - base:+d})")
                                 for i, v in enumerate(valores[::-1])],
                           textposition="outside", cliponaxis=False, hovertext=nombres[::-1],
                           hovertemplate="%{hovertext}: %{x}/100<extra></extra>"))
    for x in (35, 60):
        fig.add_vline(x=x, line=dict(color=BORDE, dash="dot"))
    fig.update_xaxes(range=[0, 112], visible=False)
    fig.update_yaxes(tickfont=dict(size=12, color=TINTA))
    return _base(fig, alto)


def figura_cartera(c: pd.DataFrame, alto: int = 300) -> go.Figure:
    """Mapa de calor de la cartera: riesgo de paralizacion vs impacto si se paraliza."""
    fig = go.Figure()
    fig.add_shape(type="rect", x0=60, x1=112, y0=3.5, y1=5.5, fillcolor="rgba(208,59,59,0.08)", line_width=0,
                  layer="below")
    fig.add_annotation(x=110, y=5.4, text="Prioridad máxima", showarrow=False, xanchor="right",
                       font=dict(size=12, color="#a32424"))
    fig.add_scatter(x=c["riesgo"], y=c["impacto"], mode="markers+text",
                    marker=dict(size=26, color=[NIVEL_COLOR[n] for n in c["nivel"]], line=dict(color="white", width=2)),
                    text=c["id"], textfont=dict(color="white", size=12), customdata=c[["proceso", "dias_plazo"]],
                    hovertemplate="<b>%{customdata[0]}</b><br>Riesgo %{x}/100 · impacto %{y}/5<br>"
                                  "Faltan %{customdata[1]} días<extra></extra>", showlegend=False)
    for x in (35, 60):
        fig.add_vline(x=x, line=dict(color=BORDE, dash="dot"))
    fig.update_xaxes(range=[-12, 112], tickvals=[0, 20, 40, 60, 80, 100], title="Riesgo de paralización",
                     gridcolor="#f1f3f5")
    fig.update_yaxes(range=[0.4, 5.6], tickvals=[1, 2, 3, 4, 5], title="Impacto si se paraliza",
                     gridcolor="#f1f3f5")
    return _base(fig, alto).update_layout(margin=dict(l=10, r=10, t=10, b=40))

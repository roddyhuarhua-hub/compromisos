"""Varios proyectos en una sola herramienta: una unidad minera, frentes de exploracion o los clientes de
una consultora, cada uno con sus comunidades y actores, sin perder la mirada corporativa.

Cada comunidad pertenece a un proyecto; compromisos, conflictos y procesos heredan el proyecto de su
comunidad. Un actor pertenece a los proyectos de su comunidad o, si no tiene comunidad (Estado, ONG,
medios, equipo de la empresa), a los de las comunidades con las que se relaciona. Si aparece en dos o
mas proyectos es un actor transversal: puede llevar un conflicto de un ambito a otro.
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from . import actores as ac
from . import conflictos as cf
from . import registro, riesgos, visual

TODOS = "🌐 Todos los proyectos"
SIN_PROYECTO = "Sin proyecto"
COLOR_PROYECTO = ["#2d4a33", "#2a78d6", "#c2410c", "#6250d6", "#1baf7a", "#eda100", "#8a8984"]


# ------------------------------------------------------------------ carga de la demo
def cargar_demo(carpeta: Path) -> dict[str, pd.DataFrame]:
    """Une la unidad minera de ejemplo con los proyectos de exploracion de ejemplo (carpeta exploracion/)."""
    ex = carpeta / "exploracion"

    def ambos(principal: str, extra: str) -> pd.DataFrame:
        partes = [pd.read_csv(carpeta / principal)]
        if (ex / extra).exists():
            partes.append(pd.read_csv(ex / extra))
        return pd.concat(partes, ignore_index=True)

    return dict(
        comunidades=normalizar_comunidades(ambos("comunidades.csv", "comunidades.csv")),
        proyectos=pd.read_csv(carpeta / "proyectos.csv").fillna("") if (carpeta / "proyectos.csv").exists()
        else pd.DataFrame(columns=["proyecto", "tipo", "region", "fase", "responsable"]),
        registro=registro.normalizar(ambos("registro_demo.csv", "registro.csv")),
        actores=ac.normalizar_actores(ambos("actores_demo.csv", "actores.csv")),
        relaciones=ac.normalizar_relaciones(ambos("relaciones_demo.csv", "relaciones.csv")),
        posturas=ac.normalizar_historial(ambos("posturas_demo.csv", "posturas.csv")),
        conflictos=cf.normalizar(ambos("conflictos_demo.csv", "conflictos.csv")),
        procesos=riesgos.normalizar_procesos(ambos("procesos_demo.csv", "procesos.csv")),
        partes=riesgos.normalizar_partes(ambos("proceso_actores_demo.csv", "proceso_actores.csv")),
        escenarios=riesgos.normalizar_escenarios(ambos("escenarios_demo.csv", "escenarios.csv")),
        acciones=riesgos.normalizar_acciones(ambos("acciones_demo.csv", "acciones.csv")),
    )


def normalizar_comunidades(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "proyecto" not in df:
        df["proyecto"] = ""
    df["proyecto"] = df["proyecto"].fillna("").astype(str).str.strip().replace("", SIN_PROYECTO)
    return df.drop_duplicates("comunidad", keep="last").reset_index(drop=True)


def lista(comunidades: pd.DataFrame) -> list[str]:
    return list(dict.fromkeys(comunidades["proyecto"]))


def colores(comunidades: pd.DataFrame) -> dict[str, str]:
    """Color fijo de cada proyecto (el mismo en el portafolio y en los demas graficos)."""
    return {p: COLOR_PROYECTO[i % len(COLOR_PROYECTO)] for i, p in enumerate(lista(comunidades))}


# ------------------------------------------------------------------ pertenencia
def proyectos_actor(A: pd.DataFrame, R: pd.DataFrame, comunidades: pd.DataFrame) -> dict[str, set[str]]:
    """nombre -> proyectos a los que pertenece (por su comunidad o por sus relaciones, hasta 2 pasos)."""
    de_com = dict(zip(comunidades["comunidad"], comunidades["proyecto"]))
    perte = {n: ({de_com[c]} if c in de_com else set()) for n, c in zip(A["nombre"], A["comunidad"])}
    vecinos: dict[str, set[str]] = {n: set() for n in perte}
    for o, d in zip(R["origen"], R["destino"]):
        vecinos.setdefault(o, set()).add(d)
        vecinos.setdefault(d, set()).add(o)
        perte.setdefault(o, set())
        perte.setdefault(d, set())
    fijos = {n for n, p in perte.items() if p}
    # 1) quien se relaciona con actores de una comunidad hereda sus proyectos
    for n in perte:
        if n not in fijos:
            perte[n] = set().union(*(perte[v] for v in vecinos.get(n, ()) if v in fijos)) \
                if vecinos.get(n) else set()
    # 2) quien sigue sin proyecto (p. ej. el equipo de la empresa) hereda el de sus vecinos
    vacios = [n for n, p in perte.items() if not p]
    heredado = {n: set().union(*(perte[v] for v in vecinos.get(n, ()))) if vecinos.get(n) else set()
                for n in vacios}
    perte.update(heredado)
    return perte


def transversales(A: pd.DataFrame, R: pd.DataFrame, comunidades: pd.DataFrame) -> pd.DataFrame:
    """Actores que no son de la empresa y aparecen en dos o mas proyectos."""
    perte = proyectos_actor(A, R, comunidades)
    d = A[A["tipo"] != "Empresa"].copy()
    d["proyectos"] = d["nombre"].map(lambda n: sorted(perte.get(n, set())))
    d = d[d["proyectos"].map(len) >= 2]
    d["n_proyectos"] = d["proyectos"].map(len)
    return d.sort_values(["n_proyectos", "influencia", "postura"], ascending=[False, False, True])


def filtrar(datos: dict[str, pd.DataFrame], proyecto: str) -> dict[str, pd.DataFrame]:
    """Vista de un proyecto (o de todos). No modifica los datos originales."""
    if proyecto == TODOS:
        return dict(datos)
    coms = datos["comunidades"]
    coms_p = coms[coms["proyecto"] == proyecto]
    nombres_c = set(coms_p["comunidad"])
    perte = proyectos_actor(datos["actores"], datos["relaciones"], coms)
    A = datos["actores"][datos["actores"]["nombre"].map(lambda n: proyecto in perte.get(n, set()))]
    nombres_a = set(A["nombre"])
    R = datos["relaciones"]
    P = datos["procesos"][datos["procesos"]["comunidad"].isin(nombres_c)]
    ids = set(P["id"])
    out = dict(datos)
    out.update(
        comunidades=coms_p.reset_index(drop=True),
        registro=datos["registro"][datos["registro"]["comunidad"].isin(nombres_c)],
        actores=A, relaciones=R[R["origen"].isin(nombres_a) & R["destino"].isin(nombres_a)],
        posturas=datos["posturas"][datos["posturas"]["nombre"].isin(nombres_a)],
        conflictos=datos["conflictos"][datos["conflictos"]["comunidad"].isin(nombres_c)],
        procesos=P, partes=datos["partes"][datos["partes"]["proceso_id"].isin(ids)],
        escenarios=datos["escenarios"][datos["escenarios"]["proceso_id"].isin(ids)],
        acciones=datos["acciones"][datos["acciones"]["proceso_id"].isin(ids)],
    )
    return out


def reemplazar(total: pd.DataFrame, vista: pd.DataFrame, editado: pd.DataFrame) -> pd.DataFrame:
    """Guarda lo editado en la vista de un proyecto sin borrar las filas de los demas proyectos."""
    resto = total.drop(index=total.index.intersection(vista.index))
    return pd.concat([resto, editado], ignore_index=True)


from .zoom import encuadre  # noqa: E402  centro y zoom para una o varias regiones


# ------------------------------------------------------------------ resumen corporativo
def resumen(datos: dict[str, pd.DataFrame], hoy: date) -> pd.DataFrame:
    """Una fila por proyecto con los indicadores que la gerencia compara."""
    coms = datos["comunidades"]
    reg = registro.con_estado(datos["registro"], hoy)
    A_hoy = ac.al_corte(datos["actores"], datos["posturas"], hoy)
    perte = proyectos_actor(A_hoy, datos["relaciones"], coms)
    info = datos["proyectos"].set_index("proyecto") if not datos["proyectos"].empty else pd.DataFrame()
    desde = date(hoy.year - 3, hoy.month, 1)
    filas = []
    for i, p in enumerate(lista(coms)):
        sub = filtrar(datos, p)
        nombres_c = set(sub["comunidades"]["comunidad"])
        r = reg[reg["comunidad"].isin(nombres_c)]
        ind = visual.indice_comunidades(r, sub["comunidades"]) if not r.empty else pd.DataFrame()
        c = sub["conflictos"]
        c3 = c[c["fecha"] >= desde] if not c.empty else c
        fuerza = c3[c3["tipo"].isin(cf.DE_FUERZA)] if not c3.empty else c3
        A_p = A_hoy[A_hoy["nombre"].map(lambda n: p in perte.get(n, set()))]
        cart = riesgos.cartera(sub["procesos"], sub["partes"], A_hoy, datos["posturas"], datos["conflictos"], reg,
                               hoy) if not sub["procesos"].empty else pd.DataFrame()
        prox = cart.dropna(subset=["dias_plazo"]) if not cart.empty else cart
        prox = prox[prox["dias_plazo"] >= 0].sort_values("dias_plazo") if not prox.empty else prox
        exig = int(r["cumplido"].sum() + (r["estado"] == "Vencido").sum()) if not r.empty else 0
        filas.append(dict(
            proyecto=p, color=COLOR_PROYECTO[i % len(COLOR_PROYECTO)],
            tipo=info["tipo"].get(p, "") if "tipo" in info else "", region=info["region"].get(p, "")
            if "region" in info else "", fase=info["fase"].get(p, "") if "fase" in info else "",
            responsable=info["responsable"].get(p, "") if "responsable" in info else "",
            comunidades=len(nombres_c), compromisos=len(r), vencidos=int((r["estado"] == "Vencido").sum()),
            por_vencer=int((r["estado"] == "Por vencer").sum()),
            cumplimiento=(r["cumplido"].sum() / exig) if exig else 0.0,
            indice_max=float(ind["indice"].max()) if not ind.empty else 0.0,
            criticas=int((ind["semaforo"] == "Crítico").sum()) if not ind.empty else 0,
            eventos=len(c3), medidas_fuerza=len(fuerza),
            dias_paralizacion=int(fuerza["duracion_dias"].sum()) if not fuerza.empty else 0,
            actores=len(A_p), opositores_clave=int(((A_p["postura"] < 0) & (A_p["influencia"] >= 4)).sum()),
            procesos=len(cart), riesgo_alto=int((cart["nivel"] == "Alto").sum()) if not cart.empty else 0,
            riesgo_max=int(cart["riesgo"].max()) if not cart.empty else 0,
            proximo_hito=(f"{prox.iloc[0]['proceso']} ({int(prox.iloc[0]['dias_plazo'])} días)"
                          if not prox.empty else "—"),
        ))
    out = pd.DataFrame(filas)
    if not out.empty:  # alerta corporativa: mezcla de incumplimiento, conflicto y procesos en riesgo
        out["alerta"] = (0.4 * out["indice_max"] + 0.3 * out["riesgo_max"]
                         + 0.3 * (out["dias_paralizacion"] * 8).clip(upper=100)).round(0)
        out["nivel"] = pd.cut(out["alerta"], [-1, 35, 55, 101], labels=["Bajo", "Medio", "Alto"]).astype(str)
    return out


def figura_comparacion(res: pd.DataFrame, alto: int = 330) -> go.Figure:
    """Compromisos por estado en cada proyecto (barras apiladas)."""
    fig = go.Figure()
    nombres = res["proyecto"][::-1]
    cumplidos = (res["compromisos"] - res["vencidos"] - res["por_vencer"])[::-1]
    for etiqueta, valores, color in (("Vencidos", res["vencidos"][::-1], visual.COLOR_ESTADO["Vencido"]),
                                     ("Por vencer", res["por_vencer"][::-1], visual.COLOR_ESTADO["Por vencer"]),
                                     ("Cumplidos o en plazo", cumplidos, "#9fc9a8")):
        fig.add_bar(y=nombres, x=valores, name=etiqueta, orientation="h", marker_color=color, text=valores,
                    textposition="inside", insidetextanchor="middle", textfont=dict(color="white", size=13),
                    marker_line=dict(color="white", width=2))
    fig.update_layout(barmode="stack", bargap=0.35)
    fig = visual.base(fig, alto, "Compromisos por proyecto")
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0), margin=dict(l=8, r=8, t=80, b=8))
    fig.update_yaxes(tickfont=dict(size=13, color=visual.TINTA))
    return fig


def figura_alerta(res: pd.DataFrame, alto: int = 300) -> go.Figure:
    """Alerta de cada proyecto (0-100) con lo que la explica."""
    d = res.sort_values("alerta")
    color = {"Alto": "#d03b3b", "Medio": "#eda100", "Bajo": "#1baf7a"}
    fig = go.Figure(go.Bar(
        y=d["proyecto"], x=d["alerta"], orientation="h", marker_color=d["nivel"].map(color),
        text=[f"<b>{int(a)}</b>  ·  {dp} días de paralización · proceso más expuesto {rm}/100"
              for a, dp, rm in zip(d["alerta"], d["dias_paralizacion"], d["riesgo_max"])],
        textposition="outside", cliponaxis=False, hovertemplate="%{y}: %{x}/100<extra></extra>"))
    for x in (35, 55):
        fig.add_vline(x=x, line=dict(color=visual.GRID, dash="dot"))
    fig = visual.base(fig, alto, "Alerta por proyecto (0–100)")
    fig.update_xaxes(range=[0, 190], visible=False)
    fig.update_yaxes(tickfont=dict(size=13, color=visual.TINTA))
    fig.update_layout(bargap=0.4)
    return fig


def figura_mapa(res: pd.DataFrame, comunidades: pd.DataFrame, ind: pd.DataFrame, fondo: str = "⛰️ Relieve",
                alto: int = 520) -> go.Figure:
    """Cada proyecto con su nombre y sus comunidades coloreadas por semaforo."""
    capas, atribucion, texto_oscuro = visual.FONDOS.get(fondo, visual.FONDOS["⛰️ Relieve"])
    fig = go.Figure()
    c = comunidades.merge(ind[["comunidad", "semaforo", "vencidos"]], on="comunidad", how="left") \
        if not ind.empty else comunidades.assign(semaforo="Estable", vencidos=0)
    c["semaforo"] = c["semaforo"].fillna("Estable")
    c["vencidos"] = c["vencidos"].fillna(0)
    for nivel_ in ["Estable", "Atención", "Crítico"]:
        s_ = c[c["semaforo"] == nivel_]
        if not s_.empty:
            fig.add_trace(go.Scattermap(
                lat=s_["lat"], lon=s_["lon"], mode="markers", name=nivel_,
                marker=dict(size=10 + s_["vencidos"].clip(upper=15) * 1.4, color=visual.SEMAFORO[nivel_],
                            opacity=0.95),
                customdata=s_[["comunidad", "proyecto", "vencidos"]].values,
                hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>Vencidos: %{customdata[2]:.0f}"
                              "<extra></extra>"))
    cen = comunidades.groupby("proyecto").agg(lat=("lat", "mean"), lon=("lon", "mean")).reindex(res["proyecto"])
    # el proyecto mas al este se rotula a la derecha y los demas debajo, para que no se encimen
    pos = ["middle right" if lo == cen["lon"].max() else "bottom center" for lo in cen["lon"]]
    centro, zoom = encuadre(comunidades["lat"], comunidades["lon"], alto_px=alto)
    paso = 18 / (256 * 2 ** zoom / 360)  # ~18 px en grados: el rotulo no debe tapar los puntos (se ocultaria)
    for (nom, f_), pos_ in zip(cen.iterrows(), pos):  # Scattermap acepta una sola posicion por traza
        derecha = pos_ == "middle right"
        fig.add_trace(go.Scattermap(
            lat=[f_["lat"] - (0 if derecha else paso)], lon=[f_["lon"] + (paso if derecha else 0)], mode="markers+text", marker=dict(size=1, opacity=0), showlegend=False, hoverinfo="skip", text=[nom],
            textposition=pos_, textfont=dict(size=14, color=visual.TINTA if texto_oscuro else "#ffffff")))
    fig.update_layout(
        map=dict(style=os.getenv("ESTILO_MAPA") or ("carto-positron" if not capas else "white-bg"),
                 center=centro, zoom=zoom,
                 layers=[dict(sourcetype="raster", source=[u], below="traces", sourceattribution=atribucion)
                         for u in capas]),
        height=alto, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=0.01, x=0.01, bgcolor="rgba(255,255,255,0.85)",
                    title=dict(text="Semáforo  ")))
    return fig

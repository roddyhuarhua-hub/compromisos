"""Mapeo de actores: registro, analisis de red (networkx) y graficos.

- Cada reunion procesada por la IA agrega actores y relaciones (se fusionan por nombre).
- La red se analiza con networkx: centralidad de grado (cuantos vinculos), intermediacion
  (quien conecta grupos que de otro modo no se hablan) y "puentes" entre comunidades.
"""
from __future__ import annotations

import unicodedata

import networkx as nx
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .modelos import ExtraccionReunion

COL_ACTORES = ["nombre", "tipo", "cargo", "organizacion", "comunidad", "postura", "influencia", "fuente"]
COL_RELACIONES = ["origen", "destino", "tipo", "descripcion", "fuente"]
COL_HISTORIAL = ["nombre", "fecha", "reunion", "comunidad", "postura", "influencia", "evidencia"]

POSTURA_TXT = {-2: "Opositor", -1: "Crítico", 0: "Neutral", 1: "Favorable", 2: "Aliado"}
# Paleta divergente: naranja (en contra) <-> gris neutro <-> azul (a favor)
POSTURA_COLOR = {-2: "#c2410c", -1: "#f29b6b", 0: "#a3a3a0", 1: "#6da7ec", 2: "#1c5cab"}
REL_ESTILO = {  # color, guion, ancho
    "Conflicto": ("#d03b3b", "solid", 2.6),
    "Alianza": ("#1baf7a", "solid", 2.0),
    "Representa a": ("#8a8984", "solid", 1.4),
    "Influye en": ("#6250d6", "dot", 1.6),
    "Negocia con": ("#2a78d6", "dash", 1.6),
    "Parentesco": ("#eda100", "dot", 1.6),
}
SIMBOLO_TIPO = {
    "Dirigente comunal": "circle", "Organización de base": "circle", "Autoridad local": "square",
    "Estado": "square", "Empresa": "diamond", "ONG / Iglesia": "triangle-up",
    "Medio de comunicación": "triangle-up", "Otro": "circle",
}
TINTA, TINTA_2 = "#1f2a37", "#5b6675"


def clave(nombre: str) -> str:
    """Normaliza un nombre para fusionar actores ('Julián Quispe' == 'julian quispe')."""
    t = unicodedata.normalize("NFKD", str(nombre)).encode("ascii", "ignore").decode().lower()
    return " ".join(t.split())


# ------------------------------------------------------------------ registro
def normalizar_actores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in COL_ACTORES:
        if c not in df.columns:
            df[c] = None
    df["postura"] = pd.to_numeric(df["postura"], errors="coerce").fillna(0).clip(-2, 2).astype(int)
    df["influencia"] = pd.to_numeric(df["influencia"], errors="coerce").fillna(3).clip(1, 5).astype(int)
    texto = ["nombre", "tipo", "cargo", "organizacion", "comunidad", "fuente"]
    df[texto] = df[texto].fillna("").astype(str)
    df = df[df["nombre"].str.strip() != ""]
    return df[COL_ACTORES].drop_duplicates(subset="nombre", keep="last").reset_index(drop=True)


def normalizar_relaciones(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in COL_RELACIONES:
        if c not in df.columns:
            df[c] = ""
    df = df[COL_RELACIONES].fillna("").astype(str)
    return df[(df["origen"] != "") & (df["destino"] != "") & (df["origen"] != df["destino"])].reset_index(drop=True)


def normalizar_historial(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in COL_HISTORIAL:
        if c not in df.columns:
            df[c] = None
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").dt.date
    df["postura"] = pd.to_numeric(df["postura"], errors="coerce").fillna(0).clip(-2, 2).astype(int)
    df["influencia"] = pd.to_numeric(df["influencia"], errors="coerce").fillna(3).clip(1, 5).astype(int)
    texto = ["nombre", "reunion", "comunidad", "evidencia"]
    df[texto] = df[texto].fillna("").astype(str)
    df = df.dropna(subset=["fecha"])
    return df[COL_HISTORIAL].sort_values(["fecha", "nombre"]).reset_index(drop=True)


def fusionar(actores: pd.DataFrame, relaciones: pd.DataFrame, ext: ExtraccionReunion,
             comunidad_reunion: str, fuente: str, historial: pd.DataFrame | None = None,
             fecha=None, reunion: str = "") -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Agrega a los registros los actores y relaciones que la IA extrajo de una reunion.
    Si un actor ya existe (mismo nombre normalizado) se actualiza su postura e influencia, y la
    postura observada queda en el historial con su fecha (asi se ven los cambios en el tiempo)."""
    actores = actores.copy()
    historial = historial if historial is not None else pd.DataFrame(columns=COL_HISTORIAL)
    fecha = fecha or pd.Timestamp.today().date()
    fotos = []
    existentes = {clave(n): n for n in actores["nombre"]}
    nuevos = []
    for a in ext.actores:
        k = clave(a.nombre)
        com = a.comunidad or (comunidad_reunion if a.tipo in ("Dirigente comunal", "Organización de base") else "")
        if k in existentes:
            i = actores.index[actores["nombre"] == existentes[k]][0]
            actores.loc[i, ["postura", "influencia"]] = [a.postura, max(a.influencia, actores.loc[i, "influencia"])]
            for campo in ("cargo", "organizacion", "comunidad"):
                valor = com if campo == "comunidad" else getattr(a, campo)
                if valor and not actores.loc[i, campo]:
                    actores.loc[i, campo] = valor
        else:
            nuevos.append(dict(nombre=a.nombre, tipo=a.tipo, cargo=a.cargo, organizacion=a.organizacion,
                               comunidad=com, postura=a.postura, influencia=a.influencia, fuente=fuente))
            existentes[k] = a.nombre
        fotos.append(dict(nombre=existentes[k], fecha=fecha, reunion=reunion or fuente, comunidad=com,
                          postura=a.postura, influencia=a.influencia, evidencia=a.evidencia))
    actores = normalizar_actores(pd.concat([actores, pd.DataFrame(nuevos)], ignore_index=True))
    historial = normalizar_historial(pd.concat([historial, pd.DataFrame(fotos, columns=COL_HISTORIAL)],
                                               ignore_index=True))
    rels = [dict(origen=existentes.get(clave(r.origen), r.origen), destino=existentes.get(clave(r.destino), r.destino),
                 tipo=r.tipo, descripcion=r.descripcion, fuente=fuente) for r in ext.relaciones]
    relaciones = normalizar_relaciones(pd.concat([relaciones, pd.DataFrame(rels)], ignore_index=True))
    return actores, relaciones, historial


# ------------------------------------------------------------------ dinamica en el tiempo
def al_corte(actores: pd.DataFrame, historial: pd.DataFrame, fecha) -> pd.DataFrame:
    """El mapa 'como estaba' en una fecha: postura e influencia del ultimo registro hasta esa fecha.
    Los actores que aun no aparecian en ninguna reunion quedan fuera; los que no tienen historial se mantienen."""
    h = historial[historial["fecha"] <= fecha].sort_values("fecha")
    ultimo = h.groupby("nombre").last()[["postura", "influencia"]]
    con_historial = set(historial["nombre"])
    a = actores[actores["nombre"].isin(ultimo.index) | ~actores["nombre"].isin(con_historial)].copy()
    a = a.set_index("nombre")
    a.update(ultimo)
    return normalizar_actores(a.reset_index())


def cambios(historial: pd.DataFrame, desde, hasta) -> pd.DataFrame:
    """Actores cuya postura cambio entre dos fechas (antes = ultima postura conocida al inicio del periodo)."""
    h = historial[historial["fecha"] <= hasta].sort_values("fecha")
    filas = []
    for nombre, g in h.groupby("nombre"):
        previo = g[g["fecha"] <= desde]
        antes = previo.iloc[-1] if not previo.empty else g.iloc[0]
        despues = g.iloc[-1]
        delta = int(despues["postura"]) - int(antes["postura"])
        if delta == 0:
            continue
        motivo = g[(g["fecha"] > antes["fecha"]) & (g["postura"] != antes["postura"])]
        filas.append(dict(nombre=nombre, comunidad=despues["comunidad"], antes=int(antes["postura"]),
                          ahora=int(despues["postura"]), delta=delta, influencia=int(despues["influencia"]),
                          fecha_cambio=motivo.iloc[0]["fecha"] if not motivo.empty else despues["fecha"],
                          reunion=motivo.iloc[0]["reunion"] if not motivo.empty else despues["reunion"],
                          evidencia=motivo.iloc[0]["evidencia"] if not motivo.empty else despues["evidencia"]))
    if not filas:
        return pd.DataFrame(columns=["nombre", "comunidad", "antes", "ahora", "delta", "influencia",
                                     "fecha_cambio", "reunion", "evidencia"])
    d = pd.DataFrame(filas)
    d["riesgo"] = -d["delta"] * d["influencia"]  # quien se aleja y tiene peso, primero
    return d.sort_values(["riesgo", "fecha_cambio"], ascending=[False, False]).reset_index(drop=True)


def figura_cambios(c: pd.DataFrame, alto: int | None = None) -> go.Figure:
    """Grafico de pesas: de donde a donde se movio cada actor (naranja = se aleja, azul = se acerca)."""
    d = c.iloc[::-1]
    fig = go.Figure()
    for _, r in d.iterrows():
        col = "#c2410c" if r["delta"] < 0 else "#1c5cab"
        fig.add_annotation(x=r["ahora"], y=r["nombre"], ax=r["antes"], ay=r["nombre"], xref="x", yref="y",
                           axref="x", ayref="y", showarrow=True, arrowhead=2, arrowsize=1.2, arrowwidth=2.4,
                           arrowcolor=col, standoff=7, startstandoff=7)
    fig.add_trace(go.Scatter(x=d["antes"], y=d["nombre"], mode="markers", name="Antes",
                             marker=dict(size=11, color="white", line=dict(color="#8a8984", width=2)),
                             hovertemplate="%{y}: antes %{x}<extra></extra>"))
    fig.add_trace(go.Scatter(x=d["ahora"], y=d["nombre"], mode="markers", name="Ahora",
                             marker=dict(size=13, color=[POSTURA_COLOR[v] for v in d["ahora"]],
                                         line=dict(color="white", width=1.5)),
                             customdata=d[["reunion", "evidencia"]].values,
                             hovertemplate="<b>%{y}</b><br>%{customdata[0]}<br>“%{customdata[1]}”<extra></extra>"))
    fig.update_xaxes(range=[-2.5, 2.5], tickvals=list(POSTURA_TXT), ticktext=list(POSTURA_TXT.values()),
                     showgrid=True, gridcolor="rgba(31,42,55,0.06)", zeroline=True, zerolinecolor="rgba(31,42,55,0.25)")
    fig.update_yaxes(showgrid=False)
    fig.update_layout(height=alto or max(220, 34 * len(d) + 70), margin=dict(l=8, r=8, t=8, b=8),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
                      font=dict(family="Inter, Segoe UI, sans-serif", color=TINTA_2),
                      hoverlabel=dict(bgcolor="white", font_size=12))
    return fig


SERIE = ["#2a78d6", "#d03b3b", "#1baf7a", "#eda100", "#6250d6", "#8a8984"]


def figura_trayectorias(historial: pd.DataFrame, nombres: list[str], alto: int = 380) -> go.Figure:
    """Postura de cada actor reunion tras reunion (linea escalonada)."""
    fig = go.Figure()
    fig.add_hrect(y0=0.5, y1=2.5, fillcolor="rgba(28,92,171,0.06)", line_width=0, layer="below")
    fig.add_hrect(y0=-2.5, y1=-0.5, fillcolor="rgba(194,65,12,0.06)", line_width=0, layer="below")
    for i, n in enumerate(nombres):
        h = historial[historial["nombre"] == n].sort_values("fecha")
        if h.empty:
            continue
        col = SERIE[i % len(SERIE)]
        fig.add_trace(go.Scatter(
            x=h["fecha"], y=h["postura"], mode="lines+markers", name=n, line=dict(color=col, width=2.5, shape="hv"),
            marker=dict(size=8, color=col, line=dict(color="white", width=1.5)),
            customdata=h[["reunion", "evidencia"]].values,
            hovertemplate="<b>" + n + "</b> · %{x|%d/%m/%Y}<br>%{customdata[0]}<br>“%{customdata[1]}”<extra></extra>"))
    fig.update_yaxes(range=[-2.5, 2.5], tickvals=list(POSTURA_TXT), ticktext=list(POSTURA_TXT.values()),
                     showgrid=True, gridcolor="rgba(31,42,55,0.06)", zeroline=False)
    fig.update_xaxes(showgrid=False, tickformat="%b %Y")
    fig.update_layout(height=alto, margin=dict(l=8, r=8, t=8, b=8), plot_bgcolor="rgba(0,0,0,0)",
                      paper_bgcolor="rgba(0,0,0,0)", hovermode="closest",
                      legend=dict(orientation="h", y=-0.15, x=0),
                      font=dict(family="Inter, Segoe UI, sans-serif", color=TINTA_2),
                      hoverlabel=dict(bgcolor="white", font_size=12))
    return fig


# ------------------------------------------------------------------ red
def red(actores: pd.DataFrame, relaciones: pd.DataFrame) -> nx.Graph:
    g = nx.Graph()
    for _, a in actores.iterrows():
        g.add_node(a["nombre"], **a.to_dict())
    for _, r in relaciones.iterrows():
        for n in (r["origen"], r["destino"]):
            if n not in g:
                g.add_node(n, nombre=n, tipo="Otro", cargo="", organizacion="", comunidad="",
                           postura=0, influencia=2, fuente="relación")
        g.add_edge(r["origen"], r["destino"], tipo=r["tipo"], descripcion=r["descripcion"],
                   peso=2.0 if r["tipo"] in ("Alianza", "Representa a", "Parentesco") else 1.0)
    return g


def metricas(g: nx.Graph) -> pd.DataFrame:
    """Indicadores por actor: grado, intermediacion y si es puente entre comunidades."""
    if g.number_of_nodes() == 0:
        return pd.DataFrame(columns=COL_ACTORES + ["vinculos", "intermediacion", "comunidades_conectadas", "puente"])
    grado = dict(g.degree())
    inter = nx.betweenness_centrality(g, normalized=True)
    filas = []
    for n, d in g.nodes(data=True):
        coms = {g.nodes[v].get("comunidad") for v in g.neighbors(n)} | {d.get("comunidad")}
        coms.discard("")
        coms.discard(None)
        filas.append({**{c: d.get(c) for c in COL_ACTORES}, "vinculos": grado[n],
                      "intermediacion": round(inter[n], 3), "comunidades_conectadas": len(coms),
                      "conflictos": sum(1 for v in g.neighbors(n) if g.edges[n, v]["tipo"] == "Conflicto")})
    m = pd.DataFrame(filas)
    m["puente"] = m["comunidades_conectadas"] >= 2
    m["postura_txt"] = m["postura"].map(POSTURA_TXT)
    return m.sort_values("intermediacion", ascending=False).reset_index(drop=True)


def _separar(angulos: dict, minimo: float) -> dict:
    """Separa angulos (radianes) para que dos nodos del mismo anillo no se tapen."""
    orden = sorted(angulos, key=angulos.get)
    a = [angulos[n] for n in orden]
    for _ in range(60):
        movido = False
        for k in range(1, len(a)):
            if a[k] - a[k - 1] < minimo:
                d = (minimo - (a[k] - a[k - 1])) / 2
                a[k - 1] -= d
                a[k] += d
                movido = True
        if not movido:
            break
    return dict(zip(orden, a))


def _posiciones(g: nx.Graph) -> tuple[dict, dict]:
    """Disposicion legible y estable: cada comunidad es un grupo en el anillo exterior (su dirigente
    al centro del grupo); la empresa va al centro; Estado, autoridades y sociedad civil en un anillo
    intermedio, orientados hacia las comunidades con las que se relacionan."""
    comunidades = sorted({d.get("comunidad") for _, d in g.nodes(data=True) if d.get("comunidad")})
    nc = max(1, len(comunidades))
    ang_com = {c: np.pi / 2 - 2 * np.pi * i / nc for i, c in enumerate(comunidades)}
    R_COM, R_EXT, R_EMP = 3.6, 1.9, 0.8
    pos, anclas = {}, {}
    for c in comunidades:
        centro = R_COM * np.array([np.cos(ang_com[c]), np.sin(ang_com[c])])
        anclas[c] = centro
        miembros = sorted((n for n, d in g.nodes(data=True) if d.get("comunidad") == c),
                          key=lambda n: (-int(g.nodes[n].get("influencia", 3)), n))
        pos[miembros[0]] = centro
        resto = miembros[1:]
        r = 0.62 + 0.05 * max(0, len(resto) - 4)
        for k, n in enumerate(resto):
            t = ang_com[c] + np.pi + 2 * np.pi * (k + 0.5) / max(1, len(resto))
            pos[n] = centro + r * np.array([np.cos(t), np.sin(t)])

    def angulo_vecinos(n):
        angs = [ang_com[g.nodes[v]["comunidad"]] for v in g.neighbors(n) if g.nodes[v].get("comunidad")]
        if not angs:
            return None
        return float(np.arctan2(np.mean(np.sin(angs)), np.mean(np.cos(angs))))

    externos = [n for n, d in g.nodes(data=True) if not d.get("comunidad")]
    empresa = [n for n in externos if g.nodes[n].get("tipo") == "Empresa"]
    otros = [n for n in externos if n not in empresa]
    if empresa:  # el de mayor influencia al centro
        empresa.sort(key=lambda n: (-int(g.nodes[n].get("influencia", 3)), n))
        pos[empresa[0]] = np.zeros(2)
        libres = iter(np.linspace(0, 2 * np.pi, max(1, len(empresa) - 1), endpoint=False) + 0.3)
        ang = {n: (angulo_vecinos(n) if angulo_vecinos(n) is not None else next(libres)) for n in empresa[1:]}
        for n, t in _separar(ang, 0.7).items():
            pos[n] = R_EMP * np.array([np.cos(t), np.sin(t)])
    libres = iter(np.linspace(0, 2 * np.pi, max(1, len(otros)), endpoint=False) + 0.15)
    ang = {}
    for n in otros:
        a = angulo_vecinos(n)
        ang[n] = a if a is not None else next(libres)
    for n, t in _separar(ang, 0.5).items():
        pos[n] = R_EXT * np.array([np.cos(t), np.sin(t)])
    return pos, anclas


def figura_red(g: nx.Graph, m: pd.DataFrame, alto: int = 640, resaltar: str | None = None) -> go.Figure:
    pos, anclas = _posiciones(g)
    fig = go.Figure()
    # aristas agrupadas por tipo (una traza por tipo para la leyenda)
    for tipo, (color, guion, ancho) in REL_ESTILO.items():
        xs, ys = [], []
        for u, v, d in g.edges(data=True):
            if d["tipo"] != tipo:
                continue
            if resaltar and resaltar not in (u, v):
                continue
            xs += [pos[u][0], pos[v][0], None]
            ys += [pos[u][1], pos[v][1], None]
        if xs:
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name=tipo, hoverinfo="skip",
                                     line=dict(color=color, width=ancho, dash=guion), opacity=0.75))
    # etiquetas de comunidad (fondo de cada grupo)
    for com, c in anclas.items():
        c = c + np.array([0, 0.95 if c[1] > -1 else -1.15])  # rotulo por fuera del grupo
        fig.add_annotation(x=c[0], y=c[1], text=f"<b>{com.replace('C.C. ', '')}</b>", showarrow=False,
                           font=dict(size=12, color=TINTA_2), bgcolor="rgba(238,241,245,0.9)", borderpad=3)
    # nodos
    mi = m.set_index("nombre")
    vecinos = set(g.neighbors(resaltar)) | {resaltar} if resaltar and resaltar in g else None
    for post in sorted(POSTURA_TXT):
        nodos = [n for n, d in g.nodes(data=True) if int(d.get("postura", 0)) == post]
        if not nodos:
            continue
        x = [pos[n][0] for n in nodos]
        y = [pos[n][1] for n in nodos]
        size = [7 + 4 * int(g.nodes[n].get("influencia", 3)) for n in nodos]
        simb = [SIMBOLO_TIPO.get(g.nodes[n].get("tipo"), "circle") for n in nodos]
        borde = ["#111827" if (n in mi.index and mi.loc[n, "puente"] and mi.loc[n, "intermediacion"] > 0.05)
                 else "white" for n in nodos]
        opac = [1.0 if (vecinos is None or n in vecinos) else 0.18 for n in nodos]
        etiquetas = [n if ((vecinos and n in vecinos) or (vecinos is None and (
                         int(g.nodes[n].get("influencia", 3)) >= 5 or
                         (not g.nodes[n].get("comunidad") and int(g.nodes[n].get("influencia", 3)) >= 4))))
                     else "" for n in nodos]
        custom = [[n, g.nodes[n].get("cargo", ""), g.nodes[n].get("organizacion", ""),
                   g.nodes[n].get("comunidad", "") or "—", POSTURA_TXT[post], g.nodes[n].get("influencia", 3),
                   int(mi.loc[n, "vinculos"]) if n in mi.index else 0,
                   float(mi.loc[n, "intermediacion"]) if n in mi.index else 0] for n in nodos]
        fig.add_trace(go.Scatter(
            x=x, y=y, mode="markers+text", name=POSTURA_TXT[post], text=etiquetas,
            textposition="bottom center", textfont=dict(size=10.5, color=TINTA),
            marker=dict(size=size, color=POSTURA_COLOR[post], symbol=simb, opacity=opac,
                        line=dict(color=borde, width=2)),
            customdata=custom,
            hovertemplate=("<b>%{customdata[0]}</b><br>%{customdata[1]} · %{customdata[2]}"
                           "<br>Comunidad: %{customdata[3]}<br>Postura: %{customdata[4]} · Influencia: %{customdata[5]}/5"
                           "<br>Vínculos: %{customdata[6]} · Intermediación: %{customdata[7]:.2f}<extra></extra>"),
        ))
    fig.update_xaxes(visible=False, range=[-5.6, 5.6])
    fig.update_yaxes(visible=False, range=[-5.0, 5.0], scaleanchor="x", scaleratio=1)
    fig.update_layout(
        height=alto, margin=dict(l=4, r=4, t=4, b=4), plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)", dragmode="pan",
        legend=dict(orientation="h", yanchor="top", y=-0.01, x=0, font=dict(size=11.5)),
        font=dict(family="Inter, Segoe UI, sans-serif", color=TINTA_2),
        hoverlabel=dict(bgcolor="white", font_size=12),
    )
    return fig


def matriz_poder_interes(m: pd.DataFrame, alto: int = 470) -> go.Figure:
    """Matriz influencia (eje Y) x postura hacia la empresa (eje X), con cuadrantes de gestion."""
    d = m.copy()
    rng = np.random.default_rng(3)  # separacion leve para que no se tapen puntos iguales
    d["x"] = d["postura"] + rng.uniform(-0.28, 0.28, len(d))
    d["y"] = d["influencia"] + rng.uniform(-0.28, 0.28, len(d))
    fig = go.Figure()
    zonas = [  # x0, x1, y0, y1, texto, color
        (-2.5, -0.5, 3.5, 5.5, "Gestionar de cerca<br>(influyentes y críticos)", "rgba(194,65,12,0.08)"),
        (0.5, 2.5, 3.5, 5.5, "Aliados clave<br>(involucrar)", "rgba(28,92,171,0.08)"),
        (-2.5, -0.5, 0.5, 3.5, "Monitorear<br>(críticos con poca influencia)", "rgba(194,65,12,0.04)"),
        (0.5, 2.5, 0.5, 3.5, "Mantener informados", "rgba(28,92,171,0.04)"),
    ]
    for x0, x1, y0, y1, txt, col in zonas:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1, fillcolor=col, line_width=0, layer="below")
        fig.add_annotation(x=(x0 + x1) / 2, y=y1 - 0.25, text=txt, showarrow=False,
                           font=dict(size=11, color=TINTA_2))
    for post in sorted(POSTURA_TXT):
        s = d[d["postura"] == post]
        if s.empty:
            continue
        fig.add_trace(go.Scatter(
            x=s["x"], y=s["y"], mode="markers", name=POSTURA_TXT[post],
            marker=dict(size=10 + 1.6 * s["vinculos"].clip(upper=10), color=POSTURA_COLOR[post],
                        symbol=[SIMBOLO_TIPO.get(t, "circle") for t in s["tipo"]],
                        line=dict(color="white", width=1.5)),
            customdata=s[["nombre", "cargo", "comunidad", "vinculos"]].values,
            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>%{customdata[2]}"
                          "<br>Vínculos: %{customdata[3]}<extra></extra>",
        ))
    fig.update_xaxes(range=[-2.5, 2.5], tickvals=list(POSTURA_TXT), ticktext=list(POSTURA_TXT.values()),
                     title="Postura hacia la empresa", showgrid=False, zeroline=True, zerolinecolor="rgba(31,42,55,0.2)")
    fig.update_yaxes(range=[0.5, 5.5], tickvals=[1, 2, 3, 4, 5], title="Influencia", showgrid=True,
                     gridcolor="rgba(31,42,55,0.06)")
    fig.update_layout(height=alto, margin=dict(l=8, r=8, t=8, b=8), plot_bgcolor="rgba(0,0,0,0)",
                      paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
                      font=dict(family="Inter, Segoe UI, sans-serif", color=TINTA_2),
                      hoverlabel=dict(bgcolor="white", font_size=12))
    return fig


def balance_comunidades(m: pd.DataFrame) -> go.Figure:
    """Cuantos actores de cada postura hay en cada comunidad (barras apiladas divergentes)."""
    d = m[m["comunidad"] != ""].copy()
    d["comunidad_c"] = d["comunidad"].str.replace("C.C. ", "", regex=False)
    t = d.pivot_table(index="comunidad_c", columns="postura", values="nombre", aggfunc="count", fill_value=0)
    t = t.reindex(columns=sorted(POSTURA_TXT), fill_value=0)
    t = t.loc[(t[[1, 2]].sum(axis=1) - t[[-2, -1]].sum(axis=1)).sort_values().index]
    fig = go.Figure()
    for post in [-1, -2]:
        fig.add_trace(go.Bar(y=t.index, x=-t[post], orientation="h", name=POSTURA_TXT[post],
                             marker=dict(color=POSTURA_COLOR[post], line=dict(color="white", width=2)),
                             customdata=t[post], hovertemplate="%{y}: %{customdata} " + POSTURA_TXT[post].lower() + "<extra></extra>"))
    for post in [0, 1, 2]:
        fig.add_trace(go.Bar(y=t.index, x=t[post], orientation="h", name=POSTURA_TXT[post],
                             marker=dict(color=POSTURA_COLOR[post], line=dict(color="white", width=2)),
                             hovertemplate="%{y}: %{x} " + POSTURA_TXT[post].lower() + "<extra></extra>"))
    lim = max(1, int(t.abs().sum(axis=1).max()))
    fig.update_layout(barmode="relative", height=330, margin=dict(l=8, r=8, t=8, b=8),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                      legend=dict(orientation="h", y=-0.12, x=0, traceorder="normal"),
                      font=dict(family="Inter, Segoe UI, sans-serif", color=TINTA_2))
    fig.update_xaxes(range=[-lim, lim], tickvals=list(range(-lim, lim + 1, max(1, lim // 3))),
                     ticktext=[str(abs(v)) for v in range(-lim, lim + 1, max(1, lim // 3))],
                     showgrid=True, gridcolor="rgba(31,42,55,0.06)", zeroline=True, zerolinecolor=TINTA)
    fig.update_yaxes(showgrid=False)
    return fig

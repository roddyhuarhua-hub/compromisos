"""Conflictividad historica en laminas 4K (16:9) para presentaciones: una lamina por grafico,
con su mensaje clave y la columna 'Lo que hay que saber'. Misma marca que las laminas del panel."""
from __future__ import annotations

from datetime import date

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Rectangle

from . import mapa_base
from .conflictos import DE_FUERZA, TIPO_COLOR, indicadores
from .panel_imagen import BORDE, TINTA, TINTA_2, VERDE, VERDE_OSC, _a_png, _claves, _corto, _lamina
from .visual import SEMAFORO

LADO = dict(x=0.675, w=0.29, y=0.1, h=0.71)


def _tam(d: pd.DataFrame) -> np.ndarray:
    return (140 + 160 * np.sqrt(d["duracion_dias"].clip(lower=0.5))).to_numpy()


def _leyenda_tipos(ax, tipos, **kw):
    h = [Line2D([], [], marker="o", ls="", color=TIPO_COLOR[t], markersize=10, label=t) for t in tipos]
    ax.legend(handles=h, frameon=False, fontsize=11.5, **kw)


def _mapa(ax, df: pd.DataFrame, comunidades: pd.DataFrame, fondo: str = "satelite"):
    d = df.dropna(subset=["lat", "lon"])
    c = comunidades.dropna(subset=["lat", "lon"])
    for _, r in d[d["tipo"].isin(DE_FUERZA)].iterrows():  # halo de calor: dias de paralizacion
        for k, a in ((9, 0.05), (5, 0.08)):
            ax.scatter(r["lon"], r["lat"], s=(80 + 60 * r["duracion_dias"]) * k, color="#eb6834", alpha=a, lw=0,
                       zorder=1)
    ax.scatter(c["lon"], c["lat"], s=110, color="white", edgecolors=TINTA, linewidths=1.5, marker="^", zorder=2)
    for _, r in c.iterrows():
        ax.annotate(_corto(r["comunidad"]), (r["lon"], r["lat"]), xytext=(0, -20), textcoords="offset points",
                    ha="center", fontsize=12, fontweight="bold", color=TINTA, zorder=5,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.8))
    for tipo, color in TIPO_COLOR.items():
        s = d[d["tipo"] == tipo]
        if not s.empty:
            ax.scatter(s["lon"], s["lat"], s=_tam(s), color=color, alpha=0.88, zorder=3,
                       edgecolors=np.where(s["hubo_violencia"], "#111827", "white"),
                       linewidths=np.where(s["hubo_violencia"], 2.5, 1.2))
    todo = pd.concat([d[["lat", "lon"]], c[["lat", "lon"]]])
    mx = (todo["lon"].max() - todo["lon"].min()) * 0.12 + 0.03
    my = (todo["lat"].max() - todo["lat"].min()) * 0.12 + 0.03
    ax.set_xlim(todo["lon"].min() - mx, todo["lon"].max() + mx)
    ax.set_ylim(todo["lat"].min() - my, todo["lat"].max() + my)
    ax.set_aspect(1 / np.cos(np.radians(todo["lat"].mean())), adjustable="box")
    ax.set_facecolor("#eef3ee")
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    mapa_base.poner_fondo(ax, fondo)  # imagen satelital o relieve debajo (si hay internet)
    _leyenda_tipos(ax, [t for t in TIPO_COLOR if (d["tipo"] == t).any()], loc="upper center",
                   bbox_to_anchor=(0.5, -0.01), ncol=4)


def _cronologia(ax, df: pd.DataFrame):
    d = df.copy()
    d["com"] = d["comunidad"].replace("", "Sin comunidad").map(_corto)
    orden = d.groupby("com").size().sort_values().index.tolist()
    y = {c: i for i, c in enumerate(orden)}
    for tipo, color in TIPO_COLOR.items():
        s = d[d["tipo"] == tipo]
        if not s.empty:
            ax.scatter(pd.to_datetime(s["fecha"]), s["com"].map(y), s=_tam(s), color=color, alpha=0.88, zorder=3,
                       edgecolors=np.where(s["hubo_violencia"], "#111827", "white"),
                       linewidths=np.where(s["hubo_violencia"], 2.5, 1.2))
    ax.set_yticks(range(len(orden)), orden, fontsize=14, color=TINTA)
    ax.set_ylim(-0.7, len(orden) - 0.3)
    ax.grid(axis="y", color=BORDE)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.tick_params(axis="x", labelsize=13)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    _leyenda_tipos(ax, [t for t in TIPO_COLOR if (d["tipo"] == t).any()], loc="upper center",
                   bbox_to_anchor=(0.5, -0.08), ncol=4)


def laminas_conflictos(conf: pd.DataFrame, ind: pd.DataFrame, comunidades: pd.DataFrame, hoy: date,
                       cliente: str = "", filtros: str = "", fondo: str = "satelite") -> list[tuple[str, bytes]]:
    """Devuelve [(nombre_archivo, png 3840x2160), ...]."""
    out = []
    if conf.empty:
        return out
    k = indicadores(conf, hoy)
    fuerza = conf[conf["tipo"].isin(DE_FUERZA)]
    anios = pd.to_datetime(conf["fecha"]).dt.year
    periodo = f"{anios.min()}–{anios.max()}"

    # 1. resumen
    fig = _lamina("Conflictividad histórica del territorio",
                  f"{k['eventos']} eventos de conflicto entre {periodo}: {k['medidas_fuerza']} medidas de fuerza que "
                  f"sumaron {k['dias_paralizacion']} días de paralización.", cliente, hoy, filtros)
    kpis = [("Eventos registrados", f"{k['eventos']}", f"{k['medidas_fuerza']} medidas de fuerza", VERDE),
            ("Días de paralización", f"{k['dias_paralizacion']}", "bloqueos, paros y tomas", "#a32424"),
            ("Bloqueos de vía", f"{k['bloqueos']}", "tránsito afectado", "#c2410c"),
            ("Con violencia", f"{k['con_violencia']}", "heridos, detenidos o daños", "#111827"),
            ("Último evento (días)", f"{k['dias_desde_ultimo']}", f"hace {k['dias_desde_ultimo']} días · {k['ultimo']:%d/%m/%Y}",
             "#eda100")]
    for i, (e, v, s_, c) in enumerate(kpis):
        x = 0.035 + i * 0.188
        fig.patches.append(FancyBboxPatch((x, 0.5), 0.175, 0.28, boxstyle="round,pad=0,rounding_size=0.01",
                                          transform=fig.transFigure, fc="white", ec=BORDE, lw=1.2, zorder=-10))
        fig.patches.append(Rectangle((x, 0.768), 0.175, 0.012, transform=fig.transFigure, fc=c, ec="none",
                                     zorder=-9))
        fig.text(x + 0.015, 0.72, e, fontsize=14, color=TINTA_2)
        fig.text(x + 0.015, 0.585, v, fontsize=50 if len(v) > 5 else 58, fontweight="bold", color=TINTA)
        fig.text(x + 0.015, 0.53, s_, fontsize=13, color=TINTA_2)
    fig.text(0.035, 0.43, "Hechos más recientes", fontsize=18, fontweight="bold", color=VERDE_OSC)
    for i, (_, r) in enumerate(conf.sort_values("fecha", ascending=False).head(4).iterrows()):
        y = 0.37 - i * 0.07
        fig.patches.append(Rectangle((0.035, y - 0.012), 0.006, 0.05, transform=fig.transFigure,
                                     fc=TIPO_COLOR.get(r["tipo"], "#8a8984"), ec="none"))
        fig.text(0.05, y + 0.012, f"{r['fecha']:%d/%m/%Y} · {r['titulo']}", fontsize=14, fontweight="bold",
                 color=TINTA)
        fig.text(0.05, y - 0.012, f"{r['tipo']} · {r['lugar'] or _corto(r['comunidad'])} · {r['duracion_dias']} días"
                 f" · {r['desenlace']}" + (" · con violencia" if r["hubo_violencia"] else ""), fontsize=12,
                 color=TINTA_2)
    out.append(("01_conflictividad_resumen.png", _a_png(fig)))

    # 2. mapa
    lugares = conf[conf["lugar"] != ""].groupby("lugar").agg(n=("tipo", "count"), dias=("duracion_dias", "sum"))
    lugares = lugares.sort_values(["n", "dias"], ascending=False)
    top = lugares.index[0] if not lugares.empty else "—"
    fig = _lamina("Dónde ocurrieron los conflictos",
                  f"{top} es el punto caliente: {int(lugares.iloc[0]['n'])} eventos y "
                  f"{int(lugares.iloc[0]['dias'])} días de medidas." if not lugares.empty else "Lugares de los eventos.",
                  cliente, hoy, filtros)
    ax = fig.add_axes([0.035, 0.16, 0.62, 0.66])
    _mapa(ax, conf, comunidades, fondo)
    _claves(fig, **LADO, titulo="Puntos calientes que se repiten", puntos=[
        (f"{int(r.n)}", f"eventos en {lugar} ({int(r.dias)} días)", "#c2410c")
        for lugar, r in lugares.head(3).iterrows()])
    out.append(("02_mapa_conflictos.png", _a_png(fig)))

    # 3. cronologia
    por_com = conf.groupby("comunidad").size().sort_values(ascending=False)
    fig = _lamina("Cronología del conflicto por comunidad",
                  f"{_corto(por_com.index[0])} es la comunidad con más eventos ({por_com.iloc[0]}). Tamaño = días "
                  "de duración; borde negro = hubo violencia.", cliente, hoy, filtros)
    ax = fig.add_axes([0.2, 0.2, 0.765, 0.6])
    ax.set_facecolor("none")
    _cronologia(ax, conf)
    out.append(("03_cronologia_conflictos.png", _a_png(fig)))

    # 4. por año
    t = conf.assign(anio=anios).pivot_table(index="anio", columns="tipo", values="titulo", aggfunc="count",
                                             fill_value=0)
    dias = fuerza.assign(anio=pd.to_datetime(fuerza["fecha"]).dt.year).groupby("anio")["duracion_dias"].sum()
    pico = t.sum(axis=1).idxmax()
    fig = _lamina("Eventos de conflicto por año",
                  f"{pico} fue el año más conflictivo ({t.sum(axis=1).max()} eventos); el año con más días de "
                  f"paralización fue {dias.idxmax() if not dias.empty else '—'}.", cliente, hoy, filtros)
    ax = fig.add_axes([0.07, 0.2, 0.57, 0.6])
    ax.set_facecolor("none")
    abajo = np.zeros(len(t))
    for tipo, color in TIPO_COLOR.items():
        if tipo in t.columns:
            ax.bar(t.index.astype(str), t[tipo], bottom=abajo, color=color, edgecolor="white", lw=1.5, label=tipo)
            abajo += t[tipo].values
    for x, total in zip(t.index.astype(str), t.sum(axis=1)):
        ax.text(x, total + 0.1, str(total), ha="center", va="bottom", fontsize=14, fontweight="bold", color=TINTA)
    ax.set_xticks(range(len(t)), [f"{a}\n{int(dias.get(a, 0))} días" for a in t.index], fontsize=13)
    ax.tick_params(axis="y", labelsize=12)
    ax.grid(axis="y", color=BORDE)
    ax.legend(frameon=False, fontsize=11, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.13))
    _claves(fig, **LADO, titulo="Lo que hay que saber", puntos=[
        (f"{t.sum(axis=1).max()}", f"eventos en {pico}, el año más conflictivo", "#a32424"),
        (f"{int(dias.max()) if not dias.empty else 0}", f"días de paralización en "
         f"{dias.idxmax() if not dias.empty else '—'}", "#c2410c"),
        (f"{t.sum(axis=1).iloc[-1]}", f"eventos en {t.index[-1]} (último año del registro)", VERDE)])
    out.append(("04_conflictos_por_anio.png", _a_png(fig)))

    # 5. dias de paralizacion por comunidad
    if not fuerza.empty:
        g = fuerza.assign(com=fuerza["comunidad"].replace("", "Sin comunidad").map(_corto)).groupby("com").agg(
            dias=("duracion_dias", "sum"), medidas=("tipo", "count"), violencia=("hubo_violencia", "sum")
        ).sort_values("dias")
        fig = _lamina("Días de paralización por comunidad",
                      f"{g.index[-1]} acumula {int(g['dias'].iloc[-1])} días de bloqueos, paros y tomas.",
                      cliente, hoy, filtros)
        ax = fig.add_axes([0.2, 0.15, 0.4, 0.63])
        ax.set_facecolor("none")
        ax.barh(g.index, g["dias"], color="#c2410c", height=0.6)
        for i, (dd, m, v) in enumerate(zip(g["dias"], g["medidas"], g["violencia"])):
            ax.text(dd + g["dias"].max() * 0.02, i, f"{dd} días · {m} medida{'s' * (m != 1)}"
                    + (f" · {v} con violencia" if v else ""), va="center", fontsize=13, color=TINTA)
        ax.set_xlim(0, g["dias"].max() * 1.9)
        ax.tick_params(axis="y", labelsize=15, length=0)
        ax.tick_params(axis="x", labelsize=12)
        ax.spines["left"].set_visible(False)
        _claves(fig, **LADO, titulo="Lo que hay que saber", puntos=[
            (f"{k['dias_paralizacion']}", "días de paralización en total", "#a32424"),
            (f"{k['bloqueos']}", "bloqueos de vía", "#c2410c"),
            (f"{k['con_violencia']}", "eventos con violencia (heridos, detenidos o daños)", "#111827")])
        out.append(("05_dias_paralizacion.png", _a_png(fig)))

    # 6. motivos
    m = conf["tema"].replace("", "Otro").value_counts().sort_values()
    fig = _lamina("¿Por qué protestan?", f"{m.index[-1]} es la principal demanda: {m.iloc[-1]} de {len(conf)} eventos.",
                  cliente, hoy, filtros)
    ax = fig.add_axes([0.2, 0.15, 0.42, 0.63])
    ax.set_facecolor("none")
    ax.barh(m.index, m.values, color=VERDE, height=0.6)
    for i, v in enumerate(m.values):
        ax.text(v + m.max() * 0.02, i, str(v), va="center", fontsize=14, fontweight="bold", color=TINTA)
    ax.tick_params(axis="y", labelsize=15, length=0)
    ax.tick_params(axis="x", labelsize=12)
    ax.spines["left"].set_visible(False)
    tf = fuerza["tema"].replace("", "Otro").value_counts()
    _claves(fig, **LADO, titulo="En las medidas de fuerza", puntos=[
        (f"{n}", f"de {len(fuerza)} bloqueos, paros o tomas fueron por {t.lower()}", "#c2410c")
        for t, n in tf.head(3).items()])
    out.append(("06_motivos_conflicto.png", _a_png(fig)))

    # 7. incumplimiento y conflicto
    if not ind.empty:
        desde = date(hoy.year - 3, hoy.month, 1)
        rec = conf[conf["fecha"] >= desde]
        ev = rec.groupby("comunidad").size()
        dd = rec[rec["tipo"].isin(DE_FUERZA)].groupby("comunidad")["duracion_dias"].sum()
        d = ind.assign(eventos=ind["comunidad"].map(ev).fillna(0), dias=ind["comunidad"].map(dd).fillna(0))
        r = np.corrcoef(d["vencidos"], d["eventos"])[0, 1] if len(d) >= 3 and d["vencidos"].std() > 0 else None
        fig = _lamina("Incumplimiento y conflicto",
                      ("Donde más compromisos se vencen, más se protesta" if r and r > 0.4 else
                       "Relación entre compromisos vencidos y conflicto") +
                      (f" (correlación {r:.2f}, eventos desde {desde:%Y})." if r is not None else "."),
                      cliente, hoy, filtros)
        ax = fig.add_axes([0.08, 0.15, 0.56, 0.63])
        ax.set_facecolor("none")
        ax.scatter(d["vencidos"], d["eventos"], s=300 + 60 * d["dias"], c=[SEMAFORO[s] for s in d["semaforo"]],
                   alpha=0.85, edgecolors="white", linewidths=2, zorder=3)
        vistos: dict = {}
        for _, f in d.sort_values("vencidos").iterrows():
            n = vistos.get(f["eventos"], 0)  # rotulos alternados arriba/abajo si comparten altura
            vistos[f["eventos"]] = n + 1
            ax.annotate(_corto(f["comunidad"]), (f["vencidos"], f["eventos"]), xytext=(0, 16 if n % 2 == 0 else -26),
                        textcoords="offset points", ha="center", fontsize=13, color=TINTA, fontweight="bold")
        if r is not None:
            a, b = np.polyfit(d["vencidos"], d["eventos"], 1)
            xs = np.array([0, d["vencidos"].max()])
            ax.plot(xs, a * xs + b, ls=":", color=TINTA_2, lw=1.8)
        ax.set_xlabel("Compromisos vencidos sin cumplir (hoy)", fontsize=14)
        ax.set_ylabel(f"Eventos de conflicto desde {desde:%Y}", fontsize=14)
        ax.tick_params(labelsize=12)
        ax.grid(color=BORDE)
        ax.set_ylim(-0.5, d["eventos"].max() * 1.25 + 0.5)
        ax.set_xlim(-0.8, d["vencidos"].max() * 1.15 + 1)
        top_r = d.sort_values(["eventos", "vencidos"], ascending=False).iloc[0]
        _claves(fig, **LADO, titulo="Lo que hay que saber", puntos=[
            (f"{r:.2f}" if r is not None else "–", "correlación entre vencidos y eventos de conflicto", VERDE_OSC),
            (f"{int(top_r['eventos'])}", f"eventos recientes en {_corto(top_r['comunidad'])}, con "
             f"{int(top_r['vencidos'])} compromisos vencidos", SEMAFORO["Crítico"]),
            ("→", "cumplir a tiempo es la mejor prevención del conflicto", VERDE)])
        out.append(("07_incumplimiento_y_conflicto.png", _a_png(fig)))
    plt.close("all")
    return out

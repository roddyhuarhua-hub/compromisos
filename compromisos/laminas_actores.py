"""Mapa de actores en laminas 4K (16:9) para presentaciones: red de relaciones, actores clave,
matriz poder-postura, balance por comunidad y dinamica de posturas. Misma marca que las otras laminas."""
from __future__ import annotations

from datetime import date

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Rectangle

from . import actores as ac
from .panel_imagen import BORDE, TINTA, TINTA_2, VERDE, VERDE_OSC, _a_png, _claves, _corto, _lamina

LADO = dict(x=0.675, w=0.29, y=0.1, h=0.71)
MARCADOR = {"circle": "o", "square": "s", "diamond": "D", "triangle-up": "^"}
ESTILO_LINEA = {"solid": "-", "dot": ":", "dash": "--"}


def dibujar_red(ax, A: pd.DataFrame, R: pd.DataFrame, escala: float = 1.0, leyenda: bool = True,
                letra_leyenda: float | None = None):
    """Red de actores (misma disposicion que en la app): comunidades en el anillo exterior, empresa al centro."""
    g = ac.red(A, R)
    pos, anclas = ac._posiciones(g)
    for u, v, d in g.edges(data=True):
        color, guion, ancho = ac.REL_ESTILO.get(d["tipo"], ("#8a8984", "solid", 1))
        ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]], color=color, alpha=0.6, lw=ancho * 0.8 * escala,
                ls=ESTILO_LINEA[guion], zorder=1)
    for n, d in g.nodes(data=True):
        ax.scatter(*pos[n], s=(25 + 28 * int(d.get("influencia", 3))) * escala ** 2,
                   c=ac.POSTURA_COLOR[int(d.get("postura", 0))],
                   marker=MARCADOR[ac.SIMBOLO_TIPO.get(d.get("tipo"), "circle")], edgecolors="white",
                   linewidths=1 * escala, zorder=3)
        if int(d.get("influencia", 3)) >= 5 or (not d.get("comunidad") and int(d.get("influencia", 3)) >= 4):
            ax.annotate(n, pos[n], xytext=(0, -11 * escala), textcoords="offset points", ha="center",
                        fontsize=6.5 * escala, color=TINTA, zorder=4)
    for com, c in anclas.items():
        y = c[1] + (0.95 if c[1] > -1 else -1.15)
        ax.text(c[0], y, _corto(com), ha="center", fontsize=8 * escala, fontweight="bold", color=TINTA_2,
                bbox=dict(boxstyle="round,pad=0.25", fc="#eef1f5", ec="none"))
    if leyenda:
        letra = letra_leyenda or 8 * escala
        h = [Line2D([], [], marker="o", ls="", color=ac.POSTURA_COLOR[p], markersize=letra * 0.8, label=t)
             for p, t in ac.POSTURA_TXT.items()]
        h += [Line2D([], [], color=c, ls=ESTILO_LINEA[gu], lw=2.5, label=t)
              for t, (c, gu, _) in ac.REL_ESTILO.items()]
        ax.legend(handles=h, loc="upper center", bbox_to_anchor=(0.5, -0.04), ncol=6, frameon=False,
                  fontsize=letra, columnspacing=1.2, handlelength=1.8)
    ax.set_aspect("equal")
    ax.axis("off")


def _resumen(fig, kpis):
    for i, (e, v, s_, c) in enumerate(kpis):
        x = 0.035 + i * 0.188
        fig.patches.append(FancyBboxPatch((x, 0.5), 0.175, 0.28, boxstyle="round,pad=0,rounding_size=0.01",
                                          transform=fig.transFigure, fc="white", ec=BORDE, lw=1.2, zorder=-10))
        fig.patches.append(Rectangle((x, 0.768), 0.175, 0.012, transform=fig.transFigure, fc=c, ec="none",
                                     zorder=-9))
        fig.text(x + 0.015, 0.72, e, fontsize=14, color=TINTA_2)
        fig.text(x + 0.015, 0.585, v, fontsize=58, fontweight="bold", color=TINTA)
        fig.text(x + 0.015, 0.53, s_, fontsize=13, color=TINTA_2)


def laminas_actores(A: pd.DataFrame, R: pd.DataFrame, H: pd.DataFrame, corte: date, cliente: str = "",
                    filtros: str = "", meses: int = 6) -> list[tuple[str, bytes]]:
    """A y R ya filtrados y 'al corte'; H es el historial de posturas. Devuelve [(archivo, png 4K), ...]."""
    out = []
    if A.empty:
        return out
    m = ac.metricas(ac.red(A, R))
    desde = (pd.Timestamp(corte) - pd.DateOffset(months=meses)).date()
    Hc = H[(H["fecha"] <= corte) & H["nombre"].isin(m["nombre"])]
    cam = ac.cambios(Hc, desde, corte)
    alejan, acercan = cam[cam["delta"] < 0], cam[cam["delta"] > 0]
    aliados, opos = int((m["postura"] > 0).sum()), int((m["postura"] < 0).sum())
    puentes = m[m["puente"] & (m["intermediacion"] > 0.05)]
    criticos = m[(m["postura"] < 0) & (m["influencia"] >= 4)].sort_values(["influencia", "postura"],
                                                                        ascending=[False, True])

    # 1. resumen
    fig = _lamina("Mapa de actores: resumen",
                  f"{len(m)} actores y {len(R)} relaciones: {aliados} aliados o favorables y {opos} críticos u "
                  f"opositores ({len(criticos)} con alta influencia).", cliente, hoy=corte, filtros=filtros)
    _resumen(fig, [("Actores mapeados", f"{len(m)}", f"{len(R)} relaciones", "#1c5cab"),
                   ("Aliados o favorables", f"{aliados}", f"{aliados / len(m):.0%} del total", "#1c5cab"),
                   ("Críticos u opositores", f"{opos}", f"{len(criticos)} con alta influencia", "#c2410c"),
                   ("Actores puente", f"{len(puentes)}", "conectan comunidades", TINTA),
                   (f"Se alejaron ({meses} meses)", f"{len(alejan)}", f"{len(acercan)} se acercaron", "#d03b3b")])
    fig.text(0.035, 0.43, "Gestionar de cerca (críticos con alta influencia)", fontsize=18, fontweight="bold",
             color=VERDE_OSC)
    for i, (_, r) in enumerate(criticos.head(4).iterrows()):
        y = 0.37 - i * 0.07
        fig.patches.append(Rectangle((0.035, y - 0.012), 0.006, 0.05, transform=fig.transFigure,
                                     fc=ac.POSTURA_COLOR[int(r["postura"])], ec="none"))
        fig.text(0.05, y + 0.012, f"{r['nombre']} · {r['cargo'] or r['tipo']}", fontsize=14, fontweight="bold",
                 color=TINTA)
        fig.text(0.05, y - 0.012, f"{_corto(r['comunidad'] or r['organizacion'])} · {r['postura_txt']} · "
                 f"influencia {r['influencia']}/5 · {r['vinculos']} vínculos", fontsize=12, color=TINTA_2)
    out.append(("01_actores_resumen.png", _a_png(fig)))

    # 2. red
    top = m.iloc[0]
    fig = _lamina("Red de relaciones e influencias",
                  f"{top['nombre']} ({top['cargo'] or top['tipo']}) es el actor que más conecta la red. "
                  "Color = postura hacia la empresa; tamaño = influencia.", cliente, corte, filtros)
    ax = fig.add_axes([0.035, 0.17, 0.62, 0.62])
    dibujar_red(ax, A, R, escala=1.8, letra_leyenda=11.5)
    _claves(fig, **LADO, titulo="Lo que hay que saber", puntos=[
        (f"{len(puentes)}", "actores puente: conectan comunidades distintas", TINTA),
        (f"{int((R['tipo'] == 'Conflicto').sum())}", "relaciones en conflicto", "#d03b3b"),
        (f"{int((R['tipo'] == 'Alianza').sum())}", "alianzas entre actores", "#1baf7a")])
    out.append(("02_red_de_actores.png", _a_png(fig)))

    # 3. actores clave
    k8 = m.head(10).iloc[::-1]
    fig = _lamina("Actores clave de la red",
                  "Intermediación: cuánto pasa por cada actor la comunicación entre los demás. Si uno de ellos "
                  "cambia de postura, la red se reconfigura.", cliente, corte, filtros)
    ax = fig.add_axes([0.25, 0.12, 0.37, 0.68])
    ax.set_facecolor("none")
    ax.barh([f"{r['nombre']}\n{_corto(r['comunidad'] or r['organizacion'])}" for _, r in k8.iterrows()],
            k8["intermediacion"], color=[ac.POSTURA_COLOR[int(p)] for p in k8["postura"]], height=0.65)
    for i, (_, r) in enumerate(k8.iterrows()):
        ax.text(r["intermediacion"] + k8["intermediacion"].max() * 0.02, i,
                f"{r['postura_txt']} · {r['vinculos']} vínculos" + (" · puente" if r["puente"] else ""),
                va="center", fontsize=12, color=TINTA)
    ax.set_xlim(0, k8["intermediacion"].max() * 1.75)
    ax.tick_params(axis="y", labelsize=12.5, length=0)
    ax.tick_params(axis="x", labelsize=11)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Intermediación", fontsize=13)
    _claves(fig, **LADO, titulo="Lo que hay que saber", puntos=[
        (f"{top['intermediacion']:.2f}", f"intermediación de {top['nombre']}, el actor más central",
         ac.POSTURA_COLOR[int(top["postura"])]),
        (f"{int((m.head(10)['postura'] < 0).sum())}", "de los 10 actores más centrales son críticos u opositores",
         "#c2410c"),
        (f"{int((m.head(10)['postura'] > 0).sum())}", "de los 10 son aliados o favorables", "#1c5cab")])
    out.append(("03_actores_clave.png", _a_png(fig)))

    # 4. matriz poder-postura
    fig = _lamina("Matriz poder – postura",
                  "Dónde poner la energía: los críticos con alta influencia se gestionan de cerca; los aliados "
                  "influyentes se involucran.", cliente, corte, filtros)
    ax = fig.add_axes([0.07, 0.13, 0.57, 0.68])
    ax.set_facecolor("none")
    zonas = [(-2.5, -0.5, 3.5, 5.5, "Gestionar de cerca", "#c2410c", 0.08),
             (0.5, 2.5, 3.5, 5.5, "Aliados clave (involucrar)", "#1c5cab", 0.08),
             (-2.5, -0.5, 0.5, 3.5, "Monitorear", "#c2410c", 0.035),
             (0.5, 2.5, 0.5, 3.5, "Mantener informados", "#1c5cab", 0.035)]
    for x0, x1, y0, y1, txt, col, a in zonas:
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, color=col, alpha=a, lw=0, zorder=0))
        ax.text((x0 + x1) / 2, y0 + 0.1, txt, ha="center", va="bottom", fontsize=14, color=TINTA_2,
                fontweight="bold", alpha=0.85)
    rng = np.random.default_rng(3)
    x = m["postura"] + rng.uniform(-0.28, 0.28, len(m))
    y = m["influencia"] + rng.uniform(-0.28, 0.28, len(m))
    ax.scatter(x, y, s=120 + 25 * m["vinculos"].clip(upper=10), c=[ac.POSTURA_COLOR[int(p)] for p in m["postura"]],
               edgecolors="white", linewidths=1.5, zorder=3)
    rotular = set(criticos.head(4)["nombre"]) | set(
        m[m["postura"] > 0].sort_values(["influencia", "vinculos"], ascending=False).head(3)["nombre"])
    n_rot = 0
    for xi, yi, (_, r) in sorted(zip(x, y, m.iterrows()), key=lambda t: t[0]):
        if r["nombre"] in rotular:
            n_rot += 1  # rotulos alternados arriba/abajo para que no se encimen
            borde = xi < -1.6 or xi > 1.6  # en los extremos el rotulo va hacia adentro
            ax.annotate(r["nombre"], (xi, yi), xytext=((10 if xi < 0 else -10) if borde else 0,
                                                       -18 if borde else (11 if n_rot % 2 else -22)),
                        textcoords="offset points", ha=("left" if xi < 0 else "right") if borde else "center",
                        fontsize=11.5, color=TINTA, zorder=4, fontweight="bold",
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.7))
    ax.set_xlim(-2.5, 2.5)
    ax.set_ylim(0.5, 5.5)
    ax.set_xticks(list(ac.POSTURA_TXT), list(ac.POSTURA_TXT.values()), fontsize=13)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.tick_params(axis="y", labelsize=12)
    ax.set_xlabel("Postura hacia la empresa", fontsize=14)
    ax.set_ylabel("Influencia", fontsize=14)
    ax.axvline(0, color=BORDE, lw=1.2)
    _claves(fig, **LADO, titulo="Gestionar de cerca", puntos=[
        (f"{int(r['influencia'])}/5", f"{r['nombre']} · {_corto(r['comunidad'] or r['organizacion'])} · "
         f"{r['postura_txt']}", ac.POSTURA_COLOR[int(r["postura"])]) for _, r in criticos.head(3).iterrows()]
        or [("0", "sin críticos de alta influencia", VERDE)])
    out.append(("04_matriz_poder_postura.png", _a_png(fig)))

    # 5. balance por comunidad
    d = m[m["comunidad"] != ""]
    if not d.empty:
        t = d.pivot_table(index="comunidad", columns="postura", values="nombre", aggfunc="count", fill_value=0)
        t = t.reindex(columns=sorted(ac.POSTURA_TXT), fill_value=0)
        saldo = t[[1, 2]].sum(axis=1) - t[[-2, -1]].sum(axis=1)
        t = t.loc[saldo.sort_values().index]
        fig = _lamina("Balance de posturas por comunidad",
                      f"{_corto(saldo.idxmin())} tiene el saldo más desfavorable y "
                      f"{_corto(saldo.idxmax())}, la más favorable (izquierda: en contra; derecha: neutral o a favor).",
                      cliente, corte, filtros)
        ax = fig.add_axes([0.24, 0.17, 0.4, 0.62])
        ax.set_facecolor("none")
        etiquetas = [_corto(c) for c in t.index]
        izq = np.zeros(len(t))
        for p in (-1, -2):
            ax.barh(etiquetas, -t[p], left=izq, color=ac.POSTURA_COLOR[p], edgecolor="white", height=0.62,
                    label=ac.POSTURA_TXT[p])
            izq -= t[p].values
        der = np.zeros(len(t))
        for p in (0, 1, 2):
            ax.barh(etiquetas, t[p], left=der, color=ac.POSTURA_COLOR[p], edgecolor="white", height=0.62,
                    label=ac.POSTURA_TXT[p])
            der += t[p].values
        lim = max(1, int(max(-izq.min(), der.max())))
        ax.set_xlim(-lim - 0.5, lim + 0.5)
        ax.set_xticks(range(-lim, lim + 1), [str(abs(v)) for v in range(-lim, lim + 1)], fontsize=11)
        ax.axvline(0, color=TINTA, lw=1.2)
        ax.tick_params(axis="y", labelsize=15, length=0)
        ax.spines["left"].set_visible(False)
        ax.legend(frameon=False, fontsize=12, ncol=5, loc="upper center", bbox_to_anchor=(0.45, -0.07))
        _claves(fig, **LADO, titulo="Lo que hay que saber", puntos=[
            (f"{int(saldo.min()):+d}", f"saldo de {_corto(saldo.idxmin())} (aliados menos críticos)", "#c2410c"),
            (f"{int(saldo.max()):+d}", f"saldo de {_corto(saldo.idxmax())}", "#1c5cab"),
            (f"{int((saldo < 0).sum())}", "comunidades con más críticos que aliados", "#d03b3b")])
        out.append(("05_balance_por_comunidad.png", _a_png(fig)))

    # 6. cambios de postura
    if not cam.empty:
        c = cam.head(12).iloc[::-1]
        r0 = alejan.iloc[0] if not alejan.empty else cam.iloc[0]
        fig = _lamina(f"Quién cambió de postura en los últimos {meses} meses",
                      f"Alerta temprana: {r0['nombre']} pasó de {ac.POSTURA_TXT[r0['antes']]} a "
                      f"{ac.POSTURA_TXT[r0['ahora']]} ({r0['fecha_cambio']:%d/%m/%Y}).", cliente, corte, filtros)
        ax = fig.add_axes([0.2, 0.12, 0.43, 0.68])
        ax.set_facecolor("none")
        yy = np.arange(len(c))
        for i, (_, r) in enumerate(c.iterrows()):
            col = "#c2410c" if r["delta"] < 0 else "#1c5cab"
            ax.annotate("", xy=(r["ahora"], i), xytext=(r["antes"], i),
                        arrowprops=dict(arrowstyle="-|>", color=col, lw=3, shrinkA=9, shrinkB=9, mutation_scale=22))
        ax.scatter(c["antes"], yy, s=180, color="white", edgecolors="#8a8984", linewidths=2.5, zorder=3)
        ax.scatter(c["ahora"], yy, s=240, color=[ac.POSTURA_COLOR[v] for v in c["ahora"]], edgecolors="white",
                   linewidths=1.5, zorder=3)
        ax.set_yticks(yy, [f"{r['nombre']}\n{_corto(r['comunidad']) or 'externo'}" for _, r in c.iterrows()],
                      fontsize=12)
        ax.set_xticks(list(ac.POSTURA_TXT), list(ac.POSTURA_TXT.values()), fontsize=13)
        ax.set_xlim(-2.5, 2.5)
        ax.grid(axis="x", color=BORDE)
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_visible(False)
        _claves(fig, **LADO, titulo="Lo que hay que saber", puntos=[
            (f"{len(alejan)}", f"actores se alejaron de la empresa "
             f"({int((alejan['influencia'] >= 4).sum())} con alta influencia)", "#c2410c"),
            (f"{len(acercan)}", "actores se acercaron: oportunidad de alianza", "#1c5cab"),
            ("“", f"{r0['evidencia']} — {r0['nombre']}", TINTA_2)])
        out.append(("06_cambios_de_postura.png", _a_png(fig)))

        # 7. trayectorias
        mov = (Hc.groupby("nombre").agg(n=("postura", "nunique"), inf=("influencia", "max"), reg=("postura", "size")))
        mov = mov[mov["reg"] >= 3].assign(s=lambda x: x["n"] * x["inf"]).sort_values("s", ascending=False)
        elegidos = mov.index[:4].tolist()
        if elegidos:
            fig = _lamina("Trayectoria de los actores clave",
                          "Las posturas cambian: cada punto es la postura observada en una reunión.", cliente, corte,
                          filtros)
            ax = fig.add_axes([0.1, 0.17, 0.86, 0.62])
            ax.set_facecolor("none")
            ax.axhspan(0.5, 2.5, color="#1c5cab", alpha=0.05)
            ax.axhspan(-2.5, -0.5, color="#c2410c", alpha=0.05)
            for i, n in enumerate(elegidos):
                h = Hc[Hc["nombre"] == n].sort_values("fecha")
                col = ac.SERIE[i % len(ac.SERIE)]
                ax.step(pd.to_datetime(h["fecha"]), h["postura"], where="post", color=col, lw=3, label=n)
                ax.scatter(pd.to_datetime(h["fecha"]), h["postura"], color=col, s=70, zorder=3,
                           edgecolors="white")
            ax.set_yticks(list(ac.POSTURA_TXT), list(ac.POSTURA_TXT.values()), fontsize=13)
            ax.set_ylim(-2.5, 2.5)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
            ax.tick_params(axis="x", labelsize=12)
            ax.grid(axis="y", color=BORDE)
            ax.legend(frameon=False, fontsize=13, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.07))
            out.append(("07_trayectorias.png", _a_png(fig)))
    plt.close("all")
    return out

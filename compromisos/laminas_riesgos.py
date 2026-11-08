"""Riesgos y decisiones en laminas 4K (16:9): cartera de procesos, riesgo del proceso elegido, quien
puede frenarlo, escenarios y plan de accion. Misma marca que las demas laminas."""
from __future__ import annotations

import textwrap
from datetime import date

import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Rectangle

from . import actores as ac
from . import riesgos as rg
from .panel_imagen import BORDE, TINTA, TINTA_2, VERDE_OSC, _a_png, _claves, _corto, _lamina

LADO = dict(x=0.675, w=0.29, y=0.1, h=0.71)
SIMBOLO = {"Decide": "*", "Puede vetar": "D", "Influye": "o", "Afectado": "s"}


def _ejes(ax):
    ax.set_facecolor("white")
    ax.grid(color="#f1f3f5")
    ax.tick_params(labelsize=13)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)


def _escenarios(pr, partes, A, H, conf, reg, hoy, escenarios, contexto=None) -> list[tuple[str, int, dict]]:
    es = escenarios[escenarios["proceso_id"] == pr["id"]]
    out = []
    for n in dict.fromkeys(es["escenario"]):
        g = es[es["escenario"] == n]
        cam = dict(zip(g["nombre"], g["postura_nueva"]))
        out.append((n, rg.evaluar(pr, partes, A, H, conf, reg, hoy, cam, contexto=contexto)["puntos"], cam))
    return out


def laminas_riesgos(pr: pd.Series, partes: pd.DataFrame, A: pd.DataFrame, R: pd.DataFrame, H: pd.DataFrame,
                    conf: pd.DataFrame, reg: pd.DataFrame, escenarios: pd.DataFrame, acciones: pd.DataFrame,
                    hoy: date, cliente: str = "", contexto: pd.DataFrame | None = None) -> list[tuple[str, bytes]]:
    """A al corte; reg con estado. Devuelve [(archivo, png 3840x2160), ...]."""
    out = []
    r = rg.evaluar(pr, partes, A, H, conf, reg, hoy, contexto=contexto)
    p = r["partes"]
    filtro = f"{pr['id']} · {_corto(pr['comunidad'])}"

    # 1. riesgo del proceso
    fig = _lamina(f"Riesgo de paralización: {r['puntos']}/100 ({r['nivel'].lower()})",
                  textwrap.shorten(f"{pr['proceso']} · {pr['comunidad']} · hito: {pr['hito']}", 130),
                  cliente, hoy, filtro)
    color = rg.NIVEL_COLOR[r["nivel"]]
    fig.patches.append(FancyBboxPatch((0.035, 0.42), 0.2, 0.38, boxstyle="round,pad=0,rounding_size=0.01",
                                      transform=fig.transFigure, fc="white", ec=BORDE, lw=1.2, zorder=-10))
    fig.patches.append(Rectangle((0.035, 0.788), 0.2, 0.012, transform=fig.transFigure, fc=color, ec="none",
                                 zorder=-9))
    fig.text(0.05, 0.74, "Riesgo de paralización", fontsize=15, color=TINTA_2)
    fig.text(0.05, 0.6, f"{r['puntos']}", fontsize=96, fontweight="bold", color=color)
    fig.text(0.05, 0.545, f"de 100 · nivel {r['nivel'].lower()}", fontsize=15, color=TINTA)
    plazo = f"faltan {r['dias_plazo']} días" if r["dias_plazo"] is not None and r["dias_plazo"] >= 0 else "plazo vencido"
    fig.text(0.05, 0.495, f"Plazo: {pr['fecha_limite']:%d/%m/%Y} ({plazo})" if pd.notna(pr["fecha_limite"]) else
             "Sin plazo", fontsize=13, color=TINTA_2)
    fig.text(0.05, 0.455, f"Impacto: {'●' * pr['impacto']}{'○' * (5 - pr['impacto'])}", fontsize=13, color=TINTA_2)
    ax = fig.add_axes([0.42, 0.43, 0.24, 0.3])
    nombres = list(rg.MAXIMOS)[::-1]
    pts = [r["componentes"][n][0] for n in nombres]
    ax.barh(nombres, [rg.MAXIMOS[n] for n in nombres], color="#eef1f4", height=0.55)
    ax.barh(nombres, pts, height=0.55, color=[rg.NIVEL_COLOR[rg.nivel(100 * v / rg.MAXIMOS[n])]
                                              for v, n in zip(pts, nombres)])
    for i, (v, n) in enumerate(zip(pts, nombres)):
        ax.text(rg.MAXIMOS[n] + 0.8, i, f"{v:.0f} de {rg.MAXIMOS[n]}", va="center", fontsize=13, color=TINTA)
    ax.set_xlim(0, 52)
    ax.set_xticks([])
    ax.tick_params(axis="y", labelsize=14, length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_facecolor("none")
    fig.text(0.255, 0.765, "De dónde viene el riesgo", fontsize=16, fontweight="bold", color=VERDE_OSC)
    fig.text(0.035, 0.36, "Si se paraliza", fontsize=18, fontweight="bold", color=VERDE_OSC)
    fig.text(0.035, 0.33, textwrap.fill(pr["si_se_paraliza"] or "—", 95), fontsize=15, color=TINTA, va="top",
             linespacing=1.4)
    fig.text(0.035, 0.22, "Responsable del proceso", fontsize=18, fontweight="bold", color=VERDE_OSC)
    fig.text(0.035, 0.18, f"{pr['responsable'] or '—'} · estado: {pr['estado'] or '—'}", fontsize=15, color=TINTA)
    _claves(fig, **LADO, titulo="Por qué", puntos=[
        (f"{v:.0f}", t, rg.NIVEL_COLOR[rg.nivel(100 * v / rg.MAXIMOS[n])]) for n, (v, t) in r["componentes"].items()])
    out.append(("01_riesgo_del_proceso.png", _a_png(fig)))

    # 2. quien puede frenar el proceso
    frenan = p[p["presion"] > 0]
    nv = int(frenan["rol"].isin(["Decide", "Puede vetar"]).sum())
    fig = _lamina("Quién puede frenar el proceso",
                  f"{len(frenan)} actores del proceso están en contra; "
                  f"{nv} de ellos {'decide o puede' if nv == 1 else 'deciden o pueden'} vetar. "
                  "Color = postura; tamaño = influencia; forma = rol.", cliente, hoy, filtro)
    ax = fig.add_axes([0.06, 0.2, 0.585, 0.59])
    _ejes(ax)
    ax.add_patch(Rectangle((-2.5, 3.5), 2, 2.65, color="#d03b3b", alpha=0.07, lw=0, zorder=0))
    ax.text(-2.45, 6.05, "Pueden frenar el proceso", fontsize=13, color="#a32424", va="top")
    ax.add_patch(Rectangle((0.5, 3.5), 2, 2.65, color="#1c5cab", alpha=0.06, lw=0, zorder=0))
    ax.text(2.45, 6.05, "Aliados con poder", fontsize=13, color="#1c5cab", va="top", ha="right")
    d = p.copy()
    d["_n"] = d.groupby(["postura", "influencia"]).cumcount()
    d["x"] = d["postura"] + (d["_n"] % 3 - 1 + (d.groupby(["postura", "influencia"])["_n"].transform("max") == 0))\
        * 0.33
    d["y"] = d["influencia"] - (d["_n"] // 3) * 0.32
    for _, a in d.iterrows():
        ax.scatter(a["x"], a["y"], s=120 + 90 * a["influencia"], marker=SIMBOLO.get(a["rol"], "o"),
                   color=ac.POSTURA_COLOR[int(a["postura"])], edgecolors="white", linewidths=1.5, zorder=3)
        arriba = a["_n"] % 2 == 0
        ax.annotate(textwrap.fill(a["nombre"], 16), (a["x"], a["y"]), xytext=(0, 13 if arriba else -15),
                    textcoords="offset points", ha="center", va="bottom" if arriba else "top", fontsize=10.5, color=TINTA, zorder=4)
    ax.set_xlim(-2.6, 2.6)
    ax.set_ylim(0.4, 6.2)
    ax.set_xticks(list(ac.POSTURA_TXT), list(ac.POSTURA_TXT.values()))
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_xlabel("Postura hacia la empresa", fontsize=14)
    ax.set_ylabel("Influencia", fontsize=14)
    ax.legend(handles=[Line2D([], [], marker=m, ls="", color=TINTA_2, markersize=11, label=k)
                       for k, m in SIMBOLO.items() if (d["rol"] == k).any()], frameon=False, fontsize=12,
              loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=4)
    puntos = []
    for _, a in frenan.head(3).iterrows():
        pu = rg.puentes(a["nombre"], A, R)
        puntos.append((textwrap.shorten(a["nombre"], 24), f"Le preocupa: {a['preocupacion'] or '—'}. "
                       f"Estrategia: {a['estrategia'].lower()}."
                       + (f" Puente: {pu[0]}." if pu else ""), ac.POSTURA_COLOR[int(a["postura"])]))
    fig.patches.append(FancyBboxPatch((LADO["x"], LADO["y"]), LADO["w"], LADO["h"],
                                      boxstyle="round,pad=0,rounding_size=0.01", transform=fig.transFigure,
                                      fc="white", ec=BORDE, lw=1.2, zorder=-10))
    fig.text(LADO["x"] + 0.018, LADO["y"] + LADO["h"] - 0.05, "A quién atender primero", fontsize=16,
             fontweight="bold", color=VERDE_OSC)
    paso = (LADO["h"] - 0.09) / max(1, len(puntos))
    for i, (cifra, texto, col) in enumerate(puntos):
        yy = LADO["y"] + LADO["h"] - 0.09 - i * paso
        fig.text(LADO["x"] + 0.018, yy - 0.035, cifra, fontsize=17, fontweight="bold", color=col)
        fig.text(LADO["x"] + 0.018, yy - 0.055, textwrap.fill(texto, 44), fontsize=12, color=TINTA, va="top",
                 linespacing=1.35)
    out.append(("02_quien_puede_frenar.png", _a_png(fig)))

    # 3. escenarios
    res = _escenarios(pr, partes, A, H, conf, reg, hoy, escenarios, contexto)
    if res:
        mejor = min(res, key=lambda t: t[1])
        fig = _lamina("¿Qué pasa si…? Escenarios antes de decidir",
                      f"El mejor escenario es «{textwrap.shorten(mejor[0], 70)}»: el riesgo pasa de {r['puntos']} a "
                      f"{mejor[1]} ({mejor[1] - r['puntos']:+d}).", cliente, hoy, filtro)
        ax = fig.add_axes([0.3, 0.16, 0.35, 0.62])
        nombres = ["Situación actual"] + [n for n, _, _ in res]
        vals = [r["puntos"]] + [v for _, v, _ in res]
        y = np.arange(len(vals))[::-1]
        ax.barh(y, vals, color=[rg.NIVEL_COLOR[rg.nivel(v)] for v in vals], height=0.6,
                edgecolor=[TINTA] + ["white"] * len(res), linewidth=2)
        for yy, v, i in zip(y, vals, range(len(vals))):
            ax.text(v + 1.5, yy, f"{v}" + ("" if i == 0 else f"  ({v - r['puntos']:+d})"), va="center", fontsize=16,
                    fontweight="bold", color=TINTA)
        ax.set_yticks(y, [textwrap.fill(n, 34) for n in nombres], fontsize=13)
        for x in (35, 60):
            ax.axvline(x, color=BORDE, ls=":", lw=1.5)
        ax.set_xlim(0, 112)
        ax.set_xticks([])
        ax.tick_params(axis="y", length=0)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.set_facecolor("none")
        motivo = dict(zip(escenarios["nombre"], escenarios["motivo"]))
        cambios = [f"{textwrap.shorten(n, 26)}: {ac.POSTURA_TXT[int(p.loc[p['nombre'] == n, 'postura'].iloc[0])]} → "
                   f"{ac.POSTURA_TXT[v]}" for n, v in mejor[2].items() if (p["nombre"] == n).any()]
        peor = max(res, key=lambda t: t[1])
        _claves(fig, **LADO, titulo="Lo que hay que saber", puntos=[
            (f"{mejor[1] - r['puntos']:+d}", "con el mejor escenario: " + "; ".join(cambios[:3]), "#1baf7a"),
            (f"{peor[1] - r['puntos']:+d}", f"si se elige «{textwrap.shorten(peor[0], 50)}»", rg.NIVEL_COLOR[
                rg.nivel(peor[1])]),
            (f"{len(res)}", "escenarios evaluados con el mismo método (postura esperada de cada actor)", TINTA)])
        out.append(("03_escenarios.png", _a_png(fig)))

    # 4. plan de accion
    ac_p = acciones[acciones["proceso_id"] == pr["id"]].sort_values("fecha", na_position="last")
    sin = frenan[~frenan["nombre"].isin(ac_p["nombre"])]
    fig = _lamina("Plan de acción por actor",
                  f"{len(ac_p)} acciones, {int((ac_p['estado'] == 'Hecha').sum())} hechas"
                  + (f"; {len(sin)} actores en contra aún sin acción ({', '.join(sin['nombre'].head(3))})."
                     if len(sin) else "; todos los actores en contra tienen una acción asignada."),
                  cliente, hoy, filtro)
    cols = [("Actor", 0.035, 24), ("Estrategia", 0.205, 22), ("Acción", 0.36, 58), ("Responsable", 0.72, 16),
            ("Fecha", 0.832, 8), ("Estado", 0.882, 10)]
    fig.patches.append(Rectangle((0.035, 0.765), 0.93, 0.045, transform=fig.transFigure, fc=VERDE_OSC, ec="none"))
    for t, x, _ in cols:
        fig.text(x + 0.008, 0.78, t, fontsize=14, fontweight="bold", color="white")
    color_estado = {"Hecha": "#1baf7a", "En curso": "#eda100", "Pendiente": "#5b6675"}
    alto_f = min(0.085, 0.68 / max(1, len(ac_p)))
    for i, (_, a) in enumerate(ac_p.head(8).iterrows()):
        y = 0.765 - (i + 1) * alto_f
        fig.patches.append(Rectangle((0.035, y), 0.93, alto_f, transform=fig.transFigure,
                                     fc="white" if i % 2 == 0 else "#f9fafb", ec=BORDE, lw=0.6, zorder=-5))
        vals = [a["nombre"], a["estrategia"], a["accion"], a["responsable"],
                f"{a['fecha']:%d/%m}" if pd.notna(a["fecha"]) else "—", a["estado"]]
        for (t, x, w), v in zip(cols, vals):
            fig.text(x + 0.008, y + alto_f / 2, textwrap.fill(textwrap.shorten(str(v), 2 * w), w),
                     fontsize=12.5, va="center",
                     color=color_estado.get(v, TINTA) if t == "Estado" else TINTA,
                     fontweight="bold" if t in ("Actor", "Estado") else "normal", linespacing=1.3)
    out.append(("04_plan_de_accion.png", _a_png(fig)))
    return out

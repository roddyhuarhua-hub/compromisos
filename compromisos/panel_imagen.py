"""Panel ejecutivo en laminas de alta resolucion (4K, 16:9): una lamina por grafico, cada una con su
mensaje clave, para armar una presentacion sin saturar las diapositivas.

Se dibuja en el servidor con matplotlib, asi que no depende del navegador ni de servicios externos.
Respeta los filtros que el usuario tenga activos en el panel.
"""
from __future__ import annotations

import io
import textwrap
import zipfile
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

from .visual import COLOR_ESTADO, SEMAFORO  # noqa: E402

IMG = Path(__file__).resolve().parents[1] / "img"
VERDE, VERDE_OSC, TINTA, TINTA_2, BORDE, FONDO = "#2d4a33", "#1f3a26", "#1f2a37", "#5b6675", "#e3e7eb", "#f6f7f9"
ORDEN = ["Vencido", "Por vencer", "En plazo", "Sin plazo", "Cumplido"]
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.edgecolor": BORDE, "axes.labelcolor": TINTA_2,
                     "xtick.color": TINTA_2, "ytick.color": TINTA_2, "axes.spines.top": False,
                     "axes.spines.right": False})


def _tarjeta(fig, x, y, w, h, titulo=None, izq=0.03, der=0.015, abajo=0.035):
    """Fondo blanco redondeado con titulo; devuelve un eje (transparente) para dibujar dentro."""
    fig.patches.append(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.008",
                                      transform=fig.transFigure, fc="white", ec=BORDE, lw=1.2, zorder=-10))
    if titulo:
        fig.text(x + 0.012, y + h - 0.035, titulo, fontsize=15, fontweight="bold", color=TINTA)
    ax = fig.add_axes([x + izq, y + abajo, w - izq - der, h - abajo - (0.065 if titulo else 0.02)])
    ax.set_facecolor("none")
    return ax


def _kpi(fig, x, y, w, h, etiqueta, valor, sub, color):
    fig.patches.append(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.008",
                                      transform=fig.transFigure, fc="white", ec=BORDE, lw=1.2, zorder=-10))
    fig.patches.append(Rectangle((x, y + h - 0.009), w, 0.009, transform=fig.transFigure, fc=color, ec="none",
                                 zorder=-9))
    fig.text(x + 0.012, y + h - 0.036, etiqueta, fontsize=13, color=TINTA_2)
    fig.text(x + 0.012, y + 0.036, valor, fontsize=36, fontweight="bold", color=TINTA)
    fig.text(x + 0.012, y + 0.012, sub, fontsize=11.5, color=TINTA_2)


def _mapa(ax, ind: pd.DataFrame):
    d = ind.dropna(subset=["lat", "lon"])
    if d.empty:
        ax.axis("off")
        return
    for _, r in d.iterrows():
        for k, a in ((6, 0.05), (4, 0.08), (2.5, 0.12)):  # halo de "calor" por numero de reuniones
            ax.scatter(r["lon"], r["lat"], s=(300 + 160 * r["reuniones"]) * k, color=SEMAFORO[r["semaforo"]],
                       alpha=a, lw=0, zorder=1)
        ax.scatter(r["lon"], r["lat"], s=120 + 28 * min(r["vencidos"], 15), color=SEMAFORO[r["semaforo"]],
                   ec="white", lw=2, zorder=3)
        otros = d[d["comunidad"] != r["comunidad"]]
        cerca = otros[(abs(otros["lon"] - r["lon"]) < 0.12) & (abs(otros["lat"] - r["lat"]) < 0.05)]
        abajo = (cerca["lat"] > r["lat"]).any()  # si hay un vecino encima, el rotulo va debajo
        ax.annotate(r["comunidad"].replace("C.C. ", ""), (r["lon"], r["lat"]), xytext=(0, -22 if abajo else 14),
                    textcoords="offset points", ha="center", fontsize=13, color=TINTA, fontweight="bold", zorder=4,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.75))
    mx, my = (d["lon"].max() - d["lon"].min()) * 0.25 + 0.03, (d["lat"].max() - d["lat"].min()) * 0.25 + 0.03
    ax.set_xlim(d["lon"].min() - mx, d["lon"].max() + mx)
    ax.set_ylim(d["lat"].min() - my, d["lat"].max() + my)
    ax.set_aspect("equal", adjustable="box")
    ax.set_facecolor("#eef3ee")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    for nivel, c in SEMAFORO.items():
        ax.scatter([], [], color=c, s=80, label=nivel)
    ax.legend(loc="lower left", fontsize=10.5, frameon=True, framealpha=0.9, edgecolor="none")


def _semaforo(ax, ind: pd.DataFrame):
    d = ind.sort_values("indice")
    y = np.arange(len(d))
    ax.barh(y, d["indice"], color=[SEMAFORO[s] for s in d["semaforo"]], height=0.62)
    for yi, v, ven, cum in zip(y, d["indice"], d["vencidos"], d["cumplimiento"]):
        ax.text(v + 1.2, yi, f"{v:.0f}", va="center", fontsize=12, fontweight="bold", color=TINTA)
        ax.text(101, yi, f"{ven} venc. · cumple {cum:.0%}", va="center", fontsize=10.5, color=TINTA_2)
    ax.set_yticks(y, [c.replace("C.C. ", "") for c in d["comunidad"]], fontsize=11.5, color=TINTA)
    ax.axvline(25, color=SEMAFORO["Atención"], ls=":", lw=1.2)
    ax.axvline(40, color=SEMAFORO["Crítico"], ls=":", lw=1.2)
    ax.set_xlim(0, 100)
    ax.tick_params(axis="x", labelsize=10)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)


def _dona(ax, df: pd.DataFrame, tasa):
    conteo = [(e, int((df["estado"] == e).sum())) for e in ORDEN if (df["estado"] == e).any()]
    ax.pie([n for _, n in conteo], colors=[COLOR_ESTADO[e] for e, _ in conteo], startangle=90, counterclock=False,
           wedgeprops=dict(width=0.32, edgecolor="white", linewidth=2.5))
    ax.text(0, 0.1, f"{tasa:.0%}" if tasa is not None else "–", ha="center", va="center", fontsize=34,
            fontweight="bold", color=TINTA)
    ax.text(0, -0.2, "cumplimiento", ha="center", va="center", fontsize=12, color=TINTA_2)
    ax.legend([f"{e}: {n}" for e, n in conteo], loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=12,
              frameon=False, handlelength=1, handleheight=1)
    ax.set_aspect("equal")


def _brecha(ax, df: pd.DataFrame, hoy: date):
    venc = pd.to_datetime(df.loc[df["fecha_limite"].notna() & (df["fecha_limite"] <= hoy), "fecha_limite"])
    cump = pd.to_datetime(df.loc[df["cumplido"] & df["fecha_cumplimiento"].notna(), "fecha_cumplimiento"])
    if venc.empty:
        ax.axis("off")
        return
    meses = pd.period_range(venc.min().to_period("M"), pd.Timestamp(hoy).to_period("M"), freq="M")
    a = venc.dt.to_period("M").value_counts().reindex(meses, fill_value=0).cumsum()
    b = cump.dt.to_period("M").value_counts().reindex(meses, fill_value=0).cumsum()
    x = meses.to_timestamp()
    ax.plot(x, a.values, color="#8a8984", lw=2.4, ls=":", label="Debían cumplirse")
    ax.plot(x, b.values, color=COLOR_ESTADO["Cumplido"], lw=2.6, label="Cumplidos")
    ax.fill_between(x, b.values, a.values, color=COLOR_ESTADO["Vencido"], alpha=0.1)
    ax.text(x[-1], a.values[-1], f"Brecha: {a.values[-1] - b.values[-1]}  ", ha="right", va="bottom",
            fontsize=13, fontweight="bold", color=COLOR_ESTADO["Vencido"])
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.tick_params(labelsize=10)
    ax.grid(axis="y", color=BORDE)
    ax.legend(fontsize=11, frameon=False, loc="upper left")


def _quien(ax, df: pd.DataFrame):
    t = df.pivot_table(index="responsable", columns="estado", values="id", aggfunc="count", fill_value=0)
    t = t.reindex(columns=[e for e in ORDEN if e in t.columns])
    t = t.loc[t.sum(axis=1).sort_values().index]
    izq = np.zeros(len(t))
    for e in t.columns:
        ax.barh(t.index, t[e], left=izq, color=COLOR_ESTADO[e], height=0.6, edgecolor="white", lw=1.5, label=e)
        for yi, (l, v) in enumerate(zip(izq, t[e])):
            if v >= 3:
                ax.text(l + v / 2, yi, str(v), ha="center", va="center", fontsize=11, color="white",
                        fontweight="bold")
        izq += t[e].values
    ax.tick_params(axis="y", length=0, labelsize=12, labelcolor=TINTA)
    ax.tick_params(axis="x", labelsize=10)
    ax.spines["left"].set_visible(False)
    ax.legend(fontsize=10.5, frameon=False, ncol=5, loc="upper center", bbox_to_anchor=(0.45, -0.1),
              handlelength=1, columnspacing=1)


def _calor(ax, df: pd.DataFrame):
    abiertos = df[df["estado"].isin(["Vencido", "Por vencer"])]
    t = abiertos.pivot_table(index="tema", columns="comunidad", values="id", aggfunc="count", fill_value=0)
    if t.empty:
        ax.axis("off")
        return
    t = t.loc[t.sum(axis=1).sort_values(ascending=False).index]
    ax.imshow(t.values, cmap="Reds", aspect="auto", vmin=0, vmax=max(3, t.values.max()))
    for i in range(t.shape[0]):
        for j in range(t.shape[1]):
            v = t.values[i, j]
            if v:
                ax.text(j, i, str(v), ha="center", va="center", fontsize=11,
                        color="white" if v > t.values.max() / 2 else TINTA)
    ax.set_xticks(range(t.shape[1]), [c.replace("C.C. ", "").replace("Santa Rosa de ", "S.R. ") for c in t.columns],
                  rotation=28, ha="right", fontsize=10.5)
    ax.set_yticks(range(t.shape[0]), t.index, fontsize=11)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)


# ------------------------------------------------------------------ laminas
def _lamina(titulo: str, mensaje: str, cliente: str, hoy: date, filtros: str):
    """Lienzo 16:9 con la marca: titulo, mensaje clave y pie. Devuelve la figura."""
    fig = plt.figure(figsize=(16, 9), dpi=240, facecolor=FONDO)
    fig.patches.append(Rectangle((0, 0.985), 1, 0.015, transform=fig.transFigure, fc=VERDE, ec="none", zorder=-10))
    fig.text(0.035, 0.905, titulo, fontsize=30, fontweight="bold", color=VERDE_OSC)
    fig.text(0.035, 0.855, mensaje, fontsize=16, color=TINTA, wrap=True)
    logo = plt.imread(IMG / "logo_confluentia_horizontal.png")
    ax = fig.add_axes([0.83, 0.895, 0.14, 0.06])
    ax.imshow(logo)
    ax.axis("off")
    fig.patches.append(Rectangle((0.035, 0.06), 0.93, 0.0015, transform=fig.transFigure, fc=BORDE, ec="none"))
    pie = " · ".join(x for x in [cliente, f"Corte: {hoy:%d/%m/%Y}", filtros or "Todas las comunidades"] if x)
    fig.text(0.035, 0.03, f"Confluentia · {pie}", fontsize=11, color=TINTA_2)
    fig.text(0.965, 0.03, "Datos de ejemplo ficticios", fontsize=11, color=TINTA_2, ha="right")
    return fig


def _claves(fig, x, y, w, h, titulo, puntos: list[tuple[str, str, str]]):
    """Columna lateral 'Lo que hay que saber': (cifra, texto, color)."""
    fig.patches.append(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.01",
                                      transform=fig.transFigure, fc="white", ec=BORDE, lw=1.2, zorder=-10))
    fig.text(x + 0.018, y + h - 0.05, titulo, fontsize=16, fontweight="bold", color=VERDE_OSC)
    paso = (h - 0.09) / max(1, len(puntos))
    for i, (cifra, texto, color) in enumerate(puntos):
        yy = y + h - 0.09 - i * paso
        fig.text(x + 0.018, yy - 0.045, cifra, fontsize=28, fontweight="bold", color=color)
        fig.text(x + 0.018, yy - 0.068, textwrap.fill(texto, 40), fontsize=12.5, color=TINTA, va="top",
                 linespacing=1.35)


def _a_png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=240, facecolor=FONDO)
    plt.close(fig)
    return buf.getvalue()


def _corto(c: str) -> str:
    return str(c).replace("C.C. ", "")


def laminas(df: pd.DataFrame, ind: pd.DataFrame, k: dict, hoy: date, cliente: str = "",
            filtros: str = "") -> list[tuple[str, bytes]]:
    """Devuelve [(nombre_archivo, png 3840x2160), ...], una lamina por seccion del panel."""
    out = []
    tasa = k["tasa_cumplimiento"]
    criticas = ind[ind["semaforo"] == "Crítico"]
    venc = df[df["estado"] == "Vencido"]
    peor = ind.iloc[0] if not ind.empty else None
    grande = dict(x=0.035, w=0.62, y=0.1, h=0.71)
    lado = dict(x=0.675, w=0.29, y=0.1, h=0.71)

    # 1. resumen
    fig = _lamina("Resumen ejecutivo",
                  f"{k['vencidos']} de {k['total']} compromisos están vencidos sin cumplir; "
                  f"{len(criticas)} comunidades en estado crítico.", cliente, hoy, filtros)
    kpis = [("Compromisos registrados", f"{k['total']}", f"{df['reunion'].nunique()} reuniones", "#1c5cab"),
            ("Vencidos sin cumplir", f"{k['vencidos']}", "acción inmediata", COLOR_ESTADO["Vencido"]),
            ("Vencen en 30 días", f"{k['por_vencer']}", "programar seguimiento", COLOR_ESTADO["Por vencer"]),
            ("Tasa de cumplimiento", f"{tasa:.0%}" if tasa is not None else "–", "de los ya exigibles",
             COLOR_ESTADO["Cumplido"]),
            ("Comunidades críticas", f"{len(criticas)}", f"{k['alto_riesgo_abiertos']} de riesgo alto abiertos",
             "#a32424")]
    for i, (e, v, s_, c) in enumerate(kpis):
        x = 0.035 + i * 0.188
        fig.patches.append(FancyBboxPatch((x, 0.5), 0.175, 0.28, boxstyle="round,pad=0,rounding_size=0.01",
                                          transform=fig.transFigure, fc="white", ec=BORDE, lw=1.2, zorder=-10))
        fig.patches.append(Rectangle((x, 0.768), 0.175, 0.012, transform=fig.transFigure, fc=c, ec="none",
                                     zorder=-9))
        fig.text(x + 0.015, 0.72, e, fontsize=14, color=TINTA_2)
        fig.text(x + 0.015, 0.585, v, fontsize=58, fontweight="bold", color=TINTA)
        fig.text(x + 0.015, 0.53, s_, fontsize=13, color=TINTA_2)
    fig.text(0.035, 0.43, "Alertas prioritarias", fontsize=18, fontweight="bold", color=VERDE_OSC)
    peso = {"alto": 0, "medio": 1, "bajo": 2}
    top = venc.assign(p=venc["riesgo_conflicto"].map(peso).fillna(1)).sort_values(["p", "dias_restantes"]).head(4)
    for i, (_, r) in enumerate(top.iterrows()):
        y = 0.37 - i * 0.07
        fig.patches.append(Rectangle((0.035, y - 0.012), 0.006, 0.05, transform=fig.transFigure,
                                     fc=COLOR_ESTADO["Vencido"], ec="none"))
        fig.text(0.05, y + 0.012, f"{_corto(r['comunidad'])}: {r['descripcion']}", fontsize=14, fontweight="bold",
                 color=TINTA)
        fig.text(0.05, y - 0.012, f"{r['responsable']} · vencido hace {abs(int(r['dias_restantes']))} días · "
                 f"riesgo {r['riesgo_conflicto']}", fontsize=12, color=TINTA_2)
    out.append(("01_resumen_ejecutivo.png", _a_png(fig)))

    if df.empty or ind.empty:
        return out

    # 2. mapa territorial
    fig = _lamina("Mapa territorial de riesgo social",
                  f"{_corto(peor['comunidad'])} concentra el mayor riesgo (índice {peor['indice']:.0f}/100, "
                  f"{peor['vencidos']} compromisos vencidos).", cliente, hoy, filtros)
    ax = fig.add_axes([grande["x"], grande["y"], grande["w"], grande["h"]])
    _mapa(ax, ind)
    _claves(fig, **lado, titulo="Lo que hay que saber", puntos=[
        (f"{len(criticas)}", "comunidades en estado crítico: " + ", ".join(_corto(c) for c in criticas["comunidad"]),
         SEMAFORO["Crítico"]),
        (f"{df['reunion'].nunique()}", f"reuniones registradas en {df['comunidad'].nunique()} comunidades",
         VERDE),
        (f"{int(ind['familias'].fillna(0).sum()):,}".replace(",", " "), "familias en el área de influencia",
         "#1c5cab")])
    fig.text(grande["x"], 0.075, "Halo: intensidad de reuniones · tamaño del círculo: compromisos vencidos · "
             "color: semáforo del índice de riesgo", fontsize=11, color=TINTA_2)
    out.append(("02_mapa_territorial.png", _a_png(fig)))

    # 3. semaforo
    fig = _lamina("Semáforo social por comunidad",
                  "Índice 0–100 que pondera el riesgo de conflicto y el estado de cada compromiso "
                  "(crítico > 40, atención 25–40).", cliente, hoy, filtros)
    ax = fig.add_axes([0.2, 0.12, 0.33, 0.66])
    ax.set_facecolor("none")
    _semaforo(ax, ind)
    ax.tick_params(axis="y", labelsize=15)
    mejor = ind.iloc[-1]
    _claves(fig, **lado, titulo="Lo que hay que saber", puntos=[
        (f"{peor['indice']:.0f}", f"{_corto(peor['comunidad'])}: índice más alto; cumple solo el "
         f"{peor['cumplimiento']:.0%} de lo exigible", SEMAFORO["Crítico"]),
        (f"{(ind['semaforo'] == 'Atención').sum()}", "comunidades en atención: pueden pasar a crítico si "
         "vencen más compromisos", SEMAFORO["Atención"]),
        (f"{mejor['indice']:.0f}", f"{_corto(mejor['comunidad'])}: la relación más estable "
         f"({mejor['cumplimiento']:.0%} de cumplimiento)", SEMAFORO["Estable"])])
    out.append(("03_semaforo_social.png", _a_png(fig)))

    # 4. estado
    fig = _lamina("Estado de los compromisos",
                  f"Se cumplió el {tasa:.0%} de lo que ya era exigible; {k['por_vencer']} compromisos vencen "
                  "en los próximos 30 días." if tasa is not None else "Estado de los compromisos registrados.",
                  cliente, hoy, filtros)
    ax = fig.add_axes([0.06, 0.12, 0.5, 0.66])
    ax.set_facecolor("none")
    _dona(ax, df, tasa)
    for t in ax.get_legend().get_texts():
        t.set_fontsize(16)
    _claves(fig, **lado, titulo="Lo que hay que saber", puntos=[
        (f"{k['vencidos']}", "vencidos sin cumplir: cada uno es un reclamo potencial", COLOR_ESTADO["Vencido"]),
        (f"{k['por_vencer']}", "vencen en 30 días: programar seguimiento ya", COLOR_ESTADO["Por vencer"]),
        (f"{k['cumplidos']}", "cumplidos con evidencia", COLOR_ESTADO["Cumplido"])])
    out.append(("04_estado_compromisos.png", _a_png(fig)))

    # 5. quien incumple
    por_resp = venc["responsable"].value_counts()
    quien = por_resp.index[0] if not por_resp.empty else "—"
    fig = _lamina("¿Quién está incumpliendo?",
                  f"{quien} acumula {por_resp.iloc[0] if not por_resp.empty else 0} de los {len(venc)} compromisos "
                  "vencidos.", cliente, hoy, filtros)
    ax = fig.add_axes([0.12, 0.17, 0.52, 0.6])
    ax.set_facecolor("none")
    _quien(ax, df)
    ax.tick_params(axis="y", labelsize=16)
    _claves(fig, **lado, titulo="Lo que hay que saber", puntos=[
        (f"{n}", f"vencidos a cargo de {r}", COLOR_ESTADO["Vencido"]) for r, n in por_resp.head(3).items()])
    out.append(("05_quien_incumple.png", _a_png(fig)))

    # 6. temas
    abiertos = df[df["estado"].isin(["Vencido", "Por vencer"])]
    temas = abiertos["tema"].value_counts()
    fig = _lamina("Temas con compromisos abiertos",
                  f"{temas.index[0] if not temas.empty else '—'} es el tema con más compromisos vencidos o por vencer.",
                  cliente, hoy, filtros)
    ax = fig.add_axes([0.18, 0.2, 0.46, 0.58])
    ax.set_facecolor("none")
    _calor(ax, df)
    ax.tick_params(labelsize=13)
    _claves(fig, **lado, titulo="Lo que hay que saber", puntos=[
        (f"{n}", f"abiertos en {t}", COLOR_ESTADO["Vencido"]) for t, n in temas.head(3).items()])
    out.append(("06_temas_por_comunidad.png", _a_png(fig)))

    # 7. brecha
    fig = _lamina("Brecha de cumplimiento acumulada",
                  "Diferencia entre los compromisos que debían cumplirse y los que se cumplieron, mes a mes.",
                  cliente, hoy, filtros)
    ax = fig.add_axes([0.07, 0.12, 0.57, 0.66])
    ax.set_facecolor("none")
    _brecha(ax, df, hoy)
    ax.tick_params(labelsize=13)
    exig = int((df["fecha_limite"].notna() & (df["fecha_limite"] <= hoy)).sum())
    _claves(fig, **lado, titulo="Lo que hay que saber", puntos=[
        (f"{exig}", "compromisos que ya debían cumplirse", "#8a8984"),
        (f"{k['cumplidos']}", "cumplidos", COLOR_ESTADO["Cumplido"]),
        (f"{exig - k['cumplidos']}", "brecha acumulada: lo que debía cumplirse y aún no se cumple",
         COLOR_ESTADO["Vencido"])])
    out.append(("07_brecha_cumplimiento.png", _a_png(fig)))
    return out


def zip_laminas(lams: list[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, datos in lams:
            z.writestr(nombre, datos)
    return buf.getvalue()


def pptx_laminas(lams: list[tuple[str, bytes]]) -> bytes:
    """Una diapositiva 16:9 por lamina, a pantalla completa."""
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    for _, datos in lams:
        s = prs.slides.add_slide(prs.slide_layouts[6])
        s.shapes.add_picture(io.BytesIO(datos), 0, 0, width=prs.slide_width, height=prs.slide_height)
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()

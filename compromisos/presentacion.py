"""Exporta el tablero a una presentacion PowerPoint (.pptx) con la marca de Confluentia.

Los graficos de barras y de dona son graficos NATIVOS de PowerPoint: se pueden editar,
cambiar de color o actualizar los datos dentro de la propia presentacion. La red de actores
se dibuja con matplotlib (imagen), porque PowerPoint no tiene un grafico de redes.
"""
from __future__ import annotations

import io
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
import pandas as pd  # noqa: E402
from pptx import Presentation  # noqa: E402
from pptx.chart.data import CategoryChartData  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION  # noqa: E402
from pptx.enum.shapes import MSO_SHAPE  # noqa: E402
from pptx.enum.text import PP_ALIGN  # noqa: E402
from pptx.util import Inches, Pt  # noqa: E402

from . import actores as ac  # noqa: E402
from .visual import COLOR_ESTADO, SEMAFORO  # noqa: E402

IMG = Path(__file__).resolve().parents[1] / "img"
VERDE, VERDE_OSC, TINTA, GRIS = "2D4A33", "1F3A26", "1F2A37", "5B6675"
LEMA = "Inteligencia social para decisiones estratégicas en territorio"


def _rgb(h: str) -> RGBColor:
    return RGBColor.from_string(h.lstrip("#").upper())


def _texto(slide, x, y, w, h, texto, size=14, bold=False, color=TINTA, align=PP_ALIGN.LEFT):
    caja = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = caja.text_frame
    tf.word_wrap = True
    for i, linea in enumerate(texto.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run()
        r.text = linea
        r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(size), bold, _rgb(color), "Calibri"
    return caja


def _rect(slide, x, y, w, h, color, forma=MSO_SHAPE.RECTANGLE):
    s = slide.shapes.add_shape(forma, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = _rgb(color)
    s.line.fill.background()
    s.shadow.inherit = False
    return s


def _diapositiva(prs, titulo, subtitulo, corte):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _rect(s, 0, 0, 13.333, 0.12, VERDE)
    _texto(s, 0.5, 0.3, 10.0, 0.6, titulo, 26, True, VERDE_OSC)
    if subtitulo:
        _texto(s, 0.5, 0.88, 10.5, 0.4, subtitulo, 13, False, GRIS)
    s.shapes.add_picture(str(IMG / "logo_confluentia_horizontal.png"), Inches(10.63), Inches(0.38), width=Inches(2.2))
    _rect(s, 0.5, 7.0, 12.33, 0.01, "D5DBD6")
    _texto(s, 0.5, 7.05, 9, 0.3, f"Confluentia · {LEMA}", 9, False, GRIS)
    _texto(s, 9.3, 7.05, 3.53, 0.3, f"Corte: {corte:%d/%m/%Y} · Datos de ejemplo ficticios", 9, False, GRIS,
           PP_ALIGN.RIGHT)
    return s


def _kpi(slide, x, y, w, etiqueta, valor, sub, color):
    caja = _rect(slide, x, y, w, 1.45, "FFFFFF", MSO_SHAPE.ROUNDED_RECTANGLE)
    caja.adjustments[0] = 0.08
    caja.line.color.rgb = _rgb("E3E7EB")
    _rect(slide, x, y, w, 0.08, color)
    _texto(slide, x + 0.15, y + 0.15, w - 0.3, 0.3, etiqueta, 11, False, GRIS)
    _texto(slide, x + 0.15, y + 0.42, w - 0.3, 0.6, valor, 30, True, TINTA)
    _texto(slide, x + 0.15, y + 1.0, w - 0.3, 0.4, sub, 10, False, GRIS)


def _tabla(slide, x, y, w, df: pd.DataFrame, anchos: list[float], size=10):
    filas, cols = len(df) + 1, len(df.columns)
    t = slide.shapes.add_table(filas, cols, Inches(x), Inches(y), Inches(w), Inches(0.3 * filas)).table
    for j, (c, a) in enumerate(zip(df.columns, anchos)):
        t.columns[j].width = Inches(a)
        celda = t.cell(0, j)
        celda.text = str(c)
        celda.fill.solid()
        celda.fill.fore_color.rgb = _rgb(VERDE)
    for i, fila in enumerate(df.itertuples(index=False), start=1):
        for j, v in enumerate(fila):
            celda = t.cell(i, j)
            celda.text = "" if pd.isna(v) else str(v)
            celda.fill.solid()
            celda.fill.fore_color.rgb = _rgb("FFFFFF" if i % 2 else "F2F5F2")
    for i in range(filas):
        for j in range(cols):
            for p in t.cell(i, j).text_frame.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(size)
                    r.font.color.rgb = _rgb("FFFFFF" if i == 0 else TINTA)
                    r.font.bold = i == 0
    return t


def _colorear_puntos(grafico, colores):
    for punto, color in zip(grafico.plots[0].series[0].points, colores):
        punto.format.fill.solid()
        punto.format.fill.fore_color.rgb = _rgb(color)


def _imagen_red(A: pd.DataFrame, R: pd.DataFrame) -> io.BytesIO:
    g = ac.red(A, R)
    pos, anclas = ac._posiciones(g)
    fig, ax = plt.subplots(figsize=(8.2, 6.2), dpi=200)
    for u, v, d in g.edges(data=True):
        color, guion, ancho = ac.REL_ESTILO.get(d["tipo"], ("#8a8984", "solid", 1))
        ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]], color=color, alpha=0.6, lw=ancho * 0.7,
                ls={"solid": "-", "dot": ":", "dash": "--"}[guion], zorder=1)
    marcador = {"circle": "o", "square": "s", "diamond": "D", "triangle-up": "^"}
    for n, d in g.nodes(data=True):
        ax.scatter(*pos[n], s=25 + 28 * int(d.get("influencia", 3)), c=ac.POSTURA_COLOR[int(d.get("postura", 0))],
                   marker=marcador[ac.SIMBOLO_TIPO.get(d.get("tipo"), "circle")], edgecolors="white",
                   linewidths=1, zorder=3)
        if int(d.get("influencia", 3)) >= 5 or (not d.get("comunidad") and int(d.get("influencia", 3)) >= 4):
            ax.annotate(n, pos[n], xytext=(0, -11), textcoords="offset points", ha="center", fontsize=6.5,
                        color="#1f2a37", zorder=4)
    for com, c in anclas.items():
        y = c[1] + (0.95 if c[1] > -1 else -1.15)
        ax.text(c[0], y, com.replace("C.C. ", ""), ha="center", fontsize=8, fontweight="bold", color="#5b6675",
                bbox=dict(boxstyle="round,pad=0.25", fc="#eef1f5", ec="none"))
    for post, txt in ac.POSTURA_TXT.items():
        ax.scatter([], [], c=ac.POSTURA_COLOR[post], s=40, label=txt)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.06), ncol=5, frameon=False, fontsize=8)
    ax.set_aspect("equal")
    ax.axis("off")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf


def generar(df: pd.DataFrame, ind: pd.DataFrame, k: dict, A: pd.DataFrame, R: pd.DataFrame,
            H: pd.DataFrame, corte: date, cliente: str = "Minera Andina S.A.C. (ejemplo)") -> bytes:
    """Arma la presentacion completa y devuelve los bytes del .pptx."""
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)

    # 1. portada
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _rect(s, 0, 0, 5.2, 7.5, VERDE)
    s.shapes.add_picture(str(IMG / "logo_confluentia_blanco.png"), Inches(0.75), Inches(1.6), width=Inches(3.7))
    _texto(s, 5.9, 2.0, 6.9, 0.5, "REPORTE DE GESTIÓN SOCIAL", 14, True, VERDE)
    _texto(s, 5.9, 2.5, 6.9, 1.6, "Seguimiento de compromisos\ny mapa de actores", 36, True, VERDE_OSC)
    _texto(s, 5.9, 4.3, 6.9, 0.5, cliente, 18, False, TINTA)
    _texto(s, 5.9, 4.8, 6.9, 0.5, f"Fecha de corte: {corte:%d/%m/%Y}", 14, False, GRIS)
    _texto(s, 5.9, 6.4, 6.9, 0.5, "Generado con Compromisos · www.confluentia.pe", 11, False, GRIS)

    # 2. resumen ejecutivo
    s = _diapositiva(prs, "Resumen ejecutivo", f"{k['total']} compromisos en {df['reunion'].nunique()} reuniones "
                     f"con {df['comunidad'].nunique()} comunidades", corte)
    tasa = k["tasa_cumplimiento"]
    criticas = int((ind["semaforo"] == "Crítico").sum())
    datos = [("Compromisos registrados", f"{k['total']}", f"{df['reunion'].nunique()} reuniones", "1C5CAB"),
             ("Vencidos sin cumplir", f"{k['vencidos']}", "requieren acción inmediata", COLOR_ESTADO["Vencido"]),
             ("Vencen en 30 días", f"{k['por_vencer']}", "programar seguimiento", COLOR_ESTADO["Por vencer"]),
             ("Tasa de cumplimiento", f"{tasa:.0%}" if tasa is not None else "–", "de los ya exigibles",
              COLOR_ESTADO["Cumplido"]),
             ("Comunidades en estado crítico", f"{criticas}", f"{k['alto_riesgo_abiertos']} de riesgo alto abiertos",
              "A32424")]
    for i, (e, v, sub, c) in enumerate(datos):
        _kpi(s, 0.5 + i * 2.5, 1.5, 2.3, e, v, sub, c)
    _texto(s, 0.5, 3.3, 12, 0.4, "Alertas prioritarias", 16, True, VERDE_OSC)
    peso = {"alto": 0, "medio": 1, "bajo": 2}
    alertas = (df[df["estado"] == "Vencido"].assign(p=lambda d: d["riesgo_conflicto"].map(peso).fillna(1))
               .sort_values(["p", "dias_restantes"]).head(5))
    lineas = [f"•  {r['comunidad'].replace('C.C. ', '')}: {r['descripcion']} — {r['responsable']}, "
              f"vencido hace {abs(int(r['dias_restantes']))} días (riesgo {r['riesgo_conflicto']})"
              for _, r in alertas.iterrows()]
    _texto(s, 0.5, 3.75, 12.3, 3.0, "\n".join(lineas) or "Sin compromisos vencidos.", 13, False, TINTA)

    # 3. semaforo por comunidad (grafico nativo)
    s = _diapositiva(prs, "Semáforo social por comunidad",
                     "Índice de riesgo 0–100: pondera el riesgo de conflicto y el estado de cada compromiso", corte)
    d = ind.sort_values("indice")
    cd = CategoryChartData()
    cd.categories = [c.replace("C.C. ", "") for c in d["comunidad"]]
    cd.add_series("Índice de riesgo", [float(v) for v in d["indice"]])
    gr = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.5), Inches(1.45), Inches(7.3), Inches(5.4),
                            cd).chart
    gr.has_legend, gr.has_title = False, False
    gr.plots[0].gap_width = 60
    gr.plots[0].has_data_labels = True
    gr.plots[0].data_labels.font.size = Pt(11)
    gr.plots[0].data_labels.number_format, gr.plots[0].data_labels.number_format_is_linked = "0", False
    gr.value_axis.maximum_scale, gr.value_axis.has_major_gridlines = 100, False
    gr.value_axis.tick_labels.font.size = gr.category_axis.tick_labels.font.size = Pt(11)
    _colorear_puntos(gr, [SEMAFORO[x] for x in d["semaforo"]])
    tabla = ind[["comunidad", "compromisos", "vencidos", "cumplimiento", "semaforo"]].copy()
    tabla["comunidad"] = tabla["comunidad"].str.replace("C.C. ", "")
    tabla["cumplimiento"] = (tabla["cumplimiento"] * 100).round(0).astype(int).astype(str) + " %"
    tabla.columns = ["Comunidad", "Compr.", "Vencidos", "Cumpl.", "Semáforo"]
    _tabla(s, 8.1, 1.55, 4.75, tabla, [1.75, 0.65, 0.8, 0.7, 0.85], 10)

    # 4. estado de compromisos y quien incumple
    s = _diapositiva(prs, "Estado de los compromisos", "Distribución por estado y vencidos por responsable", corte)
    orden = [e for e in COLOR_ESTADO if (df["estado"] == e).any()]
    cd = CategoryChartData()
    cd.categories = orden
    cd.add_series("Compromisos", [int((df["estado"] == e).sum()) for e in orden])
    gr = s.shapes.add_chart(XL_CHART_TYPE.DOUGHNUT, Inches(0.5), Inches(1.45), Inches(5.8), Inches(5.4), cd).chart
    gr.has_title = False
    gr.has_legend = True
    gr.legend.position, gr.legend.include_in_layout = XL_LEGEND_POSITION.BOTTOM, False
    gr.legend.font.size = Pt(11)
    gr.plots[0].has_data_labels = True
    gr.plots[0].data_labels.font.size = Pt(12)
    _colorear_puntos(gr, [COLOR_ESTADO[e] for e in orden])
    resp = df[df["estado"] == "Vencido"]["responsable"].value_counts()
    cd = CategoryChartData()
    cd.categories = list(resp.index)
    cd.add_series("Vencidos", [int(v) for v in resp.values])
    gr = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(6.8), Inches(1.45), Inches(6.0), Inches(5.4),
                            cd).chart
    gr.has_legend = False
    gr.has_title = True
    gr.chart_title.text_frame.text = "Compromisos vencidos por responsable"
    gr.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(13)
    gr.plots[0].has_data_labels = True
    gr.plots[0].gap_width = 70
    gr.value_axis.has_major_gridlines = False
    gr.category_axis.tick_labels.font.size = gr.value_axis.tick_labels.font.size = Pt(11)
    _colorear_puntos(gr, [COLOR_ESTADO["Vencido"]] * len(resp))

    # 5. vencidos prioritarios (tabla)
    s = _diapositiva(prs, "Compromisos vencidos prioritarios", "Ordenados por riesgo de conflicto y antigüedad", corte)
    top = (df[df["estado"] == "Vencido"].assign(p=lambda d: d["riesgo_conflicto"].map(peso).fillna(1))
           .sort_values(["p", "dias_restantes"]).head(12))
    t = pd.DataFrame({
        "Comunidad": top["comunidad"].str.replace("C.C. ", ""),
        "Compromiso": top["descripcion"].str.slice(0, 70),
        "Responsable": top["responsable"],
        "Plazo": pd.to_datetime(top["fecha_limite"]).dt.strftime("%d/%m/%Y"),
        "Días vencido": top["dias_restantes"].abs().astype(int),
        "Riesgo": top["riesgo_conflicto"],
    })
    _tabla(s, 0.5, 1.45, 12.33, t, [1.9, 5.6, 1.4, 1.2, 1.2, 1.03], 10)

    # 6. mapa de actores (red)
    m = ac.metricas(ac.red(A, R))
    s = _diapositiva(prs, "Mapa de actores y relaciones",
                     f"{len(A)} actores y {len(R)} relaciones · color = postura hacia la empresa, "
                     "tamaño = influencia", corte)
    s.shapes.add_picture(_imagen_red(A, R), Inches(0.4), Inches(1.35), height=Inches(5.55))
    _texto(s, 8.2, 1.45, 4.6, 0.4, "Actores clave (intermediación)", 15, True, VERDE_OSC)
    lineas = [f"•  {r['nombre']} — {(r['comunidad'] or r['organizacion']).replace('C.C. ', '')} · "
              f"{r['postura_txt']}{' · puente' if r['puente'] else ''}" for _, r in m.head(8).iterrows()]
    _texto(s, 8.2, 1.9, 4.6, 3.2, "\n".join(lineas), 11, False, TINTA)
    criticos = m[(m["postura"] < 0) & (m["influencia"] >= 4)].sort_values("influencia", ascending=False).head(5)
    _texto(s, 8.2, 5.0, 4.6, 0.4, "Gestionar de cerca", 15, True, "C2410C")
    _texto(s, 8.2, 5.4, 4.6, 1.5, ", ".join(criticos["nombre"]) or "—", 11, False, TINTA)

    # 7. cambios de postura
    desde = (pd.Timestamp(corte) - pd.DateOffset(months=6)).date()
    cam = ac.cambios(H[H["fecha"] <= corte], desde, corte)
    s = _diapositiva(prs, "Dinámica de posturas: quién se movió en los últimos 6 meses",
                     f"Comparación entre el {desde:%d/%m/%Y} y el {corte:%d/%m/%Y} · ordenado por riesgo "
                     "(cambio × influencia)", corte)
    if cam.empty:
        _texto(s, 0.5, 1.6, 12, 0.5, "Nadie cambió de postura en este periodo.", 14)
    else:
        aleja, acerca = int((cam["delta"] < 0).sum()), int((cam["delta"] > 0).sum())
        _kpi(s, 0.5, 1.45, 2.4, "Se alejan de la empresa", f"{aleja}",
             f"{int(((cam['delta'] < 0) & (cam['influencia'] >= 4)).sum())} con alta influencia", "C2410C")
        _kpi(s, 0.5, 3.1, 2.4, "Se acercan", f"{acerca}", "oportunidad de alianza", "1C5CAB")
        t = cam.head(11)
        t = pd.DataFrame({
            "Actor": t["nombre"],
            "Comunidad": t["comunidad"].str.replace("C.C. ", ""),
            "Cambio": [f"{ac.POSTURA_TXT[a]} → {ac.POSTURA_TXT[b]}" for a, b in zip(t["antes"], t["ahora"])],
            "Fecha": pd.to_datetime(t["fecha_cambio"]).dt.strftime("%d/%m/%Y"),
            "Evidencia": t["evidencia"].str.slice(0, 60),
        })
        _tabla(s, 3.2, 1.45, 9.63, t, [1.9, 1.7, 1.9, 1.1, 3.03], 10)

    # 8. cierre
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _rect(s, 0, 0, 13.333, 7.5, VERDE)
    s.shapes.add_picture(str(IMG / "logo_confluentia_blanco.png"), Inches(4.9), Inches(1.0), width=Inches(3.5))
    _texto(s, 0, 5.3, 13.333, 0.5, "www.confluentia.pe", 20, True, "FFFFFF", PP_ALIGN.CENTER)

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()

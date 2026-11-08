"""Version compacta de los graficos para celular (Android o iPhone)."""
from __future__ import annotations

import textwrap

import plotly.graph_objects as go


def compacto(fig: go.Figure) -> go.Figure:
    """Version del grafico para celular (Android o iPhone): letras mas chicas, leyenda abajo,
    sin nombres sobre puntos cuando son muchos (se ven al tocar) y alturas proporcionadas."""
    f = go.Figure(fig)
    lay = f.layout
    alto = lay.height or 400
    cuadrado = bool(lay.yaxis and lay.yaxis.scaleanchor)  # red de actores: proporcion 1:1
    f.update_layout(font=dict(size=10), hoverlabel=dict(font_size=11))
    if lay.title and lay.title.text:
        f.update_layout(title_font_size=12)
    m = lay.margin
    # margenes chicos, salvo los que dejan espacio a proposito para un texto (p. ej. "% vencido")
    f.update_layout(margin=dict(l=min(m.l, 6) if (m.l or 0) <= 20 else m.l,
                                r=min(m.r, 6) if (m.r or 0) <= 20 else int(m.r * 0.8)))
    leyenda_arriba = lay.legend is not None and (lay.legend.y or 0) >= 1
    if leyenda_arriba:  # la leyenda baja: el espacio de arriba ya no hace falta
        f.update_layout(margin=dict(t=40 if lay.title and lay.title.text else 10))
    # leyenda horizontal debajo del grafico, para que no tape el titulo ni las barras
    if lay.showlegend is not False and len(f.data) > 1:
        # anclada al borde inferior de la figura (no al grafico) para no chocar con el titulo del eje
        n_items = sum(1 for t in f.data if t.showlegend is not False and t.name)
        filas = max(1, -(-n_items // 3))
        b_actual = m.b if m.b is not None else 8
        f.update_layout(legend=dict(orientation="h", yref="container", yanchor="bottom", y=0, x=0,
                                    xanchor="left", font=dict(size=10), title=None, itemwidth=30),
                        margin=dict(b=b_actual + 18 * filas + 8))
        alto += 18 * filas
    n_rotulos = sum(len(t.x) for t in f.data if t.type == "scatter" and "text" in (t.mode or "")
                    and t.x is not None)
    for tr in f.data:
        if getattr(tr, "textfont", None) is not None:
            tr.textfont.size = min(tr.textfont.size or 12, 10)
        modo = getattr(tr, "mode", None) or ""
        if tr.type == "scatter" and "text" in modo and "markers" in modo and n_rotulos > 6 and \
                (tr.textposition or "middle center") != "middle center":
            tr.mode = "markers"  # demasiados nombres junto a los puntos para una pantalla chica (se ven al tocar)
        if cuadrado and tr.type == "scatter" and tr.marker is not None and tr.marker.size is not None:
            tam = tr.marker.size
            tr.marker.size = [t * 0.7 for t in tam] if hasattr(tam, "__len__") else tam * 0.7
        if tr.type == "bar" and tr.orientation == "h" and tr.y is not None and \
                all(isinstance(v, str) for v in tr.y) and max((len(v) for v in tr.y), default=0) > 22:
            tr.y = ["<br>".join(textwrap.wrap(v.replace("<br>", " "), 20)) for v in tr.y]  # nombres largos en 2 lineas
        if tr.type == "heatmap":  # nombres de columnas abajo e inclinados, sin notas al pie
            f.update_xaxes(side="bottom", tickangle=-60, tickfont=dict(size=9))
            f.update_yaxes(tickfont=dict(size=9))
            f.update_layout(margin=dict(t=36 if lay.title and lay.title.text else 8))
            f.layout.annotations = tuple(a for a in (f.layout.annotations or [])
                                         if not (a.yref == "paper" and (a.y or 0) <= 0))
    for a in lay.annotations or []:
        a.font.size = min(a.font.size or 12, 10 if a.showarrow is False else 9)
    f.update_xaxes(tickfont=dict(size=9.5), title_font=dict(size=10.5))
    f.update_yaxes(tickfont=dict(size=9.5), title_font=dict(size=10.5))
    if cuadrado:  # acercar al area donde estan los actores (menos espacio vacio)
        xs = [v for t in f.data if t.type == "scatter" and t.x is not None for v in t.x if v is not None]
        ys = [v for t in f.data if t.type == "scatter" and t.y is not None for v in t.y if v is not None]
        xs += [a.x for a in f.layout.annotations or [] if a.x is not None and a.xref in (None, "x")]
        ys += [a.y for a in f.layout.annotations or [] if a.y is not None and a.yref in (None, "y")]
        if xs and ys:
            f.update_xaxes(range=[min(xs) - 0.6, max(xs) + 0.6])
            f.update_yaxes(range=[min(ys) - 0.5, max(ys) + 0.5])
        f.update_layout(height=min(alto, 430))
    elif alto > 560:
        f.update_layout(height=int(alto * 0.8))
    else:
        f.update_layout(height=alto)
    return f

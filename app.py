"""Compromisos: de la reunion comunal al seguimiento de compromisos, con IA.

Ejecutar en local:   streamlit run app.py
"""
from __future__ import annotations

import io
import os
import uuid
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

try:  # .env en local; en Streamlit Cloud se usan los Secrets
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from compromisos import ia, registro
from compromisos.modelos import ExtraccionReunion

RAIZ = Path(__file__).parent
EJEMPLO = RAIZ / "datos" / "ejemplo"

# Colores de estado (paleta de estado fija: nunca se reutiliza para otra cosa)
COLOR_ESTADO = {
    "Vencido": "#d03b3b",
    "Por vencer": "#fab219",
    "En plazo": "#2a78d6",
    "Sin plazo": "#8a8984",
    "Cumplido": "#0ca30c",
}
ICONO_ESTADO = {"Vencido": "🔴", "Por vencer": "🟡", "En plazo": "🔵", "Sin plazo": "⚪", "Cumplido": "🟢"}
COLOR_PARTE = {"Empresa": "#2a78d6", "Estado": "#eb6834", "Comunidad": "#1baf7a", "Otro": "#8a8984"}

st.set_page_config(page_title="Compromisos", page_icon="🤝", layout="wide")


def cargar_claves() -> None:
    """Copia las claves de Streamlit Secrets al entorno (en local se leen de .env)."""
    for nombre in ("GROQ_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        try:
            if nombre in st.secrets and not os.getenv(nombre):
                os.environ[nombre] = st.secrets[nombre]
        except Exception:
            pass


cargar_claves()


def estilo_figura(fig, alto=320):
    fig.update_layout(
        height=alto,
        margin=dict(l=10, r=10, t=50, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="top", y=-0.12, x=0, title=None),
        bargap=0.35,
        font=dict(size=13),
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(128,128,128,0.15)", zeroline=False)
    fig.update_yaxes(showgrid=False)
    fig.update_traces(marker_line_width=2, marker_line_color="rgba(255,255,255,0.9)",
                      selector=dict(type="bar"))
    return fig


# ---------------------------------------------------------------- estado de sesion
if "registro" not in st.session_state:
    st.session_state.registro = registro.cargar(EJEMPLO / "registro_demo.csv")
if "extraccion" not in st.session_state:
    st.session_state.extraccion = None

# ---------------------------------------------------------------- barra lateral
with st.sidebar:
    st.title("🤝 Compromisos")
    st.caption("De la reunión comunal al seguimiento de cada acuerdo.")
    hay_clave = ia.proveedor() is not None
    if hay_clave:
        st.success(f"IA conectada: {ia.descripcion_proveedor()}")
    else:
        st.warning("Sin clave de IA: puedes usar la reunión de ejemplo.")
    hoy = st.date_input("Fecha de corte", value=date.today(), format="DD/MM/YYYY")
    st.divider()
    st.markdown("**Registro**")
    subido = st.file_uploader("Cargar registro (CSV)", type=["csv"], key="csv_registro")
    if subido is not None and st.button("Usar este registro"):
        st.session_state.registro = registro.cargar(subido)
        st.rerun()
    if st.button("Volver al registro de ejemplo"):
        st.session_state.registro = registro.cargar(EJEMPLO / "registro_demo.csv")
        st.rerun()
    st.caption("Datos de ejemplo sintéticos: comunidades y empresa ficticias.")

tab_reunion, tab_tablero, tab_registro = st.tabs(
    ["1 · Nueva reunión", "2 · Tablero de seguimiento", "3 · Registro y descargas"]
)

# ---------------------------------------------------------------- 1. nueva reunion
with tab_reunion:
    st.subheader("Sube la reunión y la IA extrae los compromisos")
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    nombre = c1.text_input("Nombre de la reunión", "Mesa de trabajo Pucará Alto")
    fecha_r = c2.date_input("Fecha", value=date(2026, 11, 4), format="DD/MM/YYYY")
    comunidad = c3.text_input("Comunidad", "C.C. Pucará Alto")
    distrito = c4.text_input("Distrito", "San Miguel")

    origen = st.radio(
        "¿Qué tienes de la reunión?",
        ["🎙️ Audio de la reunión", "📄 Foto del acta", "⌨️ Texto o transcripción", "⭐ Reunión de ejemplo"],
        horizontal=True,
    )

    texto = ""
    if origen == "🎙️ Audio de la reunión":
        audio = st.file_uploader("Audio (mp3, m4a, wav, ogg; máx. 25 MB)",
                                 type=["mp3", "m4a", "wav", "ogg", "webm", "mp4"])
        grabado = st.audio_input("…o grábala aquí mismo")
        fuente_audio = audio or grabado
        if fuente_audio and st.button("Transcribir y extraer", type="primary", disabled=not hay_clave):
            with st.status("Procesando la reunión…", expanded=True) as s:
                s.write(f"🎧 Transcribiendo ({ia.descripcion_proveedor()})…")
                datos = fuente_audio.getvalue()
                st.session_state.texto = ia.transcribir_audio(
                    getattr(fuente_audio, "name", "grabacion.wav"), datos,
                    getattr(fuente_audio, "type", "audio/wav"))
                st.session_state.minutos = len(datos) / (16000 * 60)  # aprox. 128 kbps
                s.update(label="Transcripción lista", state="complete")
    elif origen == "📄 Foto del acta":
        foto = st.file_uploader("Foto o escaneo del acta", type=["jpg", "jpeg", "png"])
        if foto:
            st.image(foto, width=320)
        if foto and st.button("Leer acta y extraer", type="primary", disabled=not hay_clave):
            with st.spinner("Leyendo el acta…"):
                st.session_state.texto = ia.leer_acta_imagen(foto.getvalue(), foto.type)
                st.session_state.minutos = 0
    elif origen == "⌨️ Texto o transcripción":
        st.session_state.texto = st.text_area("Pega aquí el acta o la transcripción", height=220,
                                              value=st.session_state.get("texto", ""))
        st.session_state.minutos = 0
    else:
        st.session_state.texto = (EJEMPLO / "transcripcion_reunion_demo.txt").read_text(encoding="utf-8")
        st.session_state.minutos = 2.5
        st.info("Reunión ficticia de demostración. Si no hay clave de IA se muestra la extracción guardada.")

    texto = st.session_state.get("texto", "")
    if texto:
        with st.expander("Ver transcripción", expanded=False):
            st.write(texto)

        if st.button("🧠 Extraer compromisos", type="primary"):
            contexto = f"{nombre}. Comunidad {comunidad}, distrito {distrito}."
            if hay_clave:
                with st.spinner("La IA está leyendo la reunión…"):
                    try:
                        ext, uso = ia.extraer_compromisos(texto, fecha_r, contexto)
                        st.session_state.costo = ia.costo_estimado(st.session_state.get("minutos", 0), uso)
                        st.session_state.uso = uso
                    except Exception as e:  # la demo no se cae: usa la extraccion guardada
                        st.error(f"No se pudo usar la IA ({e}). Muestro la extracción guardada.")
                        ext = ExtraccionReunion.model_validate_json(
                            (EJEMPLO / "extraccion_reunion_demo.json").read_text(encoding="utf-8"))
            else:
                ext = ExtraccionReunion.model_validate_json(
                    (EJEMPLO / "extraccion_reunion_demo.json").read_text(encoding="utf-8"))
            st.session_state.extraccion = ext

    ext: ExtraccionReunion | None = st.session_state.extraccion
    if ext:
        st.markdown("#### Resumen")
        st.write(ext.resumen)
        if "uso" in st.session_state:
            u = st.session_state.uso
            st.caption(f"Tokens: {u['entrada']:,} de entrada, {u['salida']:,} de salida · "
                       f"costo estimado: US$ {st.session_state.costo:.4f}")
        nuevos = registro.desde_extraccion(ext, nombre, fecha_r, comunidad, distrito,
                                           fuente="IA (revisado)")
        st.markdown(f"#### {len(nuevos)} compromisos encontrados · revísalos antes de guardar")
        editados = st.data_editor(
            nuevos[["descripcion", "responsable", "responsable_detalle", "tema",
                    "fecha_limite", "riesgo_conflicto", "cita_textual"]],
            num_rows="dynamic", width="stretch", hide_index=True,
            column_config={
                "descripcion": st.column_config.TextColumn("Compromiso", width="large"),
                "responsable": st.column_config.SelectboxColumn(
                    "Responsable", options=["Empresa", "Estado", "Comunidad", "Otro"]),
                "responsable_detalle": "Área / persona",
                "tema": "Tema",
                "fecha_limite": st.column_config.DateColumn("Plazo", format="DD/MM/YYYY"),
                "riesgo_conflicto": st.column_config.SelectboxColumn(
                    "Riesgo", options=["alto", "medio", "bajo"]),
                "cita_textual": st.column_config.TextColumn("Cita textual", width="large"),
            },
            key="editor_nuevos",
        )
        if ext.temas_pendientes:
            st.warning("**Temas sin acuerdo:** " + "; ".join(ext.temas_pendientes))

        b1, b2 = st.columns(2)
        if b1.button("✅ Guardar en el registro", type="primary"):
            base = editados.dropna(subset=["descripcion"]).copy()
            base["id"] = [uuid.uuid4().hex[:8] for _ in range(len(base))]
            base["reunion"], base["fecha_reunion"] = nombre, fecha_r
            base["comunidad"], base["distrito"] = comunidad, distrito
            base["beneficiario"], base["cumplido"] = comunidad, False
            base["fuente"] = "IA (revisado)"
            st.session_state.registro = registro.normalizar(
                pd.concat([st.session_state.registro, base], ignore_index=True))
            st.session_state.extraccion = None
            st.success("Guardado. Revisa el tablero de seguimiento.")
        b2.download_button(
            "⬇️ Descargar ficha de la reunión (.md)",
            registro.acta_markdown(ext, nombre, fecha_r, comunidad),
            file_name=f"ficha_{fecha_r:%Y%m%d}.md",
        )

# ---------------------------------------------------------------- 2. tablero
with tab_tablero:
    df = registro.con_estado(st.session_state.registro, hoy)
    f1, f2, f3 = st.columns(3)
    comunidades = f1.multiselect("Comunidad", sorted(df["comunidad"].unique()), placeholder="Todas")
    partes = f2.multiselect("Responsable", ["Empresa", "Estado", "Comunidad", "Otro"], placeholder="Todas")
    temas = f3.multiselect("Tema", sorted(df["tema"].unique()), placeholder="Todas")
    if comunidades:
        df = df[df["comunidad"].isin(comunidades)]
    if partes:
        df = df[df["responsable"].isin(partes)]
    if temas:
        df = df[df["tema"].isin(temas)]

    k = registro.indicadores(df)
    m = st.columns(5)
    m[0].metric("Compromisos", k["total"])
    m[1].metric("🔴 Vencidos sin cumplir", k["vencidos"])
    m[2].metric(f"🟡 Vencen en {registro.DIAS_ALERTA} días", k["por_vencer"])
    m[3].metric("Cumplimiento", f"{k['tasa_cumplimiento']:.0%}" if k["tasa_cumplimiento"] is not None else "–",
                help="Cumplidos entre los que ya debían cumplirse (cumplidos + vencidos)")
    m[4].metric("⚠️ Riesgo alto abiertos", k["alto_riesgo_abiertos"])

    alertas = df[df["estado"].isin(["Vencido", "Por vencer"])].sort_values("dias_restantes")
    if not alertas.empty:
        st.markdown("#### Alertas: atender primero")
        vista = alertas.assign(
            Estado=alertas["estado"].map(lambda e: f"{ICONO_ESTADO[e]} {e}"),
            Días=alertas["dias_restantes"],
        )[["Estado", "Días", "descripcion", "responsable", "comunidad", "riesgo_conflicto", "fecha_limite"]]
        st.dataframe(vista.head(8), hide_index=True, width="stretch", column_config={
            "descripcion": "Compromiso", "responsable": "Responsable", "comunidad": "Comunidad",
            "riesgo_conflicto": "Riesgo",
            "fecha_limite": st.column_config.DateColumn("Plazo", format="DD/MM/YYYY"),
            "Días": st.column_config.NumberColumn(help="Negativo = días de atraso"),
        })

    if not df.empty:
        g1, g2 = st.columns(2)
        por_parte = df.groupby(["responsable", "estado"]).size().reset_index(name="n")
        fig = px.bar(por_parte, y="responsable", x="n", color="estado", orientation="h",
                     color_discrete_map=COLOR_ESTADO,
                     category_orders={"estado": registro.ORDEN_ESTADO},
                     labels={"n": "Compromisos", "responsable": "", "estado": "Estado"},
                     title="¿Quién está incumpliendo?")
        g1.plotly_chart(estilo_figura(fig), width="stretch")

        abiertos = df[df["estado"] == "Vencido"].groupby("tema").size().sort_values().reset_index(name="n")
        fig2 = px.bar(abiertos, y="tema", x="n", orientation="h", text="n",
                      color_discrete_sequence=[COLOR_ESTADO["Vencido"]],
                      labels={"n": "Vencidos sin cumplir", "tema": ""},
                      title="Compromisos vencidos por tema")
        fig2.update_traces(textposition="outside", cliponaxis=False)
        g2.plotly_chart(estilo_figura(fig2), width="stretch")

        por_reunion = (df.groupby(["fecha_reunion", "reunion"])
                       .apply(lambda g: pd.Series({
                           "cumplidos": (g["estado"] == "Cumplido").sum(),
                           "exigibles": g["estado"].isin(["Cumplido", "Vencido"]).sum(),
                           "total": len(g)}), include_groups=False)
                       .reset_index().sort_values("fecha_reunion"))
        por_reunion["tasa"] = por_reunion["cumplidos"] / por_reunion["exigibles"].where(por_reunion["exigibles"] > 0)
        por_reunion["etiqueta"] = por_reunion["fecha_reunion"].astype(str).str[:7] + " · " + por_reunion["reunion"]
        fig3 = px.bar(por_reunion, x="etiqueta", y="tasa",
                      color_discrete_sequence=[COLOR_PARTE["Empresa"]],
                      hover_data={"cumplidos": True, "exigibles": True, "total": True, "etiqueta": False},
                      labels={"tasa": "Tasa de cumplimiento", "etiqueta": ""},
                      title="Cumplimiento por reunión (de los compromisos ya exigibles)")
        fig3.update_yaxes(tickformat=".0%", range=[0, 1], showgrid=True,
                          gridcolor="rgba(128,128,128,0.15)")
        fig3.update_xaxes(showgrid=False)
        st.plotly_chart(estilo_figura(fig3, 340), width="stretch")

# ---------------------------------------------------------------- 3. registro
with tab_registro:
    df = registro.con_estado(st.session_state.registro, hoy)
    st.markdown("Marca **Cumplido** cuando haya evidencia (acta de entrega, fotos, informe).")
    editado = st.data_editor(
        df.drop(columns=["estado", "dias_restantes"]),
        hide_index=True, width="stretch", key="editor_registro",
        disabled=["id", "fuente"],
        column_config={
            "cumplido": st.column_config.CheckboxColumn("Cumplido"),
            "fecha_limite": st.column_config.DateColumn("Plazo", format="DD/MM/YYYY"),
            "fecha_reunion": st.column_config.DateColumn("Reunión", format="DD/MM/YYYY"),
            "fecha_cumplimiento": st.column_config.DateColumn("Cumplido el", format="DD/MM/YYYY"),
            "descripcion": st.column_config.TextColumn("Compromiso", width="large"),
        },
    )
    if st.button("Guardar cambios"):
        st.session_state.registro = registro.normalizar(editado)
        st.rerun()

    csv = registro.con_estado(st.session_state.registro, hoy).to_csv(index=False).encode("utf-8")
    xlsx = io.BytesIO()
    registro.con_estado(st.session_state.registro, hoy).to_excel(xlsx, index=False)
    d1, d2 = st.columns(2)
    d1.download_button("⬇️ Descargar CSV", csv, "registro_compromisos.csv", "text/csv")
    d2.download_button("⬇️ Descargar Excel", xlsx.getvalue(), "registro_compromisos.xlsx")
    st.caption("En esta versión el registro vive en tu sesión: descárgalo para no perderlo.")

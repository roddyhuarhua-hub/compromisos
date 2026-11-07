"""Compromisos: de la reunion comunal al seguimiento de compromisos, con IA.

Ejecutar en local:   streamlit run app.py
"""
from __future__ import annotations

import base64
import io
import os
import time
import uuid
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

try:  # .env en local; en Streamlit Cloud se usan los Secrets
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from compromisos import actores, conflictos, ia, laminas_conflictos, panel_imagen, presentacion, registro, visual
from compromisos.modelos import ExtraccionReunion

RAIZ = Path(__file__).parent
EJEMPLO = RAIZ / "datos" / "ejemplo"

COLOR_ESTADO, ICONO_ESTADO = visual.COLOR_ESTADO, visual.ICONO_ESTADO
COMUNIDADES = pd.read_csv(EJEMPLO / "comunidades.csv")

st.set_page_config(page_title="Compromisos · Confluentia", page_icon=str(RAIZ / "img" / "icono_confluentia.png"),
                   layout="wide")
st.logo(str(RAIZ / "img" / "logo_confluentia_horizontal.png"), icon_image=str(RAIZ / "img" / "icono_confluentia.png"),
        size="large", link="https://www.confluentia.pe")
LOGO_BLANCO = base64.b64encode((RAIZ / "img" / "logo_confluentia_blanco.png").read_bytes()).decode()


def cfg(nombre: str, zoom: bool = False) -> dict:
    """Barra del grafico con un solo boton: descargar en PNG de alta resolucion (para PPT o informes)."""
    return {"displaylogo": False, "scrollZoom": zoom, "modeBarButtons": [["toImage"]],
            "toImageButtonOptions": {"format": "png", "filename": f"confluentia_{nombre}", "scale": 3}}


st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stTextInput, .stButton button { font-family: 'Inter', 'Segoe UI', sans-serif; }
.block-container { padding-top: 1.6rem; max-width: 1400px; }
.hero { background: linear-gradient(120deg, #1a3020 0%, #2d4a33 55%, #3f6b4a 100%); color: #fff;
        border-radius: 18px; padding: 24px 210px 26px 30px; margin-bottom: 18px; position: relative; overflow: hidden; }
.hero:after { content: ""; position: absolute; right: -60px; top: -60px; width: 260px; height: 260px;
              border-radius: 50%; background: rgba(255,255,255,0.07); }
.hero h1 { color: #fff; font-size: 30px; font-weight: 700; margin: 0 0 4px 0; padding: 0; }
.hero p { color: rgba(255,255,255,0.88); font-size: 15px; margin: 0; max-width: 820px; }
.hero .marca { position: absolute; right: 34px; top: 50%; transform: translateY(-50%); width: 150px; opacity: 0.95; z-index: 1; }
.hero .por { font-size: 12px; letter-spacing: .08em; text-transform: uppercase; color: rgba(255,255,255,0.75); margin-bottom: 4px; }
@media (max-width: 900px) { .hero .marca { display: none; } .hero { padding-right: 30px; } }
.hero .chips { margin-top: 14px; display: flex; gap: 8px; flex-wrap: wrap; }
.hero .chip { background: rgba(255,255,255,0.14); border: 1px solid rgba(255,255,255,0.25);
              padding: 4px 12px; border-radius: 999px; font-size: 12.5px; }
.kpis { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; margin: 4px 0 16px 0; }
@media (max-width: 900px) { .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.kpi { background: #fff; border: 1px solid rgba(31,42,55,0.08); border-radius: 14px; padding: 14px 16px;
       box-shadow: 0 1px 2px rgba(16,24,40,0.04); border-top: 4px solid var(--c); }
.kpi .lab { font-size: 12.5px; color: #5b6675; font-weight: 500; }
.kpi .val { font-size: 30px; font-weight: 700; color: #1f2a37; line-height: 1.2; margin-top: 2px; }
.kpi .sub { font-size: 12px; color: #5b6675; }
.card { background: #fff; border: 1px solid rgba(31,42,55,0.08); border-radius: 14px; padding: 14px 16px;
        box-shadow: 0 1px 2px rgba(16,24,40,0.04); margin-bottom: 10px; }
.card h4 { margin: 0 0 6px 0; font-size: 15px; color: #1f2a37; }
.alerta { border-left: 4px solid var(--c); padding: 10px 12px; border-radius: 10px; background: #fff;
          border-top: 1px solid rgba(31,42,55,0.06); border-right: 1px solid rgba(31,42,55,0.06);
          border-bottom: 1px solid rgba(31,42,55,0.06); margin-bottom: 8px; }
.alerta .t { font-weight: 600; color: #1f2a37; font-size: 13.5px; }
.alerta .m { font-size: 12px; color: #5b6675; margin-top: 2px; }
.badge { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 11.5px; font-weight: 600;
         color: #1f2a37; background: color-mix(in srgb, var(--c) 18%, white); border: 1px solid var(--c); }
.sem { display: flex; align-items: center; justify-content: space-between; padding: 8px 4px;
       border-bottom: 1px solid rgba(31,42,55,0.06); }
.sem:last-child { border-bottom: none; }
.sem .n { font-weight: 600; color: #1f2a37; font-size: 13.5px; }
.sem .d { font-size: 12px; color: #5b6675; }
.bar { height: 6px; border-radius: 4px; background: rgba(31,42,55,0.07); margin-top: 4px; width: 140px; }
.bar > div { height: 6px; border-radius: 4px; background: var(--c); }
.stTabs [data-baseweb="tab-list"] { gap: 6px; }
.stTabs [data-baseweb="tab"] { font-weight: 600; font-size: 15px; padding: 8px 14px; }
div[data-testid="stPlotlyChart"] { background: #fff; border: 1px solid rgba(31,42,55,0.08); border-radius: 14px;
                                   padding: 6px 8px; box-shadow: 0 1px 2px rgba(16,24,40,0.04); }
</style>
""", unsafe_allow_html=True)


def kpi(lab: str, val: str, sub: str, color: str) -> str:
    return f'<div class="kpi" style="--c:{color}"><div class="lab">{lab}</div><div class="val">{val}</div><div class="sub">{sub}</div></div>'



def cargar_claves() -> None:
    """Copia las claves de Streamlit Secrets al entorno (en local se leen de .env)."""
    for nombre in ("GROQ_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        try:
            if nombre in st.secrets and not os.getenv(nombre):
                os.environ[nombre] = st.secrets[nombre]
        except Exception:
            pass


cargar_claves()


@st.cache_data(show_spinner=False, ttl=7 * 24 * 3600)
def transcribir_cache(nombre: str, datos: bytes, tipo: str) -> str:
    """El mismo audio no se transcribe dos veces (respuesta instantanea)."""
    return ia.transcribir_audio(nombre, datos, tipo)


@st.cache_data(show_spinner=False, ttl=7 * 24 * 3600)
def extraer_cache(texto: str, fecha_iso: str, contexto: str) -> tuple[dict, dict]:
    """El mismo texto no se procesa dos veces. Solo se guardan los resultados exitosos."""
    ext, uso = ia.extraer_compromisos(texto, date.fromisoformat(fecha_iso), contexto)
    return ext.model_dump(mode="json"), uso


def procesar(texto: str, fecha_r: date, contexto: str) -> None:
    """Extrae compromisos con la IA; si falla, la demo sigue con la extraccion guardada."""
    guardada = ExtraccionReunion.model_validate_json(
        (EJEMPLO / "extraccion_reunion_demo.json").read_text(encoding="utf-8"))
    st.session_state.pop("uso", None)
    if ia.proveedor() is None:
        st.session_state.extraccion = guardada
        return
    inicio = time.perf_counter()
    try:
        with st.spinner("La IA está leyendo la reunión…"):
            datos, uso = extraer_cache(texto, fecha_r.isoformat(), contexto)
        st.session_state.extraccion = ExtraccionReunion.model_validate(datos)
        st.session_state.uso = {**uso, "segundos": time.perf_counter() - inicio}
        st.session_state.costo = ia.costo_estimado(st.session_state.get("minutos", 0), uso)
    except Exception as e:
        st.session_state.extraccion = guardada
        st.error(f"La IA no respondió a tiempo ({str(e)[:160]}). Muestro la extracción guardada; "
                 "vuelve a intentar en unos segundos.")


# ---------------------------------------------------------------- estado de sesion
if "registro" not in st.session_state:
    st.session_state.registro = registro.cargar(EJEMPLO / "registro_demo.csv")
if "extraccion" not in st.session_state:
    st.session_state.extraccion = None
if "actores" not in st.session_state:
    st.session_state.actores = actores.normalizar_actores(pd.read_csv(EJEMPLO / "actores_demo.csv"))
    st.session_state.relaciones = actores.normalizar_relaciones(pd.read_csv(EJEMPLO / "relaciones_demo.csv"))
    st.session_state.posturas = actores.normalizar_historial(pd.read_csv(EJEMPLO / "posturas_demo.csv"))
if "conflictos" not in st.session_state:
    st.session_state.conflictos = conflictos.normalizar(pd.read_csv(EJEMPLO / "conflictos_demo.csv"))

# ---------------------------------------------------------------- barra lateral
with st.sidebar:
    st.markdown("## 🤝 Compromisos")
    st.caption("Seguimiento de compromisos sociales con IA, para equipos de relaciones comunitarias. "
               "Un producto de **Confluentia**.")
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
    st.caption("Datos de ejemplo sintéticos: comunidades, empresa y ubicaciones ficticias.")

base_df = registro.con_estado(st.session_state.registro, hoy)
k_total = registro.indicadores(base_df)


@st.cache_data(show_spinner=False, max_entries=20)
def pptx_cache(df, A, R, H, corte, cliente) -> bytes:
    ind_all = visual.indice_comunidades(df, COMUNIDADES)
    return presentacion.generar(df, ind_all, registro.indicadores(df), A, R, H, corte, cliente)


@st.cache_data(show_spinner=False, max_entries=20)
def laminas_cache(df, corte, cliente, filtros) -> tuple[bytes, bytes]:
    """Laminas 4K del panel (una por grafico): devuelve (pptx, zip de PNG)."""
    ind_f = visual.indice_comunidades(df, COMUNIDADES)
    lams = panel_imagen.laminas(df, ind_f, registro.indicadores(df), corte, cliente, filtros)
    return panel_imagen.pptx_laminas(lams), panel_imagen.zip_laminas(lams)


@st.cache_data(show_spinner=False, max_entries=20)
def laminas_conf_cache(conf, df, corte, cliente, filtros) -> tuple[bytes, bytes]:
    """Laminas 4K de conflictividad: devuelve (pptx, zip de PNG)."""
    ind_c = visual.indice_comunidades(df, COMUNIDADES)
    lams = laminas_conflictos.laminas_conflictos(conf, ind_c, COMUNIDADES, corte, cliente, filtros)
    return panel_imagen.pptx_laminas(lams), panel_imagen.zip_laminas(lams)


with st.sidebar:
    st.divider()
    st.markdown("**📥 Llévalo a tu presentación**")
    cliente = st.text_input("Cliente (para la portada)", "Minera Andina S.A.C. (ejemplo)")
    if st.button("Preparar presentación (.pptx)", width="stretch"):
        with st.spinner("Armando las diapositivas…"):
            st.session_state.pptx = pptx_cache(base_df, st.session_state.actores, st.session_state.relaciones,
                                               st.session_state.posturas, hoy, cliente)
    if st.session_state.get("pptx"):
        st.download_button("⬇️ Descargar presentación", st.session_state.pptx, type="primary", width="stretch",
                           file_name=f"confluentia_reporte_{hoy:%Y%m%d}.pptx",
                           mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")
    st.caption("8 diapositivas con la marca Confluentia: resumen, semáforo, estados, vencidos, mapa de actores y "
               "cambios de postura. Los gráficos son editables en PowerPoint. Cada gráfico de la app también se "
               "baja como imagen con el ícono 📷 que aparece al pasar el mouse.")
st.markdown(f"""
<div class="hero">
  <img class="marca" src="data:image/png;base64,{LOGO_BLANCO}" alt="Confluentia">
  <div class="por">Confluentia · Inteligencia social para decisiones estratégicas en territorio</div>
  <h1>🤝 Compromisos</h1>
  <p>De la mesa de diálogo al seguimiento de cada acuerdo. La IA escucha la reunión, extrae quién prometió qué
  y para cuándo, y alerta antes de que un compromiso incumplido se convierta en conflicto.</p>
  <div class="chips">
    <span class="chip">📍 {base_df['comunidad'].nunique()} comunidades</span>
    <span class="chip">🗓️ {base_df['reunion'].nunique()} reuniones</span>
    <span class="chip">📌 {k_total['total']} compromisos</span>
    <span class="chip">🕸️ {len(st.session_state.actores)} actores mapeados</span>
    <span class="chip">🎙️ Whisper + Gemini</span>
    <span class="chip">Corte: {hoy:%d/%m/%Y}</span>
  </div>
</div>
""", unsafe_allow_html=True)

tab_tablero, tab_actores, tab_conflictos, tab_reunion, tab_registro = st.tabs(
    ["📊 Panel ejecutivo", "🕸️ Mapa de actores", "🔥 Conflictividad", "🎙️ Nueva reunión", "📋 Registro y descargas"]
)

# ---------------------------------------------------------------- 1. nueva reunion
with tab_reunion:
    st.subheader("Sube la reunión y la IA extrae los compromisos")
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    nombre = c1.text_input("Nombre de la reunión", "Mesa de trabajo Pucará Alto")
    fecha_r = c2.date_input("Fecha", value=date(2026, 11, 4), format="DD/MM/YYYY")
    comunidad = c3.selectbox("Comunidad", COMUNIDADES["comunidad"].tolist(), index=0, accept_new_options=True)
    distrito_def = COMUNIDADES.set_index("comunidad")["distrito"].get(comunidad, "")
    distrito = c4.text_input("Distrito", distrito_def)

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
                t0 = time.perf_counter()
                st.session_state.texto = transcribir_cache(
                    getattr(fuente_audio, "name", "grabacion.wav"), datos,
                    getattr(fuente_audio, "type", None) or "audio/wav")
                st.session_state.minutos = len(datos) / (16000 * 60)  # aprox. 128 kbps
                s.write(f"✅ Transcrito en {time.perf_counter() - t0:.0f} s. 🧠 Extrayendo compromisos…")
                procesar(st.session_state.texto, fecha_r,
                         f"{nombre}. Comunidad {comunidad}, distrito {distrito}.")
                s.update(label="Reunión procesada", state="complete")
    elif origen == "📄 Foto del acta":
        foto = st.file_uploader("Foto o escaneo del acta", type=["jpg", "jpeg", "png"])
        if foto:
            st.image(foto, width=320)
        if foto and st.button("Leer acta y extraer", type="primary", disabled=not hay_clave):
            with st.spinner("Leyendo el acta…"):
                st.session_state.texto = ia.leer_acta_imagen(foto.getvalue(), foto.type)
                st.session_state.minutos = 0
                procesar(st.session_state.texto, fecha_r,
                         f"{nombre}. Comunidad {comunidad}, distrito {distrito}.")
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
            procesar(texto, fecha_r, f"{nombre}. Comunidad {comunidad}, distrito {distrito}.")

    ext: ExtraccionReunion | None = st.session_state.extraccion
    if ext:
        st.markdown("#### Resumen")
        st.write(ext.resumen)
        if "uso" in st.session_state:
            u = st.session_state.uso
            st.caption(f"✅ Extraído con IA ({u.get('modelo', '')}) en {u.get('segundos', 0):.1f} s · "
                       f"tokens: {u['entrada']:,} de entrada, {u['salida']:,} de salida · "
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

        act_nuevos = pd.DataFrame([a.model_dump() for a in ext.actores],
                                  columns=["nombre", "tipo", "cargo", "organizacion", "comunidad",
                                           "postura", "influencia", "evidencia"])
        rel_nuevas = pd.DataFrame([r.model_dump() for r in ext.relaciones],
                                  columns=["origen", "destino", "tipo", "descripcion"])
        st.markdown(f"#### 🕸️ {len(act_nuevos)} actores y {len(rel_nuevas)} relaciones detectados")
        st.caption("Postura hacia la empresa: −2 opositor … +2 aliado. Influencia: 1 a 5. "
                   "Se suman al Mapa de actores al guardar (si el actor ya existe, se actualiza).")
        act_editados = st.data_editor(
            act_nuevos, num_rows="dynamic", width="stretch", hide_index=True, key="editor_actores",
            column_config={
                "nombre": "Actor", "cargo": "Cargo", "organizacion": "Organización", "comunidad": "Comunidad",
                "tipo": st.column_config.SelectboxColumn("Tipo", options=list(actores.SIMBOLO_TIPO)),
                "postura": st.column_config.NumberColumn("Postura", min_value=-2, max_value=2, step=1),
                "influencia": st.column_config.NumberColumn("Influencia", min_value=1, max_value=5, step=1),
                "evidencia": st.column_config.TextColumn("Evidencia (cita)", width="large"),
            })
        rel_editadas = st.data_editor(
            rel_nuevas, num_rows="dynamic", width="stretch", hide_index=True, key="editor_relaciones",
            column_config={
                "origen": "Actor A", "destino": "Actor B", "descripcion": "Descripción",
                "tipo": st.column_config.SelectboxColumn("Relación", options=list(actores.REL_ESTILO)),
            })

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
            try:
                ext_rev = ExtraccionReunion(
                    resumen=ext.resumen, compromisos=[], temas_pendientes=ext.temas_pendientes,
                    actores=act_editados.dropna(subset=["nombre"]).fillna({"postura": 0, "influencia": 3})
                    .fillna("").to_dict("records"),
                    relaciones=rel_editadas.dropna(subset=["origen", "destino"]).fillna("").to_dict("records"))
            except Exception:
                ext_rev = ext  # si la edicion no es valida, se usa lo que extrajo la IA
            (st.session_state.actores, st.session_state.relaciones,
             st.session_state.posturas) = actores.fusionar(
                st.session_state.actores, st.session_state.relaciones, ext_rev, comunidad,
                fuente=f"{nombre} ({fecha_r:%d/%m/%Y})", historial=st.session_state.posturas,
                fecha=fecha_r, reunion=nombre)
            st.session_state.extraccion = None
            st.session_state.pop("pptx", None)  # la presentacion se vuelve a armar con los datos nuevos
            st.toast("✅ Guardado. El Panel ejecutivo y el Mapa de actores ya lo incluyen.")
            st.rerun()
        b2.download_button(
            "⬇️ Descargar ficha de la reunión (.md)",
            registro.acta_markdown(ext, nombre, fecha_r, comunidad),
            file_name=f"ficha_{fecha_r:%Y%m%d}.md",
        )

# ---------------------------------------------------------------- 2. panel ejecutivo
with tab_tablero:
    df = base_df
    f1, f2, f3 = st.columns(3)
    comunidades_f = f1.multiselect("Comunidad", sorted(df["comunidad"].unique()), placeholder="Todas")
    partes = f2.multiselect("Responsable", ["Empresa", "Estado", "Comunidad", "Otro"], placeholder="Todas")
    temas = f3.multiselect("Tema", sorted(df["tema"].unique()), placeholder="Todos")
    if comunidades_f:
        df = df[df["comunidad"].isin(comunidades_f)]
    if partes:
        df = df[df["responsable"].isin(partes)]
    if temas:
        df = df[df["tema"].isin(temas)]

    k = registro.indicadores(df)
    tasa = k["tasa_cumplimiento"]
    filtros_txt = " · ".join(
        [", ".join(c.replace("C.C. ", "") for c in comunidades_f)] * bool(comunidades_f)
        + [f"Responsable: {', '.join(partes)}"] * bool(partes) + [f"Tema: {', '.join(temas)}"] * bool(temas))
    with st.popover("📥 Llevar este panel a una presentación", width="stretch"):
        st.markdown("**7 láminas en 4K (3840 × 2160)**, una por gráfico y cada una con su mensaje clave: "
                    "resumen, mapa territorial, semáforo, estado, quién incumple, temas y brecha. "
                    "Respetan los filtros que tengas activos.")
        clave_lam = (filtros_txt, hoy, cliente, len(df), int(df["cumplido"].sum()))
        if st.button("Preparar láminas", type="primary", disabled=df.empty):
            with st.spinner("Dibujando las láminas en alta resolución…"):
                st.session_state.laminas = (clave_lam, laminas_cache(df, hoy, cliente, filtros_txt))
        lam = st.session_state.get("laminas")
        if lam and lam[0] == clave_lam:  # solo si corresponden a los filtros actuales
            p1, p2 = st.columns(2)
            p1.download_button("⬇️ PowerPoint (.pptx)", lam[1][0], width="stretch",
                               file_name=f"confluentia_panel_{hoy:%Y%m%d}.pptx",
                               mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")
            p2.download_button("⬇️ Imágenes PNG (.zip)", lam[1][1], width="stretch",
                               file_name=f"confluentia_panel_{hoy:%Y%m%d}.zip", mime="application/zip")
    ind = visual.indice_comunidades(df, COMUNIDADES) if not df.empty else pd.DataFrame()
    criticas = int((ind["semaforo"] == "Crítico").sum()) if not ind.empty else 0
    st.markdown('<div class="kpis">' + "".join([
        kpi("Compromisos registrados", f"{k['total']}", f"{df['reunion'].nunique()} reuniones", "#1c5cab"),
        kpi("🔴 Vencidos sin cumplir", f"{k['vencidos']}", "requieren acción inmediata", COLOR_ESTADO["Vencido"]),
        kpi(f"🟡 Vencen en {registro.DIAS_ALERTA} días", f"{k['por_vencer']}", "programar seguimiento", COLOR_ESTADO["Por vencer"]),
        kpi("✅ Tasa de cumplimiento", f"{tasa:.0%}" if tasa is not None else "–", "de los ya exigibles", COLOR_ESTADO["Cumplido"]),
        kpi("⚠️ Comunidades en estado crítico", f"{criticas}", f"{k['alto_riesgo_abiertos']} compromisos de riesgo alto abiertos", "#a32424"),
    ]) + "</div>", unsafe_allow_html=True)

    if df.empty:
        st.info("No hay compromisos con estos filtros.")
    else:
        # --- mapa + semaforo
        reuniones = (df.groupby(["reunion", "fecha_reunion", "comunidad"]).size()
                     .reset_index(name="compromisos").merge(COMUNIDADES, on="comunidad", how="left"))
        rng = np.random.default_rng(7)  # dispersion leve para que el calor no sea un punto
        reuniones["lat"] = reuniones["lat"] + rng.normal(0, 0.012, len(reuniones))
        reuniones["lon"] = reuniones["lon"] + rng.normal(0, 0.012, len(reuniones))
        c1, c2 = st.columns([1.75, 1])
        with c1:
            st.markdown("#### 🗺️ Mapa de calor de reuniones y semáforo por comunidad")
            fondo = st.segmented_control("Fondo del mapa", list(visual.FONDOS), default="🛰️ Satélite",
                                         label_visibility="collapsed") or "🛰️ Satélite"
            st.plotly_chart(visual.mapa(ind, reuniones, fondo=fondo), width="stretch",
                            config=cfg("mapa_comunidades", zoom=True))
            st.caption("Halo: intensidad de reuniones. Círculos: comunidades, coloreadas por índice de riesgo; "
                       "el tamaño crece con los compromisos vencidos. Usa la rueda del mouse para acercar.")
        with c2:
            st.markdown("#### 🚦 Semáforo social")
            filas = []
            for _, r in ind.iterrows():
                col = visual.SEMAFORO[r["semaforo"]]
                filas.append(
                    f'<div class="sem"><div><div class="n">{r["comunidad"].replace("C.C. ", "")}</div>'
                    f'<div class="d">{int(r["vencidos"])} vencidos · {int(r["reuniones"])} reuniones · '
                    f'cumple {r["cumplimiento"]:.0%}</div>'
                    f'<div class="bar"><div style="width:{max(4, r["indice"])}%; --c:{col}"></div></div></div>'
                    f'<span class="badge" style="--c:{col}">{r["semaforo"]} · {r["indice"]:.0f}</span></div>')
            st.markdown('<div class="card">' + "".join(filas) + "</div>", unsafe_allow_html=True)
            st.markdown("##### Cumplimiento global")
            st.plotly_chart(visual.gauge(tasa, 200), width="stretch", config=cfg("cumplimiento"))

        # --- alertas + estados
        c3, c4 = st.columns([1.2, 1])
        with c3:
            st.markdown("#### 🔔 Alertas: atender primero")
            alertas = df[df["estado"].isin(["Vencido", "Por vencer"])].copy()
            alertas["peso"] = alertas["riesgo_conflicto"].map(visual.PESO_RIESGO)
            alertas["cercania"] = alertas["dias_restantes"].abs()  # lo recien vencido o por vencer primero
            alertas = alertas.sort_values(["peso", "cercania"], ascending=[False, True]).head(6)
            html = []
            for _, r in alertas.iterrows():
                col = COLOR_ESTADO[r["estado"]]
                dias = int(r["dias_restantes"])
                cuando = f"{-dias} días de atraso" if dias < 0 else f"vence en {dias} días"
                html.append(
                    f'<div class="alerta" style="--c:{col}"><div class="t">{ICONO_ESTADO[r["estado"]]} {r["descripcion"]}</div>'
                    f'<div class="m">{r["comunidad"]} · {r["responsable"]} ({r["responsable_detalle"] or "-"}) · '
                    f'<b>{cuando}</b> · riesgo {r["riesgo_conflicto"]}</div></div>')
            st.markdown("".join(html) or "Sin alertas 🎉", unsafe_allow_html=True)
        with c4:
            st.markdown("#### Estado de los compromisos")
            st.plotly_chart(visual.dona_estados(df, registro.ORDEN_ESTADO), width="stretch",
                            config=cfg("estados"))

        # --- calendario
        st.plotly_chart(visual.calendario(df, hoy), width="stretch", config=cfg("calendario_vencimientos"))

        # --- analisis
        c5, c6 = st.columns(2)
        c5.plotly_chart(visual.calor_tema(df), width="stretch", config=cfg("temas_por_comunidad"))
        c6.plotly_chart(visual.quien_incumple(df, registro.ORDEN_ESTADO), width="stretch",
                        config=cfg("quien_incumple"))
        st.plotly_chart(visual.brecha(df, hoy), width="stretch", config=cfg("brecha_cumplimiento"))

# ---------------------------------------------------------------- 2b. mapa de actores
with tab_actores:
    A, R, H = st.session_state.actores, st.session_state.relaciones, st.session_state.posturas
    st.markdown("Cada reunión que procesa la IA alimenta este mapa: **quién es quién** en cada comunidad, "
                "su postura hacia la empresa, su influencia y **cómo se relacionan** entre caseríos y comunidades. "
                "Como las posturas cambian, cada reunión deja una *foto* fechada: mueve la línea de tiempo para "
                "ver el mapa como estaba en otro momento.")
    fechas_h = sorted(set(H["fecha"]) | {hoy})
    corte = st.select_slider("📅 Ver el mapa a la fecha", options=fechas_h, value=fechas_h[-1],
                             format_func=lambda d: d.strftime("%d/%m/%Y"), key="act_corte")
    A = actores.al_corte(A, H, corte)
    g1, g2, g3 = st.columns([1.4, 1.2, 1])
    coms_a = sorted(c for c in A["comunidad"].unique() if c)
    sel_coms = g1.multiselect("Comunidades", coms_a, placeholder="Todas", key="act_com")
    sel_tipos = g2.multiselect("Tipo de actor", list(actores.SIMBOLO_TIPO), placeholder="Todos", key="act_tipo")
    externos = g3.toggle("Incluir Estado, empresa y sociedad civil", value=True)
    A_f = A.copy()
    if sel_coms:
        A_f = A_f[A_f["comunidad"].isin(sel_coms) | ((A_f["comunidad"] == "") & externos)]
    elif not externos:
        A_f = A_f[A_f["comunidad"] != ""]
    if sel_tipos:
        A_f = A_f[A_f["tipo"].isin(sel_tipos)]
    nombres = set(A_f["nombre"])
    R_f = R[R["origen"].isin(nombres) & R["destino"].isin(nombres)]
    G = actores.red(A_f, R_f)
    M = actores.metricas(G)

    if M.empty:
        st.info("No hay actores con estos filtros.")
    else:
        opositores = int((M["postura"] < 0).sum())
        aliados = int((M["postura"] > 0).sum())
        puentes = M[M["puente"] & (M["intermediacion"] > 0.05)]
        n_conflictos = int((R_f["tipo"] == "Conflicto").sum())
        hace_6m = (pd.Timestamp(corte) - pd.DateOffset(months=6)).date()
        mov = actores.cambios(H[H["nombre"].isin(M["nombre"])], hace_6m, corte)
        st.markdown('<div class="kpis">' + "".join([
            kpi("Actores mapeados", f"{len(M)}", f"{len(R_f)} relaciones", "#1c5cab"),
            kpi("🔵 Aliados o favorables", f"{aliados}", f"{aliados / len(M):.0%} del total", "#1c5cab"),
            kpi("🟠 Críticos u opositores", f"{opositores}",
                f"{int(((M['postura'] < 0) & (M['influencia'] >= 4)).sum())} con alta influencia", "#c2410c"),
            kpi("🔗 Actores puente", f"{len(puentes)}", "conectan comunidades distintas", "#1f2a37"),
            kpi("↘️ Se alejaron (6 meses)", f"{int((mov['delta'] < 0).sum())}",
                f"{int((mov['delta'] > 0).sum())} se acercaron · {n_conflictos} relaciones en conflicto", "#d03b3b"),
        ]) + "</div>", unsafe_allow_html=True)

        c1, c2 = st.columns([1.75, 1])
        with c1:
            st.markdown("#### 🕸️ Red de relaciones e influencias")
            foco = st.selectbox("Resaltar un actor y sus vínculos", ["(ninguno)"] + M["nombre"].tolist(),
                                key="act_foco")
            st.plotly_chart(actores.figura_red(G, M, resaltar=None if foco == "(ninguno)" else foco),
                            width="stretch", config=cfg("red_actores", zoom=True))
            st.caption("Color: postura hacia la empresa. Tamaño: influencia. Forma: ● comunidad, ■ Estado/autoridad, "
                       "◆ empresa, ▲ ONG/iglesia/medios. Borde oscuro: actor puente. Cada grupo es una comunidad.")
        with c2:
            st.markdown("#### ⭐ Actores clave de la red")
            st.caption("Intermediación: qué tanto pasa por este actor la comunicación entre los demás "
                       "(si se cae o cambia de postura, la red se reconfigura).")
            filas = []
            for _, r in M.head(8).iterrows():
                col = actores.POSTURA_COLOR[int(r["postura"])]
                ancho = max(4, int(100 * r["intermediacion"] / max(M["intermediacion"].max(), 1e-9)))
                filas.append(
                    f'<div class="sem"><div><div class="n">{r["nombre"]}</div>'
                    f'<div class="d">{r["cargo"] or r["tipo"]} · {(r["comunidad"] or "externo").replace("C.C. ", "")}'
                    f' · {r["vinculos"]} vínculos{" · 🔗 puente" if r["puente"] else ""}</div>'
                    f'<div class="bar"><div style="width:{ancho}%;--c:{col}"></div></div></div>'
                    f'<span class="badge" style="background:{col}">{r["postura_txt"]}</span></div>')
            st.markdown("".join(filas), unsafe_allow_html=True)

        c3, c4 = st.columns(2)
        with c3:
            st.markdown("#### 🎯 Matriz poder – postura")
            st.plotly_chart(actores.matriz_poder_interes(M), width="stretch", config=cfg("matriz_poder_postura"))
            criticos = M[(M["postura"] < 0) & (M["influencia"] >= 4)].sort_values(
                ["influencia", "postura", "vinculos"], ascending=[False, True, False]).head(6)
            if not criticos.empty:
                st.warning("**Gestionar de cerca:** " + ", ".join(
                    f"{r['nombre']} ({(r['comunidad'] or r['organizacion']).replace('C.C. ', '')})"
                    for _, r in criticos.iterrows()))
        with c4:
            st.markdown("#### ⚖️ Balance de posturas por comunidad")
            if (M["comunidad"] != "").any():
                st.plotly_chart(actores.balance_comunidades(M), width="stretch", config=cfg("balance_posturas"))
            st.markdown("#### 🔗 Relaciones entre comunidades")
            com_de = A.set_index("nombre")["comunidad"]
            inter = R_f.assign(c_o=R_f["origen"].map(com_de), c_d=R_f["destino"].map(com_de))
            inter = inter[(inter["c_o"] != "") & (inter["c_d"] != "") & (inter["c_o"] != inter["c_d"])]
            if inter.empty:
                st.caption("Sin relaciones registradas entre comunidades con estos filtros.")
            else:
                st.dataframe(
                    inter.assign(Entre=inter["c_o"].str.replace("C.C. ", "") + " ↔ " + inter["c_d"].str.replace("C.C. ", ""))
                    [["Entre", "tipo", "descripcion"]].rename(columns={"tipo": "Relación", "descripcion": "Detalle"}),
                    hide_index=True, width="stretch")

    # ------------------------------------------------ dinamica: cambios de postura
    st.markdown("### ⏳ Dinámica de posturas en el territorio")
    d1, d2 = st.columns([1, 2.2])
    periodo = d1.radio("Comparar contra", ["3 meses atrás", "6 meses atrás", "1 año atrás", "Primer registro"],
                       index=1, key="act_periodo")
    meses = {"3 meses atrás": 3, "6 meses atrás": 6, "1 año atrás": 12}.get(periodo)
    desde = (pd.Timestamp(corte) - pd.DateOffset(months=meses)).date() if meses else min(H["fecha"])
    Hf = H[H["nombre"].isin(A["nombre"])]
    if sel_coms:
        Hf = Hf[Hf["nombre"].isin(A_f["nombre"])]
    cam = actores.cambios(Hf, desde, corte)
    alejan, acercan = cam[cam["delta"] < 0], cam[cam["delta"] > 0]
    d1.markdown(
        f'<div class="kpis" style="grid-template-columns:1fr 1fr">'
        + kpi("↘️ Se alejan", f"{len(alejan)}", f"{int((alejan['influencia'] >= 4).sum())} con alta influencia", "#c2410c")
        + kpi("↗️ Se acercan", f"{len(acercan)}", "oportunidad de alianza", "#1c5cab") + "</div>",
        unsafe_allow_html=True)
    if not alejan.empty:
        r = alejan.iloc[0]
        d1.error(f"**Alerta temprana:** {r['nombre']} pasó de *{actores.POSTURA_TXT[r['antes']]}* a "
                 f"*{actores.POSTURA_TXT[r['ahora']]}* ({r['fecha_cambio']:%d/%m/%Y}, {r['reunion']}). "
                 f"“{r['evidencia']}”")
    with d2:
        st.markdown(f"#### Quién cambió de postura desde el {desde:%d/%m/%Y}")
        if cam.empty:
            st.info("Nadie cambió de postura en este periodo.")
        else:
            st.plotly_chart(actores.figura_cambios(cam.head(14)), width="stretch", config=cfg("cambios_postura"))
            st.caption("○ postura antes → ● postura ahora. Naranja: se aleja de la empresa; azul: se acerca. "
                       "Ordenado por riesgo (cuánto se movió × su influencia). Pasa el mouse para ver la evidencia.")
    st.markdown("#### 📈 Trayectoria de cada actor, reunión tras reunión")
    # por defecto: los actores influyentes con la historia mas movida (mas posturas distintas)
    mov_h = (Hf[Hf["fecha"] <= corte].groupby("nombre")
             .agg(n=("postura", "nunique"), inf=("influencia", "max"), reg=("postura", "size")))
    mov_h = mov_h[mov_h["reg"] >= 3].assign(score=lambda d: d["n"] * d["inf"]).sort_values("score", ascending=False)
    por_defecto = mov_h.index[:4].tolist() or cam["nombre"].head(4).tolist()
    elegidos = st.multiselect("Actores a seguir", sorted(H["nombre"].unique()), default=por_defecto,
                              key="act_tray", max_selections=6)
    if elegidos:
        st.plotly_chart(actores.figura_trayectorias(H[H["fecha"] <= corte], elegidos), width="stretch",
                        config=cfg("trayectorias_actores"))
    if not cam.empty:
        st.dataframe(
            cam.assign(antes=cam["antes"].map(actores.POSTURA_TXT), ahora=cam["ahora"].map(actores.POSTURA_TXT),
                       comunidad=cam["comunidad"].str.replace("C.C. ", ""))
            [["nombre", "comunidad", "antes", "ahora", "fecha_cambio", "reunion", "evidencia"]]
            .rename(columns={"nombre": "Actor", "comunidad": "Comunidad", "antes": "Antes", "ahora": "Ahora",
                             "fecha_cambio": "Cambió el", "reunion": "Reunión", "evidencia": "Evidencia"}),
            hide_index=True, width="stretch",
            column_config={"Cambió el": st.column_config.DateColumn(format="DD/MM/YYYY")})

    with st.expander("📝 Editar y descargar el mapa de actores"):
        e1, e2 = st.columns(2)
        A_ed = e1.data_editor(st.session_state.actores, num_rows="dynamic", hide_index=True, width="stretch", key="ed_actores")
        R_ed = e2.data_editor(R, num_rows="dynamic", hide_index=True, width="stretch", key="ed_relaciones")
        b1, b2, b3 = st.columns(3)
        if b1.button("Guardar cambios del mapa"):
            st.session_state.actores = actores.normalizar_actores(A_ed)
            st.session_state.relaciones = actores.normalizar_relaciones(R_ed)
            st.rerun()
        b2.download_button("⬇️ Actores (CSV)", st.session_state.actores.to_csv(index=False).encode("utf-8"), "actores.csv", "text/csv")
        b3.download_button("⬇️ Relaciones (CSV)", R.to_csv(index=False).encode("utf-8"), "relaciones.csv", "text/csv")
        st.download_button("⬇️ Historial de posturas (CSV)", H.to_csv(index=False).encode("utf-8"),
                           "historial_posturas.csv", "text/csv")

# ---------------------------------------------------------------- 2c. conflictividad
with tab_conflictos:
    C = st.session_state.conflictos
    st.markdown("La memoria del territorio: **paralizaciones, bloqueos de vías, tomas y otras manifestaciones** "
                "contra la empresa, con el lugar exacto donde ocurrieron, quién convocó, qué exigían y cómo terminó. "
                "Sirve para anticipar: los conflictos suelen repetirse en los mismos lugares y por las mismas demandas.")
    if C.empty:
        st.info("Aún no hay eventos registrados. Agrégalos abajo, en **Registrar un evento**.")
    else:
        anios = sorted({f.year for f in C["fecha"]})
        h1, h2, h3 = st.columns([1.3, 1.4, 1.3])
        rango = h1.slider("Años", anios[0], max(anios[-1], anios[0] + 1), (anios[0], anios[-1]), key="conf_anios") \
            if len(anios) > 1 else (anios[0], anios[0])
        tipos_f = h2.multiselect("Tipo de medida", list(conflictos.TIPO_COLOR), placeholder="Todas", key="conf_tipo")
        coms_f = h3.multiselect("Comunidad", sorted(c for c in C["comunidad"].unique() if c), placeholder="Todas",
                                key="conf_com")
        Cf = C[C["fecha"].map(lambda f: rango[0] <= f.year <= rango[1])]
        if tipos_f:
            Cf = Cf[Cf["tipo"].isin(tipos_f)]
        if coms_f:
            Cf = Cf[Cf["comunidad"].isin(coms_f)]
        kc = conflictos.indicadores(Cf, hoy)
        st.markdown('<div class="kpis">' + "".join([
            kpi("Eventos registrados", f"{kc['eventos']}", f"{kc['medidas_fuerza']} medidas de fuerza", "#2d4a33"),
            kpi("⏱️ Días de paralización", f"{kc['dias_paralizacion']}", "bloqueos, paros y tomas", "#a32424"),
            kpi("🚧 Bloqueos de vía", f"{kc['bloqueos']}", "tránsito y operación afectados", "#c2410c"),
            kpi("⚠️ Con violencia", f"{kc['con_violencia']}", "heridos, detenidos o daños", "#111827"),
            kpi("📅 Último evento", f"{kc['dias_desde_ultimo']} días" if kc["ultimo"] else "–",
                f"{kc['ultimo']:%d/%m/%Y}" + (f" · {kc['en_curso']} en curso" if kc["en_curso"] else "")
                if kc["ultimo"] else "", "#eda100"),
        ]) + "</div>", unsafe_allow_html=True)

        filtros_c = " · ".join([f"{rango[0]}–{rango[1]}"] + [", ".join(tipos_f)] * bool(tipos_f)
                               + [", ".join(c.replace("C.C. ", "") for c in coms_f)] * bool(coms_f))
        with st.popover("📥 Bajar estos gráficos para una presentación", width="stretch"):
            st.markdown("**7 láminas en 4K (3840 × 2160)**, una por gráfico y cada una con su mensaje clave: "
                        "resumen, mapa de conflictos, cronología, eventos por año, días de paralización, motivos e "
                        "incumplimiento vs. conflicto. Respetan los filtros activos.")
            clave_c = (filtros_c, hoy, cliente, len(Cf), int(Cf["duracion_dias"].sum()) if not Cf.empty else 0)
            if st.button("Preparar láminas", type="primary", disabled=Cf.empty, key="btn_lam_conf"):
                with st.spinner("Dibujando las láminas en alta resolución…"):
                    st.session_state.laminas_conf = (clave_c, laminas_conf_cache(Cf, base_df, hoy, cliente,
                                                                                filtros_c))
            lc = st.session_state.get("laminas_conf")
            if lc and lc[0] == clave_c:
                q1, q2 = st.columns(2)
                q1.download_button("⬇️ PowerPoint (.pptx)", lc[1][0], width="stretch",
                                   file_name=f"confluentia_conflictividad_{hoy:%Y%m%d}.pptx", key="dl_conf_pptx",
                                   mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")
                q2.download_button("⬇️ Imágenes PNG (.zip)", lc[1][1], width="stretch", key="dl_conf_zip",
                                   file_name=f"confluentia_conflictividad_{hoy:%Y%m%d}.zip", mime="application/zip")
            st.caption("Cada gráfico de esta pestaña también se baja suelto con el ícono 📷 al pasar el mouse.")

        if Cf.empty:
            st.info("No hay eventos con estos filtros.")
        else:
            m1, m2 = st.columns([1.75, 1])
            with m1:
                st.markdown("#### 📍 Dónde ocurrieron")
                fondo_c = st.segmented_control("Fondo", list(visual.FONDOS), default="🛰️ Satélite",
                                               label_visibility="collapsed", key="conf_fondo") or "🛰️ Satélite"
                st.plotly_chart(conflictos.mapa(Cf, COMUNIDADES, fondo_c), width="stretch",
                                config=cfg("mapa_conflictos", zoom=True))
                st.caption("Calor: lugares con más días de paralización. Cada punto es un evento, coloreado por tipo; "
                           "el tamaño crece con la duración. Pasa el mouse para ver quién convocó y qué exigían.")
            with m2:
                st.markdown("#### 🕑 Eventos más recientes")
                tarjetas = []
                for _, r in Cf.head(6).iterrows():
                    col = conflictos.TIPO_COLOR.get(r["tipo"], "#8a8984")
                    extra = " · ⚠️ violencia" if r["hubo_violencia"] else ""
                    tarjetas.append(
                        f'<div class="alerta" style="--c:{col}"><div class="t">{r["titulo"]}</div>'
                        f'<div class="m">{r["fecha"]:%d/%m/%Y} · {r["tipo"]} · {r["lugar"] or r["comunidad"]}</div>'
                        f'<div class="m">{r["duracion_dias"]} días · {r["desenlace"] or "sin desenlace"}{extra}</div>'
                        f'</div>')
                st.markdown("".join(tarjetas), unsafe_allow_html=True)
                lugares = Cf[Cf["lugar"] != ""].groupby("lugar").agg(n=("tipo", "count"),
                                                                     dias=("duracion_dias", "sum"))
                lugares = lugares[lugares["n"] >= 2].sort_values(["n", "dias"], ascending=False)
                if not lugares.empty:
                    st.warning("**Puntos calientes que se repiten:** " + "; ".join(
                        f"{l} ({r.n} eventos, {r.dias} días)" for l, r in lugares.head(3).iterrows()))

            st.markdown("#### 📜 Cronología del conflicto por comunidad")
            st.plotly_chart(conflictos.cronologia(Cf), width="stretch", config=cfg("cronologia_conflictos"))
            st.caption("Tamaño: duración de la medida. Borde negro: hubo violencia.")

            a1, a2 = st.columns(2)
            with a1:
                st.markdown("#### 📈 Eventos por año")
                st.plotly_chart(conflictos.por_anio(Cf), width="stretch", config=cfg("conflictos_por_anio"))
            with a2:
                st.markdown("#### ⏱️ Días de paralización por comunidad")
                if Cf["tipo"].isin(conflictos.DE_FUERZA).any():
                    st.plotly_chart(conflictos.dias_por_comunidad(Cf), width="stretch",
                                    config=cfg("dias_paralizacion"))
                else:
                    st.caption("Sin medidas de fuerza con estos filtros.")
            a3, a4 = st.columns(2)
            with a3:
                st.markdown("#### 🎯 ¿Por qué protestan?")
                st.plotly_chart(conflictos.motivos(Cf), width="stretch", config=cfg("motivos_conflicto"))
            with a4:
                st.markdown("#### 🔗 Incumplimiento y conflicto")
                desde_c = date(hoy.year - 3, hoy.month, 1)
                ind_c = visual.indice_comunidades(base_df, COMUNIDADES)
                st.plotly_chart(conflictos.relacion_compromisos(C, ind_c, desde_c), width="stretch",
                                config=cfg("incumplimiento_y_conflicto"))
                st.caption(f"Cada punto es una comunidad: compromisos vencidos hoy vs. eventos de conflicto desde "
                           f"{desde_c:%Y}. El tamaño crece con los días de paralización.")

    # ------------------------------------------------ registrar eventos
    with st.expander("➕ Registrar un evento", expanded=C.empty):
        modo = st.radio("¿Cómo lo registras?", ["📰 Pegar una noticia o reporte (la IA lo ordena)",
                                                "✍️ Llenar un formulario"], horizontal=True, key="conf_modo")
        if modo.startswith("📰"):
            noticia = st.text_area("Pega la noticia, el reporte de la Defensoría o tu informe de campo", height=160,
                                   key="conf_texto",
                                   placeholder="Ej.: Desde el lunes comuneros de Llacctapampa bloquean el puente "
                                               "Ccollpa exigiendo el cumplimiento del acta…")
            n1, n2 = st.columns([1, 1])
            com_def = n1.selectbox("Comunidad por defecto", [""] + COMUNIDADES["comunidad"].tolist(),
                                   key="conf_com_def")
            if n2.button("🧠 Extraer eventos", type="primary", disabled=not (hay_clave and noticia.strip())):
                with st.spinner("Leyendo el texto…"):
                    try:
                        ext_e, _ = ia.extraer_eventos(noticia, hoy, f"Comunidades de la zona: "
                                                      f"{', '.join(COMUNIDADES['comunidad'])}")
                        st.session_state.eventos_nuevos = conflictos.desde_extraccion(ext_e, COMUNIDADES, com_def)
                    except Exception as e:  # noqa: BLE001
                        st.error(f"No se pudo extraer: {str(e)[:200]}")
            if not hay_clave:
                st.caption("Necesita una clave de IA configurada; mientras tanto usa el formulario.")
        else:
            with st.form("form_evento", clear_on_submit=True):
                f1, f2, f3 = st.columns(3)
                fe = f1.date_input("Fecha", value=hoy, format="DD/MM/YYYY")
                ti = f2.selectbox("Tipo de medida", list(conflictos.TIPO_COLOR))
                co = f3.selectbox("Comunidad", COMUNIDADES["comunidad"].tolist())
                tt = st.text_input("Qué pasó (título)", placeholder="Bloqueo del puente Ccollpa")
                g1, g2 = st.columns(2)
                lu = g1.text_input("Lugar exacto", placeholder="Puente Ccollpa, km 12")
                cv = g2.text_input("Quién convocó", placeholder="Frente de Defensa…")
                de = st.text_input("Qué exigían")
                g3, g4, g5, g6 = st.columns(4)
                du = g3.number_input("Duración (días)", 0, 365, 1)
                pa = g4.number_input("Participantes aprox.", 0, 100000, 100, step=50)
                vi = g5.checkbox("Hubo violencia")
                ds = g6.selectbox("Desenlace", ["Mesa de diálogo", "Acta de acuerdos", "Levantamiento sin acuerdo",
                                                "Intervención policial", "Declaratoria de emergencia", "En curso",
                                                "Otro"])
                tema_ev = st.selectbox("Tema", ["Agua", "Empleo local", "Salud", "Educación", "Infraestructura",
                                                "Tierras", "Ambiente", "Proyectos productivos", "Monitoreo",
                                                "Comunicación", "Otro"])
                if st.form_submit_button("Agregar a la revisión", type="primary") and tt:
                    lat0, lon0 = COMUNIDADES.set_index("comunidad").loc[co, ["lat", "lon"]]
                    st.session_state.eventos_nuevos = conflictos.normalizar(pd.DataFrame([dict(
                        fecha=fe, tipo=ti, titulo=tt, lugar=lu, comunidad=co, lat=lat0, lon=lon0, convocantes=cv,
                        demanda=de, tema=tema_ev, duracion_dias=du, participantes=pa, intensidad="media",
                        hubo_violencia=vi, desenlace=ds, fuente="registro manual")]))

        nuevos_ev = st.session_state.get("eventos_nuevos")
        if nuevos_ev is not None:
            if nuevos_ev.empty:
                st.info("La IA no encontró hechos de conflicto en ese texto.")
            else:
                st.markdown(f"**{len(nuevos_ev)} evento(s) para revisar.** Corrige la ubicación (lat/lon) si "
                            "conoces el punto exacto.")
                rev = st.data_editor(nuevos_ev, num_rows="dynamic", hide_index=True, width="stretch",
                                     key="ed_eventos_nuevos",
                                     column_config={"fecha": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                                    "tipo": st.column_config.SelectboxColumn(
                                                        options=list(conflictos.TIPO_COLOR))})
                if st.button("✅ Guardar en el historial", type="primary"):
                    st.session_state.conflictos = conflictos.normalizar(
                        pd.concat([st.session_state.conflictos, rev], ignore_index=True))
                    st.session_state.eventos_nuevos = None
                    st.toast("✅ Evento guardado: ya aparece en el mapa y la cronología.")
                    st.rerun()

    with st.expander("📝 Editar, cargar o descargar el historial"):
        C_ed = st.data_editor(C, num_rows="dynamic", hide_index=True, width="stretch", key="ed_conflictos",
                              column_config={"fecha": st.column_config.DateColumn(format="DD/MM/YYYY")})
        e1, e2, e3 = st.columns(3)
        if e1.button("Guardar cambios del historial"):
            st.session_state.conflictos = conflictos.normalizar(C_ed)
            st.rerun()
        e2.download_button("⬇️ Historial (CSV)", C.to_csv(index=False).encode("utf-8"), "conflictos.csv", "text/csv")
        sub_c = e3.file_uploader("Cargar historial (CSV)", type=["csv"], key="csv_conflictos",
                                 label_visibility="collapsed")
        if sub_c is not None and st.button("Usar este historial"):
            st.session_state.conflictos = conflictos.normalizar(pd.read_csv(sub_c))
            st.rerun()
        st.caption("Columnas: " + ", ".join(conflictos.COLUMNAS) + ". Puedes cargar tu propia base, por ejemplo la "
                   "que armes a partir de los reportes mensuales de la Defensoría del Pueblo.")

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

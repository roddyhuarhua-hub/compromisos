"""Compromisos: de la reunion comunal al seguimiento de compromisos, con IA.

Ejecutar en local:   streamlit run app.py
"""
from __future__ import annotations

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

from compromisos import ia, registro, visual
from compromisos.modelos import ExtraccionReunion

RAIZ = Path(__file__).parent
EJEMPLO = RAIZ / "datos" / "ejemplo"

COLOR_ESTADO, ICONO_ESTADO = visual.COLOR_ESTADO, visual.ICONO_ESTADO
COMUNIDADES = pd.read_csv(EJEMPLO / "comunidades.csv")

st.set_page_config(page_title="Compromisos · seguimiento social con IA", page_icon="🤝", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stTextInput, .stButton button { font-family: 'Inter', 'Segoe UI', sans-serif; }
.block-container { padding-top: 1.6rem; max-width: 1400px; }
.hero { background: linear-gradient(120deg, #0d366b 0%, #1c5cab 55%, #2a78d6 100%); color: #fff;
        border-radius: 18px; padding: 26px 30px; margin-bottom: 18px; position: relative; overflow: hidden; }
.hero:after { content: ""; position: absolute; right: -60px; top: -60px; width: 260px; height: 260px;
              border-radius: 50%; background: rgba(255,255,255,0.07); }
.hero h1 { color: #fff; font-size: 30px; font-weight: 700; margin: 0 0 4px 0; padding: 0; }
.hero p { color: rgba(255,255,255,0.88); font-size: 15px; margin: 0; max-width: 820px; }
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

# ---------------------------------------------------------------- barra lateral
with st.sidebar:
    st.markdown("## 🤝 Compromisos")
    st.caption("Seguimiento de compromisos sociales con IA, para equipos de relaciones comunitarias.")
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
st.markdown(f"""
<div class="hero">
  <h1>🤝 Compromisos</h1>
  <p>De la mesa de diálogo al seguimiento de cada acuerdo. La IA escucha la reunión, extrae quién prometió qué
  y para cuándo, y alerta antes de que un compromiso incumplido se convierta en conflicto.</p>
  <div class="chips">
    <span class="chip">📍 {base_df['comunidad'].nunique()} comunidades</span>
    <span class="chip">🗓️ {base_df['reunion'].nunique()} reuniones</span>
    <span class="chip">📌 {k_total['total']} compromisos</span>
    <span class="chip">🎙️ Whisper + Gemini</span>
    <span class="chip">Corte: {hoy:%d/%m/%Y}</span>
  </div>
</div>
""", unsafe_allow_html=True)

tab_tablero, tab_reunion, tab_registro = st.tabs(
    ["📊 Panel ejecutivo", "🎙️ Nueva reunión", "📋 Registro y descargas"]
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
            st.toast("✅ Guardado. Mira el Panel ejecutivo: el mapa y las alertas ya lo incluyen.")
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
            st.plotly_chart(visual.mapa(ind, reuniones), width="stretch",
                            config={"scrollZoom": True, "displayModeBar": False})
            st.caption("Azul: intensidad de reuniones. Círculos: comunidades, coloreadas por índice de riesgo; "
                       "el tamaño crece con los compromisos vencidos.")
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
            st.plotly_chart(visual.gauge(tasa, 200), width="stretch", config={"displayModeBar": False})

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
                            config={"displayModeBar": False})

        # --- calendario
        st.plotly_chart(visual.calendario(df, hoy), width="stretch", config={"displayModeBar": False})

        # --- analisis
        c5, c6 = st.columns(2)
        c5.plotly_chart(visual.calor_tema(df), width="stretch", config={"displayModeBar": False})
        c6.plotly_chart(visual.quien_incumple(df, registro.ORDEN_ESTADO), width="stretch",
                        config={"displayModeBar": False})
        st.plotly_chart(visual.brecha(df, hoy), width="stretch", config={"displayModeBar": False})

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

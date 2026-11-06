# 🤝 Compromisos

**Demo:** https://compromisos-roddy.streamlit.app · **Video de respaldo:** _pendiente_

> Proyecto final de la Diplomatura Q-Lab PUCP · Data Science con Python ([issue #204](https://github.com/d2cml-ai/Data-Science-Python/issues/204)).

## 1. One-liner

**Hacemos el seguimiento de los compromisos sociales para los equipos de relaciones comunitarias de minería, hidrocarburos y energía, mediante IA que transcribe cada reunión con la comunidad y convierte lo prometido en un registro con plazos y alertas.**

## 2. Founder

**Roddy Huarhua.** Historiador, con dos tesis sobre conflictos socioambientales en el Perú. Trabajo en relaciones comunitarias para empresas privadas y dirijo la consultora [Confluentia](https://www.confluentia.pe). Portafolio: [roddyhuarhua-hub.github.io](https://roddyhuarhua-hub.github.io).

He estado en las mesas donde se firman los compromisos y he visto qué pasa después: el acta queda en un archivador, el Excel lo actualiza una sola persona, y cuando esa persona rota, nadie sabe qué se prometió. Conozco el vocabulario (ANA, monitoreo participativo, padrón comunal, presupuesto participativo) y tengo acceso directo a los usuarios.

## 3. Problema

**Quién lo sufre.** Los equipos de relaciones comunitarias (relacionistas de campo y jefes de asuntos sociales) de empresas extractivas y de energía, y las consultoras que los apoyan. Del otro lado, las comunidades que esperan que se cumpla lo pactado.

**Qué cuesta.** Un compromiso incumplido u olvidado (un monitoreo de agua, un porcentaje de empleo local) es uno de los detonantes más frecuentes de la reactivación de conflictos que reporta mensualmente la Defensoría del Pueblo (ver mi [dashboard de conflictos sociales](https://roddyhuarhua-hub.github.io/Data-Science-Python/)). Un día de paralización de una operación cuesta mucho más que todo el sistema de seguimiento de un año. Además, el relacionista pierde horas pasando la reunión al acta y al Excel, y la gerencia recibe el estado de los compromisos tarde y a mano.

**Cómo se resuelve hoy.** Cuaderno de campo, acta manuscrita firmada, un Excel compartido y la memoria de las personas. Algunos usan software de gestión de stakeholders (genérico, caro, en inglés) que igual exige tipear todo a mano.

**Evidencia de usuarios.** Notas de 3 conversaciones en [`docs/research/`](docs/research/):

| # | Perfil | Lo que más aprendí |
|---|---|---|
| 1 | _pendiente_ | _pendiente_ |
| 2 | _pendiente_ | _pendiente_ |
| 3 | _pendiente_ | _pendiente_ |

## 4. Solución e insight

1. Subes el **audio** de la reunión (o lo grabas en la app), una **foto del acta** o el texto.
2. **Whisper** lo transcribe en español.
3. Un **LLM con salida estructurada** (validada con Pydantic) extrae cada compromiso: qué, quién (empresa, Estado, comunidad), plazo en fecha exacta, tema, riesgo de conflicto y la **cita textual** que lo respalda. También lista las demandas que quedaron **sin acuerdo**.
4. El relacionista **revisa y corrige** en una tabla antes de guardar (la IA propone, la persona decide).
5. El **tablero** muestra vencidos, por vencer, tasa de cumplimiento, quién incumple y en qué temas. Se descarga el registro (CSV/Excel) y una ficha de la reunión para compartir con la comunidad.

**Insight.** El problema no es que falte un lugar donde anotar los compromisos, sino que **anotarlos cuesta trabajo extra justo después de una reunión tensa**, y por eso no se hace. Si la captura sale sola del audio, el registro se llena. La cita textual es clave: en una mesa de diálogo lo que vale es lo que se dijo, y la cita permite verificarlo.

## 5. ¿Por qué ahora?

- Hace tres años transcribir una hora de audio en español con buena calidad costaba alrededor de US$ 0.36 por API (o una GPU propia). Hoy Whisper large v3 turbo en Groq cuesta cerca de **US$ 0.04 por hora** y responde en segundos.
- Los LLM de 2023 no garantizaban un JSON válido. Hoy la **salida estructurada** (modo JSON + validación de esquema) es estándar, lo que permite llenar un registro sin intervención.
- Los modelos con visión leen actas manuscritas, que siguen siendo el documento oficial en el campo.
- La presión regulatoria y de inversionistas (ESG, estándares de debida diligencia) exige demostrar el cumplimiento de compromisos sociales con evidencia.

## 6. Demo

- **URL pública:** https://compromisos-roddy.streamlit.app (Streamlit Community Cloud, con Gemini + Whisper local)
- **Correr en local:**

  ```bash
  git clone https://github.com/roddyhuarhua-hub/compromisos.git
  cd compromisos
  python -m venv .venv
  .venv\Scripts\activate          # en Windows (en Mac/Linux: source .venv/bin/activate)
  pip install -r requirements.txt
  copy .env.example .env          # y pega tu GROQ_API_KEY o GEMINI_API_KEY dentro de .env
  streamlit run app.py
  ```

  Sin clave, la opción **⭐ Reunión de ejemplo** muestra el flujo completo con una extracción guardada.

- **Capturas:**

  | Nueva reunión | Tablero | Registro |
  |---|---|---|
  | ![](img/01_nueva_reunion.png) | ![](img/02_tablero.png) | ![](img/03_registro.png) |

- **Arquitectura:**

  ```mermaid
  flowchart LR
      A[🎙️ Audio de la reunión] -->|Whisper large v3 turbo| T[Transcripción]
      F[📄 Foto del acta] -->|Llama 4 Scout visión| T
      X[⌨️ Texto] --> T
      T -->|Llama 3.3 70B + JSON + Pydantic| E[Compromisos estructurados]
      E --> R{Revisión humana}
      R --> REG[(Registro CSV / Excel)]
      REG --> D[📊 Tablero: alertas, KPIs, gráficos]
      E --> FI[📝 Ficha de la reunión]
  ```

- **Modelos y por qué:**

  | Paso | Modelo (Groq) | Por qué |
  |---|---|---|
  | Transcripción | `whisper-large-v3-turbo` | Mejor relación calidad/costo en español; US$ 0.04/h |
  | Extracción | `llama-3.3-70b-versatile` | Buen español, modo JSON, barato y rápido |
  | Actas en foto | `llama-4-scout-17b-16e-instruct` | Lee manuscritos sin instalar OCR pesado en el servidor |

  **Alternativa con Gemini** (si no hay clave de Groq): el audio se transcribe con **Whisper local** (`faster-whisper`, modelo `base`, en el propio servidor) y la extracción y la lectura de actas usan el Gemini **Flash-Lite** más reciente de la cuenta (se detecta solo; en la prueba real `gemini-3.5-flash-lite`: 8 compromisos, US$ 0.004 por reunión), con salida JSON. Si un modelo está saturado o no responde en 25 s, la app pasa sola al siguiente. La app usa la primera clave que encuentre. Los modelos se cambian con variables de entorno (`.env.example`).

## 7. Modelo de negocio

**Quién paga.** La empresa (gerencia de asuntos sociales / relaciones comunitarias), no la comunidad. Segundo segmento: consultoras sociales que gestionan varias mesas.

| Plan | Precio | Incluye |
|---|---|---|
| Consultor | S/ 350 al mes | 1 usuario, 20 reuniones al mes |
| Unidad operativa | S/ 1 200 al mes | hasta 15 usuarios, reuniones ilimitadas, reportes para gerencia |
| Implementación | S/ 4 000 (pago único) | carga del histórico de actas y capacitación |

**Costo por usuario** (estimado con los precios públicos de Groq, ver `compromisos/ia.py`):

- Reunión de 1 hora: Whisper ≈ US$ 0.04 + extracción ≈ 15 000 tokens de entrada y 2 000 de salida ≈ US$ 0.01 → **≈ US$ 0.05 por reunión**.
- Un relacionista activo (20 reuniones al mes) ≈ **US$ 1 al mes en tokens**.
- Servidor: Streamlit Community Cloud gratis para la demo; en producción ≈ US$ 25 al mes (base de datos + hosting) para toda una unidad operativa.

Margen bruto superior al 95 %. El costo real del negocio es la venta y la implementación en campo.

## 8. Herramientas del curso

| Herramienta (sesión) | Dónde |
|---|---|
| Speech-to-text con Whisper (S13) | `compromisos/ia.py` → `transcribir_audio()` (Whisper en Groq o `faster-whisper` local) |
| LLM con salidas estructuradas (S08) | `compromisos/ia.py` → `extraer_compromisos()` y `compromisos/modelos.py` (esquema Pydantic) |
| Dashboards (S05) | `app.py` → pestaña *Tablero de seguimiento* (KPIs, filtros, gráficos Plotly) |
| Despliegue y evaluación (S12) | Streamlit Community Cloud + `tests/` |

## 9. Qué hizo el agente

Usé **Claude Code** como asistente de programación. Generó:

- La estructura del repositorio, `app.py` (interfaz Streamlit) y el paquete `compromisos/` (llamadas a Groq, esquema Pydantic, lógica de estados y alertas).
- El prompt de extracción, a partir de mis criterios de riesgo (agua, tierras, salud y empleo local = riesgo alto).
- La transcripción de ejemplo, la extracción de ejemplo y el registro sintético (`scripts/generar_registro_demo.py`).
- Las pruebas (`tests/`), la guía de entrevistas y este README a partir de mis notas.

Yo definí el problema y el flujo desde mi experiencia en campo, hice las entrevistas, revisé los compromisos extraídos y grabé la reunión de prueba.

## Datos y privacidad

- Los datos de ejemplo son **sintéticos**: comunidades, empresa y personas ficticias.
- Los audios reales de reuniones no se suben al repositorio (`.gitignore`) y no se guardan en el servidor: el registro vive en la sesión y se descarga.
- No se suben claves: se usa `.env` (ignorado) o los *Secrets* de Streamlit Cloud.

## Hoja de ruta

Base de datos persistente con usuarios, recordatorios por WhatsApp al responsable, transcripción en quechua, carga de evidencias de cumplimiento (fotos, actas de entrega) y mapa por comunidad.

## Licencia

[MIT](LICENSE)

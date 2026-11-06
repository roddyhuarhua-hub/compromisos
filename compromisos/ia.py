"""Llamadas a modelos de IA: transcripcion (Whisper), lectura de actas (vision) y
extraccion de compromisos con salida estructurada (LLM + Pydantic).

Proveedores (se usa el primero que tenga clave):
  1. Groq   (GROQ_API_KEY):   Whisper large v3 turbo + Llama 3.3 70B + Llama 4 Scout (vision)
  2. Gemini (GEMINI_API_KEY): Whisper local (faster-whisper) para el audio + Gemini Flash
     para extraer compromisos y leer actas. Si faster-whisper no esta instalado, Gemini
     transcribe el audio.
Los nombres de modelo se cambian con variables de entorno sin tocar el codigo.
"""
from __future__ import annotations

import base64
import json
import os
import tempfile
from datetime import date
from functools import lru_cache

from pydantic import ValidationError

from .modelos import ExtraccionReunion

MODELO_WHISPER = os.getenv("MODELO_WHISPER", "whisper-large-v3-turbo")
MODELO_LLM = os.getenv("MODELO_LLM", "llama-3.3-70b-versatile")
MODELO_VISION = os.getenv("MODELO_VISION", "meta-llama/llama-4-scout-17b-16e-instruct")
MODELO_GEMINI = os.getenv("MODELO_GEMINI", "gemini-flash-latest")
MODELO_WHISPER_LOCAL = os.getenv("MODELO_WHISPER_LOCAL", "base")

# Precios aproximados en USD para estimar costo por reunion (ver README, seccion 7).
PRECIOS = {
    "groq": {"audio_hora": 0.04, "entrada": 0.59, "salida": 0.79},
    "gemini": {"audio_hora": 0.0, "entrada": 0.30, "salida": 2.50},
}


class SinClaveError(RuntimeError):
    """No hay ninguna clave de IA configurada."""


def proveedor() -> str | None:
    if os.getenv("GROQ_API_KEY"):
        return "groq"
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        return "gemini"
    return None


def descripcion_proveedor() -> str:
    p = proveedor()
    if p == "groq":
        return f"Groq · {MODELO_WHISPER} + {MODELO_LLM}"
    if p == "gemini":
        audio = f"Whisper local ({MODELO_WHISPER_LOCAL})" if _hay_whisper_local() else "Gemini"
        return f"{audio} + {MODELO_GEMINI}"
    return "sin IA"


def _groq():
    from groq import Groq  # import diferido: la app abre aunque no este instalado

    return Groq(api_key=os.environ["GROQ_API_KEY"])


def _gemini():
    from google import genai

    return genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))


def _exigir_proveedor() -> str:
    p = proveedor()
    if not p:
        raise SinClaveError(
            "Falta GROQ_API_KEY o GEMINI_API_KEY. Ponla en .env (local) o en Secrets (Streamlit Cloud)."
        )
    return p


# ------------------------------------------------------------------ audio
def _hay_whisper_local() -> bool:
    try:
        import faster_whisper  # noqa: F401

        return True
    except ImportError:
        return False


@lru_cache(maxsize=1)
def _whisper_local():
    from faster_whisper import WhisperModel

    return WhisperModel(MODELO_WHISPER_LOCAL, device="cpu", compute_type="int8")


def transcribir_audio(nombre_archivo: str, contenido: bytes, tipo_mime: str = "audio/wav") -> str:
    """Convierte el audio de la reunion en texto con Whisper."""
    p = _exigir_proveedor()
    if p == "groq":
        resp = _groq().audio.transcriptions.create(
            file=(nombre_archivo, contenido),
            model=MODELO_WHISPER,
            language="es",
            response_format="text",
            temperature=0,
        )
        return resp if isinstance(resp, str) else getattr(resp, "text", str(resp))

    if _hay_whisper_local():
        sufijo = os.path.splitext(nombre_archivo)[1] or ".wav"
        with tempfile.NamedTemporaryFile(suffix=sufijo, delete=False) as f:
            f.write(contenido)
            ruta = f.name
        try:
            segmentos, _ = _whisper_local().transcribe(ruta, language="es", vad_filter=True)
            return " ".join(s.text.strip() for s in segmentos)
        finally:
            os.unlink(ruta)

    from google.genai import types

    resp = _gemini().models.generate_content(
        model=MODELO_GEMINI,
        contents=[
            "Transcribe literalmente este audio en español. Indica quién habla si se presenta. "
            "Devuelve solo la transcripción.",
            types.Part.from_bytes(data=contenido, mime_type=tipo_mime or "audio/wav"),
        ],
    )
    return resp.text or ""


# ------------------------------------------------------------------ actas en foto
PROMPT_ACTA = (
    "Transcribe fielmente el texto de esta acta de reunion comunal. "
    "Conserva nombres, fechas, montos y la lista de acuerdos. "
    "Devuelve solo el texto, sin comentarios."
)


def leer_acta_imagen(contenido: bytes, tipo_mime: str) -> str:
    """Lee la foto de un acta manuscrita o impresa y devuelve su texto."""
    p = _exigir_proveedor()
    if p == "groq":
        b64 = base64.b64encode(contenido).decode()
        resp = _groq().chat.completions.create(
            model=MODELO_VISION,
            temperature=0,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT_ACTA},
                    {"type": "image_url", "image_url": {"url": f"data:{tipo_mime};base64,{b64}"}},
                ],
            }],
        )
        return resp.choices[0].message.content or ""

    from google.genai import types

    resp = _gemini().models.generate_content(
        model=MODELO_GEMINI,
        contents=[PROMPT_ACTA, types.Part.from_bytes(data=contenido, mime_type=tipo_mime)],
    )
    return resp.text or ""


# ------------------------------------------------------------------ extraccion
SISTEMA = """Eres un especialista en relaciones comunitarias en Peru (mineria, hidrocarburos, energia).
Lees la transcripcion o el acta de una reunion entre una empresa, el Estado y una comunidad,
y extraes TODOS los compromisos asumidos por cualquiera de las partes.

Reglas:
- Un compromiso es una accion concreta que alguien se obliga a hacer ("la empresa entregara...",
  "la municipalidad gestionara...", "la comunidad facilitara el acceso...").
- No inventes datos. Si no se dice el plazo, deja fecha_limite en null.
- Convierte plazos relativos a fecha ISO (AAAA-MM-DD) usando la fecha de la reunion: "en 30 dias",
  "a fin de mes", "antes de la campana agricola" (si no es inferible, null).
- cita_textual: copia la frase exacta de la transcripcion que respalda el compromiso.
- riesgo_conflicto: alto si involucra agua, tierras, salud, empleo local o un compromiso ya incumplido
  que se repite; medio si es economico o de infraestructura; bajo si es tramite o comunicacion.
- Responde solo con JSON valido con este esquema:
{esquema}
"""


def _completar_json(mensajes: list[dict], p: str) -> tuple[str, int, int]:
    """Envia la conversacion al LLM en modo JSON. Devuelve (texto, tokens_in, tokens_out)."""
    if p == "groq":
        resp = _groq().chat.completions.create(
            model=MODELO_LLM,
            temperature=0,
            response_format={"type": "json_object"},
            messages=mensajes,
        )
        u = resp.usage
        return (resp.choices[0].message.content or "{}",
                getattr(u, "prompt_tokens", 0) if u else 0,
                getattr(u, "completion_tokens", 0) if u else 0)

    from google.genai import types

    sistema = "\n".join(m["content"] for m in mensajes if m["role"] == "system")
    contenidos = [
        types.Content(role="model" if m["role"] == "assistant" else "user",
                      parts=[types.Part.from_text(text=m["content"])])
        for m in mensajes if m["role"] != "system"
    ]
    resp = _gemini().models.generate_content(
        model=MODELO_GEMINI,
        contents=contenidos,
        config=types.GenerateContentConfig(
            system_instruction=sistema,
            temperature=0,
            response_mime_type="application/json",
        ),
    )
    u = resp.usage_metadata
    return (resp.text or "{}",
            getattr(u, "prompt_token_count", 0) or 0 if u else 0,
            getattr(u, "candidates_token_count", 0) or 0 if u else 0)


def extraer_compromisos(
    texto: str,
    fecha_reunion: date,
    contexto: str = "",
) -> tuple[ExtraccionReunion, dict]:
    """Extrae compromisos con salida estructurada. Devuelve (resultado, uso_de_tokens)."""
    p = _exigir_proveedor()
    esquema = json.dumps(ExtraccionReunion.model_json_schema(), ensure_ascii=False)
    mensajes = [
        {"role": "system", "content": SISTEMA.format(esquema=esquema)},
        {
            "role": "user",
            "content": f"Fecha de la reunion: {fecha_reunion.isoformat()}\n"
            f"Contexto: {contexto or 'sin datos'}\n\nTEXTO:\n{texto}",
        },
    ]
    uso = {"entrada": 0, "salida": 0, "proveedor": p}
    ultimo_error = None
    for _ in range(2):  # un reintento si el JSON no valida
        crudo, t_in, t_out = _completar_json(mensajes, p)
        uso["entrada"] += t_in
        uso["salida"] += t_out
        try:
            return ExtraccionReunion.model_validate_json(_limpiar_json(crudo)), uso
        except ValidationError as e:
            ultimo_error = e
            mensajes.append({"role": "assistant", "content": crudo})
            mensajes.append(
                {"role": "user", "content": f"El JSON no cumple el esquema: {e}. Corrigelo."}
            )
    raise ValueError(f"El modelo no devolvio un JSON valido: {ultimo_error}")


def _limpiar_json(crudo: str) -> str:
    """Quita cercos ```json ... ``` si el modelo los agrega."""
    t = crudo.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        t = t.rsplit("```", 1)[0]
    return t.strip()


def costo_estimado(minutos_audio: float, uso: dict) -> float:
    """Costo en USD de procesar una reunion."""
    precio = PRECIOS.get(uso.get("proveedor", "groq"), PRECIOS["groq"])
    return (
        minutos_audio / 60 * precio["audio_hora"]
        + uso.get("entrada", 0) / 1e6 * precio["entrada"]
        + uso.get("salida", 0) / 1e6 * precio["salida"]
    )

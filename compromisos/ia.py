"""Llamadas a modelos de IA: transcripcion (Whisper), lectura de actas (vision) y
extraccion de compromisos con salida estructurada (LLM + Pydantic).

Proveedor: Groq (API compatible con OpenAI, tiene capa gratuita).
Los nombres de modelo se pueden cambiar con variables de entorno sin tocar el codigo.
"""
from __future__ import annotations

import base64
import json
import os
from datetime import date

from pydantic import ValidationError

from .modelos import ExtraccionReunion

MODELO_WHISPER = os.getenv("MODELO_WHISPER", "whisper-large-v3-turbo")
MODELO_LLM = os.getenv("MODELO_LLM", "llama-3.3-70b-versatile")
MODELO_VISION = os.getenv("MODELO_VISION", "meta-llama/llama-4-scout-17b-16e-instruct")

# Precios aproximados en USD para estimar costo por usuario (ver README, seccion 7).
PRECIO_WHISPER_HORA = 0.04
PRECIO_LLM_MILLON_ENTRADA = 0.59
PRECIO_LLM_MILLON_SALIDA = 0.79


class SinClaveError(RuntimeError):
    """No hay GROQ_API_KEY configurada."""


def _cliente(api_key: str | None = None):
    clave = api_key or os.getenv("GROQ_API_KEY")
    if not clave:
        raise SinClaveError(
            "Falta GROQ_API_KEY. Ponla en el archivo .env (local) o en Secrets (Streamlit Cloud)."
        )
    from groq import Groq  # import diferido: la app abre aunque no este instalado

    return Groq(api_key=clave)


def transcribir_audio(nombre_archivo: str, contenido: bytes, api_key: str | None = None) -> str:
    """Convierte el audio de la reunion en texto con Whisper."""
    cliente = _cliente(api_key)
    resp = cliente.audio.transcriptions.create(
        file=(nombre_archivo, contenido),
        model=MODELO_WHISPER,
        language="es",
        response_format="text",
        temperature=0,
    )
    return resp if isinstance(resp, str) else getattr(resp, "text", str(resp))


def leer_acta_imagen(contenido: bytes, tipo_mime: str, api_key: str | None = None) -> str:
    """Lee la foto de un acta manuscrita o impresa y devuelve su texto."""
    cliente = _cliente(api_key)
    b64 = base64.b64encode(contenido).decode()
    resp = cliente.chat.completions.create(
        model=MODELO_VISION,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Transcribe fielmente el texto de esta acta de reunion comunal. "
                            "Conserva nombres, fechas, montos y la lista de acuerdos. "
                            "Devuelve solo el texto, sin comentarios."
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": f"data:{tipo_mime};base64,{b64}"}},
                ],
            }
        ],
    )
    return resp.choices[0].message.content or ""


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


def extraer_compromisos(
    texto: str,
    fecha_reunion: date,
    contexto: str = "",
    api_key: str | None = None,
) -> tuple[ExtraccionReunion, dict]:
    """Extrae compromisos con salida estructurada. Devuelve (resultado, uso_de_tokens)."""
    cliente = _cliente(api_key)
    esquema = json.dumps(ExtraccionReunion.model_json_schema(), ensure_ascii=False)
    mensajes = [
        {"role": "system", "content": SISTEMA.format(esquema=esquema)},
        {
            "role": "user",
            "content": f"Fecha de la reunion: {fecha_reunion.isoformat()}\n"
            f"Contexto: {contexto or 'sin datos'}\n\nTEXTO:\n{texto}",
        },
    ]
    uso = {"entrada": 0, "salida": 0}
    ultimo_error = None
    for _ in range(2):  # un reintento si el JSON no valida
        resp = cliente.chat.completions.create(
            model=MODELO_LLM,
            temperature=0,
            response_format={"type": "json_object"},
            messages=mensajes,
        )
        if resp.usage:
            uso["entrada"] += resp.usage.prompt_tokens
            uso["salida"] += resp.usage.completion_tokens
        crudo = resp.choices[0].message.content or "{}"
        try:
            return ExtraccionReunion.model_validate_json(crudo), uso
        except ValidationError as e:
            ultimo_error = e
            mensajes.append({"role": "assistant", "content": crudo})
            mensajes.append(
                {"role": "user", "content": f"El JSON no cumple el esquema: {e}. Corrigelo."}
            )
    raise ValueError(f"El modelo no devolvio un JSON valido: {ultimo_error}")


def costo_estimado(minutos_audio: float, uso: dict) -> float:
    """Costo en USD de procesar una reunion."""
    return (
        minutos_audio / 60 * PRECIO_WHISPER_HORA
        + uso.get("entrada", 0) / 1e6 * PRECIO_LLM_MILLON_ENTRADA
        + uso.get("salida", 0) / 1e6 * PRECIO_LLM_MILLON_SALIDA
    )

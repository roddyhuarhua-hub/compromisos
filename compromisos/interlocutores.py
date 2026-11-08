"""Transcripcion con interlocutores (diarizacion): quien dijo que en la reunion.

Usa Gemini, que ya tiene la app (no necesita otra clave): escucha el audio y separa los turnos como
"Interlocutor 1", "Interlocutor 2"... Si alguien se presenta ("soy el presidente de la comunidad"), usa su nombre
o su cargo. Despues el relacionista puede renombrar cada interlocutor antes de extraer los compromisos, y asi la
IA atribuye mejor cada compromiso y cada postura a quien la dijo.

Limitacion: en asambleas con mucho ruido o con varias personas hablando a la vez puede confundir voces. Para
clientes que lo necesiten, un servicio especializado (AssemblyAI, Deepgram) mejora la separacion.
"""
from __future__ import annotations

import os
import re
import tempfile
from collections import OrderedDict

PROMPT = (
    "Transcribe literalmente este audio de una reunión en español (puede haber palabras en quechua o aimara: "
    "transcríbelas como se oyen). Separa los turnos de habla. Empieza cada turno en una línea nueva con el "
    "formato:\n[mm:ss] Hablante: texto\n"
    "Para el hablante usa 'Interlocutor 1', 'Interlocutor 2', etc., siempre el mismo número para la misma voz. "
    "Si la persona se presenta o la nombran (por ejemplo 'soy Julián Quispe, presidente comunal'), usa desde ese "
    "momento su nombre y cargo entre paréntesis, por ejemplo 'Julián Quispe (presidente comunal)', también en "
    "los turnos anteriores de esa misma voz. No resumas ni corrijas. Devuelve solo la transcripción."
)
LINEA = re.compile(r"^\s*(?:\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*)?([^:\[\]\n]{2,70}?):\s+(.+)$")
LIMITE_EN_LINEA = 18 * 1024 * 1024  # mas grande que esto, el audio se sube como archivo


def disponible() -> bool:
    return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))


def _cliente():
    """Cliente propio con mas tiempo de espera: transcribir una reunion larga toma minutos."""
    from google import genai
    from google.genai import types

    return genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
                        http_options=types.HttpOptions(timeout=600_000))


def _modelos() -> list[str]:
    """Para separar voces conviene Flash (mejor oido) antes que Flash-Lite."""
    from . import ia

    lista = ia.modelos_gemini()
    flash = [m for m in lista if "flash" in m and "lite" not in m]
    return flash + [m for m in lista if m not in flash]


def transcribir(nombre_archivo: str, contenido: bytes, tipo_mime: str = "audio/wav") -> str:
    """Transcripcion por turnos: '[mm:ss] Interlocutor 1: ...'."""
    from google.genai import types

    cli = _cliente()
    if len(contenido) > LIMITE_EN_LINEA:
        sufijo = os.path.splitext(nombre_archivo)[1] or ".wav"
        with tempfile.NamedTemporaryFile(suffix=sufijo, delete=False) as f:
            f.write(contenido)
            ruta = f.name
        try:
            parte = cli.files.upload(file=ruta, config=types.UploadFileConfig(mime_type=tipo_mime or "audio/wav"))
        finally:
            os.unlink(ruta)
    else:
        parte = types.Part.from_bytes(data=contenido, mime_type=tipo_mime or "audio/wav")
    ultimo = None
    for modelo in _modelos()[:4]:
        try:
            resp = cli.models.generate_content(model=modelo, contents=[PROMPT, parte])
            if resp.text and resp.text.strip():
                return resp.text.strip()
        except Exception as e:  # saturado o no disponible: probar el siguiente
            ultimo = e
    raise RuntimeError(f"No se pudo separar interlocutores: {ultimo}")


def turnos(texto: str) -> list[dict]:
    """Lineas 'Hablante: texto' -> lista de turnos. Las lineas sin hablante se unen al turno anterior."""
    out: list[dict] = []
    for linea in str(texto).splitlines():
        if not linea.strip():
            continue
        m = LINEA.match(linea)
        if m and len(m.group(2).split()) <= 8:
            out.append(dict(tiempo=m.group(1) or "", hablante=m.group(2).strip(), texto=m.group(3).strip()))
        elif out:
            out[-1]["texto"] += " " + linea.strip()
        else:
            out.append(dict(tiempo="", hablante="", texto=linea.strip()))
    out = [t for t in out if t["hablante"]]
    # la misma persona con y sin cargo ("Luis Paredes (Minera Andina)" y "Luis Paredes") es un solo hablante
    completo: dict[str, str] = {}
    for t in out:
        base = t["hablante"].split("(")[0].strip().lower()
        if base not in completo or ("(" in t["hablante"] and "(" not in completo[base]):
            completo[base] = t["hablante"]
    for t in out:
        t["hablante"] = completo[t["hablante"].split("(")[0].strip().lower()]
    return out


def hablantes(ts: list[dict]) -> "OrderedDict[str, dict]":
    """Cada hablante con sus turnos y su proporcion de palabras (quien llevo la voz en la reunion)."""
    res: OrderedDict[str, dict] = OrderedDict()
    for t in ts:
        h = res.setdefault(t["hablante"], dict(turnos=0, palabras=0))
        h["turnos"] += 1
        h["palabras"] += len(t["texto"].split())
    total = sum(h["palabras"] for h in res.values()) or 1
    for h in res.values():
        h["parte"] = h["palabras"] / total
    return res


def renombrar(texto: str, nombres: dict[str, str]) -> str:
    """Cambia 'Interlocutor 2' por el nombre que puso el relacionista, solo donde aparece como hablante."""
    for viejo, nuevo in nombres.items():
        if nuevo and nuevo.strip() and nuevo.strip() != viejo:
            texto = re.sub(rf"(^\s*(?:\[[\d:]+\]\s*)?){re.escape(viejo)}:", rf"\g<1>{nuevo.strip()}:", texto,
                           flags=re.M)
    return texto

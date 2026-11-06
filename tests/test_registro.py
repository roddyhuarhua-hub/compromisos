from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from compromisos import ia, registro
from compromisos.modelos import ExtraccionReunion

EJEMPLO = Path(__file__).resolve().parents[1] / "datos" / "ejemplo"
HOY = date(2026, 11, 6)


def _ext():
    return ExtraccionReunion.model_validate_json(
        (EJEMPLO / "extraccion_reunion_demo.json").read_text(encoding="utf-8"))


def test_estados():
    df = registro.normalizar(pd.DataFrame([
        {"descripcion": "a", "fecha_limite": "2026-11-01", "cumplido": "False"},
        {"descripcion": "b", "fecha_limite": "2026-11-20", "cumplido": "False"},
        {"descripcion": "c", "fecha_limite": "2027-03-01", "cumplido": "False"},
        {"descripcion": "d", "fecha_limite": "", "cumplido": "False"},
        {"descripcion": "e", "fecha_limite": "2026-01-01", "cumplido": "True"},
    ]))
    est = registro.con_estado(df, HOY)
    assert list(est["estado"]) == ["Vencido", "Por vencer", "En plazo", "Sin plazo", "Cumplido"]
    assert est["dias_restantes"].iloc[0] == -5


def test_indicadores_tasa():
    df = registro.con_estado(registro.cargar(EJEMPLO / "registro_demo.csv"), HOY)
    k = registro.indicadores(df)
    assert k["total"] == len(df)
    assert 0 <= k["tasa_cumplimiento"] <= 1


def test_desde_extraccion_y_ficha():
    ext = _ext()
    df = registro.desde_extraccion(ext, "Mesa", date(2026, 11, 4), "C.C. Pucará Alto")
    assert len(df) == 7 and set(df["responsable"]) <= {"Empresa", "Estado", "Comunidad"}
    ficha = registro.acta_markdown(ext, "Mesa", date(2026, 11, 4), "C.C. Pucará Alto")
    assert "posta de salud" in ficha and ficha.count("\n| ") == 8


def test_extraer_reintenta_si_json_invalido(monkeypatch):
    respuestas = iter(["{no es json", _ext().model_dump_json()])

    def crear(**kw):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=next(respuestas)))],
            usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=500),
        )

    falso = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=crear)))
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setattr(ia, "_groq", lambda: falso)
    ext, uso = ia.extraer_compromisos("texto", date(2026, 11, 4))
    assert len(ext.compromisos) == 7
    assert uso["entrada"] == 2000 and uso["salida"] == 1000
    assert ia.costo_estimado(60, uso) > 0.04


def test_limpiar_json_y_proveedor(monkeypatch):
    assert ia._limpiar_json('```json\n{"a": 1}\n```') == '{"a": 1}'
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    assert ia.proveedor() == "gemini"


def test_elegir_modelo_gemini():
    nombres = ["models/gemini-2.0-flash", "models/gemini-2.5-flash", "models/gemini-2.5-flash-lite",
               "models/gemini-3-flash-preview", "models/gemini-2.5-pro", "models/gemini-2.5-flash-image"]
    assert ia.elegir_modelo_gemini(nombres) == "gemini-2.5-flash"
    assert ia.ordenar_modelos_gemini(nombres)[:3] == ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
    assert ia.elegir_modelo_gemini(["models/gemini-3-flash-preview"]) == "gemini-3-flash-preview"
    assert ia.elegir_modelo_gemini(["models/gemini-2.5-pro"]) is None


def test_gemini_salta_modelo_saturado(monkeypatch):
    llamados = []

    def gen(model, **kw):
        llamados.append(model)
        if model == "gemini-3.8-flash":
            raise RuntimeError("503 UNAVAILABLE. This model is currently experiencing high demand.")
        return SimpleNamespace(text="ok")

    falso = SimpleNamespace(models=SimpleNamespace(generate_content=gen))
    monkeypatch.setattr(ia, "_gemini", lambda: falso)
    monkeypatch.setitem(ia._CLIENTES, "modelos_gemini", ["gemini-3.8-flash", "gemini-2.5-flash"])
    monkeypatch.delitem(ia._CLIENTES, "modelo_ok", raising=False)
    assert ia._generar_gemini(contents=["hola"]).text == "ok"
    assert llamados == ["gemini-3.8-flash", "gemini-3.8-flash", "gemini-2.5-flash"]  # reintenta 1 vez
    assert ia.modelo_gemini() == "gemini-2.5-flash"

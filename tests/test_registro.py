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
    assert ia.elegir_modelo_gemini(nombres) == "gemini-2.5-flash-lite"
    assert ia.ordenar_modelos_gemini(nombres)[:3] == ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash"]
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


def test_transcribir_respaldo_gemini_si_whisper_falla(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(ia, "_hay_whisper_local", lambda: True)

    def roto():
        raise TypeError("open() got an unexpected keyword argument 'metadata_errors'")

    monkeypatch.setattr(ia, "_whisper_local", roto)
    monkeypatch.setattr(ia, "_generar_gemini", lambda **kw: SimpleNamespace(text="hola desde gemini"))
    assert ia.transcribir_audio("a.wav", b"RIFF....", "audio/wav") == "hola desde gemini"


def test_indice_comunidades():
    from compromisos import visual

    df = registro.con_estado(registro.cargar(EJEMPLO / "registro_demo.csv"), HOY)
    com = pd.read_csv(EJEMPLO / "comunidades.csv")
    ind = visual.indice_comunidades(df, com)
    assert ind["indice"].between(0, 100).all()
    assert set(ind["semaforo"]) <= {"Estable", "Atención", "Crítico"}
    assert ind["lat"].notna().all()


def test_mapeo_actores_dinamico():
    from datetime import date

    from compromisos import actores as ac
    from compromisos.modelos import Actor, ExtraccionReunion, Relacion

    A = ac.normalizar_actores(pd.DataFrame([dict(nombre="Julián Quispe", tipo="Dirigente comunal",
                                                 comunidad="C.C. X", postura=1, influencia=5)]))
    R = ac.normalizar_relaciones(pd.DataFrame(columns=ac.COL_RELACIONES))
    H = ac.normalizar_historial(pd.DataFrame([dict(nombre="Julián Quispe", fecha="2026-01-10", postura=1,
                                                   influencia=5, reunion="R1")]))
    ext = ExtraccionReunion(resumen="", actores=[
        Actor(nombre="julian quispe", tipo="Dirigente comunal", postura=-1, influencia=5, evidencia="No cumplen"),
        Actor(nombre="Marta Ccahuana", tipo="Organización de base", postura=0, influencia=3)],
        relaciones=[Relacion(origen="Julián Quispe", destino="Marta Ccahuana", tipo="Alianza")])
    A2, R2, H2 = ac.fusionar(A, R, ext, "C.C. X", "R2", historial=H, fecha=date(2026, 6, 1), reunion="R2")
    assert len(A2) == 2 and len(R2) == 1 and len(H2) == 3          # fusiona por nombre normalizado
    assert A2.set_index("nombre").loc["Julián Quispe", "postura"] == -1
    assert A2.set_index("nombre").loc["Marta Ccahuana", "comunidad"] == "C.C. X"
    # el mapa al corte de marzo muestra la postura de entonces y aun no conoce a Marta
    antes = ac.al_corte(A2, H2, date(2026, 3, 1))
    assert list(antes["nombre"]) == ["Julián Quispe"] and antes["postura"].iloc[0] == 1
    c = ac.cambios(H2, date(2026, 3, 1), date(2026, 7, 1))
    assert c.iloc[0]["nombre"] == "Julián Quispe" and c.iloc[0]["delta"] == -2 and c.iloc[0]["evidencia"] == "No cumplen"
    m = ac.metricas(ac.red(A2, R2))
    assert set(m["vinculos"]) == {1}


def test_laminas_panel_4k():
    from PIL import Image
    import io as _io

    from compromisos import panel_imagen, visual

    hoy = date(2026, 11, 7)
    df = registro.con_estado(registro.cargar(Path("datos/ejemplo/registro_demo.csv")), hoy)
    ind = visual.indice_comunidades(df, pd.read_csv("datos/ejemplo/comunidades.csv"))
    lams = panel_imagen.laminas(df, ind, registro.indicadores(df), hoy, "Cliente")
    assert len(lams) == 7
    assert Image.open(_io.BytesIO(lams[0][1])).size == (3840, 2160)
    assert panel_imagen.pptx_laminas(lams[:1])[:2] == b"PK"


def test_conflictividad():
    from compromisos import conflictos
    from compromisos.modelos import EventoConflicto, ExtraccionEventos

    com = pd.read_csv("datos/ejemplo/comunidades.csv")
    c = conflictos.normalizar(pd.read_csv("datos/ejemplo/conflictos_demo.csv"))
    k = conflictos.indicadores(c, date(2026, 11, 7))
    assert k["eventos"] == len(c) and k["dias_paralizacion"] > 0 and k["bloqueos"] >= 1
    ext = ExtraccionEventos(eventos=[EventoConflicto(fecha=date(2026, 11, 2), tipo="Bloqueo de vía",
                                                     titulo="Bloqueo del puente", comunidad="Pucara Alto",
                                                     duracion_dias=2)])
    nuevos = conflictos.desde_extraccion(ext, com)
    assert nuevos.iloc[0]["comunidad"] == "C.C. Pucará Alto"  # nombre sin tilde se ubica igual
    assert abs(nuevos.iloc[0]["lat"] - (-14.05)) < 0.05


def test_laminas_conflictos_4k():
    from PIL import Image
    import io as _io

    from compromisos import conflictos, laminas_conflictos, visual

    hoy = date(2026, 11, 7)
    com = pd.read_csv("datos/ejemplo/comunidades.csv")
    df = registro.con_estado(registro.cargar(Path("datos/ejemplo/registro_demo.csv")), hoy)
    c = conflictos.normalizar(pd.read_csv("datos/ejemplo/conflictos_demo.csv"))
    lams = laminas_conflictos.laminas_conflictos(c, visual.indice_comunidades(df, com), com, hoy, "Cliente")
    assert len(lams) == 7
    assert Image.open(_io.BytesIO(lams[1][1])).size == (3840, 2160)

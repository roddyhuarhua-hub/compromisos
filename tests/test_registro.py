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


def test_laminas_actores_4k():
    from PIL import Image
    import io as _io

    from compromisos import actores as ac, laminas_actores

    corte = date(2026, 11, 7)
    A = ac.normalizar_actores(pd.read_csv("datos/ejemplo/actores_demo.csv"))
    R = ac.normalizar_relaciones(pd.read_csv("datos/ejemplo/relaciones_demo.csv"))
    H = ac.normalizar_historial(pd.read_csv("datos/ejemplo/posturas_demo.csv"))
    lams = laminas_actores.laminas_actores(ac.al_corte(A, H, corte), R, H, corte, "Cliente")
    assert len(lams) == 7
    assert Image.open(_io.BytesIO(lams[1][1])).size == (3840, 2160)


def test_mapa_base_une_mosaicos(monkeypatch):
    """El fondo satelital se arma con los tiles descargados (aqui simulados, sin internet)."""
    import io as _io

    from PIL import Image

    from compromisos import mapa_base

    def falso(url):
        b = _io.BytesIO()
        Image.new("RGB", (256, 256), (30, 90, 40)).save(b, "PNG")
        return b.getvalue()

    monkeypatch.setattr(mapa_base, "_descargar", falso)
    img, extent, atribucion = mapa_base.mosaico(-73.3, -72.4, -14.4, -13.9)
    assert img.shape[0] == 600 and extent == (-73.3, -72.4, -14.4, -13.9) and "Esri" in atribucion
    assert tuple(img[300, 300]) == (30, 90, 40)
    monkeypatch.setattr(mapa_base, "_descargar", lambda url: None)  # sin internet: no rompe
    assert mapa_base.mosaico(-73.3, -72.4, -14.4, -13.9) is None


def _datos_riesgo():
    from compromisos import actores as ac, conflictos as cf, riesgos as rg
    hoy = date(2026, 11, 7)
    H = ac.normalizar_historial(pd.read_csv(EJEMPLO / "posturas_demo.csv"))
    A = ac.al_corte(ac.normalizar_actores(pd.read_csv(EJEMPLO / "actores_demo.csv")), H, hoy)
    return dict(
        hoy=hoy, H=H, A=A, R=ac.normalizar_relaciones(pd.read_csv(EJEMPLO / "relaciones_demo.csv")),
        conf=cf.normalizar(pd.read_csv(EJEMPLO / "conflictos_demo.csv")),
        reg=registro.con_estado(registro.cargar(EJEMPLO / "registro_demo.csv"), hoy),
        P=rg.normalizar_procesos(pd.read_csv(EJEMPLO / "procesos_demo.csv")),
        PA=rg.normalizar_partes(pd.read_csv(EJEMPLO / "proceso_actores_demo.csv")),
        ES=rg.normalizar_escenarios(pd.read_csv(EJEMPLO / "escenarios_demo.csv")),
        AC=rg.normalizar_acciones(pd.read_csv(EJEMPLO / "acciones_demo.csv")))


def test_riesgos_y_escenarios():
    from compromisos import riesgos as rg
    d = _datos_riesgo()
    cart = rg.cartera(d["P"], d["PA"], d["A"], d["H"], d["conf"], d["reg"], d["hoy"])
    assert cart.iloc[0]["id"] == "P1" and cart.iloc[0]["nivel"] == "Alto"  # servidumbre: la prioridad
    assert cart.set_index("id").loc["P4", "nivel"] == "Bajo"  # aliado con convenio
    p1 = d["P"].set_index("id").loc["P1"].copy()
    p1["id"] = "P1"
    base = rg.evaluar(p1, d["PA"], d["A"], d["H"], d["conf"], d["reg"], d["hoy"])
    assert 0 <= base["puntos"] <= 100 and set(base["componentes"]) == set(rg.MAXIMOS)
    assert base["partes"].iloc[0]["nombre"] in {"Prof. Teodoro Llamocca", "Primitiva Soncco"}
    mejor = rg.evaluar(p1, d["PA"], d["A"], d["H"], d["conf"], d["reg"], d["hoy"],
                       {"Prof. Teodoro Llamocca": 1, "APAFA I.E. Pucará": 1, "Primitiva Soncco": 1})
    peor = rg.evaluar(p1, d["PA"], d["A"], d["H"], d["conf"], d["reg"], d["hoy"], {"Melquiades Mamani": -2})
    assert mejor["puntos"] < base["puntos"] < peor["puntos"]
    assert rg.estrategia(-2, 5) == "Atender sus preocupaciones de cerca" and rg.estrategia(2, 5) == "Colaborar"
    assert "UGEL Aymaraes" in rg.puentes("Prof. Teodoro Llamocca", d["A"], d["R"])
    sug = rg.sugerir_acciones("P1", base["partes"], d["AC"], "Luis Paredes")
    assert "Primitiva Soncco" in set(sug["nombre"]) and "Prof. Teodoro Llamocca" not in set(sug["nombre"])


def test_laminas_riesgos_4k(monkeypatch):
    from PIL import Image
    from compromisos import laminas_riesgos, mapa_base
    monkeypatch.setattr(mapa_base, "_descargar", lambda url: None)
    d = _datos_riesgo()
    p1 = d["P"].iloc[0]
    lams = laminas_riesgos.laminas_riesgos(p1, d["PA"], d["A"], d["R"], d["H"], d["conf"], d["reg"], d["ES"], d["AC"],
                                           d["hoy"], "Cliente")
    assert [n for n, _ in lams][:2] == ["01_riesgo_del_proceso.png", "02_quien_puede_frenar.png"]
    assert len(lams) == 4
    assert Image.open(__import__("io").BytesIO(lams[0][1])).size == (3840, 2160)


def test_portafolio_varios_proyectos():
    from compromisos import portafolio as pf
    d = pf.cargar_demo(EJEMPLO)
    proyectos = pf.lista(d["comunidades"])
    assert len(proyectos) == 3 and "Exploración Cerro Azul (Cajamarca)" in proyectos
    azul = pf.filtrar(d, "Exploración Cerro Azul (Cajamarca)")
    assert set(azul["registro"]["comunidad"]) <= set(azul["comunidades"]["comunidad"])
    assert "Ricardo Valdivia" not in set(azul["actores"]["nombre"])  # el gerente de la unidad no es de Cajamarca
    assert {"Marco Llanos", "ONG Agua y Territorio"} <= set(azul["actores"]["nombre"])
    assert set(azul["procesos"]["id"]) == {"A1", "A2"}
    trans = pf.transversales(d["actores"], d["relaciones"], d["comunidades"])
    assert list(trans["nombre"]) == ["ONG Agua y Territorio"] and trans.iloc[0]["n_proyectos"] == 3
    # editar la vista de un proyecto no borra los datos de los demas
    editado = azul["conflictos"].iloc[:1]
    total = pf.reemplazar(d["conflictos"], azul["conflictos"], editado)
    assert len(total) == len(d["conflictos"]) - len(azul["conflictos"]) + 1
    res = pf.resumen(d, date(2026, 11, 7))
    assert len(res) == 3 and res["vencidos"].sum() == (
        registro.con_estado(d["registro"], date(2026, 11, 7))["estado"] == "Vencido").sum()
    centro, zoom = pf.encuadre(d["comunidades"]["lat"], d["comunidades"]["lon"])
    assert zoom < 6 < pf.encuadre(azul["comunidades"]["lat"], azul["comunidades"]["lon"])[1]


def test_anticipar_contexto_jugadas_tendencia():
    from compromisos import anticipar, riesgos as rg
    d = _datos_riesgo()
    ctx = anticipar.normalizar_contexto(pd.read_csv(EJEMPLO / "contexto_demo.csv"))
    p1 = d["P"].set_index("id").loc["P1"].copy()
    p1["id"] = "P1"
    args = (p1, d["PA"], d["A"], d["H"], d["conf"], d["reg"], d["hoy"])
    sin = rg.evaluar(*args)
    con = rg.evaluar(*args, contexto=ctx)
    assert con["puntos"] > sin["puntos"] and con["componentes"]
    # una denuncia de hace un año ya no pesa; un cambio de directiva en 4 meses si
    viejo = pd.DataFrame([dict(fecha="2025-10-01", comunidad="X", tipo="Denuncia policial", descripcion="a"),
                          dict(fecha="2027-03-01", comunidad="X", tipo="Cambio de directiva", descripcion="b")])
    v = anticipar.vigentes(anticipar.normalizar_contexto(viejo), "X", "", d["hoy"])
    assert list(v["tipo"]) == ["Cambio de directiva"]
    # doble discurso: dice en publico menos de lo que dice en privado
    p = rg.partes_con_postura(d["PA"][d["PA"]["proceso_id"] == "P1"], d["A"])
    assert p["doble_discurso"].any() and (p.loc[p["doble_discurso"], "postura_privada"] >
                                          p.loc[p["doble_discurso"], "postura"]).all()
    kw = dict(partes=d["PA"], A=d["A"], H=d["H"], conf=d["conf"], reg=d["reg"], hoy=d["hoy"], contexto=ctx)
    jug, comb = anticipar.mejores_jugadas(rg.evaluar, p1, con["partes"], con["puntos"], n=3, **kw)
    assert not jug.empty and (jug["baja"] > 0).all() and list(jug["baja"]) == sorted(jug["baja"], reverse=True)
    assert comb is None or comb < con["puntos"]
    bruto = registro.cargar(EJEMPLO / "registro_demo.csv")
    t = anticipar.tendencia(rg.evaluar, p1, d["PA"], d["A"], d["H"], d["conf"], bruto, d["hoy"], ctx)
    assert len(t) >= 6 and t.iloc[-1]["fecha"] == d["hoy"] and t.iloc[-1]["puntos"] == con["puntos"]
    assert anticipar.probabilidad(80) == "muy probable" and anticipar.probabilidad(10) == "poco probable"


def test_vencidos_por_prioridad_y_validacion():
    from compromisos import anticipar, gerencia
    hoy = date(2026, 11, 7)
    df = registro.con_estado(registro.cargar(EJEMPLO / "registro_demo.csv"), hoy)
    from compromisos import actores as ac, conflictos as cf
    A = ac.al_corte(ac.normalizar_actores(pd.read_csv(EJEMPLO / "actores_demo.csv")),
                    ac.normalizar_historial(pd.read_csv(EJEMPLO / "posturas_demo.csv")), hoy)
    poder = gerencia.poder_comunidades(A, cf.normalizar(pd.read_csv(EJEMPLO / "conflictos_demo.csv")), hoy)
    assert poder.iloc[0]["comunidad"] == "C.C. Pucará Alto" and poder.iloc[0]["nivel_poder"] == "alto"
    pr = gerencia.priorizar(df, hoy, poder)
    assert len(pr) == (df["estado"] == "Vencido").sum() and set(pr["prioridad"]) <= {1, 2, 3}
    assert list(pr["prioridad"]) == sorted(pr["prioridad"])  # la prioridad 1 primero
    # el mismo vencido pesa distinto segun el poder de la comunidad para paralizar
    assert gerencia.prioridad("alto", 10, poder=1) == 1 and gerencia.prioridad("alto", 10, poder=0) == 2
    assert gerencia.prioridad("medio", 10, poder=1) == 1 and gerencia.prioridad("bajo", 10, poder=0) == 3
    alto_pucara = pr[pr["comunidad"] == "C.C. Pucará Alto"]["prioridad"].min()
    assert alto_pucara == 1 and pr[pr["comunidad"] == "C.C. Qollpa Ccasa"]["prioridad"].min() >= 2
    p1 = pr[pr["prioridad"] == 1].iloc[0]
    assert "opositor" in p1["motivo_poder"]
    assert p1["atender_antes"] == hoy + __import__("datetime").timedelta(days=7)
    assert "P1" in gerencia.tabla_html(pr) and gerencia.figura_vencidos(pr, hoy).data
    # lo que no esta validado no sube el riesgo
    ctx = anticipar.normalizar_contexto(pd.DataFrame([
        dict(fecha="2026-11-01", comunidad="X", tipo="Denuncia policial", descripcion="a", validado=False)]))
    assert anticipar.por_validar(ctx) == 1 and anticipar.vigentes(ctx, "X", "", hoy).empty
    ctx.loc[0, "validado"] = True
    assert len(anticipar.vigentes(ctx, "X", "", hoy)) == 1


def test_modulos_por_cliente():
    from compromisos import modulos
    assert modulos.leer("temprana") == ["reunion", "actores", "riesgos"]
    assert modulos.leer("riesgos, actores") == ["reunion", "actores", "riesgos"]  # la captura va siempre
    assert modulos.leer("") is None and modulos.leer("inventado") == ["reunion"]
    assert modulos.leer("corporativo") == list(modulos.MODULOS)
    assert modulos.paquete_de(["actores", "riesgos"]) == "temprana"


def test_ruta_para_bajar_el_riesgo():
    from compromisos import anticipar, riesgos as rg, ruta
    d = _datos_riesgo()
    ctx = anticipar.normalizar_contexto(pd.read_csv(EJEMPLO / "contexto_demo.csv"))
    p1 = d["P"].set_index("id").loc["P1"].copy()
    p1["id"] = "P1"
    kw = dict(partes=d["PA"], A=d["A"], H=d["H"], conf=d["conf"], reg=d["reg"], hoy=d["hoy"], contexto=ctx)
    base = rg.evaluar(p1, **kw)
    rt = ruta.ruta(rg.evaluar, p1, base["partes"], base["puntos"], pasos=6,
                   puentes_de=lambda n: rg.puentes(n, d["A"], d["R"]), **kw)
    assert len(rt) >= 3 and (rt["baja"] > 0).all()
    assert list(rt["riesgo"]) == sorted(rt["riesgo"], reverse=True)  # cada paso baja el riesgo
    assert rt["mes_acum"].is_monotonic_increasing and rt["como"].str.len().min() > 20
    assert ruta.meses_paso(-2, False, "Agravio antiguo") == 4 and ruta.meses_paso(-1, True) == 1
    assert ruta.figura_ruta(rt, base["puntos"]).data


RSS_EJEMPLO = """<?xml version="1.0"?><rss><channel>
<item><title>Comuneros de Pucará anuncian paro por el agua - Diario Regional</title><link>https://ejemplo.pe/1</link>
<pubDate>Fri, 06 Nov 2026 10:00:00 GMT</pubDate><source url="https://ejemplo.pe">Diario Regional</source>
<description>Exigen monitoreo del manante</description></item>
<item><title>JNE convoca elecciones municipales complementarias en Apurímac - Andina</title><link>https://ejemplo.pe/2</link>
<pubDate>Thu, 05 Nov 2026 10:00:00 GMT</pubDate><source url="https://andina.pe">Andina</source></item>
<item><title>Sube el precio del cobre - Medio Nacional</title><link>https://ejemplo.pe/3</link>
<pubDate>Thu, 05 Nov 2026 10:00:00 GMT</pubDate><source url="https://x.pe">Medio Nacional</source></item>
<item><title>Noticia vieja - X</title><link>https://ejemplo.pe/4</link><pubDate>Thu, 01 Jan 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_noticias_del_dia():
    from compromisos import anticipar, noticias, portafolio as pf
    d = pf.cargar_demo(EJEMPLO)
    uma = "Unidad Minera Andina (Apurímac)"
    hoy = date(2026, 11, 7)
    lug = noticias.lugares(uma, d["comunidades"], d["proyectos"])
    assert lug["region"] == ["Apurímac"] and "Pucará Alto" in lug["comunidades"]
    assert any("elecciones" in q for q in noticias.consultas(lug))
    n = noticias.buscar(uma, d["comunidades"], d["proyectos"], hoy=hoy, bajar=lambda u: RSS_EJEMPLO.encode())
    assert len(n) == 3  # sin repetidas ni viejas
    paro = n.iloc[0]
    assert paro["titulo"].startswith("Comuneros de Pucará") and paro["alerta"] == 3 and paro["alcance"] == "Local"
    assert paro["medio"] == "Diario Regional" and not paro["titulo"].endswith("Diario Regional")
    elec = n[n["titulo"].str.contains("JNE")].iloc[0]
    assert elec["tema"] == "Político y electoral" and elec["tipo_contexto"] == "Elecciones o cambio de autoridades"
    assert n[n["titulo"].str.contains("cobre")].iloc[0]["tema"] == "Económico"
    ctx = anticipar.normalizar_contexto(noticias.a_contexto(n, d["comunidades"]), d["comunidades"])
    assert (~ctx["validado"]).all() and ctx["enlace"].str.startswith("https").all()
    assert anticipar.vigentes(ctx, "C.C. Pucará Alto", uma, hoy).empty  # por validar: no suma al riesgo
    assert noticias.buscar(uma, d["comunidades"], hoy=hoy, bajar=lambda u: None).empty  # sin internet no rompe

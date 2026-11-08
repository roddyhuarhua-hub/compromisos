"""Agrega a los datos de ejemplo lo que pidieron los gerentes entrevistados (docs/research/):

- contexto: denuncias ambientales, comerciales o policiales, cambios de directiva, normas en debate y
  riesgos de seguridad (datos/ejemplo/contexto_demo.csv y exploracion/contexto.csv);
- actores: postura publica distinta de la privada e interes de fondo;
- compromisos que esperan una entrega de la otra parte (columna depende_de).

Todo es ficticio. Se puede correr varias veces: deja el mismo resultado.
    python scripts/enriquecer_demo.py
"""
from pathlib import Path

import pandas as pd

EJ = Path(__file__).resolve().parents[1] / "datos" / "ejemplo"
EX = EJ / "exploracion"
UMA = "Unidad Minera Andina (Apurímac)"

CONTEXTO_UMA = [
    ("2026-10-28", "", "C.C. Pucará Alto", "Denuncia ambiental",
     "Medio ambiente denunció a un comunero por arrojar desmonte al río; la comunidad envió una carta de reclamo "
     "y suspendió las encuestas del estudio ambiental", 3),
    ("2027-03-15", "", "C.C. Pucará Alto", "Cambio de directiva",
     "Elección de la nueva junta directiva comunal: la actual no quiere decidir la servidumbre antes", 2),
    ("2026-09-20", "", "C.C. Llacctapampa", "Denuncia comercial",
     "El área comercial denunció la entrega de mineral adulterado por un grupo de mineros artesanales", 2),
    ("2026-10-10", UMA, "", "Norma o política en debate",
     "Proyecto de ley sobre servidumbres mineras en debate en el Congreso", 1),
    # aun sin validar: no sube el riesgo hasta que el equipo lo confirme
    ("2026-11-05", "", "C.C. Pucará Alto", "Otro detonante",
     "Una radio local informa que dirigentes de fuera convocarían un paro regional", 2, "Radio local (ejemplo)", False),
]
CONTEXTO_EX = [
    ("2027-02-20", "", "C.C. Sallalli", "Cambio de directiva",
     "Renovación de la directiva comunal; la nueva junta decidirá el acuerdo de uso superficial", 2),
    ("2026-10-02", "", "C.C. Huayrapata", "Riesgo de seguridad",
     "Las rondas restringen el paso del personal de la empresa por la ruta principal", 3),
    ("2026-08-30", "", "C.C. Quinuamayo", "Denuncia policial",
     "Denuncia policial tras un enfrentamiento en el acceso a las plataformas", 2),
]
# nombre: (postura publica o None, interes de fondo)
ACTORES = {
    "Melquiades Mamani": (None, "Busca la reelección en marzo: necesita mostrar un logro visible (agua o empleo) "
                                "antes de comprometerse con la servidumbre"),
    "Prof. Teodoro Llamocca": (None, "Agravio antiguo: en una gestión anterior la empresa ofreció aulas que nunca "
                                     "llegaron; es un tema de reconocimiento más que de dinero"),
    "Benedicta Ccoyllo": (-1, "En privado acepta la servidumbre si se respeta su parcela, pero en asamblea no se "
                              "atreve a contradecir al Frente de Defensa"),
    "Primitiva Soncco": (None, "Las rondas reclaman ser parte de la comisión negociadora"),
    "Teófilo Ccahuana": (-1, "Apoya el proyecto en reuniones privadas; en público teme quedar como «vendido»"),
    "Justino Pariona": (0, "Favorable, pero no lo dice en asamblea hasta ver empleo para los jóvenes"),
    "Hipólito Ayala": (None, "Termina su mandato en febrero y no quiere cargar con la decisión"),
    "Segundo Chilón": (None, "Su liderazgo en la central de rondas depende de mantenerse firme frente a la empresa"),
}
# palabra clave en la descripcion -> lo que se espera de la otra parte
DEPENDE = {
    "inspección técnica de la ANA": "Que la comunidad entregue el padrón de usuarios del manante",
    "trocha carrozable": "Que la comunidad entregue el estudio de suelo y el permiso ambiental del tramo",
    "padrón": "Que la directiva valide el padrón en asamblea",
}


def contexto(filas, ruta):
    """Cada fila: fecha, proyecto, comunidad, tipo, descripcion, intensidad[, fuente, validado]."""
    base = ("Informe semanal (ejemplo)", True)
    filas = [tuple(f) + base[len(f) - 6:] for f in filas]
    pd.DataFrame(filas, columns=["fecha", "proyecto", "comunidad", "tipo", "descripcion", "intensidad", "fuente",
                                 "validado"]).assign(enlace="").to_csv(ruta, index=False)


def actores(ruta):
    a = pd.read_csv(ruta, dtype=str, keep_default_na=False)
    a["postura_publica"] = a["nombre"].map(lambda n: "" if ACTORES.get(n, (None,))[0] is None
                                           else str(ACTORES[n][0]))
    a["interes_fondo"] = a["nombre"].map(lambda n: ACTORES.get(n, (None, ""))[1])
    a.to_csv(ruta, index=False)


def registro(ruta):
    r = pd.read_csv(ruta, dtype=str, keep_default_na=False)
    r["depende_de"] = ""
    for clave, texto in DEPENDE.items():
        m = r["descripcion"].str.contains(clave, case=False, regex=False) & (r["cumplido"].str.lower() != "true")
        r.loc[m, "depende_de"] = texto
    r.to_csv(ruta, index=False)


if __name__ == "__main__":
    contexto(CONTEXTO_UMA, EJ / "contexto_demo.csv")
    contexto(CONTEXTO_EX, EX / "contexto.csv")
    for ruta in (EJ / "actores_demo.csv", EX / "actores.csv"):
        actores(ruta)
    for ruta in (EJ / "registro_demo.csv", EX / "registro.csv"):
        registro(ruta)
    print("Datos de ejemplo enriquecidos.")

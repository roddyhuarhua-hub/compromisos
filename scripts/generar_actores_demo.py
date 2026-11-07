"""Genera el mapeo de actores SINTETICO de la demo:

- datos/ejemplo/actores_demo.csv     : ~45 actores (comunidades, Estado, empresa, sociedad civil)
- datos/ejemplo/relaciones_demo.csv  : ~65 relaciones entre actores
- datos/ejemplo/posturas_demo.csv    : historial de posturas por reunion (mapeo dinamico)

Todas las personas y organizaciones son ficticias. Uso:
    python scripts/generar_actores_demo.py
"""
from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

random.seed(2026)
SALIDA = Path(__file__).resolve().parents[1] / "datos" / "ejemplo"
comunidades = pd.read_csv(SALIDA / "comunidades.csv")

# postura promedio de cada comunidad hacia la empresa (coherente con su semaforo)
POSTURA_BASE = {
    "C.C. Pucará Alto": -1.4, "C.C. Llacctapampa": -0.8, "C.C. Santa Rosa de Ccochapampa": -0.6,
    "C.C. Tambo Real": 0.0, "C.C. Antaccasa": 0.6, "C.C. Qollpa Ccasa": 0.2, "C.C. Huancarani": 1.2,
}
NOMBRES = ["Julián", "Marta", "Teófilo", "Rosa", "Hilario", "Celestina", "Fortunato", "Gregoria", "Saturnino",
           "Epifanía", "Valentín", "Justina", "Leoncio", "Primitiva", "Eusebio", "Florencia", "Melquiades",
           "Dionisia", "Crisóstomo", "Benedicta", "Anselmo", "Feliciana", "Policarpo", "Victoria", "Severino",
           "Agripina", "Tiburcio", "Natividad"]
APELLIDOS = ["Quispe", "Ccahuana", "Huamaní", "Mamani", "Condori", "Huillca", "Puma", "Ccorahua", "Taipe",
             "Sullca", "Chalco", "Cusihuamán", "Yupanqui", "Ayquipa", "Llamocca", "Pillaca", "Huarcaya",
             "Ccoyllo", "Soncco", "Anccasi"]
ROLES = [  # cargo, tipo, organizacion, influencia
    ("Presidente comunal", "Dirigente comunal", "Junta directiva comunal", 5),
    ("Presidenta del comité de regantes", "Organización de base", "Comité de regantes", 4),
    ("Presidente de rondas campesinas", "Organización de base", "Rondas campesinas", 4),
    ("Presidenta del Vaso de Leche", "Organización de base", "Comité del Vaso de Leche", 2),
]


def postura(base: float) -> int:
    return int(max(-2, min(2, round(random.gauss(base, 0.7)))))


actores, relaciones = [], []
usados = set()


def nombre() -> str:
    while True:
        n = f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)}"
        if n not in usados:
            usados.add(n)
            return n


def actor(nom, tipo, cargo, org, com, post, infl):
    actores.append(dict(nombre=nom, tipo=tipo, cargo=cargo, organizacion=org, comunidad=com,
                        postura=post, influencia=infl, fuente="sintético"))
    return nom


def rel(a, b, tipo, desc=""):
    relaciones.append(dict(origen=a, destino=b, tipo=tipo, descripcion=desc, fuente="sintético"))


# --- empresa y Estado
gerente = actor("Ricardo Valdivia", "Empresa", "Gerente de Relaciones Comunitarias", "Minera Andina S.A.C.", "", 2, 4)
relacionistas = {
    "Pucará": actor("Luis Paredes", "Empresa", "Superintendente de RR.CC. zona norte", "Minera Andina S.A.C.", "", 2, 4),
    "Chalhuanca": actor("Carla Mendoza", "Empresa", "Relacionista comunitaria zona oeste", "Minera Andina S.A.C.", "", 2, 3),
    "Antabamba": actor("Óscar Rivas", "Empresa", "Relacionista comunitario zona sur", "Minera Andina S.A.C.", "", 2, 3),
}
for r in relacionistas.values():
    rel(gerente, r, "Influye en", "Dirige el equipo de campo")
alcaldes = {d: actor(f"Alcalde de {d}", "Autoridad local", "Alcalde distrital", f"Municipalidad Distrital de {d}",
                     "", random.choice([-1, 0, 1]), 4) for d in comunidades["distrito"].unique()}
ana = actor("Autoridad Local del Agua", "Estado", "", "ANA", "", 0, 3)
oefa = actor("OEFA - Oficina Desconcentrada", "Estado", "", "OEFA", "", 0, 3)
defensoria = actor("Defensoría del Pueblo", "Estado", "Oficina defensorial", "Defensoría del Pueblo", "", 0, 4)
gore = actor("Gobierno Regional", "Estado", "Gerencia de Recursos Naturales", "Gobierno Regional", "", 1, 3)
frente = actor("Frente de Defensa del Agua y la Vida", "Organización de base", "Coordinadora interdistrital",
               "Frente de Defensa", "", -2, 5)
ong = actor("ONG Agua y Territorio", "ONG / Iglesia", "Equipo legal", "ONG Agua y Territorio", "", -1, 3)
parroquia = actor("Parroquia San Pedro", "ONG / Iglesia", "Párroco", "Iglesia católica", "", 0, 3)
radio = actor("Radio Sonqo", "Medio de comunicación", "Programa matinal en quechua", "Radio local", "", -1, 3)
rel(gerente, defensoria, "Negocia con", "Mesa de diálogo con observación defensorial")
rel(ana, oefa, "Alianza", "Monitoreos conjuntos")
rel(frente, ong, "Alianza", "Asesoría legal al Frente")
rel(frente, radio, "Influye en", "Comunicados y entrevistas")
rel(gore, gerente, "Negocia con", "Convenio de obras por impuestos")

# --- comunidades
presidentes = {}
for _, c in comunidades.iterrows():
    com, dist = c["comunidad"], c["distrito"]
    base = POSTURA_BASE.get(com, 0)
    miembros = []
    for cargo, tipo, org, infl in ROLES:
        if cargo.startswith("Presidenta del Vaso") and random.random() < 0.4:
            continue
        post = int(max(-2, min(2, round(base)))) if cargo == "Presidente comunal" else postura(base)
        n = actor(nombre(), tipo, cargo, f"{org} {com.replace('C.C. ', '')}", com, post, infl)
        miembros.append(n)
    pres = miembros[0]
    presidentes[com] = pres
    for m in miembros[1:]:
        rel(pres, m, "Representa a" if random.random() < 0.5 else "Alianza", "Dirigencia de la misma comunidad")
    rel(relacionistas[dist], pres, "Negocia con", "Interlocutor principal de la empresa")
    rel(alcaldes[dist], pres, "Negocia con" if base >= 0 else "Alianza",
        "Coordinación distrital" if base >= 0 else "Respaldo político a sus demandas")
    if base <= -0.5:  # comunidades criticas: el Frente y la ONG estan presentes
        rel(frente, pres, "Influye en", "Convoca a movilizaciones")
        rel(ong, miembros[1], "Influye en", "Asesoría en derechos de agua")
        rel(pres, relacionistas[dist], "Conflicto", "Compromisos incumplidos")
    if base >= 0.5:
        rel(pres, gerente, "Alianza", "Convenio marco vigente")
    if random.random() < 0.5:
        rel(parroquia, pres, "Influye en", "Facilita espacios de diálogo")
    if random.random() < 0.4:
        rel(radio, pres, "Influye en", "Difunde sus pronunciamientos")

# --- relaciones entre comunidades y caserios
P = presidentes
rel(P["C.C. Pucará Alto"], P["C.C. Llacctapampa"], "Conflicto", "Disputa de linderos en la zona de Ccollpa")
rel(P["C.C. Pucará Alto"], P["C.C. Santa Rosa de Ccochapampa"], "Alianza", "Comparten la cuenca y la demanda por agua")
rel(P["C.C. Santa Rosa de Ccochapampa"], P["C.C. Llacctapampa"], "Parentesco", "Familias emparentadas entre caseríos")
rel(P["C.C. Huancarani"], P["C.C. Tambo Real"], "Alianza", "Faena conjunta del canal")
rel(P["C.C. Antaccasa"], P["C.C. Qollpa Ccasa"], "Parentesco", "Dirigentes cuñados")
rel(P["C.C. Qollpa Ccasa"], P["C.C. Pucará Alto"], "Influye en", "Apoya el reclamo por el manante")
rel(P["C.C. Tambo Real"], P["C.C. Santa Rosa de Ccochapampa"], "Negocia con", "Uso compartido de pastos")

# --- historial de posturas: cada reunion de la comunidad deja una "foto" de la postura de sus actores
registro = pd.read_csv(SALIDA / "registro_demo.csv")
reuniones = (registro[["comunidad", "reunion", "fecha_reunion"]].drop_duplicates()
             .sort_values("fecha_reunion"))
# trayectoria del presidente comunal en cada reunion (la historia que cuenta la demo)
TRAYECTORIA = {
    "C.C. Antaccasa": [2, 1, 1],          # aliado que se enfria tras retrasos
    "C.C. Llacctapampa": [0, -1, -1],     # se endurece por el conflicto de linderos
    "C.C. Pucará Alto": [0, -2, -1],      # crisis del agua; mejora leve con la mesa de trabajo
    "C.C. Huancarani": [0, 1, 1],         # convenio marco: pasa a favorable
    "C.C. Santa Rosa de Ccochapampa": [0, 0, -1],
    "C.C. Tambo Real": [1, 0, 0],
    "C.C. Qollpa Ccasa": [-1, 0, 0],
}
BAJA = ["Molestia por el retraso de la obra comprometida", "Denuncia que no se cumplió lo acordado en el acta",
        "Se suma al pronunciamiento del Frente de Defensa", "Exige monitoreo independiente del agua",
        "Cuestiona la contratación de mano de obra local"]
SUBE = ["Valora la entrega de la obra comprometida", "Reconoce avances en la mesa de trabajo",
        "Agradece la contratación de comuneros", "Acepta el monitoreo participativo",
        "Respalda el convenio marco en asamblea"]
historial = []
por_nombre = {a["nombre"]: a for a in actores}
for com, grupo in reuniones.groupby("comunidad"):
    fechas = grupo.to_dict("records")
    for a in [x for x in actores if x["comunidad"] == com]:
        n = len(fechas)
        if a["cargo"] == "Presidente comunal":
            tray = TRAYECTORIA[com][-n:]
            a["postura"] = tray[-1]
        else:  # camino aleatorio hacia atras desde la postura actual
            tray = [a["postura"]]
            for _ in range(n - 1):
                tray.insert(0, int(max(-2, min(2, tray[0] + random.choice([0, 0, 0, 1, -1])))))
        previo = None
        for f, post in zip(fechas, tray):
            if previo is None:
                ev = "Primera identificación en reunión"
            elif post < previo:
                ev = random.choice(BAJA)
            elif post > previo:
                ev = random.choice(SUBE)
            else:
                ev = "Mantiene su posición"
            historial.append(dict(nombre=a["nombre"], fecha=f["fecha_reunion"], reunion=f["reunion"], comunidad=com,
                                  postura=post, influencia=a["influencia"], evidencia=ev))
            previo = post
# actores externos: primera y ultima reunion, con algunos cambios relevantes
primera, ultima = reuniones["fecha_reunion"].min(), reuniones["fecha_reunion"].max()
CAMBIO_EXTERNO = {"Alcalde de Pucará": (0, "Respalda públicamente las demandas por agua"),
                  "Parroquia San Pedro": (1, "Se distancia tras los incumplimientos"),
                  "Gobierno Regional": (0, "Firma convenio de obras por impuestos")}
for a in [x for x in actores if not x["comunidad"]]:
    ini = CAMBIO_EXTERNO.get(a["nombre"], (a["postura"], ""))[0]
    ev = CAMBIO_EXTERNO.get(a["nombre"], (0, "Mantiene su posición"))[1]
    historial.append(dict(nombre=a["nombre"], fecha=primera, reunion="Mapeo inicial de actores", comunidad="",
                          postura=ini, influencia=a["influencia"], evidencia="Primera identificación"))
    historial.append(dict(nombre=a["nombre"], fecha=ultima, reunion="Actualización del mapeo", comunidad="",
                          postura=a["postura"], influencia=a["influencia"], evidencia=ev))

pd.DataFrame(actores).to_csv(SALIDA / "actores_demo.csv", index=False)
pd.DataFrame(relaciones).to_csv(SALIDA / "relaciones_demo.csv", index=False)
pd.DataFrame(historial).sort_values(["fecha", "nombre"]).to_csv(SALIDA / "posturas_demo.csv", index=False)
print(f"{len(actores)} actores, {len(relaciones)} relaciones, {len(historial)} registros de postura -> {SALIDA}")

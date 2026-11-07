"""Genera el historial SINTETICO de conflictividad de la demo:

- datos/ejemplo/conflictos_demo.csv : ~35 eventos 2019-2026 (bloqueos de via, paros, tomas, marchas...)

La estructura sigue los campos de los reportes de conflictos sociales de la Defensoria del Pueblo
(tipo de medida, lugar, actores, demanda, duracion, violencia, desenlace). Todos los hechos, lugares y
personas son ficticios. Uso:
    python scripts/generar_conflictos_demo.py
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

random.seed(1979)
SALIDA = Path(__file__).resolve().parents[1] / "datos" / "ejemplo"
actores = pd.read_csv(SALIDA / "actores_demo.csv")
pres = actores[actores["cargo"] == "Presidente comunal"].set_index("comunidad")["nombre"].to_dict()

# lugares ficticios (cerca de las comunidades de la demo)
LUGARES = {
    "Km 42 de la vía Chalhuanca–Pucará": (-14.17, -72.88, "C.C. Santa Rosa de Ccochapampa"),
    "Puente Ccollpa": (-14.085, -72.505, "C.C. Llacctapampa"),
    "Portón principal del campamento minero": (-14.10, -72.60, "C.C. Pucará Alto"),
    "Plaza de Armas de Pucará": (-14.035, -72.565, "C.C. Pucará Alto"),
    "Desvío a Llacctapampa (vía de acceso a mina)": (-14.135, -72.49, "C.C. Llacctapampa"),
    "Reservorio de Santa Rosa": (-14.215, -72.72, "C.C. Santa Rosa de Ccochapampa"),
    "Km 18 del corredor minero (Antabamba)": (-13.995, -72.665, "C.C. Antaccasa"),
    "Plaza de Chalhuanca": (-14.28, -73.17, "C.C. Huancarani"),
    "Bocatoma del canal de Tambo Real": (-14.16, -73.03, "C.C. Tambo Real"),
    "Cerro Qollpa (zona de exploración)": (-14.345, -72.905, "C.C. Qollpa Ccasa"),
    "Manante Ccollpa": (-14.07, -72.53, "C.C. Pucará Alto"),
}

# hechos guionizados: la historia que cuenta la demo
GUION = [
    # fecha, tipo, titulo, lugar, convocantes, demanda, tema, dias, participantes, intensidad, violencia, desenlace
    ("2019-05-14", "Pronunciamiento / ultimátum", "Comunidades exigen estudio hidrogeológico del manante",
     "Plaza de Armas de Pucará", "Frente de Defensa del Agua y la Vida", "Estudio independiente del manante Ccollpa",
     "Agua", 1, 300, "baja", False, "Mesa de diálogo"),
    ("2019-08-02", "Bloqueo de vía", "Bloqueo del corredor minero por empleo local",
     "Km 18 del corredor minero (Antabamba)", "Rondas campesinas de Antaccasa", "30 % de mano de obra local",
     "Empleo local", 3, 250, "media", False, "Acta de acuerdos"),
    ("2020-02-10", "Movilización / marcha", "Marcha por el agua en Pucará",
     "Plaza de Armas de Pucará", "Frente de Defensa del Agua y la Vida", "Monitoreo participativo del agua",
     "Agua", 1, 1200, "media", False, "Mesa de diálogo"),
    ("2021-06-21", "Bloqueo de vía", "Bloqueo del puente Ccollpa",
     "Puente Ccollpa", pres.get("C.C. Llacctapampa", ""), "Respeto de linderos y compensación por servidumbre",
     "Tierras", 4, 400, "alta", True, "Intervención policial"),
    ("2022-03-09", "Toma de instalaciones", "Toma del portón principal del campamento",
     "Portón principal del campamento minero", "Frente de Defensa del Agua y la Vida",
     "Reparación por la desaparición del manante", "Agua", 2, 600, "alta", True, "Mesa de diálogo"),
    ("2022-11-15", "Paralización / paro", "Paro de 72 horas en el distrito de Pucará",
     "Plaza de Armas de Pucará", "Frente de Defensa y comunidades de Pucará", "Cumplimiento del acta de 2022",
     "Agua", 3, 2000, "alta", False, "Acta de acuerdos"),
    ("2023-07-04", "Denuncia o queja formal", "Denuncia ante OEFA por turbidez en el canal",
     "Bocatoma del canal de Tambo Real", "Comité de regantes Tambo Real", "Fiscalización ambiental del canal",
     "Ambiente", 0, None, "baja", False, "Otro"),
    ("2024-04-17", "Bloqueo de vía", "Bloqueo de la vía Chalhuanca–Pucará",
     "Km 42 de la vía Chalhuanca–Pucará", "Comunidades de Pucará y Santa Rosa",
     "Cumplimiento de obras de agua y salud comprometidas", "Infraestructura", 6, 800, "alta", False,
     "Mesa de diálogo"),
    ("2025-09-22", "Paralización / paro", "Paro indefinido: 12 días de bloqueo del corredor",
     "Km 42 de la vía Chalhuanca–Pucará", "Frente de Defensa del Agua y la Vida",
     "Cumplimiento de compromisos vencidos (reservorios, empleo, salud)", "Agua", 12, 3500, "alta", True,
     "Declaratoria de emergencia"),
    ("2026-03-12", "Pronunciamiento / ultimátum", "Ultimátum de 30 días por el reservorio",
     "Reservorio de Santa Rosa", pres.get("C.C. Santa Rosa de Ccochapampa", ""),
     "Revegetación y reservorio comprometidos", "Infraestructura", 1, 150, "media", False, "Mesa de diálogo"),
    ("2026-09-30", "Bloqueo de vía", "Bloqueo del desvío a Llacctapampa",
     "Desvío a Llacctapampa (vía de acceso a mina)", pres.get("C.C. Llacctapampa", ""),
     "Contratación de mano de obra local no calificada", "Empleo local", 3, 350, "media", False, "En curso"),
]

TIPOS_MENORES = [("Plantón", "Plantón frente a la oficina de relaciones comunitarias"),
                 ("Movilización / marcha", "Marcha pacífica de comuneros"),
                 ("Pronunciamiento / ultimátum", "Pronunciamiento en asamblea comunal"),
                 ("Denuncia o queja formal", "Queja formal ante la Defensoría del Pueblo"),
                 ("Bloqueo de vía", "Bloqueo parcial de vía por horas")]
DEMANDAS = [("Agua", "Abastecimiento de agua y monitoreo del manante"),
            ("Empleo local", "Prioridad en la contratación de comuneros"),
            ("Salud", "Campaña de salud integral comprometida"),
            ("Infraestructura", "Obras comprometidas en el convenio"),
            ("Tierras", "Compensación por uso de terrenos comunales"),
            ("Ambiente", "Polvo y ruido por el tránsito de camiones")]
PESO_COM = {"C.C. Pucará Alto": 5, "C.C. Llacctapampa": 4, "C.C. Santa Rosa de Ccochapampa": 3,
            "C.C. Tambo Real": 2, "C.C. Qollpa Ccasa": 2, "C.C. Antaccasa": 1, "C.C. Huancarani": 1}

eventos = []
for f, tipo, titulo, lugar, conv, dem, tema, dias, part, inten, viol, des in GUION:
    lat, lon, com = LUGARES[lugar]
    if conv.startswith("Frente de Defensa"):
        com = "C.C. Pucará Alto"  # el Frente nace y se organiza en Pucará Alto
    eventos.append(dict(fecha=f, tipo=tipo, titulo=titulo, lugar=lugar, comunidad=com, lat=lat, lon=lon,
                        convocantes=conv, demanda=dem, tema=tema, duracion_dias=dias, participantes=part,
                        intensidad=inten, hubo_violencia=viol, desenlace=des, fuente="sintético"))

inicio = date(2019, 1, 1)
for _ in range(24):  # hechos menores repartidos en el tiempo
    com = random.choices(list(PESO_COM), weights=list(PESO_COM.values()))[0]
    lugares = [k for k, v in LUGARES.items() if v[2] == com]
    lugar = random.choice(lugares)
    lat, lon, _ = LUGARES[lugar]
    tipo, titulo = random.choice(TIPOS_MENORES)
    tema, dem = random.choice(DEMANDAS)
    f = inicio + timedelta(days=random.randint(0, 2860))
    dias = 1 if tipo != "Denuncia o queja formal" else 0
    eventos.append(dict(
        fecha=f.isoformat(), tipo=tipo, titulo=f"{titulo} ({com.replace('C.C. ', '')})", lugar=lugar, comunidad=com,
        lat=lat + random.uniform(-0.006, 0.006), lon=lon + random.uniform(-0.006, 0.006),
        convocantes=random.choice([pres.get(com, ""), f"Junta directiva comunal {com.replace('C.C. ', '')}",
                                   "Frente de Defensa del Agua y la Vida"]),
        demanda=dem, tema=tema, duracion_dias=dias, participantes=random.choice([40, 60, 80, 120, 150, 200]),
        intensidad=random.choice(["baja", "baja", "media"]), hubo_violencia=False,
        desenlace=random.choice(["Mesa de diálogo", "Levantamiento sin acuerdo", "Acta de acuerdos", "Otro"]),
        fuente="sintético"))

df = pd.DataFrame(eventos).sort_values("fecha").reset_index(drop=True)
df.to_csv(SALIDA / "conflictos_demo.csv", index=False)
print(f"{len(df)} eventos de conflicto -> {SALIDA / 'conflictos_demo.csv'}")

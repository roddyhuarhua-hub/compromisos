"""Genera datos/ejemplo/registro_demo.csv: un registro SINTETICO de compromisos de
6 reuniones ficticias (2025-2026) para que el tablero tenga historia en la demo.

Comunidades, empresa y personas son inventadas. Uso:
    python scripts/generar_registro_demo.py
"""
from __future__ import annotations

import random
import uuid
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

random.seed(204)
HOY = date(2026, 11, 6)

REUNIONES = [
    ("Mesa de diálogo Pucará Alto", date(2025, 6, 12), "C.C. Pucará Alto", "San Miguel", "Apurímac"),
    ("Taller de empleo local", date(2025, 10, 3), "C.C. Llacctapampa", "San Miguel", "Apurímac"),
    ("Asamblea informativa EIA", date(2026, 1, 20), "C.C. Huancarani", "Chalhuanca", "Apurímac"),
    ("Mesa de trabajo agua", date(2026, 3, 15), "C.C. Pucará Alto", "San Miguel", "Apurímac"),
    ("Comité de monitoreo", date(2026, 7, 8), "C.C. Llacctapampa", "San Miguel", "Apurímac"),
    ("Reunión con rondas campesinas", date(2026, 9, 25), "C.C. Huancarani", "Chalhuanca", "Apurímac"),
]

PLANTILLAS = [
    ("Realizar monitoreo participativo de agua en el manante", "Empresa", "Monitoreo", "alto"),
    ("Entregar resultados del monitoreo en asamblea", "Empresa", "Agua", "alto"),
    ("Contratar mano de obra local no calificada (30%)", "Empresa", "Empleo local", "alto"),
    ("Capacitar a 20 jóvenes en operación de maquinaria", "Empresa", "Educación", "medio"),
    ("Financiar proyecto de cuyes mejorados", "Empresa", "Proyectos productivos", "medio"),
    ("Mejorar trocha carrozable al anexo", "Estado", "Infraestructura", "medio"),
    ("Gestionar inspección de la ANA", "Estado", "Agua", "medio"),
    ("Incluir canal de riego en presupuesto participativo", "Estado", "Infraestructura", "medio"),
    ("Campaña de salud con Diresa", "Estado", "Salud", "alto"),
    ("Entregar padrón de comuneros", "Comunidad", "Empleo local", "bajo"),
    ("Facilitar acceso a la zona de monitoreo", "Comunidad", "Monitoreo", "bajo"),
    ("Difundir cronograma de obras en quechua", "Empresa", "Comunicación", "bajo"),
    ("Revegetar zona afectada por el depósito", "Empresa", "Ambiente", "alto"),
    ("Saneamiento de linderos comunales", "Estado", "Tierras", "alto"),
]

filas = []
for nombre, fecha, comunidad, distrito, region in REUNIONES:
    for desc, resp, tema, riesgo in random.sample(PLANTILLAS, k=random.randint(4, 6)):
        limite = fecha + timedelta(days=random.choice([15, 30, 45, 60, 90, 120, 180]))
        if random.random() < 0.1:
            limite = None
        vencido_ya = limite is not None and limite < HOY
        # Mas antiguo = mas probable que se haya cumplido; la empresa cumple algo menos en agua.
        p = 0.65 if vencido_ya else 0.1
        if tema in ("Agua", "Monitoreo", "Salud"):
            p -= 0.25
        cumplido = random.random() < p
        f_cumpl = None
        if cumplido:
            base = limite or fecha + timedelta(days=60)
            f_cumpl = min(HOY, base + timedelta(days=random.randint(-10, 25)))
        filas.append({
            "id": uuid.UUID(int=random.getrandbits(128)).hex[:8],
            "reunion": nombre, "fecha_reunion": fecha, "comunidad": comunidad,
            "distrito": distrito, "region": region, "descripcion": desc,
            "responsable": resp, "responsable_detalle": "", "beneficiario": comunidad,
            "tema": tema, "fecha_limite": limite, "riesgo_conflicto": riesgo,
            "cumplido": cumplido, "fecha_cumplimiento": f_cumpl, "cita_textual": "",
            "fuente": "sintético",
        })

salida = Path(__file__).resolve().parents[1] / "datos" / "ejemplo" / "registro_demo.csv"
pd.DataFrame(filas).to_csv(salida, index=False)
print(f"{len(filas)} compromisos -> {salida}")

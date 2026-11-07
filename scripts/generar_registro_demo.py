"""Genera los datos SINTETICOS de la demo:

- datos/ejemplo/comunidades.csv : 7 comunidades ficticias con coordenadas (zona altoandina del sur)
- datos/ejemplo/registro_demo.csv : ~100 compromisos de 19 reuniones (2025-2026)

Comunidades, empresa, personas y ubicaciones exactas son inventadas. Uso:
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
SALIDA = Path(__file__).resolve().parents[1] / "datos" / "ejemplo"

# nombre, distrito, lat, lon, familias, "cumplimiento" base (para que cada comunidad cuente una historia)
COMUNIDADES = [
    ("C.C. Pucará Alto", "Pucará", -14.05, -72.55, 180, 0.30),
    ("C.C. Llacctapampa", "Pucará", -14.12, -72.46, 95, 0.55),
    ("C.C. Huancarani", "Chalhuanca", -14.29, -73.20, 140, 0.75),
    ("C.C. Santa Rosa de Ccochapampa", "Pucará", -14.20, -72.70, 210, 0.45),
    ("C.C. Antaccasa", "Antabamba", -13.98, -72.62, 70, 0.85),
    ("C.C. Qollpa Ccasa", "Antabamba", -14.36, -72.93, 120, 0.60),
    ("C.C. Tambo Real", "Chalhuanca", -14.15, -73.05, 160, 0.65),
]

TIPOS_REUNION = ["Mesa de diálogo", "Mesa de trabajo agua", "Taller de empleo local",
                 "Asamblea informativa", "Comité de monitoreo", "Reunión con rondas campesinas"]

# descripcion, responsable, detalle, tema, riesgo
PLANTILLAS = [
    ("Realizar monitoreo participativo de agua en el manante", "Empresa", "Gerencia de Medio Ambiente", "Monitoreo", "alto"),
    ("Entregar resultados del monitoreo en asamblea, en castellano y quechua", "Empresa", "Relaciones Comunitarias", "Agua", "alto"),
    ("Contratar 30% de mano de obra local no calificada", "Empresa", "Recursos Humanos", "Empleo local", "alto"),
    ("Capacitar a 20 jóvenes en operación de maquinaria pesada", "Empresa", "Relaciones Comunitarias", "Educación", "medio"),
    ("Financiar proyecto de crianza de cuyes mejorados", "Empresa", "Desarrollo Social", "Proyectos productivos", "medio"),
    ("Instalar 2 reservorios de agua para riego", "Empresa", "Desarrollo Social", "Agua", "alto"),
    ("Mejorar trocha carrozable al anexo", "Estado", "Municipalidad Distrital", "Infraestructura", "medio"),
    ("Gestionar inspección técnica de la ANA", "Estado", "Municipalidad Distrital", "Agua", "medio"),
    ("Incluir canal de riego en el presupuesto participativo", "Estado", "Municipalidad Distrital", "Infraestructura", "medio"),
    ("Campaña de salud integral con la Diresa", "Estado", "Diresa / Posta de salud", "Salud", "alto"),
    ("Saneamiento físico-legal de linderos comunales", "Estado", "Dirección Regional Agraria", "Tierras", "alto"),
    ("Entregar padrón actualizado de comuneros", "Comunidad", "Junta directiva comunal", "Empleo local", "bajo"),
    ("Facilitar acceso a la zona de monitoreo", "Comunidad", "Junta directiva comunal", "Monitoreo", "bajo"),
    ("Designar 5 monitores ambientales comunales", "Comunidad", "Asamblea comunal", "Monitoreo", "bajo"),
    ("Difundir cronograma de obras por radio local en quechua", "Empresa", "Comunicaciones", "Comunicación", "bajo"),
    ("Revegetar 3 hectáreas afectadas por el depósito", "Empresa", "Gerencia de Medio Ambiente", "Ambiente", "alto"),
    ("Becas de estudio para 10 hijos de comuneros", "Empresa", "Desarrollo Social", "Educación", "medio"),
    ("Apoyo con maquinaria para limpieza de canales", "Empresa", "Operaciones", "Infraestructura", "medio"),
]

comunidades = pd.DataFrame(COMUNIDADES, columns=["comunidad", "distrito", "lat", "lon", "familias", "_base"])
comunidades.drop(columns="_base").assign(region="Apurímac", proyecto="Unidad Minera Andina (Apurímac)").to_csv(SALIDA / "comunidades.csv", index=False)

filas = []
inicio = date(2025, 1, 15)
fechas = [inicio + timedelta(days=int(i * 40 + random.randint(-8, 8))) for i in range(15)]
fechas += [date(2026, 9, 18), date(2026, 10, 9), date(2026, 10, 23), date(2026, 10, 30)]
for i, fecha in enumerate(sorted(fechas)):
    nom, dist, _, _, _, base = COMUNIDADES[i % len(COMUNIDADES)]
    tipo = random.choice(TIPOS_REUNION)
    for desc, resp, det, tema, riesgo in random.sample(PLANTILLAS, k=random.randint(4, 7)):
        limite = fecha + timedelta(days=random.choice([15, 30, 30, 45, 60, 90, 120, 180]))
        if random.random() < 0.07:
            limite = None
        exigible = limite is None or limite < HOY
        p = base if exigible else 0.08
        if resp == "Comunidad":
            p += 0.2
        if tema in ("Agua", "Monitoreo", "Salud"):
            p -= 0.15
        cumplido = random.random() < max(0.02, min(0.95, p))
        f_cumpl = None
        if cumplido:
            ref = limite or fecha + timedelta(days=60)
            f_cumpl = min(HOY, ref + timedelta(days=random.randint(-12, 30)))
        filas.append({
            "id": uuid.UUID(int=random.getrandbits(128)).hex[:8],
            "reunion": f"{tipo} {nom.replace('C.C. ', '')}", "fecha_reunion": fecha,
            "comunidad": nom, "distrito": dist, "region": "Apurímac", "descripcion": desc,
            "responsable": resp, "responsable_detalle": det, "beneficiario": nom,
            "tema": tema, "fecha_limite": limite, "riesgo_conflicto": riesgo,
            "cumplido": cumplido, "fecha_cumplimiento": f_cumpl, "cita_textual": "",
            "fuente": "sintético",
        })

pd.DataFrame(filas).to_csv(SALIDA / "registro_demo.csv", index=False)
print(f"{len(filas)} compromisos, {len(COMUNIDADES)} comunidades -> {SALIDA}")

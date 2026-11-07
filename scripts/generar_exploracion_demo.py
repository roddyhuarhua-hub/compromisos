"""Genera los datos SINTETICOS de dos proyectos de exploracion en otras regiones, para mostrar la vista
de portafolio (una empresa o consultora con varios proyectos sin relacion entre si):

- Proyecto de exploracion Qori Urqu (Ayacucho)
- Proyecto de exploracion Cerro Azul (Cajamarca)

Escribe en datos/ejemplo/exploracion/ los mismos archivos que la unidad minera de ejemplo (registro,
actores, relaciones, posturas, conflictos, procesos...). Todas las personas, comunidades y hechos son
ficticios. Uso:
    python scripts/generar_exploracion_demo.py
"""
from __future__ import annotations

import random
import uuid
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

random.seed(1207)
RAIZ = Path(__file__).resolve().parents[1] / "datos" / "ejemplo"
SALIDA = RAIZ / "exploracion"
SALIDA.mkdir(exist_ok=True)

QORI, AZUL = "Exploración Qori Urqu (Ayacucho)", "Exploración Cerro Azul (Cajamarca)"
COMUNIDADES = [  # comunidad, distrito, lat, lon, familias, region, proyecto
    ("C.C. Sallalli", "Puquio", -14.55, -74.30, 130, "Ayacucho", QORI),
    ("C.C. Uchuyccasa", "Puquio", -14.63, -74.18, 85, "Ayacucho", QORI),
    ("C.C. Ccollpapampa", "Chipao", -14.71, -74.36, 60, "Ayacucho", QORI),
    ("C.C. Huayrapata", "Bambamarca", -6.95, -78.45, 240, "Cajamarca", AZUL),
    ("C.C. Quinuamayo", "Bambamarca", -7.03, -78.37, 170, "Cajamarca", AZUL),
    ("C.C. Rumichaca", "Hualgayoc", -6.89, -78.55, 110, "Cajamarca", AZUL),
]
info = {c[0]: c for c in COMUNIDADES}

# ------------------------------------------------------------------ compromisos
TEMAS = {  # tema: (descripcion, responsable, detalle, riesgo)
    "Agua": [("Monitoreo participativo de manantiales cercanos a las plataformas", "Empresa", "Medio Ambiente", "alto"),
             ("Instalar piezómetros con veedores comunales", "Empresa", "Hidrogeología", "alto")],
    "Tierras": [("Pagar la compensación por uso superficial de las plataformas", "Empresa", "Tierras", "alto"),
                ("Delimitar en campo las áreas de uso superficial con la junta", "Empresa", "Tierras", "medio")],
    "Empleo local": [("Contratar comuneros como ayudantes de perforación por padrón", "Empresa", "Recursos Humanos", "alto"),
                     ("Capacitar a jóvenes en seguridad para trabajos de exploración", "Empresa", "Seguridad", "medio")],
    "Infraestructura": [("Mantener la trocha de acceso a la comunidad", "Empresa", "Operaciones", "medio"),
                        ("Gestionar el mejoramiento del local comunal", "Estado", "Municipalidad Distrital", "bajo")],
    "Comunicación": [("Informar en asamblea el avance de la campaña de perforación", "Empresa", "Relaciones Comunitarias", "medio"),
                     ("Instalar una oficina de información con atención semanal", "Empresa", "Relaciones Comunitarias", "bajo")],
    "Ambiente": [("Cerrar y revegetar las plataformas terminadas", "Empresa", "Medio Ambiente", "alto"),
                 ("Taller participativo sobre la DIA en quechua", "Empresa", "Medio Ambiente", "medio")],
    "Salud": [("Campaña de salud con la posta y la Diresa", "Estado", "Diresa / Posta de salud", "bajo")],
}
# comunidad: (reuniones, proporcion de vencidos) -> historia de cada ambito
PERFIL = {"C.C. Sallalli": (3, 0.45), "C.C. Uchuyccasa": (2, 0.15), "C.C. Ccollpapampa": (2, 0.1),
          "C.C. Huayrapata": (3, 0.55), "C.C. Quinuamayo": (3, 0.4), "C.C. Rumichaca": (2, 0.2)}
HOY = date(2026, 11, 7)
filas = []
for com, (n_reu, p_venc) in PERFIL.items():
    _, dist, _, _, _, reg, _ = info[com]
    for k in range(n_reu):
        f_reu = date(2025, 9, 1) + timedelta(days=150 * k + random.randint(0, 40))
        reunion = random.choice(["Asamblea comunal", "Reunión con la junta directiva", "Taller informativo"]) \
            + f" {com.replace('C.C. ', '')}"
        for tema in random.sample(list(TEMAS), 3):
            desc, resp, det, riesgo = random.choice(TEMAS[tema])
            limite = f_reu + timedelta(days=random.choice([30, 45, 60, 90, 120]))
            vencido = limite < HOY and random.random() < p_venc
            cumplido = limite < HOY and not vencido
            filas.append(dict(id=uuid.uuid4().hex[:8], reunion=reunion, fecha_reunion=f_reu, comunidad=com,
                              distrito=dist, region=reg, descripcion=desc, responsable=resp,
                              responsable_detalle=det, beneficiario=com, tema=tema, fecha_limite=limite,
                              riesgo_conflicto=riesgo, cumplido=cumplido,
                              fecha_cumplimiento=limite - timedelta(days=random.randint(0, 10)) if cumplido else "",
                              cita_textual="", fuente="sintético"))
registro = pd.DataFrame(filas)

# ------------------------------------------------------------------ actores y relaciones
actores, relaciones, historial = [], [], []


def actor(nom, tipo, cargo, org, com, antes, ahora, infl, ev="Mantiene su posición"):
    actores.append(dict(nombre=nom, tipo=tipo, cargo=cargo, organizacion=org, comunidad=com, postura=ahora,
                        influencia=infl, fuente="sintético"))
    historial.append(dict(nombre=nom, fecha=date(2025, 9, 10), reunion="Mapeo inicial de actores", comunidad=com,
                          postura=antes, influencia=infl, evidencia="Primera identificación"))
    historial.append(dict(nombre=nom, fecha=date(2026, 10, 20), reunion="Actualización del mapeo", comunidad=com,
                          postura=ahora, influencia=infl, evidencia=ev))
    return nom


def rel(a, b, tipo, desc=""):
    relaciones.append(dict(origen=a, destino=b, tipo=tipo, descripcion=desc, fuente="sintético"))


# equipos de exploracion de la empresa
jefe_q = actor("Daniela Huamán", "Empresa", "Jefa de Relaciones Comunitarias – Qori Urqu", "Minera Andina S.A.C.",
               "", 2, 2, 4)
rel_q = actor("Wilber Ccorahua", "Empresa", "Relacionista comunitario – Qori Urqu", "Minera Andina S.A.C.", "",
              2, 2, 3)
jefe_a = actor("Marco Llanos", "Empresa", "Jefe de Relaciones Comunitarias – Cerro Azul", "Minera Andina S.A.C.",
               "", 2, 2, 4)
rel_a = actor("Rosa Chávez", "Empresa", "Relacionista comunitaria – Cerro Azul", "Minera Andina S.A.C.", "",
              2, 2, 3)
rel(jefe_q, rel_q, "Influye en", "Dirige el equipo de campo")
rel(jefe_a, rel_a, "Influye en", "Dirige el equipo de campo")
# Qori Urqu: mayoria neutral; Sallalli exige el pago por uso superficial
alc_puquio = actor("Alcalde de Puquio", "Autoridad local", "Alcalde distrital", "Municipalidad Distrital de Puquio",
                   "", 0, 1, 4, "Firma convenio de mantenimiento vial")
GENTE_Q = {  # comunidad: [(nombre, cargo, tipo, antes, ahora, infl, evidencia)]
    "C.C. Sallalli": [("Hipólito Ayala", "Presidente comunal", "Dirigente comunal", 0, -1, 5,
                       "Exige el pago pendiente por uso superficial"),
                      ("Marcelina Huarcaya", "Presidenta del comité de pastos", "Organización de base", 0, -1, 4,
                       "Reclama por plataformas en zona de pastoreo"),
                      ("Teófilo Ccahuana", "Presidente de rondas campesinas", "Organización de base", 0, 0, 3,
                       "Mantiene su posición")],
    "C.C. Uchuyccasa": [("Justino Pariona", "Presidente comunal", "Dirigente comunal", 0, 1, 5,
                         "Valora la contratación de comuneros"),
                        ("Eulalia Quispe", "Presidenta del comité de regantes", "Organización de base", 0, 0, 3,
                         "Mantiene su posición")],
    "C.C. Ccollpapampa": [("Celestino Mallma", "Presidente comunal", "Dirigente comunal", 1, 1, 4,
                           "Mantiene su posición"),
                          ("Rufina Ochoa", "Presidenta del Vaso de Leche", "Organización de base", 0, 0, 2,
                           "Mantiene su posición")],
}
# Cerro Azul: historia de agua y rondas fuertes, con precedentes de bloqueos
alc_bamba = actor("Alcalde de Bambamarca", "Autoridad local", "Alcalde provincial",
                  "Municipalidad Provincial de Hualgayoc", "", 0, -1, 4, "Respalda a las rondas en el reclamo por agua")
rondas_c = actor("Central de Rondas de Bambamarca", "Organización de base", "Presidencia de la central",
                 "Rondas campesinas", "", -1, -2, 5, "Convoca a paro contra la exploración")
GENTE_A = {
    "C.C. Huayrapata": [("Segundo Chilón", "Presidente comunal", "Dirigente comunal", -1, -2, 5,
                         "Se opone a perforar cerca de las lagunas"),
                        ("Nélida Vásquez", "Presidenta del comité de regantes", "Organización de base", -1, -1, 4,
                         "Exige monitoreo independiente del agua")],
    "C.C. Quinuamayo": [("Wilmer Tantaleán", "Presidente comunal", "Dirigente comunal", 0, -1, 5,
                         "Molesto por compromisos vencidos"),
                        ("Etelvina Cruzado", "Presidenta del Vaso de Leche", "Organización de base", 0, 0, 2,
                         "Mantiene su posición")],
    "C.C. Rumichaca": [("Agustín Becerra", "Presidente comunal", "Dirigente comunal", 1, 1, 4,
                        "Mantiene su posición")],
}
def _org(cargo: str, com: str) -> str:
    if cargo == "Presidente comunal":
        return f"Junta directiva comunal {com[5:]}"
    return f"{cargo.replace('Presidenta del ', '').replace('Presidente de ', '').capitalize()} {com[5:]}"


for gente, jefe, rel_c, alc in ((GENTE_Q, jefe_q, rel_q, alc_puquio), (GENTE_A, jefe_a, rel_a, alc_bamba)):
    for com, personas in gente.items():
        nombres = []
        for nom, cargo, tipo, antes, ahora, infl, ev in personas:
            nombres.append(actor(nom, tipo, cargo, _org(cargo, com), com, antes,
                                 ahora, infl, ev))
        pres = nombres[0]
        for n in nombres[1:]:
            rel(pres, n, "Representa a", "Dirigencia de la misma comunidad")
        rel(rel_c, pres, "Negocia con", "Interlocutor principal de la empresa")
        rel(alc, pres, "Negocia con", "Coordinación distrital")
rel(jefe_q, alc_puquio, "Negocia con", "Convenio de mantenimiento vial")
rel(rondas_c, "Segundo Chilón", "Alianza", "Defensa de las lagunas")
rel(rondas_c, "Wilmer Tantaleán", "Influye en", "Convoca a las bases")
rel(alc_bamba, rondas_c, "Alianza", "Respaldo político")
rel("Segundo Chilón", rel_a, "Conflicto", "Rechazo a las plataformas cerca de las lagunas")
rel("Hipólito Ayala", rel_q, "Conflicto", "Pago pendiente por uso superficial")
rel("Hipólito Ayala", "Justino Pariona", "Parentesco", "Compadres")
rel("Agustín Becerra", jefe_a, "Alianza", "Acuerdo de uso superficial vigente")
# actor transversal: la ONG asesora a comunidades en las tres regiones
rel("ONG Agua y Territorio", "Nélida Vásquez", "Influye en", "Asesoría en monitoreo de agua")
rel("ONG Agua y Territorio", "Marcelina Huarcaya", "Influye en", "Asesoría legal sobre uso superficial")
rel("ONG Agua y Territorio", rondas_c, "Alianza", "Pronunciamientos conjuntos")

# ------------------------------------------------------------------ conflictos
EVENTOS = [  # fecha, tipo, titulo, lugar, comunidad, dlat, dlon, convocantes, demanda, tema, dias, partic, intens, violencia, desenlace
    ("2025-11-18", "Pronunciamiento / ultimátum", "Sallalli da plazo para el pago por uso superficial",
     "Local comunal de Sallalli", "C.C. Sallalli", 0, 0, "Hipólito Ayala", "Pago por uso superficial",
     "Tierras", 1, 120, "baja", False, "Mesa de diálogo"),
    ("2026-08-04", "Plantón", "Plantón frente al campamento de exploración Qori Urqu", "Campamento Qori Urqu",
     "C.C. Sallalli", 0.03, 0.04, "Comité de pastos de Sallalli", "Retiro de plataformas de la zona de pastoreo",
     "Tierras", 1, 60, "media", False, "Acta de acuerdos"),
    ("2024-05-20", "Paralización / paro", "Paro provincial en defensa de las lagunas", "Plaza de Bambamarca",
     "C.C. Huayrapata", 0.02, 0.03, "Central de Rondas de Bambamarca", "No a la exploración en cabecera de cuenca",
     "Agua", 4, 2500, "alta", False, "Levantamiento sin acuerdo"),
    ("2025-03-11", "Bloqueo de vía", "Bloqueo del acceso a las plataformas de Cerro Azul",
     "Km 12 de la vía Bambamarca–Hualgayoc", "C.C. Huayrapata", -0.03, -0.04, "Central de Rondas de Bambamarca",
     "Monitoreo independiente de las lagunas", "Agua", 3, 400, "alta", True, "Intervención policial"),
    ("2026-02-27", "Movilización / marcha", "Marcha por compromisos vencidos de Cerro Azul", "Plaza de Bambamarca",
     "C.C. Quinuamayo", 0.05, -0.05, "Wilmer Tantaleán", "Cumplimiento de compromisos de empleo local",
     "Empleo local", 1, 600, "media", False, "Mesa de diálogo"),
    ("2026-09-15", "Bloqueo de vía", "Bloqueo de la trocha a Quinuamayo", "Puente Quinuamayo", "C.C. Quinuamayo",
     -0.01, 0.02, "Rondas de Quinuamayo", "Reparación de la trocha dañada por camionetas", "Infraestructura", 2,
     200, "media", False, "Acta de acuerdos"),
]
conf = pd.DataFrame([dict(fecha=e[0], tipo=e[1], titulo=e[2], lugar=e[3], comunidad=e[4],
                          lat=info[e[4]][2] + e[5], lon=info[e[4]][3] + e[6], convocantes=e[7], demanda=e[8],
                          tema=e[9], duracion_dias=e[10], participantes=e[11], intensidad=e[12],
                          hubo_violencia=e[13], desenlace=e[14], fuente="sintético") for e in EVENTOS])

# ------------------------------------------------------------------ procesos de exploracion
procesos = pd.DataFrame([
    dict(id="Q1", proceso="Acuerdo de uso superficial con Sallalli", tipo="Tierras y servidumbres",
         comunidad="C.C. Sallalli", hito="Firma del acuerdo en asamblea comunal", fecha_limite="2026-12-20",
         impacto=5, si_se_paraliza="Sin acuerdo no se pueden habilitar 6 de las 9 plataformas de perforación",
         responsable=jefe_q, estado="En negociación", fuente="sintético"),
    dict(id="Q2", proceso="Inicio de la campaña de perforación en Uchuyccasa", tipo="Campaña de perforación",
         comunidad="C.C. Uchuyccasa", hito="Ingreso de la máquina perforadora", fecha_limite="2027-02-15",
         impacto=3, si_se_paraliza="Se corre el cronograma de perforación un trimestre", responsable=rel_q,
         estado="En preparación", fuente="sintético"),
    dict(id="A1", proceso="Aprobación de la DIA de Cerro Azul", tipo="Permisos ambientales (DIA / FTA)",
         comunidad="C.C. Huayrapata", hito="Taller participativo de la DIA", fecha_limite="2027-01-15",
         impacto=5, si_se_paraliza="Sin taller no hay aprobación de la DIA y el proyecto se detiene",
         responsable=jefe_a, estado="En preparación", fuente="sintético"),
    dict(id="A2", proceso="Campaña de perforación en Quinuamayo", tipo="Campaña de perforación",
         comunidad="C.C. Quinuamayo", hito="Habilitación de plataformas y accesos", fecha_limite="2027-03-01",
         impacto=4, si_se_paraliza="Costos de máquina parada y pérdida de la temporada seca", responsable=rel_a,
         estado="En negociación", fuente="sintético"),
])
partes = pd.DataFrame([
    ("Q1", "Hipólito Ayala", "Decide", "Pago justo y a tiempo por el uso superficial", "Que no se pague lo pendiente"),
    ("Q1", "Marcelina Huarcaya", "Puede vetar", "Proteger la zona de pastoreo", "Plataformas en los pastos"),
    ("Q1", "Teófilo Ccahuana", "Influye", "Control del ingreso de personas", "Ingreso sin aviso de contratistas"),
    ("Q1", "ONG Agua y Territorio", "Influye", "Contratos transparentes", "Cláusulas abusivas"),
    ("Q1", "Alcalde de Puquio", "Influye", "Obras para el distrito", "Ninguna mayor"),
    ("Q2", "Justino Pariona", "Decide", "Empleo para comuneros", "Que contraten gente de fuera"),
    ("Q2", "Eulalia Quispe", "Afectado", "Cuidar el agua de riego", "Uso de agua en la perforación"),
    ("A1", "Segundo Chilón", "Decide", "Proteger las lagunas", "Perforación en cabecera de cuenca"),
    ("A1", "Central de Rondas de Bambamarca", "Puede vetar", "Que nadie toque las lagunas", "Exploración en la cuenca"),
    ("A1", "Nélida Vásquez", "Puede vetar", "Monitoreo independiente", "Resultados controlados por la empresa"),
    ("A1", "Alcalde de Bambamarca", "Influye", "Respaldo de las rondas", "Costo político"),
    ("A1", "ONG Agua y Territorio", "Influye", "Información técnica completa", "Estudios incompletos"),
    ("A2", "Wilmer Tantaleán", "Decide", "Cumplir los compromisos vencidos", "Promesas sin cumplir"),
    ("A2", "Central de Rondas de Bambamarca", "Puede vetar", "Control territorial", "Ingreso sin permiso"),
    ("A2", "Etelvina Cruzado", "Afectado", "Seguridad de los niños en la trocha", "Tránsito de camionetas"),
], columns=["proceso_id", "nombre", "rol", "interes", "preocupacion"])
escenarios = pd.DataFrame([
    ("Q1", "Pagar lo pendiente antes de la asamblea", "Hipólito Ayala", 0, "Se retira la principal bandera"),
    ("Q1", "Pagar lo pendiente antes de la asamblea", "Marcelina Huarcaya", 0, "Ve voluntad de cumplir"),
    ("Q1", "Reubicar 2 plataformas fuera de la zona de pastoreo", "Marcelina Huarcaya", 1, "Se atiende su preocupación"),
    ("A1", "Monitoreo con veedores y laboratorio elegido por la comunidad", "Nélida Vásquez", 0, "Confía en los resultados"),
    ("A1", "Monitoreo con veedores y laboratorio elegido por la comunidad", "Segundo Chilón", -1, "Baja la tensión"),
    ("A1", "Taller de la DIA sin acuerdo previo con las rondas", "Central de Rondas de Bambamarca", -2, "Convocan a paro"),
    ("A1", "Taller de la DIA sin acuerdo previo con las rondas", "Alcalde de Bambamarca", -2, "Se suma al rechazo"),
    ("A2", "Ponerse al día con los compromisos de empleo", "Wilmer Tantaleán", 0, "Se cumple lo acordado"),
], columns=["proceso_id", "escenario", "nombre", "postura_nueva", "motivo"])
acciones = pd.DataFrame([
    ("Q1", "Hipólito Ayala", "Atender sus preocupaciones de cerca", "Cronograma de pago firmado con la junta", jefe_q,
     "2026-11-20", "En curso"),
    ("A1", "Nélida Vásquez", "Atender sus preocupaciones de cerca", "Proponer monitoreo con veedores comunales",
     jefe_a, "2026-11-25", "Pendiente"),
    ("A1", "Alcalde de Bambamarca", "Involucrar y consultar", "Reunión previa para presentar la DIA", jefe_a,
     "2026-11-15", "Pendiente"),
], columns=["proceso_id", "nombre", "estrategia", "accion", "responsable", "fecha", "estado"])

comunidades = pd.DataFrame(COMUNIDADES, columns=["comunidad", "distrito", "lat", "lon", "familias", "region",
                                                 "proyecto"])
for nombre, df in [("comunidades", comunidades), ("registro", registro), ("actores", pd.DataFrame(actores)),
                   ("relaciones", pd.DataFrame(relaciones)), ("posturas", pd.DataFrame(historial)),
                   ("conflictos", conf), ("procesos", procesos), ("proceso_actores", partes),
                   ("escenarios", escenarios), ("acciones", acciones)]:
    df.to_csv(SALIDA / f"{nombre}.csv", index=False)
print(f"{len(comunidades)} comunidades, {len(registro)} compromisos, {len(actores)} actores, "
      f"{len(relaciones)} relaciones, {len(conf)} eventos, {len(procesos)} procesos -> {SALIDA}")

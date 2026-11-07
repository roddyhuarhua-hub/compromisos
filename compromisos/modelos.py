"""Esquema de la salida estructurada del LLM: compromisos, actores y relaciones."""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

Parte = Literal["Empresa", "Estado", "Comunidad", "Otro"]
Tema = Literal[
    "Agua", "Empleo local", "Salud", "Educación", "Infraestructura", "Tierras",
    "Ambiente", "Proyectos productivos", "Monitoreo", "Comunicación", "Otro",
]


class Compromiso(BaseModel):
    descripcion: str = Field(description="Que se va a hacer, en una frase clara")
    responsable: Parte = Field(description="Parte que asume el compromiso")
    responsable_detalle: str = Field(
        default="", description="Area o persona concreta, p. ej. 'Gerencia de RR.CC.' o 'ANA'"
    )
    beneficiario: str = Field(default="", description="Quien recibe el beneficio")
    tema: Tema = "Otro"
    fecha_limite: Optional[date] = Field(default=None, description="Plazo en formato AAAA-MM-DD")
    riesgo_conflicto: Literal["alto", "medio", "bajo"] = "medio"
    cita_textual: str = Field(default="", description="Frase literal que respalda el compromiso")


TipoActor = Literal[
    "Dirigente comunal", "Organización de base", "Autoridad local", "Estado",
    "Empresa", "ONG / Iglesia", "Medio de comunicación", "Otro",
]
TipoRelacion = Literal["Alianza", "Conflicto", "Representa a", "Influye en", "Parentesco", "Negocia con"]


class Actor(BaseModel):
    nombre: str = Field(description="Nombre de la persona u organizacion, tal como se menciona")
    tipo: TipoActor = "Otro"
    cargo: str = Field(default="", description="Cargo o rol, p. ej. 'presidente comunal'")
    organizacion: str = Field(default="", description="Organizacion a la que pertenece")
    comunidad: str = Field(default="", description="Comunidad o caserio al que pertenece, si aplica")
    postura: int = Field(default=0, ge=-2, le=2,
                         description="Postura hacia la empresa: -2 opositor, -1 critico, 0 neutral, 1 favorable, 2 aliado")
    influencia: int = Field(default=3, ge=1, le=5, description="Capacidad de influir en la comunidad (1 a 5)")
    evidencia: str = Field(default="", description="Frase de la reunion que muestra su postura")


class Relacion(BaseModel):
    origen: str = Field(description="Nombre del actor de origen (igual que en actores)")
    destino: str = Field(description="Nombre del actor de destino (igual que en actores)")
    tipo: TipoRelacion = "Influye en"
    descripcion: str = Field(default="", description="Breve explicacion de la relacion")


class ExtraccionReunion(BaseModel):
    resumen: str = Field(description="Resumen de la reunion en 3 a 5 lineas")
    participantes: list[str] = Field(default_factory=list)
    compromisos: list[Compromiso] = Field(default_factory=list)
    temas_pendientes: list[str] = Field(
        default_factory=list, description="Demandas planteadas que quedaron sin acuerdo"
    )
    actores: list[Actor] = Field(default_factory=list, description="Actores que participan o se mencionan")
    relaciones: list[Relacion] = Field(default_factory=list,
                                       description="Relaciones entre actores que se desprenden de la reunion")


# ------------------------------------------------------------------ conflictividad
TipoEvento = Literal[
    "Bloqueo de vía", "Paralización / paro", "Toma de instalaciones", "Movilización / marcha",
    "Plantón", "Pronunciamiento / ultimátum", "Denuncia o queja formal", "Enfrentamiento", "Otro",
]
Desenlace = Literal[
    "Mesa de diálogo", "Acta de acuerdos", "Levantamiento sin acuerdo", "Intervención policial",
    "Declaratoria de emergencia", "En curso", "Otro",
]


class EventoConflicto(BaseModel):
    fecha: Optional[date] = Field(default=None, description="Fecha de inicio AAAA-MM-DD")
    tipo: TipoEvento = "Otro"
    titulo: str = Field(description="Descripcion breve del hecho, p. ej. 'Bloqueo de la vía Pucará-Chalhuanca'")
    lugar: str = Field(default="", description="Lugar exacto: tramo de via, km, puente, campamento, plaza")
    comunidad: str = Field(default="", description="Comunidad o caserio principal involucrado")
    convocantes: str = Field(default="", description="Organizaciones o dirigentes que convocaron")
    demanda: str = Field(default="", description="Que exigian")
    tema: Tema = "Otro"
    duracion_dias: int = Field(default=1, ge=0, description="Dias que duro la medida")
    participantes: Optional[int] = Field(default=None, description="Numero aproximado de participantes")
    intensidad: Literal["alta", "media", "baja"] = "media"
    hubo_violencia: bool = Field(default=False, description="Heridos, detenidos, daños o enfrentamientos")
    desenlace: Desenlace = "Otro"


class ExtraccionEventos(BaseModel):
    eventos: list[EventoConflicto] = Field(default_factory=list)

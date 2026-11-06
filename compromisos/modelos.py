"""Esquema de datos de un compromiso (salida estructurada del LLM)."""
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


class ExtraccionReunion(BaseModel):
    resumen: str = Field(description="Resumen de la reunion en 3 a 5 lineas")
    participantes: list[str] = Field(default_factory=list)
    compromisos: list[Compromiso] = Field(default_factory=list)
    temas_pendientes: list[str] = Field(
        default_factory=list, description="Demandas planteadas que quedaron sin acuerdo"
    )

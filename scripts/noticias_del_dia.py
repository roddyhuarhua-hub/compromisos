"""Busca las noticias de los ultimos dias sobre cada proyecto y las guarda en datos/noticias.csv.

Uso:  python scripts/noticias_del_dia.py            (todos los proyectos de la demo)
      python scripts/noticias_del_dia.py --dias 3

Se puede programar una vez al dia (tarea programada de Windows, cron o GitHub Actions). La app tambien busca sola
al abrir la seccion "Contexto del día" y guarda el resultado unas horas.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import pandas as pd  # noqa: E402

from compromisos import noticias, portafolio  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=7)
    ap.add_argument("--salida", default=str(RAIZ / "datos" / "noticias.csv"))
    a = ap.parse_args()
    d = portafolio.cargar_demo(RAIZ / "datos" / "ejemplo")
    total = []
    for proy in portafolio.lista(d["comunidades"]):
        n = noticias.buscar(proy, d["comunidades"], d.get("proyectos"), dias=a.dias)
        print(f"{proy}: {len(n)} noticias ({(n['alerta'] >= 2).sum()} con señal de alerta)")
        total.append(n)
    df = pd.concat(total, ignore_index=True) if total else pd.DataFrame(columns=noticias.COLUMNAS)
    noticias.guardar(df, a.salida)
    print(f"Guardado en {a.salida}")


if __name__ == "__main__":
    main()

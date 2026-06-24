"""
analisis.py — Agregación de temperatura por punto y filtro de aptitud.

Recibe los DataFrames de temperatura diaria (uno por punto de grilla),
calcula los estadísticos del período y determina qué puntos son aptos
para el proyecto de piscicultura + aquaponía según el rango [temp_min, temp_max].
"""

from __future__ import annotations

import pandas as pd


def agregar_puntos(
    puntos: list[tuple[float, float]],
    series: list[pd.DataFrame],
) -> pd.DataFrame:
    """
    Calcula estadísticos de temperatura del período para cada punto.

    Parámetros
    ----------
    puntos : list[(lat, lon)]
    series : list[pd.DataFrame]
        Un DataFrame por punto con columnas tmin, tmax, tmean.

    Retorna
    -------
    pd.DataFrame con columnas:
        lat, lon, tmin_periodo, tmax_periodo, tmean_periodo, datos_ok
    """
    filas = []
    for (lat, lon), df in zip(puntos, series):
        if df.empty or df[["tmin", "tmax", "tmean"]].isna().all().all():
            filas.append({
                "lat": lat, "lon": lon,
                "tmin_periodo": None, "tmax_periodo": None, "tmean_periodo": None,
                "datos_ok": False,
            })
            continue
        filas.append({
            "lat": lat,
            "lon": lon,
            "tmin_periodo": round(float(df["tmin"].min()), 2),
            "tmax_periodo": round(float(df["tmax"].max()), 2),
            "tmean_periodo": round(float(df["tmean"].mean()), 2),
            "datos_ok": True,
        })
    return pd.DataFrame(filas)


def filtrar_aptos(
    df_puntos: pd.DataFrame,
    temp_min: float,
    temp_max: float,
) -> pd.DataFrame:
    """
    Marca cada punto como apto o no apto según el rango de temperatura [temp_min, temp_max].

    Un punto es APTO si la temperatura del período NUNCA sale del rango:
      - La mínima absoluta del período >= temp_min
      - La máxima absoluta del período <= temp_max

    Esta función recibe df_puntos con columnas:
      - tmin_periodo: temperatura mínima absoluta observada en el período (°C)
      - tmax_periodo: temperatura máxima absoluta observada en el período (°C)
      - tmean_periodo: temperatura media del período (°C)
      - datos_ok: bool, True si hay datos válidos para el punto

    Debes agregar una columna "apto" (bool) al DataFrame.
    Criterio acordado: apto = (tmin_periodo >= temp_min) AND (tmax_periodo <= temp_max)
    Los puntos sin datos (datos_ok == False) siempre son no aptos.

    Parámetros
    ----------
    df_puntos : pd.DataFrame   (resultado de agregar_puntos)
    temp_min  : float          temperatura mínima del rango deseado (°C)
    temp_max  : float          temperatura máxima del rango deseado (°C)

    Retorna
    -------
    El mismo DataFrame con columna "apto" (bool) agregada.
    """
    df_puntos["apto"] = (
        df_puntos["datos_ok"]
        & (df_puntos["tmin_periodo"] >= temp_min)
        & (df_puntos["tmax_periodo"] <= temp_max)
    ).fillna(False)
    return df_puntos

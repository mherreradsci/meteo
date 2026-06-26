"""
clima.py — Cliente Open-Meteo Archive para datos de temperatura diaria.

Obtiene temperatura mínima, máxima y media a 2 m del suelo para una lista
de coordenadas, usando la API gratuita de Open-Meteo (basada en ERA5).
Las fechas y los resultados siempre están en zona horaria America/Santiago.
"""

from __future__ import annotations

import logging
import math
import time
from http import HTTPStatus
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests
import requests_cache

# ── Caché en disco para no repetir llamadas idénticas ──────────────────────
_CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

requests_cache.install_cache(
    str(_CACHE_DIR / "openmeteo_cache"),
    backend="sqlite",
    expire_after=86400 * 7,  # 7 días
)

# ── Constantes ──────────────────────────────────────────────────────────────
_BASE_URL = "https://archive-api.open-meteo.com/v1/archive"
_BATCH_SIZE = 50          # puntos por solicitud (límite conservador)
_DAILY_VARS = "temperature_2m_max,temperature_2m_min,temperature_2m_mean"
_TIMEZONE = "America/Santiago"
_BATCH_DELAY = 0.5        # segundos entre lotes para respetar el rate limit
_MAX_RETRIES = 4          # reintentos ante 429

logger = logging.getLogger(__name__)


def _chunks(lst: list, n: int):
    """Divide lst en sublistas de tamaño máximo n."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def obtener_temperatura_diaria(
    puntos: list[tuple[float, float]],
    fecha_inicio: str,
    fecha_fin: str,
) -> list[pd.DataFrame]:
    """
    Consulta la temperatura diaria para cada punto en `puntos`.

    Parámetros
    ----------
    puntos : list[(lat, lon)]
        Lista de tuplas (latitud, longitud) en grados decimales.
    fecha_inicio : str
        Fecha de inicio en formato 'YYYY-MM-DD'.
    fecha_fin : str
        Fecha de término en formato 'YYYY-MM-DD'.

    Retorna
    -------
    list[pd.DataFrame]
        Un DataFrame por punto con columnas: fecha, tmin, tmax, tmean.
        El índice es DatetimeTZDtype con zona America/Santiago.
    """
    if not puntos:
        return []

    resultados: list[pd.DataFrame | None] = [None] * len(puntos)

    for lote_indices in _chunks(list(range(len(puntos))), _BATCH_SIZE):
        lote_puntos = [puntos[i] for i in lote_indices]
        lats = [p[0] for p in lote_puntos]
        lons = [p[1] for p in lote_puntos]

        params = {
            "latitude": lats,
            "longitude": lons,
            "start_date": fecha_inicio,
            "end_date": fecha_fin,
            "daily": _DAILY_VARS,
            "timezone": _TIMEZONE,
        }

        logger.debug("Consultando Open-Meteo: %d puntos, %s → %s",
                     len(lote_puntos), fecha_inicio, fecha_fin)

        for attempt in range(_MAX_RETRIES + 1):
            response = requests.get(_BASE_URL, params=params, timeout=60)
            if response.status_code == HTTPStatus.TOO_MANY_REQUESTS and attempt < _MAX_RETRIES:
                wait = 2 * (2 ** attempt)  # backoff exponencial: 2s, 4s, 8s, 16s
                logger.warning("%s recibido, reintentando en %.1f s (intento %d/%d)",
                               HTTPStatus.TOO_MANY_REQUESTS.phrase,
                               wait, attempt + 1, _MAX_RETRIES)
                time.sleep(wait)
                continue
            response.raise_for_status()
            break
        data = response.json()

        time.sleep(_BATCH_DELAY)

        # La API retorna un dict si es un punto, una lista si son varios
        if isinstance(data, dict):
            data = [data]

        for j, item in enumerate(data):
            idx = lote_indices[j]
            daily = item.get("daily", {})
            fechas = pd.to_datetime(daily["time"])

            df = pd.DataFrame({
                "fecha": fechas,
                "tmin":  daily["temperature_2m_min"],
                "tmax":  daily["temperature_2m_max"],
                "tmean": daily["temperature_2m_mean"],
            })
            df["fecha"] = df["fecha"].dt.tz_localize(
                _TIMEZONE, nonexistent="shift_forward", ambiguous="infer"
            )
            df = df.set_index("fecha")
            resultados[idx] = df

    # Rellenar huecos (en caso de fallo en algún lote)
    return [df if df is not None else pd.DataFrame(columns=["tmin", "tmax", "tmean"])
            for df in resultados]

"""
geo.py — Geografía: resolución de comunas y muestreo de grilla.

Responsabilidades:
  - Cargar el GeoJSON de comunas de Chile y buscar por código CUT o nombre.
  - Convertir una lista de coordenadas en un polígono Shapely.
  - Muestrear una grilla regular de puntos dentro de una geometría.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon, MultiPolygon

# ── Rutas ────────────────────────────────────────────────────────────────────
_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_GEOJSON_COMUNAS = _DATA_DIR / "comunas_chile.geojson"

# ── Cache de carga ───────────────────────────────────────────────────────────
_gdf_comunas: gpd.GeoDataFrame | None = None


def _normalizar_texto(texto: str) -> str:
    """Convierte a minúsculas y elimina tildes para comparación flexible."""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _cargar_comunas() -> gpd.GeoDataFrame:
    """Carga y cachea el GeoDataFrame de comunas."""
    global _gdf_comunas
    if _gdf_comunas is None:
        if not _GEOJSON_COMUNAS.exists():
            raise FileNotFoundError(
                f"GeoJSON de comunas no encontrado en {_GEOJSON_COMUNAS}.\n"
                "Ejecuta primero: python scripts/descargar_comunas.py"
            )
        _gdf_comunas = gpd.read_file(_GEOJSON_COMUNAS)
        # Asegurar CRS geográfico WGS84
        if _gdf_comunas.crs is None or _gdf_comunas.crs.to_epsg() != 4326:
            _gdf_comunas = _gdf_comunas.to_crs(epsg=4326)
    return _gdf_comunas


def comunas_disponibles() -> pd.DataFrame:
    """Retorna DataFrame con columnas [cod_comuna, nombre_comuna] de todas las comunas."""
    gdf = _cargar_comunas()
    return gdf[["cod_comuna", "nombre_comuna"]].sort_values("nombre_comuna").reset_index(drop=True)


def geometria_por_codigo(cut: str | int) -> tuple[str, object]:
    """
    Busca una comuna por código CUT.

    Retorna
    -------
    (nombre_comuna, geometria_shapely)
    """
    gdf = _cargar_comunas()
    cut_str = str(int(cut)).zfill(5)
    mask = gdf["cod_comuna"].astype(str).str.zfill(5) == cut_str
    fila = gdf[mask]
    if fila.empty:
        raise ValueError(f"No se encontró la comuna con código CUT '{cut}'.")
    row = fila.iloc[0]
    return row["nombre_comuna"], row.geometry


def geometria_por_nombre(nombre: str) -> tuple[str, object]:
    """
    Busca una comuna por nombre (insensible a mayúsculas/tildes, coincidencia parcial).

    Retorna
    -------
    (nombre_oficial, geometria_shapely)

    Lanza ValueError si hay cero o más de una coincidencia exacta.
    """
    gdf = _cargar_comunas()
    nombre_norm = _normalizar_texto(nombre)
    gdf = gdf.copy()
    gdf["_norm"] = gdf["nombre_comuna"].apply(_normalizar_texto)

    # Primero coincidencia exacta
    exactas = gdf[gdf["_norm"] == nombre_norm]
    if len(exactas) == 1:
        row = exactas.iloc[0]
        return row["nombre_comuna"], row.geometry

    # Luego coincidencia parcial
    parciales = gdf[gdf["_norm"].str.contains(nombre_norm, regex=False)]
    if parciales.empty:
        raise ValueError(f"No se encontró ninguna comuna con nombre similar a '{nombre}'.")
    if len(parciales) > 1:
        nombres = parciales["nombre_comuna"].tolist()
        raise ValueError(
            f"'{nombre}' coincide con varias comunas: {nombres}.\n"
            "Usa un nombre más específico o el código CUT."
        )
    row = parciales.iloc[0]
    return row["nombre_comuna"], row.geometry


def poligono_desde_coordenadas(coords: list[tuple[float, float]]) -> Polygon:
    """
    Crea un polígono Shapely desde una lista de (lat, lon).

    Shapely trabaja en (x=lon, y=lat), así que se invierte el orden.
    """
    if len(coords) < 3:
        raise ValueError("Se necesitan al menos 3 coordenadas para definir un polígono.")
    # coords son (lat, lon) → Shapely usa (lon, lat)
    puntos_xy = [(lon, lat) for lat, lon in coords]
    poly = Polygon(puntos_xy)
    if not poly.is_valid:
        poly = poly.buffer(0)   # corrige autointersecciones menores
    return poly


def muestrear_grilla(
    geometria,
    paso_grados: float = 0.1,
) -> list[tuple[float, float]]:
    """
    Genera una grilla regular de puntos dentro de `geometria`.

    Parámetros
    ----------
    geometria : Shapely geometry (Polygon / MultiPolygon / cualquier geometry)
    paso_grados : float
        Espaciado de la grilla en grados (~11 km por 0.1°).

    Retorna
    -------
    list[(lat, lon)]
        Puntos (latitud, longitud) que caen dentro de la geometría.
    """
    minx, miny, maxx, maxy = geometria.bounds  # (lon_min, lat_min, lon_max, lat_max)

    puntos: list[tuple[float, float]] = []
    lat = miny
    while lat <= maxy + 1e-9:
        lon = minx
        while lon <= maxx + 1e-9:
            pt = Point(lon, lat)
            if geometria.contains(pt) or geometria.boundary.distance(pt) < 1e-6:
                puntos.append((round(lat, 6), round(lon, 6)))
            lon += paso_grados
        lat += paso_grados

    if not puntos:
        # Para geometrías muy pequeñas, usar el centroide
        c = geometria.centroid
        puntos = [(round(c.y, 6), round(c.x, 6))]

    return puntos

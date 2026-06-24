"""
descargar_comunas.py — Descarga y normaliza el GeoJSON de comunas de Chile.

Fuente: GADM (Global Administrative Areas) v4.1 — nivel 3 (comunas de Chile).
        https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_CHL_3.json.zip
Solo necesita ejecutarse una vez.

Uso:
    python scripts/descargar_comunas.py
"""

import io
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

# Añadir raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent))

import geopandas as gpd

# ── Fuente de datos ──────────────────────────────────────────────────────────
# GADM 4.1 — Chile nivel 3 (comunas). Propiedades relevantes:
#   NAME_3  → nombre de la comuna
#   CC_3    → código CUT de 5 dígitos (puede estar vacío en algunos casos)
_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_CHL_3.json.zip"
_DEST = Path(__file__).parent.parent / "data" / "comunas_chile.geojson"


def descargar_y_normalizar():
    _DEST.parent.mkdir(parents=True, exist_ok=True)

    print(f"Descargando GeoJSON de comunas desde GADM:\n  {_URL}")
    print("(puede tardar ~30-60 seg, el archivo pesa ~20 MB)")

    with urllib.request.urlopen(_URL, timeout=120) as response:
        data = response.read()

    print("Descarga completa. Extrayendo ZIP...")
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        # El archivo JSON dentro del ZIP
        json_name = [n for n in zf.namelist() if n.endswith(".json")][0]
        print(f"  Archivo encontrado: {json_name}")
        json_bytes = zf.read(json_name)

    print("Cargando con geopandas...")
    gdf = gpd.read_file(io.BytesIO(json_bytes))

    # Asegurar CRS WGS84
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    print(f"\nEsquema original ({len(gdf)} filas):")
    print(f"  Columnas: {list(gdf.columns)}")
    print(f"\nMuestra:")
    print(gdf[["NAME_3", "CC_3", "NAME_1"]].head(5).to_string())

    # ── Normalizar ───────────────────────────────────────────────────────────
    # GADM nivel 3 Chile: NAME_3 está en CamelCase sin espacios (ej. "SierraGorda")
    # CC_3 es "NA" en toda la data de Chile (GADM no tiene CUT codes).
    # Solución: separar CamelCase a palabras y usar GID_3 como identificador único.
    gdf = gdf.copy()

    def camel_a_espacios(texto: str) -> str:
        """'SanPedrodeAtacama' → 'San Pedrode Atacama' → mejor que nada."""
        # Insertar espacio antes de mayúscula que sigue a minúscula
        return re.sub(r"(?<=[a-záéíóúüñ])(?=[A-ZÁÉÍÓÚÜÑ])", " ", texto).strip()

    gdf["nombre_comuna"] = gdf["NAME_3"].str.strip().apply(camel_a_espacios)
    gdf["region"] = gdf["NAME_1"].str.strip().apply(camel_a_espacios)

    # Código: extraer número del GID_3 (formato "CHL.R.P.C_1") → RPPCC 5 dígitos
    def gid3_a_codigo(gid: str) -> str:
        partes = gid.replace("_1", "").split(".")
        if len(partes) == 4:
            r, p, c = int(partes[1]), int(partes[2]), int(partes[3])
            return f"{r:02d}{p:02d}{c:01d}"  # aprox CUT: RR + PP + C
        return str(gid)

    gdf["cod_comuna"] = gdf["GID_3"].apply(gid3_a_codigo).str.zfill(5)

    # Mantener solo columnas canónicas
    gdf_out = gdf[["cod_comuna", "nombre_comuna", "region", "geometry"]].copy()

    # Guardar
    gdf_out.to_file(_DEST, driver="GeoJSON")

    print(f"\n✅ GeoJSON normalizado guardado en: {_DEST}")
    print(f"   {len(gdf_out)} comunas.")
    print(f"\nMuestra final:")
    print(gdf_out[["cod_comuna", "nombre_comuna", "region"]].head(8).to_string())


if __name__ == "__main__":
    descargar_y_normalizar()

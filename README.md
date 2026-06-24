# Buscador climático — Piscicultura Chile

Herramienta interactiva para encontrar territorios en Chile cuya temperatura histórica se mantenga dentro de un rango deseado. Diseñada para evaluar sitios candidatos a proyectos de piscicultura + aquaponía.

## ¿Qué hace?

1. Define un área (comuna por nombre o código CUT, o un polígono de coordenadas).
2. Muestrea una grilla de puntos dentro del área.
3. Consulta la temperatura diaria histórica (ERA5 vía Open-Meteo, sin costo ni clave de API).
4. Marca cada punto como **apto** si en ningún día del período la temperatura salió del rango deseado.
5. Muestra los resultados en un mapa interactivo con series temporales por punto.

## Instalación

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Descargar el GeoJSON de comunas de Chile (necesario la primera vez)
python scripts/descargar_comunas.py
```

Requiere Python 3.12.

## Uso

```bash
streamlit run app.py
```

La app queda disponible en `http://localhost:8501`.

## Parámetros principales

| Parámetro | Descripción |
|---|---|
| Tipo de área | Por comuna (nombre o CUT) o polígono de coordenadas |
| Período | Cualquier rango desde 1940 hasta el año pasado |
| Rango de temperatura | [T mínima, T máxima] deseada en °C |
| Resolución de grilla | 0.25° (≈28 km), 0.1° (≈11 km) o 0.05° (≈5.5 km) |

## Criterio de aptitud

Un punto es **apto** si la temperatura mínima absoluta del período ≥ T mínima deseada **y** la temperatura máxima absoluta ≤ T máxima deseada. Es decir, la temperatura estuvo siempre dentro del rango, sin excepción.

> Los datos son temperatura del aire a 2 m (ERA5). Se usa como proxy climático, no es temperatura del agua.

## Datos

- **Clima:** [Open-Meteo Archive API](https://open-meteo.com/) — ERA5, dato diario, sin clave de API.
- **Comunas:** GeoJSON generado por `scripts/descargar_comunas.py`.
- **Caché:** Las consultas a Open-Meteo se guardan en `data/cache/openmeteo_cache.sqlite` (TTL 7 días).

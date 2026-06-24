"""
mapa.py — Generación del mapa Folium con tiles OpenStreetMap.

Muestra los puntos de la grilla coloreados por temperatura media,
con los puntos aptos resaltados y el borde del territorio analizado.
"""

from __future__ import annotations

import branca.colormap as cm
import folium
import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping


def _centroide(geometria) -> tuple[float, float]:
    """Retorna (lat, lon) del centroide de la geometría."""
    c = geometria.centroid
    return (c.y, c.x)


def crear_mapa(
    df_puntos: pd.DataFrame,
    geometria,
    nombre_territorio: str = "",
) -> folium.Map:
    """
    Crea un mapa Folium con los puntos de temperatura sobre OpenStreetMap.

    Parámetros
    ----------
    df_puntos : pd.DataFrame
        Con columnas lat, lon, tmin_periodo, tmax_periodo, tmean_periodo, apto, datos_ok.
    geometria : Shapely geometry
        Borde del territorio analizado.
    nombre_territorio : str
        Etiqueta para el tooltip del borde.

    Retorna
    -------
    folium.Map listo para renderizar.
    """
    lat_c, lon_c = _centroide(geometria)
    mapa = folium.Map(location=[lat_c, lon_c], zoom_start=9, tiles="OpenStreetMap")

    # ── Borde del territorio ────────────────────────────────────────────────
    geo_layer = folium.GeoJson(
        data=mapping(geometria),
        name=nombre_territorio or "Territorio",
        style_function=lambda _: {
            "color": "#1a73e8",
            "weight": 2,
            "fillOpacity": 0.05,
        },
        tooltip=nombre_territorio,
    )
    geo_layer.add_to(mapa)

    # ── Colormap para temperatura media ────────────────────────────────────
    validos = df_puntos[df_puntos["datos_ok"] == True]
    if not validos.empty:
        t_min_global = validos["tmean_periodo"].min()
        t_max_global = validos["tmean_periodo"].max()
        if t_min_global == t_max_global:
            t_min_global -= 1
            t_max_global += 1
        colormap = cm.LinearColormap(
            ["#3a86ff", "#8ecae6", "#95d5b2", "#ffb703", "#e63946"],
            vmin=t_min_global,
            vmax=t_max_global,
            caption="Temperatura media del período (°C)",
        )
        colormap.add_to(mapa)
    else:
        colormap = None

    # ── Marcadores por punto ────────────────────────────────────────────────
    for _, row in df_puntos.iterrows():
        if not row["datos_ok"]:
            continue

        tmean = row["tmean_periodo"]
        color = colormap(tmean) if colormap else "#cccccc"
        apto = bool(row.get("apto", False))

        popup_html = (
            f"<b>{'✅ APTO' if apto else '❌ No apto'}</b><br>"
            f"Lat: {row['lat']:.4f} | Lon: {row['lon']:.4f}<br>"
            f"T mín: <b>{row['tmin_periodo']:.1f} °C</b><br>"
            f"T máx: <b>{row['tmax_periodo']:.1f} °C</b><br>"
            f"T prom: <b>{tmean:.1f} °C</b>"
        )

        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=8 if apto else 5,
            color="#22c55e" if apto else "#94a3b8",
            fill=True,
            fill_color=color,
            fill_opacity=0.85,
            weight=3 if apto else 1,
            popup=folium.Popup(popup_html, max_width=200),
            tooltip=f"{'✅' if apto else '○'} Tprom={tmean:.1f}°C",
        ).add_to(mapa)

    return mapa

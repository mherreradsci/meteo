"""
graficos.py — Gráficos Plotly de serie temporal de temperatura.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def serie_temporal(
    df: pd.DataFrame,
    titulo: str = "Serie temporal de temperatura",
    temp_min: float | None = None,
    temp_max: float | None = None,
) -> go.Figure:
    """
    Genera un gráfico de líneas con Tmín, Tmáx y Tprom diarios.

    Parámetros
    ----------
    df : pd.DataFrame
        Con índice temporal y columnas tmin, tmax, tmean.
    titulo : str
        Título del gráfico.
    temp_min, temp_max : float | None
        Si se pasan, dibuja líneas horizontales de referencia del rango deseado.

    Retorna
    -------
    go.Figure
    """
    fechas = df.index

    fig = go.Figure()

    # Banda de relleno entre tmin y tmax
    fig.add_trace(go.Scatter(
        x=list(fechas) + list(fechas[::-1]),
        y=list(df["tmax"]) + list(df["tmin"][::-1]),
        fill="toself",
        fillcolor="rgba(58, 134, 255, 0.12)",
        line={"color": "rgba(255,255,255,0)"},
        showlegend=True,
        name="Rango Tmín–Tmáx",
        hoverinfo="skip",
    ))

    fig.add_trace(go.Scatter(
        x=fechas, y=df["tmax"],
        mode="lines",
        name="T máxima",
        line={"color": "#e63946", "width": 1.5},
    ))
    fig.add_trace(go.Scatter(
        x=fechas, y=df["tmin"],
        mode="lines",
        name="T mínima",
        line={"color": "#3a86ff", "width": 1.5},
    ))
    fig.add_trace(go.Scatter(
        x=fechas, y=df["tmean"],
        mode="lines",
        name="T promedio",
        line={"color": "#2d6a4f", "width": 2.5, "dash": "dot"},
    ))

    # Líneas de referencia del rango deseado
    if temp_min is not None:
        fig.add_hline(
            y=temp_min,
            line_dash="dash",
            line_color="#fb8500",
            annotation_text=f"T mín deseada ({temp_min}°C)",
            annotation_position="bottom right",
        )
    if temp_max is not None:
        fig.add_hline(
            y=temp_max,
            line_dash="dash",
            line_color="#fb8500",
            annotation_text=f"T máx deseada ({temp_max}°C)",
            annotation_position="top right",
        )

    fig.update_layout(
        title=titulo,
        xaxis_title="Fecha",
        yaxis_title="Temperatura (°C)",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        hovermode="x unified",
        template="plotly_white",
        height=420,
    )
    return fig


def resumen_territorial(df_puntos: pd.DataFrame) -> go.Figure:
    """
    Scatter plot: Tprom vs Tmáx coloreado por aptitud.
    Útil para ver la distribución de puntos de todo el territorio.
    """
    aptos = df_puntos[df_puntos.get("apto", False) == True] if "apto" in df_puntos.columns else pd.DataFrame()
    no_aptos = df_puntos[df_puntos.get("apto", True) == False] if "apto" in df_puntos.columns else df_puntos

    fig = go.Figure()

    if not no_aptos.empty:
        fig.add_trace(go.Scatter(
            x=no_aptos["tmean_periodo"],
            y=no_aptos["tmax_periodo"],
            mode="markers",
            name="No apto",
            marker={"color": "#94a3b8", "size": 8, "opacity": 0.7},
            text=no_aptos.apply(lambda r: f"({r['lat']:.3f}, {r['lon']:.3f})", axis=1),
            hovertemplate="<b>No apto</b><br>Tprom=%{x:.1f}°C | Tmáx=%{y:.1f}°C<br>%{text}<extra></extra>",
        ))

    if not aptos.empty:
        fig.add_trace(go.Scatter(
            x=aptos["tmean_periodo"],
            y=aptos["tmax_periodo"],
            mode="markers",
            name="Apto ✅",
            marker={"color": "#22c55e", "size": 12, "symbol": "star", "opacity": 0.9},
            text=aptos.apply(lambda r: f"({r['lat']:.3f}, {r['lon']:.3f})", axis=1),
            hovertemplate="<b>✅ Apto</b><br>Tprom=%{x:.1f}°C | Tmáx=%{y:.1f}°C<br>%{text}<extra></extra>",
        ))

    fig.update_layout(
        title="Distribución territorial: T promedio vs T máxima",
        xaxis_title="Temperatura media del período (°C)",
        yaxis_title="Temperatura máxima del período (°C)",
        template="plotly_white",
        height=380,
    )
    return fig

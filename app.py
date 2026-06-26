"""
app.py — App Streamlit: Buscador de territorios en Chile por rango de temperatura.

Proyecto: piscicultura + aquaponía (eco_circular)

Uso:
    streamlit run app.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import cast

# Asegurar que src/ está en el path
sys.path.insert(0, str(Path(__file__).parent / "src"))

logging.basicConfig(
    format="%(levelname)s [%(name)s] %(message)s",
    level=logging.WARNING,
)
logging.getLogger("meteo").setLevel(logging.DEBUG)

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from meteo import analisis, clima, geo, graficos, mapa

# ─────────────────────────────────────────────────────────────────────────────
# Configuración de la página
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Buscador climático — Piscicultura Chile",
    page_icon="🐟",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🐟 Buscador de territorios por temperatura")
st.caption(
    "Encuentra localidades en Chile cuya temperatura histórica esté dentro del rango "
    "ideal para proyectos de piscicultura + aquaponía."
)

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar: parámetros
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Parámetros")

    # ── Modo de búsqueda ────────────────────────────────────────────────────
    modo = st.radio(
        "Tipo de área",
        ["Por comuna", "Por polígono (coordenadas)"],
        index=0,
    )

    # ── Entrada comuna ──────────────────────────────────────────────────────
    nombre_comuna: str | None = None
    cut_comuna: int | None = None
    tipo_id: str = ""
    coords_raw: str = ""
    if modo == "Por comuna":
        st.subheader("📍 Búsqueda por comuna")
        tipo_id = st.radio("Identificar por", ["Nombre", "Código CUT"], horizontal=True)
        if tipo_id == "Nombre":
            nombre_comuna = st.text_input("Nombre de la comuna", value="Antofagasta")
        else:
            cut_comuna = int(st.number_input("Código CUT", min_value=1000, max_value=99999, value=4105))
    else:
        st.subheader("🗺️ Polígono de coordenadas")
        st.caption(
            "Ingresa pares lat,lon separados por líneas. "
            "Mínimo 3 puntos. Ejemplo:\n-29.0,-71.5\n-29.5,-71.5\n-29.5,-71.0\n-29.0,-71.0"
        )
        coords_raw = st.text_area(
            "Coordenadas (lat,lon)",
            height=160,
            placeholder="-29.0,-71.5\n-29.5,-71.5\n-29.5,-71.0\n-29.0,-71.0",
        )

    # ── Fechas ──────────────────────────────────────────────────────────────
    st.subheader("📅 Período de análisis")
    import datetime
    col1, col2 = st.columns(2)
    with col1:
        fecha_inicio = st.date_input(
            "Inicio",
            value=datetime.date(2023, 1, 1),
            min_value=datetime.date(1940, 1, 1),
            max_value=datetime.date(2024, 12, 31),
        )
    with col2:
        fecha_fin = st.date_input(
            "Término",
            value=datetime.date(2023, 12, 31),
            min_value=datetime.date(1940, 1, 1),
            max_value=datetime.date(2024, 12, 31),
        )

    # ── Rango de temperatura deseado ────────────────────────────────────────
    st.subheader("🌡️ Rango de temperatura deseado (°C)")
    temp_min, temp_max = st.slider(
        "Rango [mín, máx]",
        min_value=-10.0,
        max_value=40.0,
        value=(10.0, 22.0),
        step=0.5,
    )
    st.caption(
        f"Un punto es **apto** si su temperatura mínima absoluta ≥ {temp_min}°C "
        f"**y** su máxima absoluta ≤ {temp_max}°C durante todo el período."
    )

    # ── Resolución de grilla ────────────────────────────────────────────────
    st.subheader("🔲 Resolución de grilla")
    paso_opciones = {
        "Gruesa (0.25° ≈ 28 km, rápida)": 0.25,
        "Media (0.1° ≈ 11 km)": 0.1,
        "Fina (0.05° ≈ 5.5 km, lenta)": 0.05,
    }
    paso_label = st.selectbox("Paso de grilla", list(paso_opciones.keys()), index=1)
    paso_grados = paso_opciones[paso_label]

    # ── Botón de análisis ───────────────────────────────────────────────────
    st.divider()
    ejecutar = st.button("🔍 Analizar territorio", type="primary", width="stretch")

# ─────────────────────────────────────────────────────────────────────────────
# Lógica principal
# ─────────────────────────────────────────────────────────────────────────────

# Inicializar session_state
if "resultados" not in st.session_state:
    st.session_state.resultados = None
if "series" not in st.session_state:
    st.session_state.series = None
if "puntos" not in st.session_state:
    st.session_state.puntos = None
if "geometria" not in st.session_state:
    st.session_state.geometria = None
if "nombre_territorio" not in st.session_state:
    st.session_state.nombre_territorio = ""
if "last_clicked" not in st.session_state:
    st.session_state.last_clicked = None

if ejecutar:
    # ── Validaciones ────────────────────────────────────────────────────────
    if fecha_inicio >= fecha_fin:
        st.error("❌ La fecha de inicio debe ser anterior a la fecha de término.")
        st.stop()
    if temp_min >= temp_max:
        st.error("❌ La temperatura mínima debe ser menor a la máxima.")
        st.stop()

    # ── Resolver geometría ──────────────────────────────────────────────────
    with st.spinner("Resolviendo geometría del territorio…"):
        try:
            if modo == "Por comuna":
                if tipo_id == "Nombre":
                    assert nombre_comuna is not None
                    nombre_terr, geom = geo.geometria_por_nombre(nombre_comuna)
                else:
                    assert cut_comuna is not None
                    nombre_terr, geom = geo.geometria_por_codigo(cut_comuna)
            else:
                # Parsear coordenadas
                lineas = [l.strip() for l in coords_raw.strip().splitlines() if l.strip()]
                coords = []
                for linea in lineas:
                    partes = linea.split(",")
                    if len(partes) != 2:
                        raise ValueError(f"Formato inválido: '{linea}'. Usa 'lat,lon'.")
                    coords.append((float(partes[0]), float(partes[1])))
                geom = geo.poligono_desde_coordenadas(coords)
                nombre_terr = "Polígono personalizado"
        except Exception as e:
            st.error(f"❌ Error al resolver el territorio: {e}")
            st.stop()

    # ── Muestreo de grilla ──────────────────────────────────────────────────
    with st.spinner("Muestreando grilla de puntos…"):
        puntos = geo.muestrear_grilla(geom, paso_grados)
        st.toast(f"{len(puntos)} puntos en la grilla.")

    if not puntos:
        st.error("❌ No se encontraron puntos en la grilla para la geometría indicada.")
        st.stop()

    # ── Consulta Open-Meteo ─────────────────────────────────────────────────
    with st.spinner(f"Consultando temperatura para {len(puntos)} puntos (puede tardar)…"):
        try:
            series = clima.obtener_temperatura_diaria(
                puntos,
                str(fecha_inicio),
                str(fecha_fin),
            )
        except Exception as e:
            st.error(f"❌ Error al consultar Open-Meteo: {e}")
            st.stop()

    # ── Agregación y filtro ─────────────────────────────────────────────────
    df_puntos = analisis.agregar_puntos(puntos, series)
    df_puntos = analisis.filtrar_aptos(df_puntos, temp_min, temp_max)

    if "apto" not in df_puntos.columns:
        st.error(
            "❌ La función `filtrar_aptos` todavía no está implementada.\n\n"
            "Abre `src/meteo/analisis.py` y completa el `TODO(human)` en `filtrar_aptos()`."
        )
        st.stop()

    # Guardar en session_state
    st.session_state.resultados = df_puntos
    st.session_state.series = series
    st.session_state.puntos = puntos
    st.session_state.geometria = geom
    st.session_state.nombre_territorio = nombre_terr
    st.session_state.last_clicked = None  # Resetear clic al analizar nuevo territorio

# ─────────────────────────────────────────────────────────────────────────────
# Visualización de resultados
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.resultados is not None:
    df = st.session_state.resultados
    n_aptos = int(df["apto"].sum()) if "apto" in df.columns else 0
    n_total = len(df[df["datos_ok"] == True])
    nombre_terr = st.session_state.nombre_territorio

    st.success(
        f"**{nombre_terr}** — {n_aptos} de {n_total} puntos aptos "
        f"({100*n_aptos/max(n_total,1):.0f}%)"
    )

    # ── Layout: mapa | gráficos ─────────────────────────────────────────────
    col_mapa, col_graf = st.columns([3, 2], gap="medium")

    with col_mapa:
        st.subheader("🗺️ Mapa de temperatura")
        m = mapa.crear_mapa(df, st.session_state.geometria, nombre_terr)
        mapa_data = st_folium(m, height=500, use_container_width=True)
        # st_folium resetea last_clicked cuando el mapa se recrea; lo persistimos manualmente
        if mapa_data and mapa_data.get("last_clicked"):
            st.session_state.last_clicked = mapa_data["last_clicked"]

    with col_graf:
        st.subheader("📈 Serie temporal")

        # Selección del punto: el último clic persistido en session_state, o el punto central
        punto_seleccionado = None
        last_clicked = st.session_state.last_clicked
        if last_clicked:
            lat_click = last_clicked["lat"]
            lon_click = last_clicked["lng"]
            # Encontrar el punto más cercano en la grilla
            dists = df.apply(
                lambda r: (r["lat"] - lat_click)**2 + (r["lon"] - lon_click)**2,
                axis=1,
            )
            idx_cercano = dists.idxmin()
            punto_seleccionado = idx_cercano
            st.caption(
                f"Punto seleccionado: ({df.loc[idx_cercano,'lat']:.4f}, "
                f"{df.loc[idx_cercano,'lon']:.4f})"
            )
        else:
            # Por defecto: punto con temperatura media más representativa
            validos = df[df["datos_ok"] == True]
            if not validos.empty:
                mediana = validos["tmean_periodo"].median()
                punto_seleccionado = (validos["tmean_periodo"] - mediana).abs().idxmin()
            st.caption("Haz clic en un punto del mapa para ver su serie temporal.")

        if punto_seleccionado is not None:
            series_list = cast(list[pd.DataFrame], st.session_state.series)
            serie_df = series_list[int(punto_seleccionado)]
            fila = df.loc[punto_seleccionado]
            titulo_serie = (
                f"Lat {fila['lat']:.4f} | Lon {fila['lon']:.4f} — "
                f"{'✅ Apto' if bool(fila.get('apto', False)) else '❌ No apto'}"
            )
            fig_serie = graficos.serie_temporal(
                serie_df,
                titulo=titulo_serie,
                temp_min=st.session_state.get("temp_min_ref"),
                temp_max=st.session_state.get("temp_max_ref"),
            )
            st.plotly_chart(fig_serie, width="stretch")

        # Guardar rango para la próxima renderización
        # (se hace aquí porque el sidebar ya fue ejecutado)
        st.session_state["temp_min_ref"] = temp_min
        st.session_state["temp_max_ref"] = temp_max

    # ── Gráfico de distribución territorial ────────────────────────────────
    st.subheader("📊 Distribución territorial")
    fig_dist = graficos.resumen_territorial(df)
    st.plotly_chart(fig_dist, width="stretch")

    # ── Tabla de puntos aptos ───────────────────────────────────────────────
    st.subheader("📋 Puntos aptos")
    aptos = df[df.get("apto", pd.Series(False, index=df.index)) == True] if "apto" in df.columns else pd.DataFrame()
    if aptos.empty:
        st.info("No se encontraron puntos aptos con el rango y período seleccionados.")
    else:
        st.dataframe(
            aptos[["lat", "lon", "tmin_periodo", "tmax_periodo", "tmean_periodo"]]
            .rename(columns={
                "lat": "Latitud", "lon": "Longitud",
                "tmin_periodo": "T mín (°C)", "tmax_periodo": "T máx (°C)",
                "tmean_periodo": "T prom (°C)",
            })
            .sort_values("T prom (°C)"),
            width="stretch",
        )
        # Descarga CSV
        csv_bytes = aptos.to_csv(index=False).encode()
        st.download_button(
            "⬇️ Descargar puntos aptos (CSV)",
            data=csv_bytes,
            file_name=f"puntos_aptos_{nombre_terr.replace(' ', '_')}.csv",
            mime="text/csv",
        )
else:
    # Estado inicial — mostrar instrucciones
    st.info(
        "👈 Configura los parámetros en el panel lateral y presiona **Analizar territorio** "
        "para iniciar la búsqueda.\n\n"
        "**Datos:** temperatura del aire a 2 m (ERA5 vía Open-Meteo), dato diario.\n\n"
        "**Supuesto:** se usa temperatura del aire como proxy climático; "
        "no es temperatura del agua."
    )
    with st.expander("¿Cómo funciona?"):
        st.markdown("""
1. **Define el área**: elige una comuna por nombre/CUT o dibuja un polígono con coordenadas.
2. **Elige el período**: cualquier rango desde 1940 hasta el año pasado.
3. **Fija el rango de temperatura**: [T mínima, T máxima] deseada en °C.
4. **Ejecuta**: la app muestrea una grilla de puntos dentro del área, consulta la
   temperatura histórica en Open-Meteo y marca qué puntos son aptos.
5. **Explora**: haz clic en los puntos del mapa para ver la serie temporal detallada.

**Criterio de aptitud**: un punto es apto si en **ningún día** del período la temperatura
bajó de T mínima ni subió de T máxima (i.e., la temperatura siempre estuvo dentro del rango).
        """)

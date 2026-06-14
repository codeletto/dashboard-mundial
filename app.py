"""
Dashboard Mundial 2026 - App publica (solo lectura).
Lee data.json y muestra la informacion. Se despliega en Streamlit Cloud.

Navegacion:
  - Sidebar (ocultable): cambia entre CAPAS de analisis.
  - Dentro de cada capa: pestanas para ordenar el contenido.

Ejecutar:  streamlit run app.py
"""

import base64
import os
import re
import unicodedata

import pandas as pd
import streamlit as st
import engine

FLAGS_DIR = "flags"   # carpeta con las imagenes <slug>.png
FLAG_W = 18           # ancho de la bandera en px (sube/baja este numero para ajustar)


def slug(name):
    """Convierte 'Corea del Sur' -> 'corea_del_sur' (sin acentos, minusculas)."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", "_", s.lower().strip())


def flag_uri(name):
    """data URI de la bandera, o cadena vacia si el archivo no existe."""
    path = os.path.join(FLAGS_DIR, slug(name) + ".png")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    return ""


def flag_img(name):
    """<img> de la bandera para incrustar junto al nombre (o '' si no existe)."""
    uri = flag_uri(name)
    if not uri:
        return ""
    return (f'<img src="{uri}" style="width:{FLAG_W}px;height:auto;'
            f'vertical-align:middle;margin-right:6px;border-radius:2px;">')


st.set_page_config(
    page_title="Mundial 2026 | Clasificacion",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- carga de datos ----------
data = engine.load_data("data.json")
tables = engine.all_group_tables(data)
thirds = engine.best_thirds(tables)
meta = data.get("meta", {})

# ---------- sidebar: capas de analisis ----------
st.sidebar.title("Mundial 2026")
capa = st.sidebar.radio("Capa de analisis",
                        ["Clasificacion", "Finanzas", "Predicciones"])
estado_datos = "EN VIVO" if meta.get("source") == "live" else "SNAPSHOT"
st.sidebar.divider()
st.sidebar.caption(f"Datos: **{estado_datos}**")
st.sidebar.caption(f"Actualizado: {meta.get('updated', 's/f')}")

# ---------- estilos de fondo por posicion ----------
BG_CLASIFICA = "rgba(34,197,94,0.18)"
BG_TERCERO = "rgba(234,179,8,0.18)"
BG_ELIM = "rgba(239,68,68,0.12)"
BG_FUERA = "rgba(239,68,68,0.10)"


def _cell(content, align="right"):
    return f'<td style="padding:4px 8px;text-align:{align};">{content}</td>'


def render_group_html(group, table, completo, en_vivo):
    headers = ["#", "Equipo", "PJ", "G", "E", "P", "GF", "GC", "DG", "Pts"]
    aligns = ["center", "left", "right", "right", "right", "right",
              "right", "right", "right", "right"]
    ths = "".join(
        f'<th style="padding:4px 8px;text-align:{a};font-weight:600;'
        f'border-bottom:1px solid rgba(128,128,128,.3);">{h}</th>'
        for h, a in zip(headers, aligns))

    filas = ""
    for pos, t in enumerate(table, 1):
        bg = BG_CLASIFICA if pos <= 2 else (BG_TERCERO if pos == 3 else BG_ELIM)
        vals = [str(pos), flag_img(t.name) + t.name, t.played, t.won, t.drawn,
                t.lost, t.gf, t.ga, f"{t.gd:+d}", f"<b>{t.points}</b>"]
        celdas = "".join(_cell(v, a) for v, a in zip(vals, aligns))
        filas += f'<tr style="background-color:{bg};">{celdas}</tr>'

    etiqueta = "completo" if completo else "provisional"
    vivo = ' <span style="color:#ef4444;">&#128308; en vivo</span>' if en_vivo else ""
    html = (
        f'<div style="font-size:0.9rem;margin:2px 0 4px;">'
        f'<b>Grupo {group}</b> &middot; <i>{etiqueta}</i>{vivo}</div>'
        f'<table style="width:100%;border-collapse:collapse;font-size:0.82rem;">'
        f'<thead><tr>{ths}</tr></thead><tbody>{filas}</tbody></table>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_thirds_html(thirds):
    headers = ["#", "Equipo", "Gr", "PJ", "Pts", "DG", "GF", "Estado"]
    aligns = ["center", "left", "center", "right", "right", "right", "right", "left"]
    ths = "".join(
        f'<th style="padding:4px 8px;text-align:{a};font-weight:600;'
        f'border-bottom:1px solid rgba(128,128,128,.3);">{h}</th>'
        for h, a in zip(headers, aligns))
    filas = ""
    for r in thirds:
        t = r["equipo"]
        bg = BG_CLASIFICA if r["clasifica"] else BG_FUERA
        estado = "CLASIFICA" if r["clasifica"] else "fuera (por ahora)"
        vals = [str(r["pos"]), flag_img(t.name) + t.name, r["grupo"],
                t.played, f"<b>{t.points}</b>", f"{t.gd:+d}", t.gf, estado]
        celdas = "".join(_cell(v, a) for v, a in zip(vals, aligns))
        filas += f'<tr style="background-color:{bg};">{celdas}</tr>'
    html = (
        f'<table style="width:100%;border-collapse:collapse;font-size:0.85rem;">'
        f'<thead><tr>{ths}</tr></thead><tbody>{filas}</tbody></table>'
    )
    st.markdown(html, unsafe_allow_html=True)


# ======================================================================
#  CAPA: CLASIFICACION
# ======================================================================
def render_clasificacion():
    st.title("Mundial 2026 — Quien clasifica")
    st.caption("Pasan los 2 primeros de cada grupo (24) + los 8 mejores terceros = 32 a dieciseisavos.")

    tab_g, tab_t, tab_e, tab_r = st.tabs(
        ["Grupos", "Mejores terceros", "Escenarios", "Reglas"])

    # --- pestana Grupos ---
    with tab_g:
        grupos = list(tables.keys())
        for ini in range(0, len(grupos), 3):
            cols = st.columns(3)
            for col, g in zip(cols, grupos[ini:ini + 3]):
                with col:
                    info = data["groups"][g]
                    completo = engine.group_is_complete(info)
                    en_vivo = any(engine.is_live(m) for m in info["matches"])
                    render_group_html(g, tables[g], completo, en_vivo)
                    st.write("")

    # --- pestana Mejores terceros ---
    with tab_t:
        st.subheader("Carrera por los 8 mejores terceros")
        st.caption("Criterios: puntos -> diferencia de goles -> goles a favor -> Fair Play -> ranking FIFA")
        render_thirds_html(thirds)
        st.caption("La linea entre el puesto 8 y el 9 es el corte de clasificacion.")

    # --- pestana Escenarios ---
    with tab_e:
        st.subheader("Escenarios: que puede pasar en cada grupo")
        st.caption("Prueba todos los resultados posibles de los partidos que faltan y "
                   "muestra en que posiciones puede terminar cada equipo.")
        grupo_sel = st.selectbox("Elige un grupo", list(tables.keys()),
                                 format_func=lambda g: f"Grupo {g}")
        info_sel = data["groups"][grupo_sel]

        pend = engine.pending_matches(info_sel)
        if not pend:
            st.success("Grupo completo: ya no quedan partidos por jugar.")
        else:
            st.markdown(f"**Partidos pendientes ({len(pend)}):**")
            st.markdown("\n".join(f"- {h} vs {a}" for h, a in pend))

        estado = engine.group_status(info_sel)
        erows = [{
            "Equipo": n,
            "Puede terminar en": ", ".join(str(p) for p in d["posiciones"]),
            "Estado": d["estado"],
        } for n, d in estado.items()]
        edf = pd.DataFrame(erows)

        def color_estado(row):
            est = row["Estado"]
            if est.startswith("Clasificado"):
                bg = "background-color: rgba(34,197,94,0.18)"
            elif est.startswith("Sin opciones"):
                bg = "background-color: rgba(239,68,68,0.15)"
            elif est.startswith("Su techo"):
                bg = "background-color: rgba(234,179,8,0.15)"
            else:
                bg = ""
            return [bg] * len(row)

        st.dataframe(
            edf.style.apply(color_estado, axis=1).hide(axis="index"),
            width='stretch', hide_index=True)
        st.caption("Calculo basado en puntos. Los terceros dependen ademas de otros grupos.")

    # --- pestana Reglas ---
    with tab_r:
        st.subheader("Como funcionan los desempates (Art. 13 FIFA 2026)")
        st.markdown(
            """
**Dentro de un grupo**, si hay empate en puntos, en este orden:
1. Puntos en los partidos **entre los empatados** (enfrentamiento directo)
2. Diferencia de goles **entre los empatados**
3. Goles marcados **entre los empatados**
4. Diferencia de goles en **todos** los partidos del grupo
5. Goles marcados en **todos** los partidos del grupo
6. Fair Play (amarilla -1, roja por doble amarilla -3, roja directa -4, amarilla+roja directa -5)
7. Ranking FIFA

El cambio clave de 2026: **el enfrentamiento directo manda por encima de la diferencia de goles general.**

**Para los 8 mejores terceros** (selecciones de grupos distintos):
puntos -> diferencia de goles -> goles a favor -> Fair Play -> ranking FIFA.
            """
        )


# ======================================================================
#  CAPAS EN CONSTRUCCION
# ======================================================================
def render_finanzas():
    st.title("Finanzas — Capa 3")
    st.info("En construccion. Aqui ira: valor de plantilla vs. rendimiento, "
            "costo por punto, y selecciones infravaloradas / sobrevaloradas.")


def render_predicciones():
    st.title("Predicciones — Capa 1")
    st.info("En construccion. Aqui ira: modelo predictivo (Poisson / Elo) "
            "y el registro publico de aciertos por jornada.")


# ---------- enrutado por capa ----------
if capa == "Clasificacion":
    render_clasificacion()
elif capa == "Finanzas":
    render_finanzas()
else:
    render_predicciones()

st.divider()
st.caption("Proyecto de datos · Python + pandas + Streamlit · reglas verificadas contra el reglamento oficial FIFA 2026.")
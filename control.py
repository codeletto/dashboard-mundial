"""
Control de partidos - APP LOCAL (no desplegar en la nube).

Carga/edita resultados del Mundial con formularios y los guarda en data.json.
Cada partido tiene tres estados:
  - Programado : aun no se juega (no entra en la tabla).
  - En juego   : marcador provisional (cuenta en la tabla, pendiente en escenarios).
  - Finalizado : resultado definitivo.

Despues de guardar:  git add data.json -> commit -> push.

IMPORTANTE: esta app escribe archivos, solo funciona en local.
La app publica es app.py.

Ejecutar:  streamlit run control.py
"""

import json
from datetime import date

import streamlit as st
import engine

DATA_PATH = "data.json"
ESTADOS = ["Programado", "En juego", "Finalizado"]

st.set_page_config(page_title="Control de partidos", layout="centered")


def save_data(d, path=DATA_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def current_state(matches, t1, t2):
    """Devuelve (goles_t1, goles_t2, estado) del partido t1-t2 segun data.json."""
    for m in matches:
        if {m["home"], m["away"]} == {t1, t2} and engine.has_score(m):
            g1, g2 = (m["hg"], m["ag"]) if m["home"] == t1 else (m["ag"], m["hg"])
            estado = "En juego" if engine.is_live(m) else "Finalizado"
            return g1, g2, estado
    return 0, 0, "Programado"


def pairings(teams):
    """Los 6 enfrentamientos de un grupo de 4 (todos contra todos)."""
    return [(teams[i], teams[j])
            for i in range(len(teams)) for j in range(i + 1, len(teams))]


# ---------- carga ----------
data = engine.load_data(DATA_PATH)

st.title("Control de partidos")
st.caption("Panel LOCAL. Carga resultados y guarda. Luego sube data.json con git.")

grupo = st.selectbox("Grupo", list(data["groups"].keys()),
                     format_func=lambda g: f"Grupo {g}")
info = data["groups"][grupo]
teams = [t["name"] for t in info["teams"]]

# ---------- formulario de resultados ----------
with st.form(f"form_{grupo}"):
    st.markdown(f"### Grupo {grupo}")
    entradas = {}
    for a, b in pairings(teams):
        g1, g2, est = current_state(info["matches"], a, b)
        st.markdown(f"**{a}  vs  {b}**")
        c1, c2 = st.columns(2)
        ga = c1.number_input(a, min_value=0, max_value=30, value=g1,
                             key=f"{grupo}-{a}-{b}-ga")
        gb = c2.number_input(b, min_value=0, max_value=30, value=g2,
                             key=f"{grupo}-{a}-{b}-gb")
        estado = st.radio("Estado", ESTADOS, index=ESTADOS.index(est),
                          key=f"{grupo}-{a}-{b}-estado", horizontal=True)
        entradas[(a, b)] = (ga, gb, estado)
        st.divider()
    guardar = st.form_submit_button("Guardar grupo")

if guardar:
    nuevos = []
    for (a, b), (ga, gb, estado) in entradas.items():
        if estado == "Programado":
            continue
        nuevos.append({
            "home": a, "away": b, "hg": int(ga), "ag": int(gb),
            "status": "en_juego" if estado == "En juego" else "finalizado",
        })
    data["groups"][grupo]["matches"] = nuevos
    data.setdefault("meta", {})["updated"] = date.today().isoformat()
    save_data(data)
    en_vivo = sum(1 for m in nuevos if m["status"] == "en_juego")
    st.success(f"Grupo {grupo} guardado: {len(nuevos)} partido(s)"
               f"{f', {en_vivo} en juego' if en_vivo else ''}. "
               f"Ahora: git add data.json -> commit -> push.")

# ---------- vista previa de la tabla actual ----------
st.markdown("#### Tabla actual del grupo")
tabla = engine.compute_group_table(info["teams"], info["matches"])
for pos, t in enumerate(tabla, 1):
    st.write(f"{pos}. **{t.name}** — {t.points} pts · DG {t.gd:+d} · {t.played} PJ")
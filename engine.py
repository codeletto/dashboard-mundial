"""
Motor de clasificación del Mundial 2026.

Implementa los criterios de desempate del Artículo 13 del Reglamento oficial
de la Copa Mundial de la FIFA 2026, en este orden EXACTO cuando hay empate
en puntos dentro de un grupo:

  PASO 1 (enfrentamiento directo, solo entre los empatados):
    a) puntos en los partidos entre los empatados
    b) diferencia de goles entre los empatados
    c) goles marcados entre los empatados
  PASO 2 (si siguen empatados):
    - se re-aplican a) a c) a los partidos entre las selecciones que QUEDEN
      empatadas (subconjunto). Si aún no se resuelve:
    d) diferencia de goles en TODOS los partidos del grupo
    e) goles marcados en TODOS los partidos del grupo
    f) puntos de Fair Play (amarilla -1, roja por doble amarilla -3,
       roja directa -4, amarilla + roja directa -5)
  PASO 3:
    g) ranking FIFA (más reciente; ediciones anteriores hacia atrás)

OJO: el enfrentamiento directo (paso 1) MANDA por encima de la diferencia
de goles general (paso 2). Es el cambio clave del formato 2026.

Para los 8 mejores terceros (selecciones de grupos distintos, sin
enfrentamiento directo) el orden es:
    puntos -> dif. de goles -> goles a favor -> Fair Play -> ranking FIFA
"""

import json


class TeamStats:
    """Acumula las estadisticas de una seleccion en su grupo."""

    def __init__(self, name, fifa_rank):
        self.name = name
        self.fifa_rank = fifa_rank          # menor numero = mejor ranking
        self.played = 0
        self.won = 0
        self.drawn = 0
        self.lost = 0
        self.gf = 0                         # goles a favor
        self.ga = 0                         # goles en contra
        self.fair_play = 0                  # deducciones acumuladas (<= 0)

    @property
    def points(self):
        return self.won * 3 + self.drawn

    @property
    def gd(self):
        return self.gf - self.ga

    def to_dict(self):
        return {
            "name": self.name,
            "PJ": self.played, "PG": self.won, "PE": self.drawn, "PP": self.lost,
            "GF": self.gf, "GC": self.ga, "DG": self.gd,
            "Pts": self.points, "FairPlay": self.fair_play,
            "fifa_rank": self.fifa_rank,
        }


def has_score(match):
    """True si el partido tiene ambos marcadores (cuenta para la TABLA)."""
    return match.get("hg") is not None and match.get("ag") is not None


def is_live(match):
    """True si el partido esta EN JUEGO (marcador provisional)."""
    return has_score(match) and match.get("status") == "en_juego"


def is_final(match):
    """True si el partido ya FINALIZO (resultado definitivo)."""
    return has_score(match) and match.get("status", "finalizado") != "en_juego"


def _is_played(match):
    """Alias historico: para la tabla, 'jugado' = tiene marcador (en juego o final)."""
    return has_score(match)


def _accumulate(stats, matches):
    """Llena las estadisticas de cada equipo a partir de los partidos jugados."""
    for m in matches:
        if not _is_played(m):
            continue
        h, a = stats[m["home"]], stats[m["away"]]
        hg, ag = m["hg"], m["ag"]
        h.played += 1; a.played += 1
        h.gf += hg; h.ga += ag
        a.gf += ag; a.ga += hg
        h.fair_play += m.get("fp_home", 0)
        a.fair_play += m.get("fp_away", 0)
        if hg > ag:
            h.won += 1; a.lost += 1
        elif hg < ag:
            a.won += 1; h.lost += 1
        else:
            h.drawn += 1; a.drawn += 1


def _mini_table(names, matches):
    """
    Tabla de enfrentamiento directo: solo cuenta los partidos jugados ENTRE
    las selecciones de `names`. Devuelve {nombre: {'pts','gd','gf'}}.
    """
    sub = {n: {"pts": 0, "gd": 0, "gf": 0} for n in names}
    nameset = set(names)
    for m in matches:
        if not _is_played(m):
            continue
        if m["home"] in nameset and m["away"] in nameset:
            hg, ag = m["hg"], m["ag"]
            sub[m["home"]]["gf"] += hg; sub[m["home"]]["gd"] += hg - ag
            sub[m["away"]]["gf"] += ag; sub[m["away"]]["gd"] += ag - hg
            if hg > ag:
                sub[m["home"]]["pts"] += 3
            elif hg < ag:
                sub[m["away"]]["pts"] += 3
            else:
                sub[m["home"]]["pts"] += 1; sub[m["away"]]["pts"] += 1
    return sub


def _order_by_overall(teams):
    """Criterios d-f-g: dif. goles total, goles total, fair play, ranking FIFA."""
    return sorted(
        teams,
        key=lambda t: (t.gd, t.gf, t.fair_play, -t.fifa_rank),
        reverse=True,
    )


def _order_tied(teams, matches):
    """
    Ordena un conjunto de equipos EMPATADOS EN PUNTOS aplicando el Art. 13.
    Recursivo: respeta el "re-aplicar a-c entre los que sigan empatados".
    """
    if len(teams) <= 1:
        return list(teams)

    names = [t.name for t in teams]
    mini = _mini_table(names, matches)

    def h2h_key(t):
        return (mini[t.name]["pts"], mini[t.name]["gd"], mini[t.name]["gf"])

    teams_sorted = sorted(teams, key=h2h_key, reverse=True)

    result = []
    i = 0
    while i < len(teams_sorted):
        j = i
        key = h2h_key(teams_sorted[i])
        while j < len(teams_sorted) and h2h_key(teams_sorted[j]) == key:
            j += 1
        run = teams_sorted[i:j]            # equipos aun empatados tras a-c
        if len(run) == 1:
            result.extend(run)
        elif len(run) == len(teams):
            # el enfrentamiento directo no separo a nadie -> criterios d-f-g
            result.extend(_order_by_overall(run))
        else:
            # subconjunto sigue empatado -> re-aplicar a-c solo entre ellos
            result.extend(_order_tied(run, matches))
        i = j
    return result


def compute_group_table(teams_info, matches):
    """
    Devuelve la lista ordenada (1ro a 4to) de TeamStats de un grupo.
    `teams_info`: lista de dicts {'name','fifa_rank'}.
    """
    stats = {t["name"]: TeamStats(t["name"], t["fifa_rank"]) for t in teams_info}
    _accumulate(stats, matches)

    # 1) orden base por puntos
    by_points = sorted(stats.values(), key=lambda t: t.points, reverse=True)

    # 2) resolver empates dentro de cada bloque con los mismos puntos
    ordered = []
    i = 0
    while i < len(by_points):
        j = i
        while j < len(by_points) and by_points[j].points == by_points[i].points:
            j += 1
        block = by_points[i:j]
        ordered.extend(_order_tied(block, matches) if len(block) > 1 else block)
        i = j
    return ordered


def all_group_tables(data):
    """{grupo: [TeamStats ordenados]} para los 12 grupos."""
    out = {}
    for g, info in data["groups"].items():
        out[g] = compute_group_table(info["teams"], info["matches"])
    return out


def group_is_complete(info):
    """Un grupo esta completo cuando se jugaron sus 6 partidos (4 equipos)."""
    return sum(1 for m in info["matches"] if is_final(m)) >= 6


def best_thirds(tables):
    """
    Ordena los 12 terceros y devuelve la lista completa con un flag 'clasifica'
    para los 8 primeros. Criterios: pts -> DG -> GF -> Fair Play -> ranking FIFA.
    """
    thirds = []
    for g, table in tables.items():
        if len(table) >= 3:
            t = table[2]
            thirds.append((g, t))
    thirds.sort(
        key=lambda gt: (gt[1].points, gt[1].gd, gt[1].gf, gt[1].fair_play, -gt[1].fifa_rank),
        reverse=True,
    )
    ranked = []
    for pos, (g, t) in enumerate(thirds, start=1):
        ranked.append({"pos": pos, "grupo": g, "equipo": t, "clasifica": pos <= 8})
    return ranked


def load_data(path="data.json"):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ======================================================================
#  CAPA 2 (Paso 2): CALCULADORA DE ESCENARIOS
#  Enumera los resultados posibles de los partidos que faltan en un grupo
#  y calcula en que posiciones puede terminar cada equipo.
# ======================================================================

from itertools import product


def pending_matches(info):
    """
    Devuelve los partidos del grupo que aun NO se han jugado.
    Un grupo de 4 equipos tiene 6 partidos (todos contra todos).
    """
    teams = [t["name"] for t in info["teams"]]
    todos = [tuple(sorted((teams[i], teams[j])))
             for i in range(len(teams)) for j in range(i + 1, len(teams))]
    jugados = {frozenset((m["home"], m["away"]))
               for m in info["matches"] if is_final(m)}
    return [par for par in todos if frozenset(par) not in jugados]


def possible_positions(info):
    """
    Enumera todos los escenarios posibles de los partidos pendientes y
    devuelve, por equipo, el CONJUNTO de posiciones finales que puede alcanzar.

    Cada partido pendiente tiene 3 resultados: gana local (1-0), empate (0-0)
    o gana visitante (0-1). Es un calculo basado en PUNTOS; la diferencia de
    goles se mueve solo +/-1 por partido, asi que es exacto para los puntos
    y aproximado en empates que se definan por diferencia de goles.
    """
    base = [m for m in info["matches"] if is_final(m)]
    pend = pending_matches(info)
    positions = {t["name"]: set() for t in info["teams"]}
    OUTCOMES = [(1, 0), (0, 0), (0, 1)]   # local gana / empate / visitante gana

    for combo in product(OUTCOMES, repeat=len(pend)):
        sim = list(base)
        for (home, away), (hg, ag) in zip(pend, combo):
            sim.append({"home": home, "away": away, "hg": hg, "ag": ag})
        table = compute_group_table(info["teams"], sim)
        for pos, t in enumerate(table, 1):
            positions[t.name].add(pos)
    return positions


def group_status(info):
    """
    Traduce las posiciones posibles a un estado legible por equipo.
    Solo evalua el top-2 del grupo (los terceros dependen de otros grupos).
    """
    pos = possible_positions(info)
    out = {}
    for name, ps in pos.items():
        if ps <= {1, 2}:
            estado = "Clasificado (top 2 asegurado)"
        elif min(ps) <= 2:
            estado = "Puede quedar entre los 2 primeros"
        elif min(ps) == 3:
            estado = "Su techo es 3er puesto (depende de otros grupos)"
        else:
            estado = "Sin opciones de top 2"
        out[name] = {"posiciones": sorted(ps), "estado": estado}
    return out

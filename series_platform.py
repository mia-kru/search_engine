import urllib.parse as up
from typing import Any
import streamlit as st
from tantivy import Query, Index, SchemaBuilder, Occur

import utils

# Konstanten
TMDB_PATH = "https://image.tmdb.org/t/p/original"
TMDB_PATH_SMALL = "https://image.tmdb.org/t/p/w200"
INDEX_PATH = "serien_300"  # bestehendes Tantivy-Index-Verzeichnis
TOP_K = 20          # wie viele Ergebnisse angezeigt werden sollen
CARDS_PER_PAGE = 3 # Cards, die in der zufälligen Anzeige auftauchen

schema_builder = SchemaBuilder()
# Text-Felder
schema_builder.add_text_field("wikidata", stored=True)
schema_builder.add_text_field("url", stored=True)
schema_builder.add_text_field("title", stored=True, tokenizer_name='en_stem')
schema_builder.add_text_field("description", stored=True, tokenizer_name='en_stem')  # Multi-valued text field
schema_builder.add_text_field("image", stored=True)
schema_builder.add_text_field("locations", stored=True)
schema_builder.add_text_field("countries", stored=True)
schema_builder.add_text_field("genres", stored=True)
schema_builder.add_text_field("tmdb_overview", stored=True, tokenizer_name='en_stem')
schema_builder.add_text_field("tmdb_poster_path", stored=True)
schema_builder.add_text_field("trailer", stored=True)

# Integer-Felder
schema_builder.add_integer_field("id", stored=True, indexed=True)
schema_builder.add_integer_field("follower", stored=True, fast=True)
schema_builder.add_integer_field("score", stored=True, fast=True)
schema_builder.add_integer_field("start", stored=True, fast=True)
schema_builder.add_integer_field("tmdb_genre_ids", stored=True, indexed=True)
schema_builder.add_integer_field("tmdb_vote_count", stored=True, fast=True)

# Float-Felder
schema_builder.add_float_field("tmdb_popularity", stored=True, fast=True)
schema_builder.add_float_field("tmdb_vote_average", stored=True, fast=True)

# Facettenfelder
schema_builder.add_facet_field("facet_locations")
schema_builder.add_facet_field("facet_countries")
schema_builder.add_facet_field("facet_genres")

schema = schema_builder.build()
index = Index(schema, path=str(INDEX_PATH))

searcher = index.searcher()

from streamlit.components.v1 import iframe
import pandas as pd

@st.cache_data(show_spinner=False)
def load_genres_from_csv(path="series.csv") -> list[str]:
    try:
        df = pd.read_csv(path)
        if "genres" not in df.columns:
            return []
        genres = set()
        for cell in df["genres"].dropna().astype(str):
            for g in cell.split(","):
                g = g.strip()
                if g:
                    genres.add(g)
        return sorted(genres)
    except Exception:
        return []

ALL_GENRES = load_genres_from_csv()

def doc_list(doc, field: str):
    """Gibt doc[field] als Liste zurück oder [] wenn Feld fehlt."""
    try:
        v = doc[field]
        return v if v is not None else []
    except Exception:
        return []

def doc_first(doc, field: str, default=None):
    """Gibt erstes Element aus doc[field] zurück oder default."""
    lst = doc_list(doc, field)
    return lst[0] if lst else default

def get_all_docs(limit=300):
    try:
        q_all = Query.all_query()  # falls vorhanden
    except Exception:
        q_all = index.parse_query("*", ["title"])  # fallback
    hits = searcher.search(q_all, limit).hits
    docs = []
    for score, addr in hits:
        doc = searcher.doc(addr)
        docs.append(doc)
    return docs

@st.cache_data(show_spinner=False)
def get_top_series_cards(n=5):
    docs = get_all_docs(limit=300)
    items = []
    for doc in docs:
        title = doc_first(doc, "title", "")
        doc_id = doc_first(doc, "id", None)

        poster = doc_list(doc, "tmdb_poster_path")
        poster_url = (TMDB_PATH_SMALL + poster[0]) if poster else ""

        vote_avg = doc_first(doc, "tmdb_vote_average", 0) or 0
        vote_cnt = doc_first(doc, "tmdb_vote_count", 0) or 0
        if doc_id is None or not poster_url:
            continue
        # kleine “Qualitätsbremse”: min. 50 Votes
        if vote_cnt < 50:
            continue
        items.append((float(vote_avg), int(vote_cnt), int(doc_id), title, poster_url))
    items.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return items[:n]

def render_home():
    # Banner: wir nehmen 3 Poster aus den Top-Serien und machen daraus einen Background
    top = get_top_series_cards(5)
    bg_urls = [t[4].replace("/w200", "/original") for t in top[:3]]  # größere Bilder
    bg = bg_urls[0] if bg_urls else ""

    st.markdown(
        f"""
<div class="hero">
  <div class="hero-bg" style="background-image:url('{bg}');"></div>
  <div class="hero-overlay"></div>
  <div class="hero-content">
    <div class="hero-title">TV.Base - Dein Archiv rund um Bewegtbilder</div>
    <p class="hero-subtitle">Hier auf TV.Base findest du alles rund um deine Lieblingsserien.</p>
  </div>
</div>
""",
        unsafe_allow_html=True
    )

    # Reihe 1: Top-Serien
    st.markdown('<div class="section-title">Top-Serien</div>', unsafe_allow_html=True)
    row = ['<div class="row-scroll">']
    for vote_avg, vote_cnt, doc_id, title, poster_url in top:
        href = f"?view=detail&id={doc_id}"
        row.append(
            f"""
<div class="row-item">
  <a class="card" href="{href}" target="_self">
    <img src="{poster_url}" loading="lazy" alt="poster">
    <div class="t">{title}</div>
  </a>
</div>
"""
        )
    row.append("</div>")
    st.markdown("".join(row), unsafe_allow_html=True)

    # Reihe 2: Genres (klickbar → search view)
    st.markdown('<div class="section-title">Genres</div>', unsafe_allow_html=True)
    chips = ['<div class="row-scroll">']
    for g in ALL_GENRES:
        href = f"?view=search&genre={up.quote(g)}"
        chips.append(f'<div class="row-item"><a class="genre-pill" href="{href}" target="_self">{g}</a></div>')
    chips.append("</div>")
    st.markdown("".join(chips), unsafe_allow_html=True)

from pathlib import Path

css = Path("styles.html").read_text(encoding="utf-8")

# optional: FontAwesome (für die Stern-Icons)
st.markdown(
    '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.1/css/all.min.css">',
    unsafe_allow_html=True
)

# CSS aktivieren (styles.html ist CSS-only)
st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def render_footer():
    st.markdown(
        '<div class="site-footer"><a class="brand" href="?view=home" target="_self">TV.Base</a></div>',
        unsafe_allow_html=True
    )

def render_header():
    # Layout per HTML-Container + Streamlit Widgets
    st.markdown('<div class="site-header"><div class="site-header-inner">', unsafe_allow_html=True)

    # Brand (klickbar)
    st.markdown('<a class="brand" href="?view=home" target="_self">TV.Base</a>', unsafe_allow_html=True)

    # Suche + Genre (Enter-fähig)
    with st.form("header_search", clear_on_submit=False):
        c1, c2, c3 = st.columns([6, 3, 2])
        with c1:
            q_in = st.text_input(
                "Suche",
                value=q,
                placeholder="Serie suchen …",
                label_visibility="collapsed"
            )
        with c2:
            genre_in = st.selectbox(
                "Genre",
                options=["Alle"] + ALL_GENRES,
                index=(["Alle"] + ALL_GENRES).index(genre_filter) if genre_filter in ALL_GENRES else 0,
                label_visibility="collapsed"
            )
        with c3:
            submitted = st.form_submit_button("Suchen")

    # Nav Buttons
    n1, n2, n3 = st.columns([1, 1, 1])
    with n1:
        if st.button("Serien", use_container_width=True):
            st.query_params.update({"view": "series", "q": "", "genre": ""})
            st.rerun()
    with n2:
        if st.button("Watchlist", use_container_width=True):
            st.query_params.update({"view": "watchlist"})
            st.rerun()
    with n3:
        if st.button("Evaluation", use_container_width=True):
            st.query_params.update({"view": "evaluation"})
            st.rerun()

    st.markdown("</div></div>", unsafe_allow_html=True)

    # Form Submit Handling
    if submitted:
        st.query_params.update({
            "view": "search",
            "q": q_in.strip(),
            "genre": "" if genre_in == "Alle" else genre_in
        })
        st.rerun()

full_star = '<i class="fa-solid fa-star"></i>'
half_star = '<i class="fa-solid fa-star-half-stroke"></i>'
empty_star = '<i class="fa-regular fa-star"></i>'


# Hilfsfunktion für Seitenrouting mit Anfrageparametern.
# Gibt die Query-Parameter der aktuellen Seite als Dictionary zurück.
# Falls `st.query_params` nicht verfügbar ist, wird ein leeres Dictionary zurückgegeben.
def get_qp() -> dict[str, Any]:
    return getattr(st, "query_params", {})


qp = get_qp()

def qp_get(key: str, default: str = "") -> str:
    v = qp.get(key, default)
    if isinstance(v, list):
        v = v[0] if v else default
    return str(v)

view = qp_get("view", "home")     # default: Startseite
selected_id = qp_get("id", "")
q = up.unquote_plus(qp_get("q", ""))
genre_filter = up.unquote_plus(qp_get("genre", ""))
render_header()

def render_search():
    st.subheader("Suchergebnisse")

    if not q and not genre_filter:
        st.info("Gib einen Suchbegriff ein oder wähle ein Genre.")
        return

    # Query bauen (Title Terms MUST)
    boolean_parts = []
    if q.strip():
        for term in q.lower().strip().split():
            u_q = index.parse_query(term, ["title"])
            boolean_parts.append((Occur.Must, u_q))

    # Genre Filter: simplest reliable approach → nachträglich filtern
    # (Facet-Query wäre eleganter, aber Tantivy-Python API variiert je Version)
    try:
        base_q = Query.boolean_query(boolean_parts) if boolean_parts else Query.all_query()
    except Exception:
        base_q = Query.boolean_query(boolean_parts) if boolean_parts else index.parse_query("*", ["title"])

    hits = searcher.search(base_q, TOP_K).hits

    if not hits:
        st.warning("Keine Ergebnisse gefunden.")
        return

    cards_html = ['<div class="grid">']
    added = 0
    for score, addr in hits:
        doc = searcher.doc(addr)

        # Genre-Filter nachträglich (Textfeld "genres" ist stored)
        if genre_filter:
            gs = doc_list(doc, "genres")
            if genre_filter not in gs:
                continue

        doc_id = doc["id"][0]
        title = doc["title"][0]
        poster = doc_list(doc, "tmdb_poster_path")
        poster_url = (TMDB_PATH_SMALL + poster[0]) if poster else ""
        href = f"?view=detail&id={doc_id}&q={up.quote(q)}&genre={up.quote(genre_filter)}"
        img_tag = f'<img src="{poster_url}" loading="lazy" alt="poster">' if poster_url else ""
        cards_html.append(f"""<a class="card" href="{href}" target="_self">{img_tag}<div class="t">{title}</div></a>""")
        added += 1
        if added >= TOP_K:
            break

    cards_html.append("</div>")
    st.markdown("".join(cards_html), unsafe_allow_html=True)

def render_series():
    st.subheader("Serien")

    # zeigt alle Serien (optional gefiltert nach Genre aus Query-Param)
    try:
        base_q = Query.all_query()
    except Exception:
        base_q = index.parse_query("*", ["title"])

    hits = searcher.search(base_q, TOP_K).hits

    if not hits:
        st.warning("Keine Serien gefunden.")
        return

    cards_html = ['<div class="grid">']
    added = 0
    for score, addr in hits:
        doc = searcher.doc(addr)

        # optional: Genre-Filter anwenden
        if genre_filter:
            gs = doc_list(doc, "genres")
            if genre_filter not in gs:
                continue

        doc_id = doc["id"][0]
        title = doc["title"][0]
        poster = doc_list(doc, "tmdb_poster_path")
        poster_url = (TMDB_PATH_SMALL + poster[0]) if poster else ""
        href = f"?view=detail&id={doc_id}&genre={up.quote(genre_filter)}"
        img_tag = f'<img src="{poster_url}" loading="lazy" alt="poster">' if poster_url else ""
        cards_html.append(f"""<a class="card" href="{href}" target="_self">{img_tag}<div class="t">{title}</div></a>""")
        added += 1
        if added >= TOP_K:
            break

    cards_html.append("</div>")
    st.markdown("".join(cards_html), unsafe_allow_html=True)

def render_watchlist():
    st.subheader("Watchlist")

    wl = st.session_state.get("watchlist", set())
    if not wl:
        st.info("Deine Watchlist ist leer.")
        return

    cards_html = ['<div class="grid">']
    for doc_id in sorted(wl):
        q_t = index.parse_query(str(doc_id), ["id"])
        hits = searcher.search(q_t, 1).hits
        if not hits:
            continue
        _, addr = hits[0]
        doc = searcher.doc(addr)
        title = doc["title"][0]
        poster = doc_list(doc, "tmdb_poster_path")
        poster_url = (TMDB_PATH_SMALL + poster[0]) if poster else ""
        href = f"?view=detail&id={doc_id}"
        img_tag = f'<img src="{poster_url}" loading="lazy" alt="poster">' if poster_url else ""
        cards_html.append(f"""<a class="card" href="{href}" target="_self">{img_tag}<div class="t">{title}</div></a>""")
    cards_html.append("</div>")
    st.markdown("".join(cards_html), unsafe_allow_html=True)

    if st.button("Watchlist leeren"):
        st.session_state.watchlist = set()
        st.rerun()


def render_evaluation():
    st.subheader("Evaluation")
    st.write("Bitte nimm dir 2 Minuten Zeit für unsere Umfrage 🙂")

    # Beispiel: Google Forms / Typeform / LimeSurvey Link (Embed-Link!)
    SURVEY_URL = "https://docs.google.com/forms/d/e/1FAIpQLSesh9qO-J9xvxyQHNWzbqZ--ilXqcICUzYb3CYNs2uaoR3tOg/viewform?embedded=true"

    # iFrame einbetten
    iframe(SURVEY_URL, height=900, scrolling=True)


# Detail View
if view == "detail" and selected_id:
    q_t = index.parse_query(selected_id, ["id"])
    detail_hits = searcher.search(q_t, TOP_K).hits
    detail_score, detail_address = detail_hits[0]
    detail_doc = searcher.doc(detail_address)
    detail_title = detail_doc["title"][0]
    detail_overview_src = detail_doc["tmdb_overview"] or detail_doc["description"]
    detail_overview = detail_overview_src[0]
    detail_poster = detail_doc["tmdb_poster_path"]
    detail_poster_url = (TMDB_PATH_SMALL + detail_poster[0]) if detail_poster else ""
    trailer = detail_doc["trailer"]
    video_key = detail_doc["trailer"][0] if trailer else ""
    st.title(detail_title)
    genres = detail_doc["genres"]
    tags_html = "<div>"
    if genres is not None:
        for tag in genres:
            tags_html += f'<span class="tag">{tag}</span>'
        tags_html += "</div>"
    st.markdown(tags_html, unsafe_allow_html=True)
    if video_key != "":
        st.video(f"https://www.youtube.com/watch?v={video_key}")
    st.write(detail_overview)


    if "watchlist" not in st.session_state:
        st.session_state.watchlist = set()

    if st.button("⭐ Zur Watchlist hinzufügen"):
        st.session_state.watchlist.add(int(selected_id))
        st.success("Zur Watchlist hinzugefügt!")

    if st.button("← Zurück"):
        back_view = "search" if (q or genre_filter) else "home"
        payload = {"view": back_view}
        if q:
            payload["q"] = q
        if genre_filter:
            payload["genre"] = genre_filter

        st.query_params.update(payload)
        st.query_params.pop("id", None)
        st.rerun()
    render_footer()
    st.stop()

if view == "home":
    render_home()
elif view == "search":
    render_search()
elif view == "series":
    render_series()
elif view == "watchlist":
    render_watchlist()
elif view == "evaluation":
    render_evaluation()
else:
    render_home()

render_footer()
st.stop()

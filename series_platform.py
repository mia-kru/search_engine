import urllib.parse as up
import textwrap
import html as pyhtml
from typing import Any

import streamlit as st
from tantivy import Query, Index, SchemaBuilder, Occur, Facet

# --- Config ---
SITE_NAME = "TV.Base"
TMDB_PATH_SMALL = "https://image.tmdb.org/t/p/w200"
INDEX_PATH = "serien_300"  # später: seriens_full o.ä.

RESULTS_PER_PAGE = 24
MAX_FETCH = 10000  # Tantivy Top-K (für 7k docs ok)

st.set_page_config(page_title=SITE_NAME, layout="wide")

# --- Schema (muss zum Index passen) ---
schema_builder = SchemaBuilder()
schema_builder.add_text_field("title", stored=True, tokenizer_name="en_stem")
schema_builder.add_text_field("description", stored=True, tokenizer_name="en_stem")
schema_builder.add_text_field("tmdb_overview", stored=True, tokenizer_name="en_stem")
schema_builder.add_text_field("tmdb_poster_path", stored=True)
schema_builder.add_text_field("trailer", stored=True)
schema_builder.add_text_field("genres", stored=True)
schema_builder.add_facet_field("facet_genres")
schema_builder.add_integer_field("id", stored=True, indexed=True)
schema_builder.add_float_field("tmdb_vote_average", stored=True, fast=True)
schema = schema_builder.build()

index = Index(schema, path=str(INDEX_PATH))

# --- CSS ---
with open("styles.html", "r", encoding="utf-8") as f:
    css = f.read()
st.markdown(css, unsafe_allow_html=True)

# --- Query Params ---
def get_qp() -> dict[str, Any]:
    return getattr(st, "query_params", {})

qp = get_qp()
view = qp.get("view", "home")
q = qp.get("q", "")
genre = qp.get("genre", "")
selected_id = qp.get("id", "")
page = int(qp.get("p", "1") or "1")

decoded_q = up.unquote(q) if q else ""
decoded_genre = up.unquote(genre) if genre else ""

# --- Helpers ---
@st.cache_data(show_spinner=False)
def load_all_docs(limit: int = MAX_FETCH):
    index.reload()
    s = index.searcher()
    q_all = index.parse_query("*", ["title"])
    hits = s.search(q_all, limit=limit).hits
    docs = [s.doc(addr) for _, addr in hits]
    return docs

@st.cache_data(show_spinner=False)
def get_all_genres():
    docs = load_all_docs()
    gset = set()
    for d in docs:
        for g in (d.get("genres") or []):
            if g and str(g).strip():
                gset.add(str(g).strip())
    return sorted(gset)

def build_header_html(genres_list: list[str]):
    # Options für Select
    opts = ['<option value="">Alle Genres</option>']
    for g in genres_list:
        sel = ' selected' if g == decoded_genre else ''
        opts.append(f'<option value="{pyhtml.escape(g)}"{sel}>{pyhtml.escape(g)}</option>')
    options_html = "\n".join(opts)

    return textwrap.dedent(f"""
    <div class="topbar">
      <div class="top-left">
        <a class="brand" href="/?view=home">{SITE_NAME}</a>

        <form class="searchbar" action="/" method="get">
          <input type="hidden" name="view" value="search">
          <input type="search" name="q" value="{pyhtml.escape(decoded_q)}" placeholder="Suchen…">
          <select name="genre">{options_html}</select>
          <button type="submit">Suchen</button>
        </form>
      </div>

      <div class="top-right">
        <a class="navlink" href="/?view=search">Serien</a>
        <a class="navlink" href="/?view=watchlist">Watchlist</a>
        <a class="navlink" href="/?view=people">Personen</a>
      </div>
    </div>
    """).strip()

def build_search_query(q_text: str, genre_text: str):
    parts = []

    q_text = (q_text or "").strip().lower()
    genre_text = (genre_text or "").strip()

    if q_text:
        # mehrere Terme => MUST
        for term in q_text.split():
            parts.append((Occur.Must, index.parse_query(term, ["title", "tmdb_overview", "description"])))
    else:
        parts.append((Occur.Must, index.parse_query("*", ["title"])))

    if genre_text:
        # Facet-Filter (muss beim Indexieren so gesetzt sein: "/GenreName")
        parts.append((Occur.Must, Query.term_query(schema, "facet_genres", Facet.from_string(f"/{genre_text}"))))

    if len(parts) == 1:
        return parts[0][1]
    return Query.boolean_query(parts)

def get_hits(q_text: str, genre_text: str, limit: int = MAX_FETCH):
    index.reload()
    s = index.searcher()
    query = build_search_query(q_text, genre_text)
    return s, s.search(query, limit=limit).hits

def poster_url(doc):
    p = (doc.get("tmdb_poster_path") or [])
    return (TMDB_PATH_SMALL + p[0]) if p else ""

def doc_title(doc):
    t = (doc.get("title") or [""])
    return t[0]

def doc_rating(doc):
    r = (doc.get("tmdb_vote_average") or [])
    try:
        return float(r[0]) if r else None
    except Exception:
        return None

# --- Header ---
genres_list = get_all_genres()
st.markdown(build_header_html(genres_list), unsafe_allow_html=True)

# --- ROUTES ---
# Detail Page
if view == "detail" and selected_id:
    index.reload()
    s = index.searcher()
    q_id = Query.term_query(schema, "id", int(selected_id))
    hits = s.search(q_id, limit=1).hits

    if not hits:
        st.warning("Serie nicht gefunden.")
    else:
        _, addr = hits[0]
        d = s.doc(addr)

        title = doc_title(d)
        overview_src = d.get("tmdb_overview") or d.get("description") or [""]
        overview = overview_src[0]

        st.subheader(title)

        # Genres
        gs = d.get("genres") or []
        if gs:
            chips = " ".join([f'<span class="chip">{pyhtml.escape(g)}</span>' for g in gs])
            st.markdown(f"<div class='chips'>{chips}</div>", unsafe_allow_html=True)

        # Trailer
        tr = d.get("trailer") or []
        if tr and tr[0]:
            st.video(f"https://www.youtube.com/watch?v={tr[0]}")

        st.write(overview)

    st.markdown(f"""<div class="site-footer"><a href="/?view=home">{SITE_NAME}</a></div>""",
                unsafe_allow_html=True)
    st.stop()

# Watchlist / People placeholder
if view == "watchlist":
    st.subheader("Watchlist")
    st.info("Platzhalter – hier kommt später eure Watchlist-Logik rein.")
    st.markdown(f"""<div class="site-footer"><a href="/?view=home">{SITE_NAME}</a></div>""",
                unsafe_allow_html=True)
    st.stop()

if view == "people":
    st.subheader("Personen")
    st.info("Platzhalter – Personensuche/Seite kommt später.")
    st.markdown(f"""<div class="site-footer"><a href="/?view=home">{SITE_NAME}</a></div>""",
                unsafe_allow_html=True)
    st.stop()

# Home Page
if view == "home":
    docs = load_all_docs()

    # Top 5 nach Bewertung
    rated = []
    for d in docs:
        r = doc_rating(d)
        if r is not None:
            rated.append((r, d))
    rated.sort(key=lambda x: x[0], reverse=True)
    top5 = [d for _, d in rated[:5]] if rated else docs[:5]

    # Hero Background (bis zu 12 Poster)
    bg_imgs = []
    for d in top5[:3] + docs[:12]:
        u = poster_url(d)
        if u:
            bg_imgs.append(u)
        if len(bg_imgs) >= 12:
            break

    imgs_html = "\n".join([f'<img src="{u}" loading="lazy" alt="poster">' for u in bg_imgs]) or ""
    hero_html = textwrap.dedent(f"""
    <div class="hero">
      <div class="hero-bg">{imgs_html}</div>
      <div class="hero-overlay"></div>
      <div class="hero-content">
        <div>
          <h1>{SITE_NAME} – Dein Archiv rund um Bewegtbilder</h1>
          <p>Finde Serien, filtere nach Genre und speichere Favoriten in deiner Watchlist.</p>
        </div>
      </div>
    </div>
    """).strip()
    st.markdown(hero_html, unsafe_allow_html=True)

    # Row 1: Top-Serien
    st.markdown("<div class='section'><h2>Top-Serien</h2></div>", unsafe_allow_html=True)
    cards = ["<div class='row'>"]
    for d in top5:
        pid = (d.get("id") or [""])[0]
        t = doc_title(d)
        u = poster_url(d)
        r = doc_rating(d)
        href = f"/?view=detail&id={pid}"
        img = f'<img src="{u}" loading="lazy" alt="poster">' if u else "<div></div>"
        rating_html = f"<span class='star'>★</span> {r:.1f}" if r is not None else ""
        cards.append(f"""
          <a class="poster-card" href="{href}" target="_self">
            {img}
            <div class="poster-meta">
              <div class="poster-title">{pyhtml.escape(t)}</div>
              <div class="poster-sub">{rating_html}</div>
            </div>
          </a>
        """)
    cards.append("</div>")
    st.markdown("".join(cards), unsafe_allow_html=True)

    # Row 2: Genres
    st.markdown("<div class='section'><h2>Genres</h2></div>", unsafe_allow_html=True)
    chips = ["<div class='chips'>"]
    for g in genres_list:
        href = f"/?view=search&genre={up.quote(g)}"
        chips.append(f'<a class="chip" href="{href}" target="_self">{pyhtml.escape(g)}</a>')
    chips.append("</div>")
    st.markdown("".join(chips), unsafe_allow_html=True)

    st.markdown(f"""<div class="site-footer"><a href="/?view=home">{SITE_NAME}</a></div>""",
                unsafe_allow_html=True)
    st.stop()

# Search Results Page (view=search)
# -> zeigt Grid anhand q + genre
s, hits = get_hits(decoded_q, decoded_genre, limit=MAX_FETCH)

if not hits:
    st.warning("Keine Ergebnisse gefunden.")
else:
    st.subheader("Ergebnisse")

    total = len(hits)
    total_pages = max(1, (total + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * RESULTS_PER_PAGE
    end = start + RESULTS_PER_PAGE

    # Pagination links
    prev_p = page - 1
    next_p = page + 1
    nav = []
    if page > 1:
        nav.append(f'<a class="chip" href="/?view=search&q={up.quote(decoded_q)}&genre={up.quote(decoded_genre)}&p={prev_p}" target="_self">← Prev</a>')
    nav.append(f'<span class="chip">Seite {page}/{total_pages}</span>')
    if page < total_pages:
        nav.append(f'<a class="chip" href="/?view=search&q={up.quote(decoded_q)}&genre={up.quote(decoded_genre)}&p={next_p}" target="_self">Next →</a>')
    st.markdown(f"<div class='chips'>{''.join(nav)}</div>", unsafe_allow_html=True)

    # Grid
    cards_html = ['<div class="grid">']
    for _, addr in hits[start:end]:
        d = s.doc(addr)
        pid = (d.get("id") or [""])[0]
        t = doc_title(d)
        u = poster_url(d)
        href = f"/?view=detail&id={pid}"
        img_tag = f'<img src="{u}" loading="lazy" alt="poster">' if u else ""
        cards_html.append(f"""<a class="card" href="{href}" target="_self">{img_tag}<div class="t">{pyhtml.escape(t)}</div></a>""")
    cards_html.append("</div>")
    st.markdown("".join(cards_html), unsafe_allow_html=True)

st.markdown(f"""<div class="site-footer"><a href="/?view=home">{SITE_NAME}</a></div>""",
            unsafe_allow_html=True)
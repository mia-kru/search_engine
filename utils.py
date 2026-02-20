# Code ist in Anlehnung an: https://gist.github.com/treuille/2ce0acb6697f205e44e3e0f576e810b7 geschrieben
import streamlit as st
import urllib.parse as up
from typing import Any


def get_qp() -> dict[str, Any]:
    """
    Streamlit-kompatibel: neue API (st.query_params) oder alte (experimental_*).
    Gibt immer ein dict zurück.
    """
    if hasattr(st, "query_params"):
        # st.query_params ist dict-ähnlich
        return dict(st.query_params)
    return st.experimental_get_query_params()


def qp_get(params: dict[str, Any], key: str, default: str = "") -> str:
    """Holt Param als string; Streamlit liefert teils list[str]."""
    val = params.get(key, default)
    if isinstance(val, list):
        return str(val[0]) if val else default
    return str(val)


def qp_get_decoded(params: dict[str, Any], key: str, default: str = "") -> str:
    """Wie qp_get, aber URL-decoded (macht aus %20 wieder Leerzeichen)."""
    return up.unquote_plus(qp_get(params, key, default))


def qp_set(**kwargs: str) -> None:
    """
    Setzt Query-Params kompatibel (neu/alt). Übergib nur strings.
    """
    if hasattr(st, "query_params"):
        st.query_params.update(kwargs)
    else:
        st.experimental_set_query_params(**kwargs)


def display_random_items(items: list[str], cards_per_page=3):
    n_pages = (len(items) - 1) // cards_per_page + 1
    if "page" not in st.session_state:
        st.session_state.page = 0
    page = st.session_state.page
    start = page * cards_per_page
    end = start + cards_per_page
    # Cards für die aktuelle Seite
    selected_cards = items[start:end]
    display_cards = ['<div class="random-grid">']

    for item in selected_cards:
        display_cards.append(item)
    display_cards.append("</div>")
    st.markdown("".join(display_cards), unsafe_allow_html=True)
    col_prev, col_free, col_next = st.columns([1, 16, 1])

    with col_prev:
        st.markdown('<div class="paginator-button">', unsafe_allow_html=True)
        if st.button("⟨", key=f"prev", disabled=(page == 0)):
            st.session_state.page = page - 1
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with col_next:
        st.markdown('<div class="paginator-button">', unsafe_allow_html=True)
        if st.button("⟩", key=f"next", disabled=(page == n_pages - 1)):
            st.session_state.page = page + 1
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
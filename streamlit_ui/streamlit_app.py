"""Streamlit Cloud UI for StockRAG.

Deliberately a thin HTTP client: retrieval needs torch + chromadb + two
transformer models, which do not fit Streamlit Cloud's free tier. All the
heavy lifting stays in the FastAPI deploy (HF Spaces); this file only talks
to it over HTTP, so its dependencies are streamlit + requests.

Point it at an API with STOCKRAG_API_URL (env var or .streamlit/secrets.toml).
"""

import os

import requests
import streamlit as st

DEFAULT_API = "http://localhost:8000"
TIMEOUT = 180  # NIM generation over a 6-chunk prompt runs ~3-10s; cold Spaces are slower.


def api_url() -> str:
    # st.secrets raises (not returns empty) when no secrets.toml exists, which
    # is the normal case for local runs.
    try:
        configured = st.secrets.get("STOCKRAG_API_URL", "")
    except Exception:
        configured = ""
    return (configured or os.environ.get("STOCKRAG_API_URL") or DEFAULT_API).rstrip("/")


def pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def money(value: float | None) -> str:
    if value is None:
        return "—"
    for cutoff, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(value) >= cutoff:
            return f"${value / cutoff:.2f}{suffix}"
    return f"${value:,.2f}"


st.set_page_config(page_title="StockRAG", page_icon="📈", layout="wide")
st.title("StockRAG")
st.caption("Factor engine + cited RAG over SEC filings. Numbers come from XBRL, prose answers must cite a filing chunk.")

base = st.sidebar.text_input("API URL", value=api_url())
st.sidebar.caption("FastAPI backend (HF Spaces or local uvicorn).")
provider = st.sidebar.selectbox("Generation model", ["server default", "nvidia", "gemini", "ollama"])
st.sidebar.caption("Retrieval always runs on the API host; only generation switches.")

ask_tab, factors_tab = st.tabs(["Ask", "Factors"])

with ask_tab:
    ticker = st.text_input("Ticker", value="AAPL", max_chars=5, key="ask_ticker").upper()
    question = st.text_area("Question", placeholder="What did the EU decide about Irish state aid?")

    col_ask, col_ingest = st.columns([1, 3])
    if col_ingest.button("Ingest filings first", help="Downloads and indexes this ticker's 10-K (~1 min)"):
        with st.spinner(f"Ingesting {ticker}…"):
            try:
                r = requests.post(f"{base}/ingest/{ticker}", timeout=TIMEOUT)
                r.raise_for_status()
                st.success(r.json())
            except requests.RequestException as exc:
                st.error(f"Ingest failed: {exc}")

    if col_ask.button("Ask", type="primary", disabled=not (ticker and question.strip())):
        payload = {"question": question, "ticker": ticker}
        if provider != "server default":
            payload["llm"] = provider
        with st.spinner("Retrieving and generating…"):
            try:
                r = requests.post(f"{base}/ask", json=payload, timeout=TIMEOUT)
                r.raise_for_status()
                data = r.json()
            except requests.RequestException as exc:
                st.error(f"Ask failed: {exc}")
            else:
                st.markdown(data["answer"])
                st.caption(f"prompt {data.get('prompt_version', '?')}")
                st.subheader("Sources")
                for s in data["sources"]:
                    st.markdown(f"`[{s['index']}]` **{s['form']}** {s['section']} — filed {s['filing_date']}")

with factors_tab:
    fticker = st.text_input("Ticker", value="AAPL", max_chars=5, key="factors_ticker").upper()
    if st.button("Get factors", type="primary", disabled=not fticker):
        with st.spinner(f"Pulling XBRL for {fticker}…"):
            try:
                r = requests.get(f"{base}/factors/{fticker}", timeout=TIMEOUT)
                r.raise_for_status()
                d = r.json()
            except requests.RequestException as exc:
                st.error(f"Factors failed: {exc}")
            else:
                a, b, c, e = st.columns(4)
                a.metric("Piotroski F-Score", f"{d['piotroski_score'] or '—'}/9")
                b.metric("ROE", pct(d["roe"]))
                c.metric("Net margin", pct(d["net_margin"]))
                e.metric("Revenue", money(d["revenue"]))

                st.subheader("F-Score signals")
                for key, passed in d["piotroski_signals"].items():
                    st.write(("✅ " if passed else "❌ ") + key.replace("_", " "))

                st.subheader("All metrics")
                st.json(d)

import json

import typer

app = typer.Typer(help="StockRAG: Factor Engine + Ask-My-Docs RAG CLI")


@app.command()
def health() -> None:
    """Sanity check that the CLI is wired up."""
    typer.echo("ok")


@app.command()
def factors(ticker: str) -> None:
    """Print the quantitative factor report for a ticker as JSON."""
    from stockrag.factor_engine.report import build_factor_report

    report = build_factor_report(ticker)
    typer.echo(json.dumps(report.model_dump(), indent=2))


@app.command()
def ingest(ticker: str, forms: str = "10-K", years: int = 2) -> None:
    """Download and index a ticker's SEC filings into the vector store."""
    from stockrag.ingestion.pipeline import ingest_ticker as _ingest_ticker

    form_tuple = tuple(f.strip() for f in forms.split(","))
    result = _ingest_ticker(ticker, forms=form_tuple, years=years)
    typer.echo(json.dumps(result.__dict__, indent=2))


@app.command()
def ask(question: str, ticker: str, llm: str = typer.Option(None, help="LLM provider: ollama (default) or gemini")) -> None:
    """Ask a question about a ticker's ingested filings."""
    from stockrag.rag.answer import ask as _ask

    result = _ask(question, ticker, llm_provider=llm)
    typer.echo(result.answer)
    typer.echo("")
    typer.echo("Sources:")
    for s in result.sources:
        typer.echo(f"  [{s.index}] {s.form} filed {s.filing_date} - {s.section} ({s.accession})")


@app.command(name="ingest-file")
def ingest_file(
    path: str,
    ticker: str,
    form: str = "10-K",
    filing_date: str = "",
    accession: str = "local",
) -> None:
    """Ingest a local filing HTML file (no EDGAR network access; CI-safe)."""
    from pathlib import Path

    from stockrag.ingestion.pipeline import ingest_html

    html = Path(path).read_text(encoding="utf-8", errors="ignore")
    result = ingest_html(html, ticker, form=form, filing_date=filing_date, accession=accession)
    typer.echo(json.dumps(result.__dict__, indent=2))


@app.command()
def stats() -> None:
    """SRE metrics over recorded requests: P50/P95 latency, citation coverage, cost."""
    from stockrag.rag.metrics import summarize

    typer.echo(json.dumps(summarize(), indent=2))


@app.command()
def retrieve(question: str, ticker: str, k: int = 6) -> None:
    """Debug: show what hybrid+rerank vs pure vector retrieval return."""
    from stockrag.rag.answer import get_retriever, get_vector_only_retriever

    def show(label: str, docs: list) -> None:
        typer.echo(f"--- {label} ---")
        for i, doc in enumerate(docs, start=1):
            meta = doc.metadata
            snippet = " ".join(doc.page_content.split())[:120]
            typer.echo(f"[{i}] {meta.get('section')} ({meta.get('form')} {meta.get('filing_date')}): {snippet}")
        typer.echo("")

    show("hybrid + rerank", get_retriever(ticker, k=k).invoke(question))
    show("vector only", get_vector_only_retriever(ticker, k=k).invoke(question))


if __name__ == "__main__":
    app()

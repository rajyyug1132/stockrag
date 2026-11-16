"""Run supabase/migrations against a throwaway local Postgres + pgvector and
exercise hybrid_search. Skipped unless pgserver is installed:

    uv run --with pgserver pytest tests/test_migrations_pg.py

The preamble stands in for what Supabase provides: the anon/authenticated/
service_role roles, an `extensions` schema, and default grants on public.
"""

import subprocess

import pytest

from stockrag.config import PROJECT_ROOT, settings

pgserver = pytest.importorskip("pgserver")
from pgserver.postgres_server import POSTGRES_BIN_PATH  # noqa: E402

D = settings.nvidia_embed_dim

PREAMBLE = """
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
create schema extensions;
grant usage on schema public, extensions to anon, authenticated, service_role;
alter default privileges in schema public grant all on tables to anon, authenticated, service_role;
alter default privileges in schema public grant all on functions to anon, authenticated, service_role;
"""

# One-hot-ish test vectors: onehot(k) is closest to itself.
HELPERS = f"""
create function onehot(k int) returns extensions.vector language sql immutable as $$
  select (array_agg(case when i = k then 1.0 else 0.01 end order by i))::real[]::extensions.vector({D})
  from generate_series(1, {D}) i
$$;
"""

# Section "Risk" holds chunk_index 0-4, "MD&A" 5-6; ticker OTHER must never leak.
DATA = """
insert into public.chunks (id, ticker, form, filing_date, accession, section, chunk_index,
                           char_start, char_end, content, embedding) values
 ('A:0','AAPL','10-K','2025-10-31','A','Risk',0,   0, 100,'Competition in smartphones is intense', onehot(1)),
 ('A:1','AAPL','10-K','2025-10-31','A','Risk',1,  80, 180,'Foreign exchange rates affect margins', onehot(2)),
 ('A:2','AAPL','10-K','2025-10-31','A','Risk',2, 160, 260,'Supply chain disruptions could hurt production', onehot(3)),
 ('A:3','AAPL','10-K','2025-10-31','A','Risk',3, 240, 340,'Legal proceedings and regulatory investigations', onehot(4)),
 ('A:4','AAPL','10-K','2025-10-31','A','Risk',4, 320, 420,'Cybersecurity incidents may expose data', onehot(5)),
 ('A:5','AAPL','10-K','2025-10-31','A','MD&A',5,   0, 100,'Revenue grew on services', onehot(6)),
 ('A:6','AAPL','10-K','2025-10-31','A','MD&A',6,  80, 180,'Gross margin expanded', onehot(7)),
 ('B:0','AAPL','10-Q','2026-01-30','B','Risk',0,   0, 100,'Supply constraints eased', onehot(8)),
 ('X:0','OTHER','10-K','2025-01-01','X','Risk',0,  0, 100,'Supply chain supply chain supply chain', onehot(3));
"""


def _psql(srv, sql: str, role: str | None = None) -> subprocess.CompletedProcess:
    if role:
        sql = f"set role {role};\n{sql}"
    return subprocess.run(
        [str(POSTGRES_BIN_PATH / "psql"), "-X", "-q", "-At", "-v", "ON_ERROR_STOP=1", srv.get_uri()],
        input=sql, capture_output=True, text=True,
    )


def _ok(srv, sql: str, role: str | None = None) -> list[str]:
    res = _psql(srv, sql, role)
    assert res.returncode == 0, res.stderr
    return [line for line in res.stdout.splitlines() if line]


@pytest.fixture(scope="module")
def srv(tmp_path_factory):
    server = pgserver.get_server(tmp_path_factory.mktemp("pg"), cleanup_mode="delete")
    _ok(server, PREAMBLE)
    for path in sorted((PROJECT_ROOT / "supabase" / "migrations").glob("*.sql")):
        _ok(server, path.read_text(encoding="utf-8"))
    _ok(server, HELPERS + DATA)
    yield server
    server.cleanup()


def _search(srv, q: str, emb_k: int, n: int = 30, win: int = 1, cols: str = "id") -> list[str]:
    return _ok(
        srv,
        f"select {cols} from public.hybrid_search($q${q}$q$, onehot({emb_k}), 'AAPL', {n}, {win});",
        role="service_role",
    )


def test_question_terms_are_ored_and_stemmed(srv):
    # Query vector points at A:0; with n=2 the vector leg alone returns A:0
    # and A:1 (equal distances, id tie-break). A:2 can only come from the
    # text leg, via "supplies" -> "suppli"; "banana" matches nothing, so an
    # AND-ed query would return no text hits at all.
    assert _search(srv, "What about supplies or banana?", emb_k=1, n=2) == ["A:0", "A:2"]


def test_hit_in_both_legs_outranks_single_leg_hits(srv):
    # Vector ranks: A:0, A:1, A:2, A:3. Text ranks: A:2, B:0. RRF lifts A:2
    # (3rd by vector alone) to the top with 1/63 + 1/61.
    rows = _search(srv, "supplies banana", emb_k=1, n=4, cols="id, round(score::numeric, 10)")
    assert rows[0] == f"A:2|{round(1 / 63 + 1 / 61, 10)}"
    assert [r.split("|")[0] for r in rows[1:]] == ["A:0", "A:1", "B:0"]


def test_ticker_filter(srv):
    assert not any(i.startswith("X:") for i in _search(srv, "supply chain", emb_k=3))


def test_n_limits_results(srv):
    assert len(_search(srv, "supply", emb_k=1, n=3)) == 3


def test_stopword_only_question_falls_back_to_vector_leg(srv):
    ids = _search(srv, "the of and", emb_k=5)
    assert ids[0] == "A:4" and len(ids) == 8


def test_neighbours_stay_in_section_and_are_ordered(srv):
    rows = _search(
        srv, "cybersecurity", emb_k=5, cols="id, (select string_agg((e->>'char_start'), ',') "
        "from jsonb_array_elements(neighbours) e)",
    )
    got = dict(r.split("|") for r in rows)
    assert got["A:4"] == "240,320"          # idx 3,4; idx 5 is another section
    assert got["A:2"] == "80,160,240"       # idx 1,2,3
    assert got["A:5"] == "0,80"             # first in its section
    wide = dict(r.split("|") for r in _search(
        srv, "supply", emb_k=3, win=0,
        cols="id, jsonb_array_length(neighbours)",
    ))
    assert set(wide.values()) == {"1"}


def test_neighbour_payload_shape(srv):
    rows = _search(srv, "supply", emb_k=3, n=1, cols="neighbours->1->>'content', score > 0")
    assert rows == ["Supply chain disruptions could hurt production|t"]


def test_ticker_accessions(srv):
    assert _ok(srv, "select public.ticker_accessions('AAPL');", role="service_role") == ["A", "B"]


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_public_roles_are_locked_out(srv, role):
    for sql in (
        "select count(*) from public.chunks;",
        "insert into public.request_metrics (record) values ('{}');",
        "select * from public.thesis_cache;",
        "select public.ticker_accessions('AAPL');",
        "select id from public.hybrid_search('x', onehot(1), 'AAPL');",
    ):
        res = _psql(srv, sql, role=role)
        assert res.returncode != 0 and "permission denied" in res.stderr, (role, sql, res.stdout)


def test_rls_without_policies_hides_rows_even_with_a_grant(srv):
    # Privileges alone are tested above; this checks the RLS layer itself.
    _ok(srv, "grant select on public.chunks to anon;")
    try:
        assert _ok(srv, "select count(*) from public.chunks;", role="anon") == ["0"]
    finally:
        _ok(srv, "revoke select on public.chunks from anon;")


def test_service_role_reads_and_writes_state_tables(srv):
    _ok(srv, """
        insert into public.request_metrics (record) values ('{"ticker": "AAPL"}');
        insert into public.thesis_cache (ticker, fingerprint, payload) values ('AAPL', 'f1', '{}')
          on conflict (ticker) do update set fingerprint = excluded.fingerprint;
    """, role="service_role")
    got = _ok(srv, """
        select record->>'ticker' from public.request_metrics;
        select fingerprint from public.thesis_cache where ticker = 'AAPL';
    """, role="service_role")
    assert got == ["AAPL", "f1"]

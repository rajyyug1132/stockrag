"""Static checks on supabase/migrations (CI, no database). The migrations are
executed for real by tests/test_migrations_pg.py when pgserver is installed."""

import re
from pathlib import Path

from stockrag.config import PROJECT_ROOT, settings

MIGRATIONS = PROJECT_ROOT / "supabase" / "migrations"
NAME_RE = re.compile(r"^\d{14}_[a-z0-9_]+\.sql$")


def _files() -> list[Path]:
    return sorted(MIGRATIONS.glob("*.sql"))


def _sql() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in _files())


def test_migrations_are_timestamped_and_unique():
    names = [p.name for p in _files()]
    assert names, "no migrations found"
    assert all(NAME_RE.match(n) for n in names), names
    stamps = [n[:14] for n in names]
    assert len(set(stamps)) == len(stamps)


def test_dollar_quotes_balance():
    for p in _files():
        assert p.read_text(encoding="utf-8").count("$$") % 2 == 0, p.name


def test_vector_dim_matches_config():
    dims = {int(d) for d in re.findall(r"vector\((\d+)\)", _sql())}
    assert dims == {settings.nvidia_embed_dim}


def test_tables_are_service_role_only():
    sql = _sql()
    tables = re.findall(r"create table public\.(\w+)", sql)
    assert set(tables) == {"chunks", "request_metrics", "thesis_cache"}
    for t in tables:
        assert f"alter table public.{t} enable row level security" in sql, t
    assert "create policy" not in sql.lower()


def test_functions_are_not_executable_by_public_roles():
    sql = _sql()
    funcs = re.findall(r"create or replace function public\.(\w+)\(", sql)
    assert set(funcs) == {"hybrid_search", "ticker_accessions"}
    for f in funcs:
        assert re.search(rf"revoke execute on function public\.{f}\(.*?\)\s+from public, anon, authenticated", sql, re.S), f
        assert re.search(rf"create or replace function public\.{f}\(.*?set search_path = ''", sql, re.S), f

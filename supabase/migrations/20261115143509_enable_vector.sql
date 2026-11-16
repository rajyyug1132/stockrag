-- pgvector in the `extensions` schema (Supabase convention; keeps it out of
-- public). Everything else references it as extensions.vector.
create extension if not exists vector with schema extensions;

-- Migrations: 003 Create Shared Embedding Cache Table
-- Formulates a shared vector storage table utilizing dynamic float8[] arrays for Matryoshka dimensions.

CREATE TABLE IF NOT EXISTS public.embedding_cache (
    text_hash TEXT PRIMARY KEY,
    text_content TEXT,
    dimensions INTEGER NOT NULL,
    task_type TEXT NOT NULL,
    vector float8[] NOT NULL, -- Flexible double precision array to support dynamic MRL (256d, 768d, 3072d)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable Row Level Security (RLS) for enterprise-grade security
ALTER TABLE public.embedding_cache ENABLE ROW LEVEL SECURITY;

-- Allow anonymous or authenticated read/write access (since it serves as a shared cache layer for API nodes)
CREATE POLICY "Allow read access to all" ON public.embedding_cache 
    FOR SELECT TO anon, authenticated USING (true);

CREATE POLICY "Allow insert/update access to all" ON public.embedding_cache 
    FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);

-- Index for rapid dimension-based vector retrieval
CREATE INDEX IF NOT EXISTS idx_cache_hash_dims ON public.embedding_cache (text_hash, dimensions);

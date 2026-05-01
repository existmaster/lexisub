CREATE TABLE IF NOT EXISTS terms (
  id INTEGER PRIMARY KEY,
  source_lang TEXT NOT NULL,
  source_term TEXT NOT NULL,
  ko_term TEXT NOT NULL,
  category TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  notes TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(source_lang, source_term, ko_term)
);
CREATE INDEX IF NOT EXISTS idx_terms_status ON terms(status);
CREATE INDEX IF NOT EXISTS idx_terms_lang ON terms(source_lang);

CREATE TABLE IF NOT EXISTS pdfs (
  id INTEGER PRIMARY KEY,
  path TEXT NOT NULL UNIQUE,
  title TEXT,
  language TEXT,
  page_count INTEGER,
  added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  extracted_at TIMESTAMP,
  extraction_status TEXT NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS term_sources (
  term_id INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
  pdf_id INTEGER NOT NULL REFERENCES pdfs(id) ON DELETE CASCADE,
  page_no INTEGER,
  context TEXT,
  PRIMARY KEY (term_id, pdf_id, page_no)
);

CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY,
  video_path TEXT NOT NULL,
  source_lang TEXT,
  duration_seconds INTEGER,
  status TEXT NOT NULL,
  error_message TEXT,
  output_srt TEXT,
  output_mkv TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);

-- v0.3+: knowledge-base infrastructure for future RAG. Embedding columns
-- stay NULL until v0.4 wires up sentence-transformers / mlx-embeddings.

CREATE TABLE IF NOT EXISTS pdf_chunks (
  id INTEGER PRIMARY KEY,
  pdf_id INTEGER NOT NULL REFERENCES pdfs(id) ON DELETE CASCADE,
  page_no INTEGER,
  chunk_index INTEGER NOT NULL,
  text TEXT NOT NULL,
  char_count INTEGER,
  embedding BLOB,
  embed_model TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(pdf_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_chunks_pdf ON pdf_chunks(pdf_id);

CREATE TABLE IF NOT EXISTS translation_pairs (
  id INTEGER PRIMARY KEY,
  pdf_id INTEGER REFERENCES pdfs(id) ON DELETE CASCADE,
  page_no INTEGER,
  source_lang TEXT NOT NULL,
  source_text TEXT NOT NULL,
  ko_text TEXT NOT NULL,
  embedding BLOB,
  embed_model TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(pdf_id, source_text, ko_text)
);
CREATE INDEX IF NOT EXISTS idx_pairs_pdf ON translation_pairs(pdf_id);

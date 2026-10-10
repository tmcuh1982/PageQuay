ALTER TABLE search_cursors ADD COLUMN region TEXT;
ALTER TABLE search_cursors ADD COLUMN time_range TEXT NOT NULL DEFAULT 'any';

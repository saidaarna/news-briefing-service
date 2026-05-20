CREATE TABLE IF NOT EXISTS users (
    username VARCHAR(100) PRIMARY KEY,
    preferred_topics JSONB NOT NULL DEFAULT '[]',
    excluded_sources JSONB NOT NULL DEFAULT '[]'
);

INSERT INTO users (username, preferred_topics, excluded_sources)
VALUES ('khagani', '["AI", "Tech"]', '["FakeNews.com"]')
ON CONFLICT (username) DO NOTHING;
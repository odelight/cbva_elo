-- CBVA ELO Database Schema
-- PostgreSQL schema for storing tournament data and ELO ratings

-- Players (extracted from CBVA player URLs)
CREATE TABLE players (
    id SERIAL PRIMARY KEY,
    cbva_id VARCHAR(50) UNIQUE NOT NULL,  -- e.g., "mjlabreche"
    current_elo DECIMAL(7,2) DEFAULT 1500.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tournaments
CREATE TABLE tournaments (
    id SERIAL PRIMARY KEY,
    cbva_id VARCHAR(50) UNIQUE NOT NULL,  -- e.g., "19Xt68go"
    url VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    tournament_date DATE,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Teams (a pair of players in a tournament)
CREATE TABLE teams (
    id SERIAL PRIMARY KEY,
    cbva_id VARCHAR(50) NOT NULL,  -- e.g., "gs0cxnVR"
    tournament_id INTEGER REFERENCES tournaments(id) ON DELETE CASCADE,
    player1_id INTEGER REFERENCES players(id),
    player2_id INTEGER REFERENCES players(id),
    UNIQUE(cbva_id, tournament_id)
);

-- Matches (a game between two teams)
CREATE TABLE matches (
    id SERIAL PRIMARY KEY,
    tournament_id INTEGER REFERENCES tournaments(id) ON DELETE CASCADE,
    team1_id INTEGER REFERENCES teams(id) ON DELETE CASCADE,
    team2_id INTEGER REFERENCES teams(id) ON DELETE CASCADE,
    winner_team_id INTEGER REFERENCES teams(id),
    match_type VARCHAR(20),  -- 'pool_play' or 'playoff'
    match_name VARCHAR(50),  -- e.g., 'Pool A Match 1', 'Playoff Match 3'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team1_id, team2_id, tournament_id)
);

-- Sets (individual sets within a match)
CREATE TABLE sets (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id) ON DELETE CASCADE,
    set_number INTEGER NOT NULL,
    team1_score INTEGER NOT NULL,
    team2_score INTEGER NOT NULL,
    UNIQUE(match_id, set_number)
);

-- ELO history (track rating changes over time)
CREATE TABLE elo_history (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id) ON DELETE CASCADE,
    elo_before DECIMAL(7,2) NOT NULL,
    elo_after DECIMAL(7,2) NOT NULL,
    set_id INTEGER REFERENCES sets(id) ON DELETE CASCADE,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX idx_players_cbva_id ON players(cbva_id);
CREATE INDEX idx_players_elo ON players(current_elo DESC);
CREATE INDEX idx_teams_tournament ON teams(tournament_id);
CREATE INDEX idx_teams_player1 ON teams(player1_id);
CREATE INDEX idx_teams_player2 ON teams(player2_id);
CREATE INDEX idx_matches_tournament ON matches(tournament_id);
CREATE INDEX idx_sets_match ON sets(match_id);
CREATE INDEX idx_elo_history_player ON elo_history(player_id);
CREATE INDEX idx_elo_history_recorded ON elo_history(recorded_at);

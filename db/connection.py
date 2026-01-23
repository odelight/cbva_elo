"""
Database connection utilities for CBVA ELO system.

Provides connection management and helper functions for inserting/updating
tournament data in the PostgreSQL database.
"""

import psycopg2
from .config import get_connection_params


def get_connection():
    """
    Get a database connection using configured parameters.

    Returns a psycopg2 connection object.
    """
    return psycopg2.connect(**get_connection_params())


def get_or_create_player(conn, cbva_id):
    """
    Get player ID by cbva_id, creating the player if not exists.

    Args:
        conn: Database connection
        cbva_id: CBVA player identifier (e.g., "mjlabreche")

    Returns:
        Integer player ID from database
    """
    with conn.cursor() as cur:
        # Try to insert, on conflict return existing
        cur.execute("""
            INSERT INTO players (cbva_id)
            VALUES (%s)
            ON CONFLICT (cbva_id) DO UPDATE SET cbva_id = EXCLUDED.cbva_id
            RETURNING id
        """, (cbva_id,))
        result = cur.fetchone()
        return result[0]


def get_or_create_tournament(conn, cbva_id, url, name=None, tournament_date=None):
    """
    Get tournament ID by cbva_id, creating the tournament if not exists.

    Args:
        conn: Database connection
        cbva_id: CBVA tournament identifier (e.g., "19Xt68go")
        url: Full tournament URL
        name: Optional tournament name
        tournament_date: Optional date of the tournament

    Returns:
        Integer tournament ID from database
    """
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO tournaments (cbva_id, url, name, tournament_date)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (cbva_id) DO UPDATE SET
                tournament_date = COALESCE(EXCLUDED.tournament_date, tournaments.tournament_date)
            RETURNING id
        """, (cbva_id, url, name, tournament_date))
        result = cur.fetchone()
        return result[0]


def get_or_create_team(conn, cbva_id, tournament_id, player1_id, player2_id):
    """
    Get team ID, creating the team if not exists.

    Args:
        conn: Database connection
        cbva_id: CBVA team identifier (e.g., "gs0cxnVR")
        tournament_id: Database ID of the tournament
        player1_id: Database ID of first player
        player2_id: Database ID of second player

    Returns:
        Integer team ID from database
    """
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO teams (cbva_id, tournament_id, player1_id, player2_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (cbva_id, tournament_id) DO UPDATE SET cbva_id = EXCLUDED.cbva_id
            RETURNING id
        """, (cbva_id, tournament_id, player1_id, player2_id))
        result = cur.fetchone()
        return result[0]


def get_team_by_cbva_id(conn, cbva_id, tournament_id):
    """
    Get team by cbva_id and tournament_id.

    Args:
        conn: Database connection
        cbva_id: CBVA team identifier
        tournament_id: Database ID of the tournament

    Returns:
        Tuple of (team_id, player1_id, player2_id) or None if not found
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, player1_id, player2_id FROM teams
            WHERE cbva_id = %s AND tournament_id = %s
        """, (cbva_id, tournament_id))
        return cur.fetchone()


def insert_match(conn, tournament_id, team1_id, team2_id, match_type=None, match_name=None):
    """
    Insert a match between two teams.

    Args:
        conn: Database connection
        tournament_id: Database ID of the tournament
        team1_id: Database ID of first team
        team2_id: Database ID of second team
        match_type: 'pool_play' or 'playoff'
        match_name: e.g., 'Pool A Match 1', 'Playoff Match 3'

    Returns:
        Integer match ID from database, or None if duplicate
    """
    with conn.cursor() as cur:
        # Normalize team order for consistent duplicate detection
        if team1_id > team2_id:
            team1_id, team2_id = team2_id, team1_id

        cur.execute("""
            INSERT INTO matches (tournament_id, team1_id, team2_id, match_type, match_name)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (team1_id, team2_id, tournament_id) DO NOTHING
            RETURNING id
        """, (tournament_id, team1_id, team2_id, match_type, match_name))
        result = cur.fetchone()
        return result[0] if result else None


def get_match_id(conn, tournament_id, team1_id, team2_id):
    """
    Get existing match ID for two teams in a tournament.

    Args:
        conn: Database connection
        tournament_id: Database ID of the tournament
        team1_id: Database ID of first team
        team2_id: Database ID of second team

    Returns:
        Integer match ID or None if not found
    """
    with conn.cursor() as cur:
        # Check both orderings
        cur.execute("""
            SELECT id FROM matches
            WHERE tournament_id = %s
              AND ((team1_id = %s AND team2_id = %s) OR (team1_id = %s AND team2_id = %s))
        """, (tournament_id, team1_id, team2_id, team2_id, team1_id))
        result = cur.fetchone()
        return result[0] if result else None


def insert_set(conn, match_id, set_number, team1_score, team2_score):
    """
    Insert a set result for a match.

    Args:
        conn: Database connection
        match_id: Database ID of the match
        set_number: Set number (1, 2, 3, etc.)
        team1_score: Score of team1 (as stored in matches table)
        team2_score: Score of team2 (as stored in matches table)

    Returns:
        Integer set ID from database, or None if duplicate
    """
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO sets (match_id, set_number, team1_score, team2_score)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (match_id, set_number) DO NOTHING
            RETURNING id
        """, (match_id, set_number, team1_score, team2_score))
        result = cur.fetchone()
        return result[0] if result else None


def insert_elo_history(conn, player_id, elo_before, elo_after, set_id):
    """
    Record an ELO rating change for a player.

    Args:
        conn: Database connection
        player_id: Database ID of the player
        elo_before: ELO rating before the set
        elo_after: ELO rating after the set
        set_id: Database ID of the set that caused the change

    Returns:
        Integer elo_history ID from database
    """
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO elo_history (player_id, elo_before, elo_after, set_id)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (player_id, elo_before, elo_after, set_id))
        result = cur.fetchone()
        return result[0]


def update_player_elo(conn, player_id, new_elo):
    """
    Update a player's current ELO rating.

    Args:
        conn: Database connection
        player_id: Database ID of the player
        new_elo: New ELO rating value
    """
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE players
            SET current_elo = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (new_elo, player_id))


def get_player_elo(conn, player_id):
    """
    Get a player's current ELO rating.

    Args:
        conn: Database connection
        player_id: Database ID of the player

    Returns:
        Current ELO rating as float
    """
    with conn.cursor() as cur:
        cur.execute("SELECT current_elo FROM players WHERE id = %s", (player_id,))
        result = cur.fetchone()
        return float(result[0]) if result else 1500.0


def get_all_sets_for_elo(conn):
    """
    Get all sets with team and player information for ELO calculation.

    Returns sets ordered chronologically:
    1. Tournament date (oldest first)
    2. Match type (pool_play before playoff)
    3. Match number (higher numbers first, e.g. Match 3 before Match 2)
    4. Set number (1, 2, 3...)

    Returns:
        List of dicts with set and player information
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                s.id as set_id,
                s.set_number,
                s.team1_score,
                s.team2_score,
                m.id as match_id,
                m.team1_id,
                m.team2_id,
                t1.player1_id as team1_player1,
                t1.player2_id as team1_player2,
                t2.player1_id as team2_player1,
                t2.player2_id as team2_player2
            FROM sets s
            JOIN matches m ON s.match_id = m.id
            JOIN teams t1 ON m.team1_id = t1.id
            JOIN teams t2 ON m.team2_id = t2.id
            JOIN tournaments tourn ON t1.tournament_id = tourn.id
            ORDER BY
                tourn.tournament_date ASC NULLS LAST,
                CASE m.match_type WHEN 'pool_play' THEN 0 WHEN 'playoff' THEN 1 ELSE 2 END,
                CAST(SUBSTRING(m.match_name FROM '[0-9]+') AS INTEGER) DESC NULLS LAST,
                s.set_number ASC
        """)
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def get_all_player_elos(conn):
    """
    Get current ELO ratings for all players.

    Returns:
        Dict of player_id -> (cbva_id, current_elo)
    """
    with conn.cursor() as cur:
        cur.execute("SELECT id, cbva_id, current_elo FROM players")
        return {row[0]: (row[1], float(row[2])) for row in cur.fetchall()}


def clear_elo_history(conn):
    """
    Delete all ELO history records.

    Used before recalculating ELO ratings from scratch.
    """
    with conn.cursor() as cur:
        cur.execute("DELETE FROM elo_history")


def reset_all_player_elos(conn):
    """
    Reset all players' current ELO ratings to 1500.

    Used before recalculating ELO ratings from scratch.
    """
    with conn.cursor() as cur:
        cur.execute("UPDATE players SET current_elo = 1500.00, updated_at = CURRENT_TIMESTAMP")

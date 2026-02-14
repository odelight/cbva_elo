"""Database configuration and utilities for CBVA ELO system."""

from .config import DATABASE_CONFIG, get_connection_string, get_connection_params
from .connection import (
    get_connection,
    get_or_create_player,
    get_or_create_tournament,
    get_or_create_team,
    get_team_by_cbva_id,
    insert_match,
    get_match_id,
    insert_set,
    insert_elo_history,
    update_player_elo,
    get_player_elo,
    get_all_sets_for_elo,
    get_all_sets_with_month,
    get_all_sets_with_date,
    get_all_sets_with_ratings,
    get_all_player_elos,
    clear_elo_history,
    reset_all_player_elos,
    upsert_rating_dependent_elo,
    clear_rating_dependent_elos,
    get_rating_dependent_elos,
)

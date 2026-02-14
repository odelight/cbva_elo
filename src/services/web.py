"""Flask web service for CBVA ELO system."""

import os
import sys

# Add project root to path for db imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from flask import Flask
from db import get_connection

app = Flask(__name__)


@app.route('/')
def hello():
    return '<h1>CBVA ELO Rankings</h1>'


@app.route('/health')
def health():
    """Health check endpoint for Cloud Run."""
    return 'OK', 200


@app.route('/elo/<cbva_id>')
def elo_history(cbva_id):
    """Display ELO history for a player."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Get player info and current ELO
            cur.execute("""
                SELECT id, current_elo FROM players WHERE cbva_id = %s
            """, (cbva_id,))
            player = cur.fetchone()

            if not player:
                return f'<h1>Player not found: {cbva_id}</h1>', 404

            player_id, current_elo = player

            # Get rating-dependent ELOs
            cur.execute("""
                SELECT opponent_rating, elo, games_played
                FROM rating_dependent_elo
                WHERE player_id = %s
                ORDER BY
                    CASE opponent_rating
                        WHEN 'AAA' THEN 1
                        WHEN 'AA' THEN 2
                        WHEN 'A' THEN 3
                        WHEN 'B' THEN 4
                        WHEN 'Novice' THEN 5
                        WHEN 'Unrated' THEN 6
                    END
            """, (player_id,))
            rating_elos = cur.fetchall()

            # Get ELO history with tournament, partner, and opponent info
            cur.execute("""
                SELECT
                    eh.elo_before,
                    eh.elo_after,
                    eh.recorded_at,
                    t.tournament_date,
                    m.match_type,
                    m.match_name,
                    partner.cbva_id as partner_cbva_id,
                    opp1.cbva_id as opp1_cbva_id,
                    opp2.cbva_id as opp2_cbva_id
                FROM elo_history eh
                JOIN sets s ON eh.set_id = s.id
                JOIN matches m ON s.match_id = m.id
                JOIN teams tm1 ON m.team1_id = tm1.id
                JOIN teams tm2 ON m.team2_id = tm2.id
                JOIN tournaments t ON tm1.tournament_id = t.id
                -- Determine player's team and partner
                JOIN teams my_team ON my_team.id = CASE
                    WHEN tm1.player1_id = %s OR tm1.player2_id = %s THEN m.team1_id
                    ELSE m.team2_id
                END
                JOIN players partner ON partner.id = CASE
                    WHEN my_team.player1_id = %s THEN my_team.player2_id
                    ELSE my_team.player1_id
                END
                -- Determine opponent team based on which team the player is on
                JOIN teams opp_team ON opp_team.id = CASE
                    WHEN tm1.player1_id = %s OR tm1.player2_id = %s THEN m.team2_id
                    ELSE m.team1_id
                END
                JOIN players opp1 ON opp_team.player1_id = opp1.id
                JOIN players opp2 ON opp_team.player2_id = opp2.id
                WHERE eh.player_id = %s
                ORDER BY eh.id
            """, (player_id, player_id, player_id, player_id, player_id, player_id))
            history = cur.fetchall()

        # Build HTML response
        cbva_link = f'<a href="https://cbva.com/p/{cbva_id}">{cbva_id}</a>'
        html = f'<h1>ELO History: {cbva_link}</h1>'
        html += f'<p><strong>Current ELO:</strong> {current_elo:.1f}</p>'

        # Rating-dependent ELOs section
        if rating_elos:
            html += '<h2>ELO by Opponent Rating</h2>'
            html += '<table border="1" cellpadding="5">'
            html += '<tr><th>vs Rating</th><th>ELO</th><th>Games</th></tr>'
            for opp_rating, elo, games in rating_elos:
                elo_float = float(elo)
                color = 'green' if elo_float > 1500 else 'red' if elo_float < 1500 else 'black'
                html += f'<tr>'
                html += f'<td>vs {opp_rating}</td>'
                html += f'<td style="color:{color}">{elo_float:.1f}</td>'
                html += f'<td>{games}</td>'
                html += f'</tr>'
            html += '</table>'

        if history:
            html += '<h2>Match History</h2>'
            html += '<table border="1" cellpadding="5">'
            html += '<tr><th>Date</th><th>Partner</th><th>Match</th><th>Opponent</th><th>Before</th><th>After</th><th>Change</th></tr>'
            for row in history:
                elo_before, elo_after, recorded_at, tournament_date, match_type, match_name, partner, opp1, opp2 = row
                change = float(elo_after) - float(elo_before)
                color = 'green' if change > 0 else 'red' if change < 0 else 'black'
                partner_link = f'<a href="https://cbva.com/p/{partner}">{partner}</a>'
                opp1_link = f'<a href="https://cbva.com/p/{opp1}">{opp1}</a>'
                opp2_link = f'<a href="https://cbva.com/p/{opp2}">{opp2}</a>'
                html += f'<tr>'
                html += f'<td>{tournament_date}</td>'
                html += f'<td>{partner_link}</td>'
                html += f'<td>{match_type} - {match_name}</td>'
                html += f'<td>{opp1_link} / {opp2_link}</td>'
                html += f'<td>{elo_before:.1f}</td>'
                html += f'<td>{elo_after:.1f}</td>'
                html += f'<td style="color:{color}">{change:+.1f}</td>'
                html += f'</tr>'
            html += '</table>'
        else:
            html += '<p>No ELO history found.</p>'

        return html

    finally:
        conn.close()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)

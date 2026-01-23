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
    return '<h1>Hello World</h1>'


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

            # Get ELO history with tournament and opponent info
            cur.execute("""
                SELECT
                    eh.elo_before,
                    eh.elo_after,
                    eh.recorded_at,
                    t.tournament_date,
                    m.match_type,
                    m.match_name,
                    opp1.cbva_id as opp1_cbva_id,
                    opp2.cbva_id as opp2_cbva_id
                FROM elo_history eh
                JOIN sets s ON eh.set_id = s.id
                JOIN matches m ON s.match_id = m.id
                JOIN teams tm1 ON m.team1_id = tm1.id
                JOIN teams tm2 ON m.team2_id = tm2.id
                JOIN tournaments t ON tm1.tournament_id = t.id
                -- Determine opponent team based on which team the player is on
                JOIN teams opp_team ON opp_team.id = CASE
                    WHEN tm1.player1_id = %s OR tm1.player2_id = %s THEN m.team2_id
                    ELSE m.team1_id
                END
                JOIN players opp1 ON opp_team.player1_id = opp1.id
                JOIN players opp2 ON opp_team.player2_id = opp2.id
                WHERE eh.player_id = %s
                ORDER BY eh.id
            """, (player_id, player_id, player_id))
            history = cur.fetchall()

        # Build HTML response
        cbva_link = f'<a href="https://cbva.com/p/{cbva_id}">{cbva_id}</a>'
        html = f'<h1>ELO History: {cbva_link}</h1>'
        html += f'<p><strong>Current ELO:</strong> {current_elo:.1f}</p>'

        if history:
            html += '<table border="1" cellpadding="5">'
            html += '<tr><th>Date</th><th>Match</th><th>Opponent</th><th>Before</th><th>After</th><th>Change</th></tr>'
            for row in history:
                elo_before, elo_after, recorded_at, tournament_date, match_type, match_name, opp1, opp2 = row
                change = float(elo_after) - float(elo_before)
                color = 'green' if change > 0 else 'red' if change < 0 else 'black'
                opp1_link = f'<a href="https://cbva.com/p/{opp1}">{opp1}</a>'
                opp2_link = f'<a href="https://cbva.com/p/{opp2}">{opp2}</a>'
                html += f'<tr>'
                html += f'<td>{tournament_date}</td>'
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
    app.run(debug=True, port=5000)

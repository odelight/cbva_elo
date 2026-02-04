"""
Database configuration for CBVA ELO system.

Configuration is loaded from environment variables with sensible defaults
for local development. Set these in a .env file or your environment.

Supports DATABASE_URL (used by Neon, Heroku, etc.) or individual DB_* variables.
"""

import getpass
import os
from urllib.parse import urlparse


def _parse_database_url(url):
    """Parse DATABASE_URL into connection parameters."""
    parsed = urlparse(url)
    return {
        'host': parsed.hostname,
        'port': str(parsed.port or 5432),
        'database': parsed.path.lstrip('/'),
        'user': parsed.username,
        'password': parsed.password or '',
    }


# Check for DATABASE_URL first (Neon, Heroku, etc.)
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    DATABASE_CONFIG = _parse_database_url(DATABASE_URL)
else:
    DATABASE_CONFIG = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'database': os.getenv('DB_NAME', 'cbva_elo'),
        'user': os.getenv('DB_USER', getpass.getuser()),  # Default to current system user (macOS/Homebrew)
        'password': os.getenv('DB_PASSWORD', ''),
    }


def get_connection_string():
    """
    Get PostgreSQL connection string.

    Returns a connection string suitable for psycopg2 or SQLAlchemy.
    """
    c = DATABASE_CONFIG
    if c['password']:
        return f"postgresql://{c['user']}:{c['password']}@{c['host']}:{c['port']}/{c['database']}"
    else:
        return f"postgresql://{c['user']}@{c['host']}:{c['port']}/{c['database']}"


def get_connection_params():
    """
    Get connection parameters as a dict.

    Returns a dict suitable for psycopg2.connect(**params).
    """
    params = {
        'host': DATABASE_CONFIG['host'],
        'port': DATABASE_CONFIG['port'],
        'dbname': DATABASE_CONFIG['database'],
        'user': DATABASE_CONFIG['user'],
    }
    if DATABASE_CONFIG['password']:
        params['password'] = DATABASE_CONFIG['password']
    # Require SSL for cloud databases (Neon, etc.)
    if DATABASE_URL:
        params['sslmode'] = 'require'
    return params

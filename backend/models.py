import sqlite3
import os
import time
import secrets
import hashlib
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DB_PATH", "/data/paywall.db")


def get_db():
    """Get a database connection with WAL mode for better concurrency."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize database tables."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS access_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code_hash TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL,
            product_id TEXT NOT NULL DEFAULT 'default',
            stripe_session_id TEXT UNIQUE,
            stripe_payment_intent TEXT,
            is_used INTEGER NOT NULL DEFAULT 0,
            used_at REAL,
            created_at REAL NOT NULL,
            expires_at REAL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_token_hash TEXT NOT NULL UNIQUE,
            access_code_id INTEGER NOT NULL,
            product_id TEXT NOT NULL DEFAULT 'default',
            created_at REAL NOT NULL,
            expires_at REAL,
            is_revoked INTEGER NOT NULL DEFAULT 0,
            ip_address TEXT,
            user_agent TEXT,
            FOREIGN KEY (access_code_id) REFERENCES access_codes (id)
        );

        CREATE TABLE IF NOT EXISTS failed_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            attempt_type TEXT NOT NULL,
            attempted_value_hash TEXT,
            created_at REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_access_codes_code_hash ON access_codes (code_hash);
        CREATE INDEX IF NOT EXISTS idx_access_codes_stripe_session ON access_codes (stripe_session_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions (session_token_hash);
        CREATE INDEX IF NOT EXISTS idx_failed_attempts_ip ON failed_attempts (ip_address, created_at);
    """)

    conn.commit()
    conn.close()
    logger.info("Database initialized at %s", DB_PATH)


def hash_value(value):
    """Hash a value using SHA-256 for secure storage."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_access_code():
    """Generate a cryptographically secure access code."""
    return secrets.token_urlsafe(32)


def generate_session_token():
    """Generate a cryptographically secure session token."""
    return secrets.token_urlsafe(48)


def create_access_code(email, product_id="default", stripe_session_id=None, stripe_payment_intent=None, expires_hours=None):
    """Create a new access code and store its hash."""
    code = generate_access_code()
    code_hash = hash_value(code)
    now = time.time()
    expires_at = now + (expires_hours * 3600) if expires_hours else None

    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO access_codes 
               (code_hash, email, product_id, stripe_session_id, stripe_payment_intent, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (code_hash, email, product_id, stripe_session_id, stripe_payment_intent, now, expires_at),
        )
        conn.commit()
        logger.info("Access code created for %s, product=%s", email, product_id)
        return code
    except sqlite3.IntegrityError:
        logger.error("Duplicate access code or session ID")
        conn.rollback()
        return None
    finally:
        conn.close()


def redeem_access_code(code, product_id="default"):
    """
    Redeem an access code. Returns the access_code row if valid, None otherwise.
    Codes are reusable - they are not invalidated after use.
    """
    code_hash = hash_value(code)
    now = time.time()

    conn = get_db()
    try:
        row = conn.execute(
            """SELECT * FROM access_codes
               WHERE code_hash = ? AND product_id = ?
               AND (expires_at IS NULL OR expires_at > ?)""",
            (code_hash, product_id, now),
        ).fetchone()
        if not row:
            logger.warning("Failed to redeem code (invalid or expired)")
            return None

        # Track usage but don't block reuse
        conn.execute(
            """UPDATE access_codes SET is_used = 1, used_at = ? WHERE code_hash = ?""",
            (now, code_hash),
        )
        conn.commit()
        logger.info("Access code redeemed for %s, product=%s", row["email"], product_id)
        return dict(row)
    except Exception as e:
        logger.error("Error redeeming code: %s", e)
        conn.rollback()
        return None
    finally:
        conn.close()


def create_session(access_code_id, product_id="default", ip_address=None, user_agent=None, expires_days=0):
    """Create a session token after code redemption. expires_days=0 means never expire."""
    token = generate_session_token()
    token_hash = hash_value(token)
    now = time.time()
    expires_at = now + (expires_days * 86400) if expires_days > 0 else None

    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO sessions 
               (session_token_hash, access_code_id, product_id, created_at, expires_at, ip_address, user_agent)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (token_hash, access_code_id, product_id, now, expires_at, ip_address, user_agent),
        )
        conn.commit()
        logger.info("Session created for access_code_id=%d, product=%s", access_code_id, product_id)
        return token, expires_at
    except Exception as e:
        logger.error("Error creating session: %s", e)
        conn.rollback()
        return None, None
    finally:
        conn.close()


def validate_session(token, product_id="default"):
    """Validate a session token. Returns True if valid."""
    if not token:
        return False

    token_hash = hash_value(token)
    now = time.time()

    conn = get_db()
    try:
        row = conn.execute(
            """SELECT * FROM sessions
               WHERE session_token_hash = ? AND product_id = ? AND is_revoked = 0
               AND (expires_at IS NULL OR expires_at > ?)""",
            (token_hash, product_id, now),
        ).fetchone()
        return row is not None
    except Exception as e:
        logger.error("Error validating session: %s", e)
        return False
    finally:
        conn.close()


def record_failed_attempt(ip_address, attempt_type, attempted_value=None):
    """Record a failed access attempt for rate limiting."""
    conn = get_db()
    try:
        value_hash = hash_value(attempted_value) if attempted_value else None
        conn.execute(
            """INSERT INTO failed_attempts (ip_address, attempt_type, attempted_value_hash, created_at)
               VALUES (?, ?, ?, ?)""",
            (ip_address, attempt_type, value_hash, time.time()),
        )
        conn.commit()
    except Exception as e:
        logger.error("Error recording failed attempt: %s", e)
    finally:
        conn.close()


def check_rate_limit(ip_address, attempt_type, max_attempts=10, window_seconds=3600):
    """Check if an IP has exceeded the rate limit. Returns True if rate limited."""
    cutoff = time.time() - window_seconds
    conn = get_db()
    try:
        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM failed_attempts
               WHERE ip_address = ? AND attempt_type = ? AND created_at > ?""",
            (ip_address, attempt_type, cutoff),
        ).fetchone()
        return row["cnt"] >= max_attempts
    except Exception as e:
        logger.error("Error checking rate limit: %s", e)
        return False
    finally:
        conn.close()


def cleanup_expired(days_old=30):
    """Clean up expired codes and sessions older than specified days."""
    cutoff = time.time() - (days_old * 86400)
    conn = get_db()
    try:
        conn.execute("DELETE FROM failed_attempts WHERE created_at < ?", (cutoff,))
        conn.execute(
            "DELETE FROM sessions WHERE expires_at < ? OR is_revoked = 1", (cutoff,)
        )
        conn.commit()
        logger.info("Cleaned up expired records older than %d days", days_old)
    except Exception as e:
        logger.error("Error during cleanup: %s", e)
    finally:
        conn.close()


def get_access_code_by_stripe_session(stripe_session_id):
    """Look up an access code by its Stripe session ID."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM access_codes WHERE stripe_session_id = ?",
            (stripe_session_id,),
        ).fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error("Error looking up by stripe session: %s", e)
        return None
    finally:
        conn.close()

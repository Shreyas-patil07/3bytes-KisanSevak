"""
db.py — Persistent storage layer for KisanSevak.

Uses Supabase (PostgreSQL) when SUPABASE_URL + SUPABASE_KEY are set.
Falls back to local JSON files for development.
"""

import os
import json
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths for local-file fallback
# ---------------------------------------------------------------------------
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
USERS_PATH = os.path.join(BASE_PATH, "users.json")
ORDERS_PATH = os.path.join(BASE_PATH, "orders.json")

# ---------------------------------------------------------------------------
# Supabase client (lazy-initialised)
# ---------------------------------------------------------------------------
_supabase = None


def _get_supabase():
    """Return a Supabase client, or None if env vars are missing."""
    global _supabase
    if _supabase is not None:
        return _supabase

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None

    try:
        from supabase import create_client
        _supabase = create_client(url, key)
        logger.info("Supabase client initialised.")
        return _supabase
    except Exception:
        logger.exception("Failed to initialise Supabase client — falling back to JSON files.")
        return None


def init_db():
    """Call once at app startup.  Logs which backend is active."""
    client = _get_supabase()
    if client:
        logger.info("Database backend: Supabase")
    else:
        logger.info("Database backend: local JSON files")


# ===================================================================
# USERS
# ===================================================================

def load_users() -> dict:
    client = _get_supabase()
    if client:
        try:
            resp = client.table("users").select("*").execute()
            return {row["email"]: {"name": row["name"], "password_hash": row["password_hash"]}
                    for row in resp.data}
        except Exception:
            logger.exception("Supabase load_users failed")
            return {}

    # --- JSON fallback ---
    if not os.path.exists(USERS_PATH):
        return {}
    with open(USERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_user(email: str, data: dict):
    """Insert or update a single user.  `data` = {"name": ..., "password_hash": ...}"""
    client = _get_supabase()
    if client:
        try:
            client.table("users").upsert({
                "email": email,
                "name": data["name"],
                "password_hash": data["password_hash"],
            }).execute()
            return
        except Exception:
            logger.exception("Supabase save_user failed")
            return

    # --- JSON fallback ---
    users = load_users()
    users[email] = data
    with open(USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


# ===================================================================
# ORDERS
# ===================================================================

def load_orders() -> dict:
    client = _get_supabase()
    if client:
        try:
            resp = client.table("orders").select("*").execute()
            orders: dict[str, list] = {}
            for row in resp.data:
                orders.setdefault(row["email"], []).append(row["order_data"])
            return orders
        except Exception:
            logger.exception("Supabase load_orders failed")
            return {}

    # --- JSON fallback ---
    if not os.path.exists(ORDERS_PATH):
        return {}
    with open(ORDERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_order(email: str, order: dict):
    """Append a single order for the given user."""
    client = _get_supabase()
    if client:
        try:
            client.table("orders").insert({
                "email": email,
                "order_data": order,
            }).execute()
            return
        except Exception:
            logger.exception("Supabase save_order failed")
            return

    # --- JSON fallback ---
    orders = load_orders()
    orders.setdefault(email, []).append(order)
    with open(ORDERS_PATH, "w", encoding="utf-8") as f:
        json.dump(orders, f, indent=2)

import os
import re
import json
import logging
import requests
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash

from QQDP_scoring import rank_items
from db import init_db, load_users, save_user, load_orders, save_order

# --------------------
# Logging
# --------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# --------------------
# App & Config
# --------------------
load_dotenv()

app = Flask(__name__)

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    # Keep production strict, but allow local development to boot without .env.
    is_production = os.getenv("FLASK_ENV") == "production"
    if is_production:
        raise RuntimeError("SECRET_KEY missing")
    SECRET_KEY = "dev-secret-key-change-me"
app.secret_key = SECRET_KEY

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL_ID = os.getenv("GEMINI_MODEL_ID")

model = None
if GOOGLE_API_KEY and GEMINI_MODEL_ID:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL_ID)

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
MATERIALS_PATH = os.path.join(BASE_PATH, "list_material.json")

# Initialise persistent storage (Supabase or JSON fallback)
init_db()

# --------------------
# Rate Limiter
# --------------------
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[],                 # no global limit
    storage_uri="memory://",
)


# --------------------
# Geocoding helpers
# --------------------
def pincode_to_coords(pincode: str):
    """Returns (lat, lon) or None if lookup fails."""
    try:
        resp = requests.get(
            f"https://api.postalpincode.in/pincode/{pincode}",
            timeout=5
        )
        data = resp.json()
        if not data or data[0].get("Status") != "Success":
            return None

        post_offices = data[0].get("PostOffice", [])
        if not post_offices:
            return None

        # First post office with valid coords
        for po in post_offices:
            lat = po.get("Latitude")
            lon = po.get("Longitude")
            if lat and lon and lat != "NA" and lon != "NA":
                return float(lat), float(lon)

        return None
    except Exception:
        logger.exception("PIN code geocoding failed for %s", pincode)
        return None


# City name fallback — expand as needed
CITY_COORDS = {
    "mumbai": (19.0760, 72.8777),
    "pune": (18.5204, 73.8567),
    "nagpur": (21.1458, 79.0882),
    "nashik": (19.9975, 73.7898),
    "aurangabad": (19.8762, 75.3433),
    "delhi": (28.6139, 77.2090),
    "bangalore": (12.9716, 77.5946),
    "hyderabad": (17.3850, 78.4867),
    "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639),
}


def validate_coords(lat, lon):
    """Return True if lat/lon are within valid geographic range."""
    return -90 <= lat <= 90 and -180 <= lon <= 180


# --------------------
# Session & helpers
# --------------------
def clear_chat_state():
    for key in ["farmer_lat", "farmer_lon", "category", "selected_product", "preference"]:
        session.pop(key, None)


AGRI_KEYWORDS = {
    "seed", "seeds", "fertilizer", "fertilizers", "pesticide", "pesticides",
    "crop", "crops", "soil", "farm", "farming", "farmer", "harvest",
    "irrigation", "plant", "plants", "agri", "agriculture", "kisan",
    "quality", "price", "distance", "quantity",
    "wheat", "rice", "corn", "urea", "dap", "npk", "neem",
    "chlorpyrifos", "imidacloprid"
}


PRODUCT_FLOW = {
    "seeds": {
        "question": "Which seed do you want?",
        "options": ["Wheat Seeds", "Rice Seeds", "Corn Seeds"],
        "filters": {
            "wheat seeds": "wheat",
            "rice seeds": "rice",
            "corn seeds": "corn",
        },
    },
    "fertilizers": {
        "question": "Which fertilizer do you want?",
        "options": ["Urea", "DAP", "NPK Fertilizer"],
        "filters": {
            "urea": "urea",
            "dap": "dap",
            "npk fertilizer": "npk",
        },
    },
    "pesticides": {
        "question": "Which pesticide do you want?",
        "options": ["Neem Oil", "Chlorpyrifos", "Imidacloprid"],
        "filters": {
            "neem oil": "neem",
            "chlorpyrifos": "chlorpyrifos",
            "imidacloprid": "imidacloprid",
        },
    },
}


# --------------------
# Stage prerequisite validation
# --------------------
STAGE_PREREQUISITES = {
    "ASK_CATEGORY":   ["farmer_lat", "farmer_lon"],
    "ASK_PRODUCT":    ["farmer_lat", "farmer_lon", "category"],
    "ASK_PREFERENCE": ["farmer_lat", "farmer_lon", "category", "selected_product"],
}


def validate_prerequisites(stage: str):
    """Return an error string if the session is missing prerequisites, else None."""
    required_keys = STAGE_PREREQUISITES.get(stage, [])
    missing = [k for k in required_keys if k not in session]
    if missing:
        return f"Missing prerequisites for stage {stage}: {', '.join(missing)}. Please restart the chat."
    return None


def is_non_agri_message(text):
    if not text:
        return False
    words = set(text.lower().replace(",", " ").replace(".", " ").split())
    has_agri_signal = any(word in AGRI_KEYWORDS for word in words)
    return not has_agri_signal


def agri_only_reply(next_stage):
    return jsonify({
        "reply": (
            "I can only assist with agriculture-related topics such as seeds, "
            "fertilizers, pesticides, crop quality, distance, quantity, and price."
        ),
        "stage": next_stage
    })

# --------------------
# Home
# --------------------
@app.route("/")
def home():
    if "user_email" not in session:
        return redirect(url_for("auth_page"))
    clear_chat_state()
    return render_template("index.html", user_name=session.get("user_name"))


@app.route("/auth", methods=["GET"])
def auth_page():
    if "user_email" in session:
        return redirect(url_for("home"))
    mode = request.args.get("mode", "login")
    if mode not in {"login", "signup"}:
        mode = "login"
    return render_template("auth.html", mode=mode)


@app.route("/auth/signup", methods=["POST"])
@limiter.limit("5/minute")
def auth_signup():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not name or not email or not password:
        return jsonify({"error": "Please fill all signup fields."}), 400

    users = load_users()
    if email in users:
        return jsonify({"error": "Account already exists. Please log in."}), 409

    save_user(email, {
        "name": name,
        "password_hash": generate_password_hash(password)
    })

    session["user_email"] = email
    session["user_name"] = name
    clear_chat_state()
    return jsonify({"ok": True, "redirect": url_for("home")})


@app.route("/auth/login", methods=["POST"])
@limiter.limit("5/minute")
def auth_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    users = load_users()
    user = users.get(email)
    if not user or not check_password_hash(user.get("password_hash", ""), password):
        return jsonify({"error": "Invalid email or password."}), 401

    session["user_email"] = email
    session["user_name"] = user.get("name", "Farmer")
    clear_chat_state()
    return jsonify({"ok": True, "redirect": url_for("home")})


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True, "redirect": url_for("auth_page")})


@app.route("/orders", methods=["GET"])
def orders_page():
    if "user_email" not in session:
        return redirect(url_for("auth_page"))

    all_orders = load_orders()
    orders = all_orders.get(session["user_email"], [])
    return render_template(
        "orders.html",
        user_name=session.get("user_name", "Farmer"),
        orders=orders,
    )

# --------------------
# Start chat
# --------------------
@app.route("/chat/start", methods=["GET"])
def chat_start():
    if "user_email" not in session:
        return jsonify({"error": "Please log in first.", "redirect": url_for("auth_page")}), 401
    return jsonify({
        "reply": (
            "Hello! I only help with agriculture-related decisions.\n\n"
            "Please allow location permission to continue."
        ),
        "stage": "ASK_LOCATION_PERMISSION"
    })


@app.route("/chat/location", methods=["POST"])
def chat_location():
    if "user_email" not in session:
        return jsonify({"error": "Please log in first.", "redirect": url_for("auth_page")}), 401

    data = request.get_json(silent=True) or {}
    lat = data.get("lat")
    lon = data.get("lon")

    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid location coordinates."}), 400

    if not validate_coords(lat, lon):
        return jsonify({"error": "Coordinates out of range. Latitude must be -90 to 90, longitude -180 to 180."}), 400

    session["farmer_lat"] = lat
    session["farmer_lon"] = lon

    return jsonify({
        "reply": (
            "Location set!\n\n"
            "What do you want to buy?\n"
            "• Seeds\n"
            "• Fertilizers\n"
            "• Pesticides"
        ),
        "stage": "ASK_CATEGORY"
    })

# --------------------
# Receive GPS location (REMOVED)
# --------------------

# --------------------
# PIN → LAT/LON (REMOVED)
# --------------------

# --------------------
# Main chat logic
# --------------------
@app.route("/chat", methods=["POST"])
def chat():
    if "user_email" not in session:
        return jsonify({"error": "Please log in first.", "redirect": url_for("auth_page")}), 401

    data = request.get_json(silent=True) or {}
    stage = data.get("stage")
    message = (data.get("message") or "").strip().lower()

    # ---- LOCATION TEXT FALLBACK ----
    if stage == "ASK_LOCATION_TEXT":
        if not message:
            return jsonify({
                "reply": "Please enter a valid village name, city, or 6-digit PIN code.",
                "stage": "ASK_LOCATION_TEXT"
            })

        coords = None

        # Try PIN code first
        if re.fullmatch(r"\d{6}", message):
            coords = pincode_to_coords(message)
            if not coords:
                return jsonify({
                    "reply": "Couldn't find that PIN code. Try a nearby PIN or enter your city name.",
                    "stage": "ASK_LOCATION_TEXT"
                })
        else:
            # Try city name lookup
            coords = CITY_COORDS.get(message.lower().strip())
            if not coords:
                return jsonify({
                    "reply": (
                        "Couldn't find that location. "
                        "Please enter a 6-digit PIN code or a city name (e.g. Mumbai, Pune, Nagpur)."
                    ),
                    "stage": "ASK_LOCATION_TEXT"
                })

        session["farmer_lat"], session["farmer_lon"] = coords

        return jsonify({
            "reply": (
                "Location set!\n\n"
                "What do you want to buy?\n"
                "• Seeds\n"
                "• Fertilizers\n"
                "• Pesticides"
            ),
            "stage": "ASK_CATEGORY"
        })

    # ---- Prerequisite validation for remaining stages ----
    prereq_error = validate_prerequisites(stage)
    if prereq_error:
        return jsonify({"error": prereq_error}), 400

    # ---- CATEGORY ----
    if stage == "ASK_CATEGORY":
        if message not in {"seeds", "fertilizers", "pesticides"} and is_non_agri_message(message):
            return agri_only_reply("ASK_CATEGORY")

        if message not in {"seeds", "fertilizers", "pesticides"}:
            return jsonify({
                "reply": "Please choose: seeds, fertilizers, or pesticides.",
                "stage": "ASK_CATEGORY"
            })

        session["category"] = message
        category_flow = PRODUCT_FLOW[message]
        product_options = "\n".join(f"• {opt}" for opt in category_flow["options"])

        return jsonify({
            "reply": (
                f"{category_flow['question']}\n\n"
                f"{product_options}"
            ),
            "stage": "ASK_PRODUCT"
        })

    # ---- PRODUCT ----
    if stage == "ASK_PRODUCT":
        category = session.get("category")
        category_flow = PRODUCT_FLOW.get(category)
        if not category_flow:
            return jsonify({
                "reply": "Please choose: seeds, fertilizers, or pesticides.",
                "stage": "ASK_CATEGORY"
            })

        valid_options = set(category_flow["filters"].keys())
        if message not in valid_options:
            product_options = "\n".join(f"• {opt}" for opt in category_flow["options"])
            return jsonify({
                "reply": f"Please choose one option below:\n\n{product_options}",
                "stage": "ASK_PRODUCT"
            })

        session["selected_product"] = message

        return jsonify({
            "reply": (
                "What is most important to you?\n\n"
                "• quality\n"
                "• price\n"
                "• distance\n"
                "• quantity"
            ),
            "stage": "ASK_PREFERENCE"
        })

    # ---- PREFERENCE ----
    if stage == "ASK_PREFERENCE":
        if message not in {"quality", "price", "distance", "quantity"} and is_non_agri_message(message):
            return agri_only_reply("ASK_PREFERENCE")

        if message not in {"quality", "price", "distance", "quantity"}:
            return jsonify({
                "reply": "Please reply with: quality, price, distance, or quantity.",
                "stage": "ASK_PREFERENCE"
            })

        session["preference"] = message

        with open(MATERIALS_PATH, "r") as f:
            materials = json.load(f)

        items = materials.get(session["category"], [])
        if not items:
            return jsonify({"error": "No data found"}), 404

        selected_product = session.get("selected_product")
        category_flow = PRODUCT_FLOW.get(session["category"], {})
        keyword = category_flow.get("filters", {}).get(selected_product)
        if keyword:
            filtered_items = [item for item in items if keyword in (item.get("name", "").lower())]
            if not filtered_items:
                product_options = "\n".join(f"• {opt}" for opt in category_flow.get("options", []))
                return jsonify({
                    "reply": (
                        "No matching products found for that selection. Please choose another option:\n\n"
                        f"{product_options}"
                    ),
                    "stage": "ASK_PRODUCT"
                })
            items = filtered_items

        for item in items:
            item["farmer_lat"] = session["farmer_lat"]
            item["farmer_lon"] = session["farmer_lon"]

        farmer_preference = {
        "quality": "high" if session["preference"] == "quality" else "average",
        "price": "high" if session["preference"] == "price" else "average",
        "distance": "high" if session["preference"] == "distance" else "average",
        "quantity": "high" if session["preference"] == "quantity" else "average",
        }

        ranked = rank_items(items, farmer_preference)
        if not ranked:
            return jsonify({
                "reply": "No suitable options found nearby based on quality, quantity, distance, and price.",
                "stage": "DONE",
                "ranked_items": []
            })

        top_items = ranked[:2]

        reply = (
            "Based on your preference, the top option ranks highest "
            "due to better balance of quality, availability, distance, and price."
        )

        if model:
            prompt = f"""
You are an agricultural recommendation assistant.

You must answer ONLY agriculture-related content.
If the user asks anything outside agriculture, reply exactly:
"I can only assist with agriculture-related topics."

Your job is to EXPLAIN a pre-selected best option to a farmer.
You DO NOT choose products.
You DO NOT change scores.
You DO NOT invent data.

====================
INPUT DATA
====================
Farmer Preference: {session["preference"]}
Selected Product: {session.get("selected_product", "not specified")}

Top Ranked Options (already scored, do not reorder):
{json.dumps(top_items, indent=2)}

====================
OUTPUT FORMAT (MANDATORY)
====================

🌾 Best Recommendation for You

Product: <product name>
Seller: <seller name>

Why this is the best choice:
• <reason 1 – use data>
• <reason 2 – use data>
• <reason 3 – use data>

✅ Pros:
• <pro 1>
• <pro 2>

⚠️ Cons:
• <exactly one con>

🔍 Comparison:
Compared to <2nd product name>, this option <short comparison sentence>.

====================
STRICT RULES
====================
1. Follow the format EXACTLY (headings, emojis, bullets).
2. Reasons:
   - EXACTLY 3 reasons
   - Data-backed only
3. Pros:
   - EXACTLY 2 points
4. Cons:
   - EXACTLY 1 point
5. Comparison:
   - Mention ONLY the 2nd-ranked option
6. Use simple, farmer-friendly language.
7. Do NOT mention:
   - AI
   - model
   - algorithm
   - scoring logic
8. Do NOT add extra sections.
9. Do NOT exceed 140 words.
10. If data is missing, SKIP that point instead of guessing.

Return ONLY the formatted answer.
""".strip()

            try:
                res = model.generate_content(prompt)
                if res.text:
                    reply = res.text.strip()
            except Exception as e:
                logger.exception("Gemini API error: %s", e)
                # reply already set to the fallback above

        return jsonify({
            "reply": reply,
            "stage": "DONE",
            "top_items": top_items,
            "ranked_items": ranked
        })

    return jsonify({"error": "Invalid stage"}), 400

# --------------------
# Rate-limit error handler
# --------------------
@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"error": "Too many requests. Please try again in a minute."}), 429

# --------------------
# Run
# --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

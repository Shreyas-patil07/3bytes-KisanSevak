import os
import json
import requests
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, session

from QQDP_scoring import rank_items

# --------------------
# App & Config
# --------------------
load_dotenv()

app = Flask(__name__)

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY missing")
app.secret_key = SECRET_KEY

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL_ID = os.getenv("GEMINI_MODEL_ID")

model = None
if GOOGLE_API_KEY and GEMINI_MODEL_ID:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL_ID)

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
MATERIALS_PATH = os.path.join(BASE_PATH, "list_material.json")

# --------------------
# Home
# --------------------
@app.route("/")
def home():
    session.clear()
    return render_template("index.html")

# --------------------
# Start chat
# --------------------
@app.route("/chat/start", methods=["GET"])
def chat_start():
    return jsonify({
        "reply": (
            "Hello! I will help you choose the best agricultural product.\n\n"
            "Please allow location access so I can find nearby sellers."
        ),
        "stage": "ASK_LOCATION"
    })

# --------------------
# Receive GPS location
# --------------------
@app.route("/chat/location", methods=["POST"])
def receive_location():
    data = request.get_json(silent=True) or {}

    lat = data.get("latitude")
    lon = data.get("longitude")

    if lat is None or lon is None:
        return jsonify({"error": "Latitude and longitude required"}), 400

    session["farmer_lat"] = float(lat)
    session["farmer_lon"] = float(lon)

    return jsonify({
        "reply": (
            "Location saved.\n\n"
            "What do you want to buy?\n"
            "• Seeds\n"
            "• Fertilizers\n"
            "• Pesticides"
        ),
        "stage": "ASK_CATEGORY"
    })

# --------------------
# PIN → LAT/LON (India)
# --------------------
@app.route("/chat/pin", methods=["POST"])
def pin_to_location():
    data = request.get_json(silent=True) or {}
    pin = str(data.get("pin", "")).strip()

    if not pin.isdigit() or len(pin) != 6:
        return jsonify({
            "reply": "Please enter a valid 6-digit PIN code.",
            "stage": "ASK_LOCATION_TEXT"
        })

    try:
        res = requests.get(f"https://api.postalpincode.in/pincode/{pin}", timeout=5)
        info = res.json()[0]

        if info["Status"] != "Success":
            raise ValueError("Invalid PIN")

        post_office = info["PostOffice"][0]
        district = post_office["District"]
        state = post_office["State"]

        # --------------------
        # DISTRICT → LAT/LON (fallback mapping)
        # --------------------
        DISTRICT_COORDS = {
            "Mumbai": (19.0760, 72.8777),
            "Pune": (18.5204, 73.8567),
            "Thane": (19.2183, 72.9781),
            "Nashik": (19.9975, 73.7898),
            "Nagpur": (21.1458, 79.0882),
        }

        lat, lon = DISTRICT_COORDS.get(district, (19.0760, 72.8777))

        session["farmer_lat"] = lat
        session["farmer_lon"] = lon

        return jsonify({
            "reply": (
                f"Location found for PIN {pin} ({district}, {state}).\n\n"
                "What do you want to buy?\n"
                "• Seeds\n"
                "• Fertilizers\n"
                "• Pesticides"
            ),
            "stage": "ASK_CATEGORY"
        })

    except Exception:
        return jsonify({
            "reply": "Could not find location for this PIN. Please try another PIN.",
            "stage": "ASK_LOCATION_TEXT"
        })

# --------------------
# Main chat logic
# --------------------
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    stage = data.get("stage")
    message = (data.get("message") or "").strip().lower()

    # ---- LOCATION TEXT FALLBACK (REPAIRED) ----
    if stage == "ASK_LOCATION_TEXT":
        if not message:
            return jsonify({
                "reply": "Please enter a valid village name or PIN code.",
                "stage": "ASK_LOCATION_TEXT"
            })

        # Temporary fallback coordinates
        session["farmer_lat"] = 19.1070
        session["farmer_lon"] = 72.8399

        return jsonify({
            "reply": (
                "Location noted.\n\n"
                "What do you want to buy?\n"
                "• Seeds\n"
                "• Fertilizers\n"
                "• Pesticides"
            ),
            "stage": "ASK_CATEGORY"
        })

    # ---- CATEGORY ----
    if stage == "ASK_CATEGORY":
        if message not in {"seeds", "fertilizers", "pesticides"}:
            return jsonify({
                "reply": "Please choose: seeds, fertilizers, or pesticides.",
                "stage": "ASK_CATEGORY"
            })

        session["category"] = message

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

        top_items = ranked[:2]

        reply = (
            "Based on your preference, the top option ranks highest "
            "due to better balance of quality, availability, distance, and price."
        )

        if model:
            prompt = f"""
You are an agricultural recommendation assistant.

Your job is to EXPLAIN a pre-selected best option to a farmer.
You DO NOT choose products.
You DO NOT change scores.
You DO NOT invent data.

====================
INPUT DATA
====================
Farmer Preference: {session["preference"]}

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
            except Exception:
                pass

        return jsonify({
            "reply": reply,
            "stage": "DONE",
            "top_items": top_items
        })

    return jsonify({"error": "Invalid stage"}), 400

# --------------------
# Run
# --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

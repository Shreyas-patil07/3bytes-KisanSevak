import os
import math
import json
from typing import List, Dict, Tuple

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
MATERIALS_PATH = os.path.join(BASE_PATH, "list_material.json")

MAX_DISTANCE_KM = 25
MIN_QUALITY = 0.4
MIN_QUANTITY_RATIO = 0.8

# Farmer preference intensity mapping
LEVEL_SCORE = {
    "low": 1,
    "average": 2,
    "high": 3
}

# -------------------------------------------------
# DISTANCE (HAVERSINE)
# -------------------------------------------------
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2 +
        math.cos(phi1) * math.cos(phi2) *
        math.sin(dlambda / 2) ** 2
    )
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# -------------------------------------------------
# QUALITY (FINAL, COMPOSITE)
# -------------------------------------------------
def compute_quality(item: Dict) -> float:
    if item["review_count"] == 0 or item["avg_rating"] == 0:
        review_signal = 0
    else:
        review_signal = min(
            (item["avg_rating"] / 5) * math.log10(item["review_count"] + 1),
            1
        )

    quality = (
        0.45 * item["product_quality"] +
        0.35 * item["reliability"] +
        0.20 * review_signal
    )
    return round(quality, 3)

# -------------------------------------------------
# FARMER PREFERENCE → WEIGHTS
# -------------------------------------------------
def compute_weights(preference: Dict[str, str]) -> Tuple[float, float, float, float]:
    """
    preference example:
    {
        "quality": "high",
        "quantity": "average",
        "distance": "low",
        "price": "high"
    }
    """

    q  = LEVEL_SCORE[preference["quality"]]
    qt = LEVEL_SCORE[preference["quantity"]]
    d  = LEVEL_SCORE[preference["distance"]]
    p  = LEVEL_SCORE[preference["price"]]

    total = q + qt + d + p

    return (
        q / total,    # Quality weight
        qt / total,   # Quantity weight
        d / total,    # Distance weight
        p / total     # Price weight
    )

# -------------------------------------------------
# QQDP SCORE (FINAL)
# -------------------------------------------------
def qqdp_score(
    item: Dict,
    price_min: float,
    price_max: float,
    preference: Dict[str, str]
) -> Dict | None:

    # Distance
    distance_km = haversine_km(
        item["farmer_lat"], item["farmer_lon"],
        item["seller_lat"], item["seller_lon"]
    )

    # Core components
    quality = compute_quality(item)
    quantity = min(item["available_qty"] / item["required_qty"], 1)
    distance_score = max(0, 1 - (distance_km / MAX_DISTANCE_KM))

    price_score = 1 if price_max == price_min else (
        (price_max - item["price"]) / (price_max - price_min)
    )

    # ---------------- HARD FILTERS ----------------
    if (
        quality < MIN_QUALITY or
        quantity < MIN_QUANTITY_RATIO or
        distance_km > MAX_DISTANCE_KM
    ):
        return None

    # Dynamic weights from farmer preference
    wQ, wQt, wD, wP = compute_weights(preference)

    final_score = (
        wQ  * quality +
        wQt * quantity +
        wD  * distance_score +
        wP  * price_score
    )

    return {
        "item_id": item["item_id"],
        "category": item["category"],
        "name": item["name"],
        "seller": item["seller_name"],
        "distance_km": round(distance_km, 2),
        "quality": quality,
        "final_score": round(final_score, 3),
        "price": item["price"]
    }

# -------------------------------------------------
# RANK ITEMS (GENERIC)
# -------------------------------------------------
def rank_items(items: List[Dict], preference: Dict[str, str]) -> List[Dict]:
    prices = [i["price"] for i in items]
    price_min, price_max = min(prices), max(prices)

    scored = []
    for item in items:
        result = qqdp_score(item, price_min, price_max, preference)
        if result:
            scored.append(result)

    return sorted(scored, key=lambda x: x["final_score"], reverse=True)

# -------------------------------------------------
# MAIN (EXAMPLE FLOW)
# -------------------------------------------------
if __name__ == "__main__":
    with open(MATERIALS_PATH, "r") as f:
        data = json.load(f)

    # Example farmer preference
    farmer_preference = {
        "quality": "high",
        "quantity": "average",
        "distance": "low",
        "price": "high"
    }

    best_seed = rank_items(data["seeds"], farmer_preference)[0]
    best_fertilizer = rank_items(data["fertilizers"], farmer_preference)[0]
    best_pesticide = rank_items(data["pesticides"], farmer_preference)[0]

    print("\nBEST SEED:", best_seed)
    print("\nBEST FERTILIZER:", best_fertilizer)
    print("\nBEST PESTICIDE:", best_pesticide)

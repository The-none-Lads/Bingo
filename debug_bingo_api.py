import json

import requests

BASE = "http://localhost:8000"
GAME_ID = "testgame"


def pretty(obj):
    try:
        print(json.dumps(obj, indent=2))
    except Exception:
        print(obj)


def debug_request(method, url, **kwargs):
    print(f"\n➡️ {method} {url}")
    if "json" in kwargs:
        print("Payload:", json.dumps(kwargs["json"], indent=2))
    res = requests.request(method, url, **kwargs)
    print("Status:", res.status_code)
    try:
        data = res.json()
        print("Response JSON:")
        pretty(data)
        return data
    except Exception:
        print("Raw response:", res.text)
        return None


def main():
    print("=== DEBUG BINGO API TEST ===")

    # 1. Start a game
    start = debug_request(
        "POST",
        f"{BASE}/games/{GAME_ID}/start",
        json={"mode": "progressive_rows", "ball_set": 75, "stage": 1},
    )

    # 2. Draw 5 numbers
    for i in range(5):
        debug_request("POST", f"{BASE}/games/{GAME_ID}/draw")

    # 3. Get game state
    debug_request("GET", f"{BASE}/games/{GAME_ID}/state")

    # 4. Generate 3 cards
    cards_resp = debug_request(
        "POST", f"{BASE}/cards/batch", json={"count": 3, "game_id": GAME_ID}
    )
    if not cards_resp or "cards" not in cards_resp:
        print("❌ Could not generate cards, aborting.")
        return
    first_card = cards_resp["cards"][0]
    public_id = first_card["public_id"]

    # 5. Retrieve one card
    debug_request("GET", f"{BASE}/cards/{public_id}")

    # 6. Validate that card
    debug_request(
        "POST", f"{BASE}/validate", json={"game_id": GAME_ID, "serial": public_id}
    )

    # 7. Try invalid card
    bad_id = "BADCODE1"
    debug_request("GET", f"{BASE}/cards/{bad_id}")
    debug_request(
        "POST", f"{BASE}/validate", json={"game_id": GAME_ID, "serial": bad_id}
    )

    print("\n=== DEBUG RUN COMPLETE ===")


if __name__ == "__main__":
    main()

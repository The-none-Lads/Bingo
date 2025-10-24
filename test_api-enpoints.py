import pytest
import requests
import json

BASE = "http://localhost:8000"
GAME_ID = "testgame"

def pretty(obj):
    """Pretty-print JSON objects for debug output."""
    print(json.dumps(obj, indent=2))

# --- Fixtures ---

@pytest.fixture(scope="module")
def start_game():
    res = requests.post(f"{BASE}/games/{GAME_ID}/start", json={
        "mode": "progressive_rows",
        "ball_set": 75,
        "stage": 1
    })
    assert res.status_code == 200
    return res.json()

@pytest.fixture(scope="module")
def drawn_numbers(start_game):
    numbers = []
    for _ in range(5):
        res = requests.post(f"{BASE}/games/{GAME_ID}/draw")
        assert res.status_code == 200
        data = res.json()
        numbers.append(data["drawn_number"])
    return numbers

@pytest.fixture(scope="module")
def generated_cards(start_game):
    res = requests.post(f"{BASE}/cards/batch", json={"count": 3, "game_id": GAME_ID})
    assert res.status_code == 200
    data = res.json()
    assert "cards" in data
    assert len(data["cards"]) == 3
    return data["cards"]

# --- Normal Tests ---

def test_game_started(start_game):
    assert start_game["config"]["mode"] == "progressive_rows"
    assert start_game["config"]["ball_set"] == 75

def test_draw_numbers(drawn_numbers):
    assert len(drawn_numbers) == 5
    assert all(isinstance(n, int) for n in drawn_numbers)

def test_game_state():
    res = requests.get(f"{BASE}/games/{GAME_ID}/state")
    assert res.status_code == 200
    data = res.json()
    assert data["game_id"] == GAME_ID
    assert data["status"] == "active"

def test_generate_cards(generated_cards):
    first = generated_cards[0]
    assert "public_id" in first
    assert "serial" in first
    assert "grid" in first

def test_retrieve_card(generated_cards):
    public_id = generated_cards[0]["public_id"]
    res = requests.get(f"{BASE}/cards/{public_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["exists"] is True
    assert data["public_id"] == public_id

def test_validate_card(generated_cards):
    public_id = generated_cards[0]["public_id"]
    res = requests.post(f"{BASE}/validate", json={"game_id": GAME_ID, "serial": public_id})
    assert res.status_code == 200
    data = res.json()
    assert "valid" in data
    assert data["public_id"] == public_id

def test_invalid_card():
    bad_id = "BADCODE1"
    res = requests.get(f"{BASE}/cards/{bad_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["exists"] is False

    res = requests.post(f"{BASE}/validate", json={"game_id": GAME_ID, "serial": bad_id})
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is False
    assert "error" in data["details"]


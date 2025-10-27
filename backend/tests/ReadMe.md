# Bingo Application Test Suite

This directory contains comprehensive tests for the bingo application backend.

## Test Structure

```
backend/tests/
├── conftest.py          # Shared fixtures and pytest configuration
├── test_cards.py        # Card generation and serialization tests
├── test_draws.py        # Draw engine tests
├── test_modes.py        # Game mode validation tests
└── test_api.py          # API endpoint integration tests
```

## Running Tests

### Quick Start

```bash
# Run all tests
make test

# Run with coverage
make test-coverage

# Run specific test file
cd backend
pytest tests/test_cards.py -v

# Run specific test
pytest tests/test_cards.py::TestCardGeneration::test_generate_75_ball_card_structure -v
```

### Using pytest directly

```bash
cd backend

# Run all tests with verbose output
pytest tests/ -v

# Run only unit tests
pytest tests/ -v -m unit

# Run only integration tests
pytest tests/ -v -m integration

# Run with coverage report
pytest tests/ --cov=. --cov-report=html --cov-report=term-missing

# Run specific test class
pytest tests/test_cards.py::TestCardGeneration -v

# Run tests matching a pattern
pytest tests/ -k "test_draw" -v

# Run tests and stop on first failure
pytest tests/ -x

# Show local variables in tracebacks
pytest tests/ -l

# Run tests in parallel (requires pytest-xdist)
pytest tests/ -n auto
```

## Test Categories

### Unit Tests (`test_cards.py`, `test_draws.py`, `test_modes.py`)

These tests focus on individual functions and classes without external dependencies.

**test_cards.py:**
- Card generation logic
- Serialization/deserialization
- Short ID generation
- Column range validation
- Uniqueness checks

**test_draws.py:**
- Draw engine initialization
- Number drawing logic
- Randomization
- Exhaustion handling
- State consistency

**test_modes.py:**
- Row completion detection
- Four corners validation
- Diagonal validation
- Full house validation
- Win condition logic

### Integration Tests (`test_api.py`)

These tests verify the entire API works correctly end-to-end.

**Coverage includes:**
- Game lifecycle (start, draw, state)
- Card generation and retrieval
- Validation workflows
- Error handling
- CORS configuration
- Multi-game scenarios

## Test Fixtures

### Shared Fixtures (conftest.py)

- `clean_database`: Cleans DB before/after each test
- `test_client`: FastAPI test client
- `sample_game_id`: Consistent game ID
- `started_game`: Pre-started game
- `generated_card`: Single generated card
- `generated_cards`: Multiple generated cards
- `sample_bingo_grid`: Sample 5x5 grid
- `complete_row_numbers`: Numbers for first row
- `four_corner_numbers`: Corner numbers
- `diagonal_numbers`: Diagonal numbers
- `all_grid_numbers`: All numbers for full house

## Coverage Goals

Current coverage target: **90%+**
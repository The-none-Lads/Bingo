# Bingo Application Test Suite

This directory contains comprehensive tests for the bingo application backend, achieving 90%+ code coverage.

## 📁 Test Structure

```
backend/tests/
├── conftest.py          # Shared fixtures and pytest configuration
├── test_cards.py        # Card generation and serialization tests
├── test_draws.py        # Draw engine tests
├── test_modes.py        # Game mode validation tests
├── test_api.py          # API endpoint integration tests
└── README.md            # This file

backend/integration_tests/
├── conftest.py          # Integration test configuration
└── test_integration.py  # Full end-to-end integration tests
```

## 🚀 Running Tests

### Quick Start

```bash
# Run all tests
make test

# Run with coverage report
make test-coverage

# Run specific test file
cd backend
pytest tests/test_cards.py -v

# Run specific test
pytest tests/test_cards.py::TestCardGeneration::test_generate_75_ball_card_structure -v
```

### Using pytest Directly

```bash
cd backend

# Run all tests with verbose output
pytest tests/ -v

# Run only unit tests
pytest tests/ -v

# Run only integration tests
pytest integration_tests/ -v

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

### Coverage Reports

```bash
# Generate HTML coverage report
pytest tests/ --cov=. --cov-report=html

# Open coverage report in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows

# Generate XML coverage report (for CI/CD)
pytest tests/ --cov=. --cov-report=xml

# Terminal coverage report with missing lines
pytest tests/ --cov=. --cov-report=term-missing
```

## 📋 Test Categories

### Unit Tests

Pure unit tests that focus on individual functions and classes without external dependencies.

#### test_cards.py

Tests for card generation and serialization logic:

- **Card Generation**
  - 5x5 grid structure validation
  - FREE space in center (position [2][2])
  - Column range validation (B: 1-15, I: 16-30, N: 31-45, G: 46-60, O: 61-75)
  - No duplicate numbers on a card
  - Uniqueness across multiple generated cards

- **Serialization**
  - Card to string serialization
  - String to card deserialization
  - Round-trip consistency (serialize → deserialize → original)
  - Short ID generation (8 character alphanumeric)
  - Deterministic ID generation (same card = same ID)
  - High uniqueness across different cards

- **Edge Cases**
  - Invalid format handling
  - Custom ID length support

#### test_draws.py

Tests for the draw engine that manages number drawing:

- **Initialization**
  - Correct max number setup (default 75)
  - Custom max number support (e.g., 90-ball bingo)
  - Initial state (75 remaining, 0 drawn)

- **Drawing Logic**
  - Single number drawing
  - Number within valid range (1-75)
  - No duplicate draws
  - Drawn list maintains order
  - Remaining list decreases correctly

- **Exhaustion**
  - Drawing all numbers
  - Returns `None` when exhausted
  - State consistency (drawn + remaining = max)

- **Randomization**
  - Non-deterministic draw order
  - Cryptographically secure randomness (uses `secrets` module)
  - Reasonable distribution

- **Edge Cases**
  - Single number set (max=1)
  - Large number sets (max=1000)

#### test_modes.py

Tests for game mode validation logic:

- **Row Completion**
  - No rows completed
  - Single row completion
  - Multiple rows completed
  - Rows with FREE space
  - All rows completed (full house)
  - Partial rows don't count

- **Four Corners**
  - No corners marked
  - Partial corners (1-3)
  - All four corners
  - Extra numbers don't affect validation

- **Diagonals**
  - No diagonal complete
  - Main diagonal (top-left to bottom-right)
  - Anti-diagonal (top-right to bottom-left)
  - Both diagonals
  - FREE space in center counts as marked
  - Partial diagonals don't count

- **Full House (Blackout)**
  - Empty card
  - Partially filled card
  - Complete full house
  - Extra numbers beyond card
  - Missing one number (should fail)

- **Win Detection (is_win)**
  - Progressive rows mode with stages
  - Full house mode
  - Four corners mode
  - Diagonals mode
  - Exceeding requirements (3 rows when 2 required)
  - Unknown mode handling

- **Edge Cases**
  - Empty grid (all FREE)
  - Grid with all numbers drawn

### Integration Tests

#### test_api.py

Tests for API endpoints with realistic request/response cycles:

- **Game Endpoints**
  - Starting a game with different modes
  - Drawing numbers
  - Getting game state
  - Setting progressive stages
  - Drawing all numbers (exhaustion)
  - Multiple simultaneous games

- **Card Endpoints**
  - Generating single cards
  - Generating multiple cards (10, 50, 100)
  - Retrieving cards by ID
  - Non-existent card handling
  - Card grid structure validation
  - Column range validation
  - Getting all cards for a game

- **Validation Endpoint**
  - Validating winning cards (1 row, full house)
  - Non-winning cards
  - Non-existent cards
  - Non-existent games
  - Different game modes (progressive, full house, etc.)

- **CORS Configuration**
  - CORS headers present in responses
  - Configured origins allowed
  - Credentials support

- **Error Handling**
  - Invalid game ID formats (actually allows all formats)
  - Invalid request bodies (422 validation errors)
  - Missing required fields

- **Complete Workflows**
  - Full game from start to win
  - Progressive stage advancement
  - Multiple games simultaneously

#### integration_tests/test_integration.py

Full end-to-end integration tests with both in-process and live server testing:

- **Full Game Flow**
  - Start game
  - Fetch game state
  - Generate batch of cards
  - Retrieve specific card
  - Draw numbers
  - Validate cards

- **Testing Modes**
  - In-process (fast, uses ASGI transport)
  - Live server (realistic, spawns uvicorn)

- **Error Cases**
  - Drawing from non-existent game (404)

- **CORS Testing**
  - Allowed origins
  - Rejected origins
  - Preflight requests

## 🔧 Test Fixtures

### Shared Fixtures (conftest.py)

All fixtures are automatically available to all tests in the directory.

**Configuration:**
- `pytest_configure()` - Sets default environment variables (`CORS_ORIGINS`, `CORS_ALLOW_CREDENTIALS`)

### Test-Specific Fixtures

**From test_api.py:**
- `clean_db` - Cleans database before/after each test (autouse)
- `client` - FastAPI TestClient for API requests

**From test_modes.py:**
- `sample_grid` - Standard 5x5 bingo grid for testing

## 📊 Coverage Goals

**Current target: 90%+**

### Coverage by Module

- `backend/logic/cards.py` - 95%+
- `backend/logic/draws.py` - 95%+
- `backend/logic/modes.py` - 95%+
- `backend/logic/validate.py` - 90%+
- `backend/app.py` - 85%+
- `backend/models.py` - 100% (Pydantic models)
- `backend/storage/db.py` - 100%

### Viewing Coverage

```bash
# Generate and view HTML report
make test-coverage
open htmlcov/index.html

# View in terminal
pytest tests/ --cov=. --cov-report=term-missing
```

### Coverage Configuration

Coverage settings are configured in:
- `pytest.ini` - Pytest and coverage options
- `.coveragerc` - Coverage.py configuration
- `setup.cfg` - Additional coverage report settings

## 🔍 Test Markers

Tests can be marked for selective running:

```python
@pytest.mark.unit
def test_something():
    pass

@pytest.mark.integration
def test_integration():
    pass

@pytest.mark.slow
def test_slow_operation():
    pass
```

Run marked tests:
```bash
pytest -m unit          # Only unit tests
pytest -m integration   # Only integration tests
pytest -m "not slow"    # Exclude slow tests
```

## 🐛 Debugging Tests

### Verbose Output

```bash
# Show print statements
pytest tests/ -v -s

# Show local variables on failure
pytest tests/ -v -l

# Stop on first failure
pytest tests/ -v -x

# Show full traceback
pytest tests/ -v --tb=long
```

### Debugging Specific Tests

```bash
# Run single test with full output
pytest tests/test_cards.py::TestCardGeneration::test_generate_75_ball_card_structure -v -s

# Use pdb debugger
pytest tests/ --pdb

# Drop into pdb on first failure
pytest tests/ -x --pdb
```

### Log Output

```bash
# Show all log output
pytest tests/ --log-cli-level=DEBUG

# Show specific logger
pytest tests/ --log-cli-level=DEBUG --log-cli-format="%(name)s: %(message)s"
```

## 🔄 Continuous Integration

Tests run automatically on:
- Every push to any branch
- Every pull request
- Multiple Python versions (3.10, 3.11, 3.12, 3.13)

### GitHub Actions Workflows

1. **CI Workflow** (`.github/workflows/ci.yml`)
   - Runs on all branches and PRs
   - Non-blocking linting
   - Quick smoke tests

2. **Test Workflow** (`.github/workflows/test.yml`)
   - Runs on main and Dev branches
   - Matrix testing (Python 3.10-3.13)
   - Blocking linting
   - Coverage reports to Codecov
   - Integration tests with live server

## 🧰 Testing Tools

### Installed Testing Libraries

```
pytest>=7.4.0              # Test framework
pytest-cov>=4.1.0          # Coverage plugin
pytest-asyncio>=0.21.0     # Async test support
httpx>=0.24.0              # Async HTTP client for testing
requests>=2.31.0           # HTTP client for integration tests
```

### Linting Tools

```
black>=23.0.0              # Code formatter
flake8>=6.0.0              # Style guide enforcement
mypy>=1.4.0                # Static type checker
isort>=5.12.0              # Import sorter
yamllint>=1.26.0           # YAML linter
```

## 📝 Writing New Tests

### Test Structure

```python
class TestFeatureName:
    """Test feature description."""

    def test_specific_behavior(self):
        """Test that specific behavior works correctly."""
        # Arrange
        input_data = create_test_data()
        
        # Act
        result = function_under_test(input_data)
        
        # Assert
        assert result == expected_output
```

### Best Practices

1. **Use descriptive test names**
   - `test_generate_75_ball_card_structure` ✅
   - `test_card` ❌

2. **One assertion per test** (when possible)
   - Focus on testing one behavior
   - Makes failures easier to debug

3. **Use fixtures for setup**
   - Avoid repetitive setup code
   - Keep tests DRY (Don't Repeat Yourself)

4. **Test edge cases**
   - Empty inputs
   - Maximum values
   - Invalid inputs
   - Boundary conditions

5. **Mock external dependencies**
   - Don't rely on external services
   - Use `unittest.mock` or `pytest-mock`

6. **Keep tests fast**
   - Unit tests should run in milliseconds
   - Mark slow tests with `@pytest.mark.slow`

7. **Use environment variables**
   - Configure via `conftest.py`
   - Never hardcode sensitive data

## 🎯 Test Coverage Requirements

- **Minimum**: 85% overall coverage
- **Target**: 90%+ overall coverage
- **New code**: 95%+ coverage required
- **Critical paths**: 100% coverage (validation, game logic)

## 📚 Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [FastAPI testing guide](https://fastapi.tiangolo.com/tutorial/testing/)
- [Coverage.py documentation](https://coverage.readthedocs.io/)
- [Python testing best practices](https://docs.python-guide.org/writing/tests/)

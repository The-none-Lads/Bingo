# Bingo Game Application

A modern, real-time Bingo game application with a FastAPI backend and React frontend. Features live game updates via WebSockets, card generation, validation, and a casino-style display interface.

## 🎯 Overview

This application provides a complete Bingo game experience with:
- **Real-time gameplay** with WebSocket connections for live updates
- **Multiple game modes**: Progressive Rows, Full House, Four Corners, and Diagonals
- **Card generation and management** with unique IDs
- **Card validation** system with visual feedback
- **Admin dashboard** for game control
- **Casino-style display view** with animated ball draws
- **Print-ready card layouts** for physical gameplay
- **Automatic fallback to polling** when WebSocket connection is unavailable

## 🏗️ Tech Stack

### Backend
- **Python 3.13** - Core language (supports 3.10+)
- **FastAPI** - Modern async web framework
- **Uvicorn** - ASGI server with WebSocket support
- **Pydantic** - Data validation
- **pytest** - Testing framework with 90%+ coverage

### Frontend
- **React 19** - UI framework
- **Vite 7** - Build tool and dev server
- **Tailwind CSS 4** - Utility-first styling
- **Lucide React** - Icon library
- **Nginx** - Production web server

### DevOps
- **Docker** - Containerization
- **Docker Compose** - Local orchestration
- **Kubernetes** - Production orchestration with Ingress support
- **GitHub Actions** - CI/CD pipeline
- **GitHub Container Registry (GHCR)** - Image hosting

## 📋 Prerequisites

- **Docker** and **Docker Compose** (for containerized development)
- **Python 3.10+** (for local development without Docker)
- **Node.js 20+** and **npm** (for frontend development without Docker)
- **Kubernetes cluster** (for production deployment, optional)
- **kubectl** (for Kubernetes deployment, optional)

## 🚀 Quick Start

### Using Docker Compose (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/The-none-Lads/Bingo.git
   cd bingo
   ```

2. **Start the application**
   ```bash
   docker-compose up
   ```

3. **Access the application**
   - Frontend: http://localhost:80
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

<details>
<summary><strong>Local Development Setup (Click to expand)</strong></summary>

#### Backend

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Set required environment variables
export CORS_ORIGINS="http://localhost:3000,http://localhost:80"
export CORS_ALLOW_CREDENTIALS="true"

# Run the server
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

The frontend will be available at http://localhost:5173
</details>

## 🧪 Testing

The project includes comprehensive test coverage for the backend with multiple test suites.

<details>
<summary><strong>Quick Test Commands</strong></summary>

```bash
# Run all tests
make test

# Run with coverage report
make test-coverage

# Run unit tests only
make test-unit

# Run integration tests only
make test-integration

# Lint code
make lint

# Format code
make format
```
</details>

<details>
<summary><strong>Manual Testing</strong></summary>

```bash
# Run all tests with verbose output
cd backend
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=. --cov-report=html --cov-report=term-missing

# Run specific test file
pytest tests/test_cards.py -v

# Run specific test
pytest tests/test_cards.py::TestCardGeneration::test_generate_75_ball_card_structure -v
```
</details>

<details>
<summary><strong>Test Structure</strong></summary>

- `backend/tests/test_cards.py` - Card generation and serialization tests
- `backend/tests/test_draws.py` - Draw engine tests
- `backend/tests/test_modes.py` - Game mode validation tests
- `backend/tests/test_api.py` - API endpoint integration tests
- `backend/tests/test_security_hardening.py` - Input validation, admin authorization, draw concurrency/integrity, card isolation, and WebSocket security regression tests
- `backend/integration_tests/test_integration.py` - Full integration tests

**Current test coverage: 90%+**

For detailed testing documentation, see [backend/tests/README.md](backend/tests/README.md)
</details>

## 📦 Production Deployment

<details>
<summary><strong>Building Docker Images</strong></summary>

Images are automatically built and pushed to GHCR on version tags or the `dev` tag via GitHub Actions:

Pushing a `vMAJOR.MINOR.PATCH` version tag for a commit on `main` also merges the latest `main` into the `bingo.gameserver1.cc` deployment branch.

```bash
# Tag a new version
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0

# Or push to dev for rolling updates
git push origin dev
```

### Manual Docker Build

```bash
# Build backend
docker build -f backend/Dockerfile -t ghcr.io/the-none-lads/bingo-backend:latest .

# Build frontend
docker build -f frontend/Dockerfile -t ghcr.io/the-none-lads/bingo-frontend:latest .

# Push images (requires authentication)
docker push ghcr.io/the-none-lads/bingo-backend:latest
docker push ghcr.io/the-none-lads/bingo-frontend:latest
```
</details>

<details>
<summary><strong>Kubernetes Deployment</strong></summary>

#### Prerequisites

Since the Docker images are hosted privately on GHCR, you need to configure Kubernetes with authentication:

1. **Create a GitHub Personal Access Token**
   - Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
   - Generate new token with `read:packages` scope
   - Save the token securely

2. **Create Kubernetes Secret**
   ```bash
   kubectl create secret docker-registry ghcr-secret \
     --docker-server=ghcr.io \
     --docker-username=YOUR_GITHUB_USERNAME \
     --docker-password=YOUR_GITHUB_PAT \
     --docker-email=YOUR_EMAIL@example.com
   ```

3. **Deploy to Kubernetes**
   ```bash
   # Deploy backend
   kubectl apply -f kubernetes/backend-deployment.yaml
   kubectl apply -f kubernetes/backend-service.yaml

   # Deploy frontend
   kubectl apply -f kubernetes/frontend-deployment.yaml
   kubectl apply -f kubernetes/frontend-service.yaml

   # Optional: Deploy Ingress (configure your domain first)
   kubectl apply -f kubernetes/ingress.yaml
   ```

4. **Verify deployment**
   ```bash
   kubectl get pods
   kubectl get services
   kubectl logs -f deployment/backend
   kubectl logs -f deployment/frontend
   ```

5. **Access the application**
   
   For testing:
   ```bash
   # Port forward frontend
   kubectl port-forward service/frontend 3000:3000
   
   # Port forward backend
   kubectl port-forward service/backend 8000:8000
   ```
   
   For production: Configure the Ingress resource with your domain and SSL certificates.
</details>

<details>
<summary><strong>Environment Configuration</strong></summary>

The frontend supports runtime environment configuration via environment variables:

```bash
# Docker Compose
services:
  frontend:
    environment:
      - apiBaseUrl=http://localhost:8000
      - wsBaseUrl=ws://localhost:8000/ws
      - pollInterval=20000
      - cardFetchInterval=300000
      - gameIdDefault=demo
      - enableCelebration=true
      - confettiDuration=5000
```

See [frontend/README.md](frontend/README.md) for complete configuration options.
</details>

## 🎮 Usage

<details>
<summary><strong>Admin Dashboard</strong></summary>

1. Navigate to http://localhost:80 (or your deployed URL)
2. Click the **Settings** button to access the admin dashboard
3. Configure game settings:
   - Set a unique Game ID (stored in localStorage)
   - Choose game mode (Progressive Rows, Full House, Four Corners, Diagonals)
   - Generate cards for players (10, 50, 100, or custom count)
   - Draw numbers during gameplay
   - Set progressive stages (for Progressive Rows mode)
   - Validate winning cards
</details>

<details>
<summary><strong>Display View</strong></summary>

1. Click "Switch to Display View" from the admin dashboard
2. Full-screen casino-style interface shows:
   - Last called number with animated ball
   - Full 75-number bingo board with marked numbers
   - Game mode and progress information
   - Real-time updates via WebSocket (with polling fallback)
   - Connection status indicator
</details>

<details>
<summary><strong>Card Management</strong></summary>

- **Generate Cards**: Create batches of 10, 50, 100, or custom amounts
- **View Cards**: Click on any card to expand and see the full grid
- **Print Cards**: Use the "Print All" button to print all generated cards
- **Cards are persistent**: All cards are saved on the server and can be retrieved
</details>

<details>
<summary><strong>Card Validation</strong></summary>

1. Players receive printed cards with unique IDs (e.g., `A1B2C3D4`)
2. Enter the card ID in the validation section
3. System automatically checks if the card has won based on:
   - Current game mode
   - Numbers drawn
   - Progressive stage (if applicable)
4. Celebration animation displays for winners
</details>

## 🔌 API Endpoints

<details>
<summary><strong>Game Management</strong></summary>

- `POST /games/{game_id}/start` - Start a new game
  ```json
  {
    "mode": "progressive_rows",
    "ball_set": 75,
    "stage": 1
  }
  ```
- `POST /games/{game_id}/draw` - Draw a number
- `GET /games/{game_id}/state` - Get current game state
- `POST /games/{game_id}/stage/{stage}` - Set progressive stage
- `WS /ws/{game_id}` - WebSocket connection for real-time updates
</details>

<details>
<summary><strong>Card Operations</strong></summary>

- `POST /cards/batch` - Generate multiple cards
  ```json
  {
    "count": 50,
    "game_id": "demo",
    "persistent": false
  }
  ```
  `persistent` is optional and defaults to `false`. See [Card Persistence](#card-persistence) below for what it does.
- `GET /cards/{card_id}` - Retrieve a specific card (response includes `"persistent": true|false`)
- `GET /games/{game_id}/cards` - Get all cards for a game
</details>

<a id="card-persistence"></a>
<details>
<summary><strong>Card Persistence</strong></summary>

Generated cards can be **temporary** (the default) or **persistent**, decided per-request via the `persistent` field on `POST /cards/batch`:

- **Temporary cards** (`persistent` omitted or `false`) are kept in memory only. They're available for as long as the backend process runs and are cleared when it restarts. Existing clients that don't send `persistent` at all keep getting exactly this behavior — nothing changes for them.
- **Persistent cards** (`persistent: true`) are written to a small SQLite-backed store (see `CARD_DB_PATH` above) and survive a backend restart. A persistent card is a reusable artifact — like a physical bingo card — and can be validated in as many different game sessions as you like, not just the one it was generated alongside; it is never made single-use or auto-deleted after a win.

Both card types share the same ID scheme, collision protection, and `/validate`/`GET /cards/{id}` endpoints — callers don't need to know or care which store a given card lives in. Use temporary cards for one-off/high-volume generation (e.g. printing 500 disposable cards for tonight's game) and persistent cards when you want to generate a batch once and reuse it across many future games.

If persistent storage is requested but unavailable or at capacity, the request fails clearly (`409`/`503`) rather than silently falling back to temporary storage.
</details>

<details>
<summary><strong>Validation</strong></summary>

- `POST /validate` - Validate a card for winning
  ```json
  {
    "game_id": "demo",
    "serial": "A1B2C3D4"
  }
  ```
</details>

Full API documentation available at: http://localhost:8000/docs

## 🔄 CI/CD Pipeline

The project uses GitHub Actions for automated testing and deployment.

<details>
<summary><strong>Workflows Overview</strong></summary>

1. **CI** (`.github/workflows/ci.yml`)
   - Runs on all branches and pull requests
   - Executes Python and Node.js tests
   - Runs comprehensive linting (flake8, black, isort, mypy, eslint, stylelint, yamllint)
   - All linting is non-blocking (warnings only)

2. **Tests** (`.github/workflows/test.yml`)
   - Runs on main and Dev branches
   - Tests against Python 3.10, 3.11, 3.12, 3.13
   - Comprehensive linting suite (blocking)
   - Runs unit and integration tests
   - Generates coverage reports
   - Uploads results to Codecov

3. **Docker Release** (`.github/workflows/docker-release.yml`)
   - Triggers on version tags (e.g., `v1.0.0`) or `dev` tag
   - Builds and pushes backend and frontend images to GHCR
   - Tags images with version number and `latest` (for releases)
   - Rolling `dev` tag for development builds

4. **Game Server Branch Sync** (`.github/workflows/sync-main-to-gameserver.yml`)
   - On valid version tags, merges `main` into `bingo.gameserver1.cc` when the tagged commit is on `main`
</details>

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

<details>
<summary><strong>Getting Started</strong></summary>

1. **Fork the repository**

2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Follow the existing code style
   - Add tests for new features
   - Update documentation as needed
   - Ensure backend environment variables are set:
     ```bash
     export CORS_ORIGINS="http://localhost:3000"
     export CORS_ALLOW_CREDENTIALS="true"
     ```

4. **Run tests and linting**
   ```bash
   make test
   make lint
   make format
   ```

5. **Commit your changes**
   ```bash
   git commit -m "Add: your feature description"
   ```

6. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Open a Pull Request**
   - Use the provided PR template (`.github/github_pr_template.md`)
   - Link any related issues
   - Ensure all CI checks pass
</details>

<details>
<summary><strong>Development Guidelines</strong></summary>

- Follow PEP 8 for Python code
- Use ESLint rules for JavaScript/React code
- Write tests for new features (maintain 90%+ coverage)
- Update documentation for API changes
- Use meaningful commit messages
- Add type hints to Python functions
- Use environment variables for configuration (never hardcode)

### Code Style

- **Python**: Black formatter (88 char line length)
- **JavaScript**: ESLint with React hooks plugin
- **Imports**: isort for Python import sorting
- **Type Checking**: mypy for Python type checking
</details>

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.


## 🐛 Troubleshooting

<details>
<summary><strong>Common Issues</strong></summary>

**WebSocket connection fails**
- Ensure backend is running on port 8000
- Check CORS configuration in `backend/app.py` (requires `CORS_ORIGINS` environment variable)
- Verify firewall rules allow WebSocket connections
- Application will automatically fall back to polling if WebSocket fails

**Backend fails to start**
- Ensure `CORS_ORIGINS` environment variable is set
- Check that port 8000 is not already in use
- Verify Python dependencies are installed: `pip install -r backend/requirements.txt`

**Frontend can't connect to backend**
- Verify backend is running: `curl http://localhost:8000/docs`
- Check Vite proxy configuration in `frontend/vite.config.js`
- For production, verify environment variables in `config.js`

**Cards not generating**
- Confirm game has been started via `/games/{game_id}/start`
- Check backend logs for errors: `docker-compose logs backend`
- Verify CORS origins are configured correctly

**Docker build fails**
- Clear Docker cache: `docker system prune -a`
- Ensure sufficient disk space
- Check Dockerfile paths are correct
- Verify Node.js and Python versions match requirements

**Tests failing**
- Install dev dependencies: `pip install -r requirements-dev.txt`
- Ensure environment variables are set (handled by `conftest.py`)
- Clear pytest cache: `make clean`
- Run tests individually to isolate issues

**Kubernetes pods not starting**
- Verify `ghcr-secret` exists: `kubectl get secrets`
- Check image pull permissions with GitHub token
- Review pod logs: `kubectl logs -f deployment/backend`
- Ensure resource limits are appropriate for your cluster
</details>

## 🔧 Configuration

### Production bootstrap

For production, set `ENVIRONMENT=production`, configure `CORS_ORIGINS` to the exact public frontend origin(s), and provide a random `INITIAL_ADMIN_TOKEN` of at least 32 characters before starting the backend. Production has no open bootstrap access, rejects wildcard or missing CORS origins, and disables public registration by default. Create the first administrator once with `POST /auth/register` and the `X-Bootstrap-Token` header, then remove or rotate the bootstrap token. Set `ALLOW_REGISTRATION=true` only if ongoing public account creation is intended.

<details>
<summary><strong>Backend Environment Variables</strong></summary>

- `CORS_ORIGINS` - Comma-separated list of allowed origins (e.g., `"https://bingo.example.com"`). If unset, common localhost origins are used outside production. Production requires an explicit list and rejects `"*"`.
- `CORS_ALLOW_CREDENTIALS` - Allow credentials (default: `"true"`). Automatically forced to `false` if `CORS_ORIGINS` is `"*"`, since browsers reject a wildcard origin combined with credentials.
- `ADMIN_API_KEY` (or legacy `ADMIN_SECRET`) - Optional shared secret for privileged API access via `X-Admin-Key` or `Authorization: Bearer <key>`. Account sessions with an `OPERATOR` or `ADMIN` role also authorize these operations. Open bootstrap access is available only outside production when no key or accounts exist.
- `INITIAL_ADMIN_TOKEN` - In production, required as the `X-Bootstrap-Token` header when creating the first account. Keep it secret and remove/rotate it after creating the administrator.
- `ALLOW_REGISTRATION` - Enables new account registration after the first account exists. Defaults to `true` outside production and `false` in production.
- `ENVIRONMENT` - Set to `"production"` to disable `/docs`, `/redoc`, and `/openapi.json` by default, require explicit CORS origins, disable open bootstrap, and require the initial-admin token. Override docs exposure with `ENABLE_DOCS`.
- `CARD_DB_PATH` - Where the persistent card store's SQLite file lives (default: `data/cards.db`, relative to the backend's working directory; the Docker image mounts a volume at `/app/data`). Set to `:memory:` for a fully in-process, non-persistent store (used automatically by the test suite). Games (drawn numbers, mode, stage) always remain in-memory only. Cards are ephemeral by default (in-memory, cleared on restart) unless a generation request explicitly opts in with `"persistent": true` — see [Card Persistence](#card-persistence) below.
- `MAX_GAMES` - Maximum number of concurrent games kept in memory before the oldest is evicted (default: `100`).
- `MAX_MEMORY_CARDS` - Maximum number of ephemeral (non-persistent) cards kept in memory before the oldest is evicted (default: `25000`).
- `MAX_PERSISTENT_CARDS` - Maximum number of cards the persistent store will hold. Once reached, a request for a *new* persistent card is refused with a clear `409` error rather than evicting an already-saved card (default: `100000`).
</details>

<details>
<summary><strong>Frontend Configuration</strong></summary>

Runtime configuration via `config.js` (or container environment variables):
- `apiBaseUrl` / `API_BASE_URL` - Backend API URL (default: `"http://localhost:8000"`)
- `wsBaseUrl` - WebSocket URL (default: `"ws://localhost:8000/ws"`)
- `pollInterval` - Polling interval in ms (default: `20000`)
- `cardFetchInterval` - Card refresh interval in ms (default: `300000`)
- `gameIdDefault` - Default game ID (default: `"demo"`)
- `enableCelebration` - Enable confetti (default: `true`)
- `confettiDuration` - Celebration duration in ms (default: `5000`)

See [frontend/README.md](frontend/README.md) for complete configuration guide.
</details>


## 📞 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing issues for solutions
- Review API documentation at `/docs`
- Check the troubleshooting section

## 🙏 Acknowledgments

- Built with FastAPI, React, and modern web technologies
- Icon library by Lucide React
- Styled with Tailwind CSS
- WebSocket support with automatic polling fallback

---

**Note**: This application is designed for educational and entertainment purposes. Please ensure compliance with local gambling and gaming regulations when deploying.

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

## 🏗️ Tech Stack

### Backend
- **Python 3.13** - Core language
- **FastAPI** - Modern async web framework
- **Uvicorn** - ASGI server with WebSocket support
- **Pydantic** - Data validation
- **pytest** - Testing framework

### Frontend
- **React 19** - UI framework
- **Vite 7** - Build tool and dev server
- **Tailwind CSS 4** - Utility-first styling
- **Lucide React** - Icon library
- **Nginx** - Production web server

### DevOps
- **Docker** - Containerization
- **Docker Compose** - Local orchestration
- **Kubernetes** - Production orchestration
- **GitHub Actions** - CI/CD pipeline
- **GitHub Container Registry (GHCR)** - Image hosting

## 📋 Prerequisites

- **Docker** and **Docker Compose** (for local development)
- **Python 3.10+** (for local development without Docker)
- **Node.js 20+** (for frontend development without Docker)
- **Kubernetes cluster** (for production deployment)

## 🚀 Local Development

### Quick Start with Docker Compose

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
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Manual Development Setup

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

## 🧪 Testing

The project includes comprehensive test coverage for the backend:

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

### Test Structure
- `backend/tests/test_cards.py` - Card generation and serialization tests
- `backend/tests/test_draws.py` - Draw engine tests
- `backend/tests/test_modes.py` - Game mode validation tests
- `backend/tests/test_api.py` - API endpoint integration tests

## 📦 Production Deployment

### Building Docker Images

Images are automatically built and pushed to GHCR on version tags via GitHub Actions:

```bash
# Tag a new version
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

### Manual Docker Build

```bash
# Build backend
docker build -f backend/Dockerfile -t ghcr.io/the-none-lads/bingo-backend:latest .

# Build frontend
docker build -f frontend/Dockerfile -t ghcr.io/the-none-lads/bingo-frontend:latest .

# Push images
docker push ghcr.io/the-none-lads/bingo-backend:latest
docker push ghcr.io/the-none-lads/bingo-frontend:latest
```

### Kubernetes Deployment

1. **Update image references** in `kubernetes/*.yaml` files to match your registry

1.1 *Make sure that kubernetes can access the private ghcr.io repository*
    <details><summary><strong>Configuring Private Image Access</strong></summary>

    Since the Docker images are hosted privately on GitHub Container Registry (GHCR), you need to configure Kubernetes with authentication credentials before deploying.

    #### Step 1: Create a GitHub Personal Access Token

    1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
    2. Click "Generate new token (classic)"
    3. Give it a descriptive name (e.g., "Kubernetes GHCR Pull Token")
    4. Select the `read:packages` scope
    5. Generate the token and save it securely

    #### Step 2: Create Kubernetes Secret

    Create a Docker registry secret in your Kubernetes cluster with your GitHub credentials:

    ```bash
    kubectl create secret docker-registry ghcr-secret \
    --docker-server=ghcr.io \
    --docker-username=YOUR_GITHUB_USERNAME \
    --docker-password=YOUR_GITHUB_PAT \
    --docker-email=YOUR_EMAIL@example.com
    ```

    Replace:
    - `YOUR_GITHUB_USERNAME` with your GitHub username
    - `YOUR_GITHUB_PAT` with the Personal Access Token you created
    - `YOUR_EMAIL@example.com` with your email address

    **Note**: If you're deploying to a specific namespace, add the `-n NAMESPACE` flag to the command.

    #### Step 3: Update Deployment Files

    The deployment files have already been configured to use the `ghcr-secret`. Each deployment includes:

    ```yaml
    spec:
    template:
        spec:
        imagePullSecrets:
            - name: ghcr-secret
    ```

    This tells Kubernetes to use the secret when pulling images from GHCR.

    #### Step 4: Verify Secret Creation

    Confirm the secret was created successfully:

    ```bash
    kubectl get secrets
    kubectl describe secret ghcr-secret
    ```

    #### Alternative: Declarative Secret Creation

    For GitOps workflows or version control, you can create the secret declaratively:

    ```bash
    # Generate base64 encoded Docker config
    kubectl create secret docker-registry ghcr-secret \
    --docker-server=ghcr.io \
    --docker-username=YOUR_GITHUB_USERNAME \
    --docker-password=YOUR_GITHUB_PAT \
    --docker-email=YOUR_EMAIL@example.com \
    --dry-run=client -o yaml > kubernetes/ghcr-secret.yaml
    ```

    **Security Warning**: The generated `ghcr-secret.yaml` file contains your credentials in base64 encoding (which is NOT encryption). Never commit this file to version control. Add it to `.gitignore`:

    ```bash
    echo "kubernetes/ghcr-secret.yaml" >> .gitignore
    ```

    For production environments, consider using:
    - **Sealed Secrets** - Encrypt secrets for safe storage in Git
    - **External Secrets Operator** - Sync secrets from external secret managers (AWS Secrets Manager, HashiCorp Vault, etc.)
    - **Kubernetes service accounts** with GHCR authentication if using GitHub-hosted runners
    </details>

2. **Apply Kubernetes manifests**
   ```bash
   # Deploy backend
   kubectl apply -f kubernetes/backend-deployment.yaml
   kubectl apply -f kubernetes/backend-service.yaml

   # Deploy frontend
   kubectl apply -f kubernetes/frontend-deployment.yaml
   kubectl apply -f kubernetes/frontend-service.yaml
   ```

3. **Verify deployment**
   ```bash
   kubectl get pods
   kubectl get services
   ```

4. **Access the application**
   - Use port-forwarding for testing:
     ```bash
     kubectl port-forward service/frontend 3000:3000
     kubectl port-forward service/backend 8000:8000
     ```
   - Or configure an Ingress for production access

## 🎮 Usage

### Admin Dashboard

1. Navigate to http://localhost:3000
2. Click the **Settings** button to access the admin dashboard
3. Configure game settings:
   - Set a unique Game ID
   - Choose game mode (Progressive Rows, Full House, etc.)
   - Generate cards for players
   - Draw numbers during gameplay
   - Validate winning cards

### Display View

1. Click "Switch to Display View" from the admin dashboard
2. Full-screen casino-style interface shows:
   - Last called number with animated ball
   - Full bingo board with marked numbers
   - Game mode and progress information
   - Real-time updates via WebSocket

### Card Validation

1. Players receive printed cards with unique IDs (e.g., `A1B2C3D4`)
2. Enter the card ID in the validation section
3. System automatically checks if the card has won
4. Celebration animation displays for winners

## 🔌 API Endpoints

### Game Management
- `POST /games/{game_id}/start` - Start a new game
- `POST /games/{game_id}/draw` - Draw a number
- `GET /games/{game_id}/state` - Get current game state
- `POST /games/{game_id}/stage/{stage}` - Set progressive stage
- `WS /ws/{game_id}` - WebSocket connection for real-time updates

### Card Operations
- `POST /cards/batch` - Generate multiple cards
- `GET /cards/{card_id}` - Retrieve a specific card

### Validation
- `POST /validate` - Validate a card for winning

Full API documentation available at: http://localhost:8000/docs

## 🔄 CI/CD Pipeline

The project uses GitHub Actions for automated testing and deployment:

### Workflows

1. **CI** (`.github/workflows/ci.yml`)
   - Runs on all branches and pull requests
   - Executes Python and Node.js tests
   - Validates code quality

2. **Tests** (`.github/workflows/test.yml`)
   - Runs on main and develop branches
   - Tests against Python 3.10, 3.11, 3.12, 3.13
   - Runs linters (flake8, black, isort, mypy)
   - Generates coverage reports
   - Uploads results to Codecov

3. **Docker Release** (`.github/workflows/docker-release.yml`)
   - Triggers on version tags (e.g., `v1.0.0`)
   - Builds and pushes backend and frontend images to GHCR
   - Images tagged with the git tag name

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Follow the existing code style
   - Add tests for new features
   - Update documentation as needed

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
   - Use the provided PR template
   - Link any related issues
   - Ensure all CI checks pass

### Development Guidelines

- Follow PEP 8 for Python code
- Use ESLint rules for JavaScript/React code
- Write tests for new features
- Maintain test coverage above 90%
- Update documentation for API changes
- Use meaningful commit messages

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 🐛 Troubleshooting

### Common Issues

**WebSocket connection fails**
- Ensure backend is running on port 8000
- Check CORS configuration in `backend/app.py`
- Verify firewall rules allow WebSocket connections

**Cards not generating**
- Confirm game has been started via `/games/{game_id}/start`
- Check backend logs for errors
- Verify database connection (if using persistent storage)

**Docker build fails**
- Clear Docker cache: `docker system prune -a`
- Ensure sufficient disk space
- Check Dockerfile paths are correct

**Tests failing**
- Install dev dependencies: `pip install -r requirements-dev.txt`
- Clear pytest cache: `make clean`
- Run tests individually to isolate issues

## 📞 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing issues for solutions
- Review API documentation at `/docs`

## 🙏 Acknowledgments

- Built with FastAPI, React, and modern web technologies
- Icon library by Lucide React
- Styled with Tailwind CSS

---

**Note**: This application is designed for educational and entertainment purposes. Please ensure compliance with local gambling and gaming regulations when deploying.
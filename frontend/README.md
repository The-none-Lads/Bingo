# Bingo Frontend

A modern React-based frontend for the Bingo game application with real-time updates, casino-style display, and comprehensive admin controls.

## 🎨 Features

- **Real-time Updates** - WebSocket connection with automatic fallback to polling
- **Casino-Style Display** - Full-screen display view with animated ball draws
- **Admin Dashboard** - Complete game control interface
- **Card Management** - Generate, view, and print bingo cards
- **Card Validation** - Real-time winner validation with celebrations
- **Responsive Design** - Works on desktop, tablet, and mobile
- **Print Support** - Print-ready card layouts
- **Connection Status** - Visual indicator for WebSocket/polling status

## 🛠️ Tech Stack

- **React 19.1.1** - Latest React with modern hooks
- **Vite 7.1.7** - Lightning-fast build tool and dev server
- **Tailwind CSS 4.1.16** - Utility-first CSS framework
- **Lucide React 0.548.0** - Beautiful icon library
- **Native WebSocket API** - Real-time communication
- **Nginx** - Production web server

## 📋 Prerequisites

- **Node.js 20+** and **npm**
- **Backend API** running (see main README)

## 🚀 Quick Start

<details>
<summary><strong>Development Setup</strong></summary>

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The application will be available at http://localhost:5173
</details>

<details>
<summary><strong>Production Build</strong></summary>

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```
</details>

## 🎮 Application Views

<details>
<summary><strong>Display View (Default)</strong></summary>

Full-screen casino-style interface featuring:
- Large animated ball display for last called number
- Complete 75-number bingo board
- Color-coded balls by letter (B, I, N, G, O)
- Game mode and progress information
- Real-time connection status indicator
- Winner celebration with confetti animation

**Keyboard Shortcuts:**
- Click Settings icon to switch to Admin view
</details>

<details>
<summary><strong>Admin Dashboard</strong></summary>

Comprehensive control interface with:

**Game Controls:**
- Game ID management (persisted in localStorage)
- Quick start buttons for all game modes:
  - Progressive Rows
  - Full House
  - Four Corners
  - Diagonals
- Draw number button
- Progressive stage selector (1-5 rows)
- Last drawn number display

**Card Generation:**
- Quick generate buttons (10, 50, 100 cards)
- Custom count generator
- Expandable card viewer
- Print all cards button
- Individual card display with grid
- Cards automatically saved on server

**Card Validation:**
- Enter card ID to validate
- Real-time win detection
- Visual feedback (green for winner, red for not yet)
- Card grid display with marked numbers
- Celebration animation for winners

**Game Status:**
- Numbers drawn counter
- Current game mode
- Progressive stage (if applicable)
- Active game status
</details>

## 🔧 Configuration

The frontend uses runtime configuration loaded from `config.js`, allowing environment-specific settings without rebuilding.

<details>
<summary><strong>Configuration Options</strong></summary>

Create or modify `public/config.js`:

```javascript
window.__CONFIG__ = {
  apiBaseUrl: "/",                          // Backend API base URL
  wsBaseUrl: "ws://localhost:8000/ws",      // WebSocket URL
  pollInterval: "20000",                    // Polling interval (ms)
  cardFetchInterval: "300000",              // Card refresh interval (ms)
  gameIdDefault: "demo",                    // Default game ID
  enableCelebration: "true",                // Enable confetti
  confettiDuration: "5000"                  // Celebration duration (ms)
};
```
</details>

<details>
<summary><strong>Environment Variables (Development)</strong></summary>

For development, create `.env.development`:

```bash
API_BASE_URL=/
WS_BASE_URL=/ws
POLL_INTERVAL=5000
CARD_FETCH_INTERVAL=60000
GAME_ID_DEFAULT=demo
ENABLE_CELEBRATION=true
CONFETTI_DURATION=5000
```
</details>

<details>
<summary><strong>Docker Configuration</strong></summary>

When using Docker, pass environment variables:

```yaml
services:
  frontend:
    environment:
      - apiBaseUrl=http://backend:8000
      - wsBaseUrl=ws://backend:8000/ws
      - pollInterval=20000
      - cardFetchInterval=300000
      - gameIdDefault=demo
      - enableCelebration=true
      - confettiDuration=5000
```

The `entrypoint.sh` script processes `config.template.js` with these variables at container startup.
</details>

## 🏗️ Project Structure

```
frontend/
├── public/
│   ├── config.js              # Runtime configuration (production)
│   ├── config.template.js     # Template for Docker env substitution
│   └── vite.svg               # Favicon
├── src/
│   ├── App.jsx                # Root component
│   ├── BingoApp.jsx           # Main application component
│   ├── config.js              # Configuration loader
│   ├── index.css              # Global styles and print CSS
│   └── main.jsx               # Application entry point
├── .env.development           # Development environment config
├── Dockerfile                 # Multi-stage Docker build
├── entrypoint.sh              # Docker entrypoint for config
├── eslint.config.js           # ESLint configuration
├── index.html                 # HTML template
├── package.json               # Dependencies and scripts
├── postcss.config.js          # PostCSS configuration
├── tailwind.config.js         # Tailwind CSS configuration
└── vite.config.js             # Vite configuration
```

## 🎨 Components Overview

### BingoApp.jsx

Main application component managing:
- View state (display vs admin)
- WebSocket connections with fallback
- Game state management
- Card generation and storage
- Real-time updates
- Celebration animations

**Key Functions:**
- `startGame()` - Initialize new game
- `drawNumber()` - Draw next number
- `generateCards()` - Batch card generation
- `validateCard()` - Check for winners
- `setStage()` - Set progressive stage
- `launchConfetti()` - Winner celebration

### BingoBall Component

Reusable ball component with:
- Size variants (small, medium, large, xlarge)
- Color coding by letter (B=red, I=blue, N=yellow, G=green, O=purple)
- Animation support
- Letter and number display

## 🎯 Key Features Explained

<details>
<summary><strong>Real-time Updates</strong></summary>

The application uses a hybrid approach:

1. **Primary: WebSocket Connection**
   - Connects to `ws://{backend}/ws/{gameId}`
   - Receives instant state updates
   - Shows "Live" status indicator

2. **Fallback: HTTP Polling**
   - Activates when WebSocket disconnects
   - Polls every 20 seconds (configurable)
   - Shows "Polling" status indicator
   - Automatically attempts WebSocket reconnection

3. **Smart Update Logic**
   - Prevents duplicate updates
   - Throttles polling updates when WebSocket is active
   - Maintains last update timestamp
</details>

<details>
<summary><strong>Card Persistence</strong></summary>

Cards are stored on the server and automatically refreshed:
- On page load
- Every 5 minutes (configurable)
- After generating new cards
- Can be retrieved anytime via game ID
</details>

<details>
<summary><strong>Game ID Management</strong></summary>

- Stored in localStorage for persistence
- Can be changed in admin view
- Survives page refreshes
- Defaults to "demo" if not set
</details>

<details>
<summary><strong>Print Functionality</strong></summary>

Special print styles activated via `@media print`:
- Only print-area is visible
- 2-column grid layout
- Page break avoidance
- High-quality card rendering
</details>

## 🧪 Testing

Automated unit tests cover the pure ball-history state logic (`src/ballHistory.js`), run via Node's built-in test runner (no extra dependency):

```bash
npm test
```

This exercises `deriveBallState`/`getBallTransition` against the documented scenarios: single draws, the 7-draw progression where history caps at 5, initial-state hydration (no replaying old draws as animations), and game reset. See `src/__tests__/ballHistory.test.js`.

Beyond that, manual testing is still the primary way to verify the full UI/animation experience end-to-end:

<details>
<summary><strong>Manual Testing Checklist</strong></summary>

- [ ] WebSocket connection establishes
- [ ] Fallback to polling when WebSocket fails
- [ ] Game starts in all modes
- [ ] Numbers draw correctly
- [ ] New draw animates: current ball rolls into history, oldest ball drops off past 5
- [ ] Reloading mid-game hydrates current/history instantly without replaying past draws
- [ ] Cards generate (10, 50, 100, custom)
- [ ] Card validation works
- [ ] Winners trigger celebration
- [ ] Print functionality works
- [ ] Display view shows updates
- [ ] Admin view controls work
- [ ] Admin Key field is sent as `X-Admin-Key` when the backend has `ADMIN_API_KEY` configured
- [ ] Game ID persists in localStorage
</details>

<details>
<summary><strong>Linting</strong></summary>

```bash
# Run ESLint
npm run lint

# Run Stylelint
npx stylelint "src/**/*.css"

# Run HTMLHint
npx htmlhint "**/*.html"
```
</details>

## 📦 Building for Production

<details>
<summary><strong>Standard Build</strong></summary>

```bash
npm run build
```

Output in `dist/` directory.
</details>

<details>
<summary><strong>Docker Build</strong></summary>

```bash
# Build image
docker build -f Dockerfile -t bingo-frontend:latest .

# Run container
docker run -p 80:80 \
  -e apiBaseUrl=http://backend:8000 \
  -e wsBaseUrl=ws://backend:8000/ws \
  bingo-frontend:latest
```
</details>

<details>
<summary><strong>Multi-stage Build Process</strong></summary>

1. **Build Stage** (Node.js 25-alpine)
   - Install dependencies
   - Build production bundle
   - Optimize assets

2. **Serve Stage** (Nginx Alpine)
   - Copy built files
   - Configure Nginx
   - Set up entrypoint for config
</details>

## 🚀 Deployment

<details>
<summary><strong>Nginx Configuration</strong></summary>

Default Nginx serves from `/usr/share/nginx/html`:
- Single Page Application (SPA) support
- All routes serve `index.html`
- Static asset caching
</details>

<details>
<summary><strong>Environment-Specific Builds</strong></summary>

The frontend uses runtime configuration, so one build works for all environments:

```bash
# Build once
docker build -t bingo-frontend:v1.0.0 .

# Deploy to dev
docker run -e apiBaseUrl=http://dev-api:8000 ...

# Deploy to prod
docker run -e apiBaseUrl=http://api.production.com ...
```
</details>

## 🎨 Styling

<details>
<summary><strong>Tailwind CSS 4</strong></summary>

Modern utility-first CSS with:
- JIT compilation
- Custom color schemes
- Responsive design utilities
- Print-specific styles
</details>

<details>
<summary><strong>Custom Styles</strong></summary>

Print styles in `src/index.css`:
```css
@media print {
  body * { visibility: hidden; }
  #print-area, #print-area * { visibility: visible; }
  /* ... */
}
```
</details>

<details>
<summary><strong>Color Scheme</strong></summary>

**Bingo Ball Colors:**
- B (1-15): Red (`bg-red-500`)
- I (16-30): Blue (`bg-blue-500`)
- N (31-45): Yellow (`bg-yellow-500`)
- G (46-60): Green (`bg-green-500`)
- O (61-75): Purple (`bg-purple-500`)
</details>

## 🔍 Troubleshooting

<details>
<summary><strong>Development Issues</strong></summary>

**Port already in use:**
```bash
# Kill process on port 5173
lsof -ti:5173 | xargs kill -9

# Or use different port
npm run dev -- --port 3001
```

**Dependencies not installing:**
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

**HMR not working:**
- Check Vite configuration
- Ensure file watching is enabled
- Try restarting dev server
</details>

<details>
<summary><strong>Production Issues</strong></summary>

**Config not loading:**
- Verify `config.js` exists in production build
- Check `entrypoint.sh` has execute permissions
- Verify environment variables are passed to container

**WebSocket connection fails:**
- Check `wsBaseUrl` configuration
- Verify backend allows WebSocket upgrades
- Check CORS configuration on backend

**API requests fail:**
- Verify `apiBaseUrl` is correct
- Check network connectivity
- Review browser console for CORS errors
</details>

## 📚 Dependencies

<details>
<summary><strong>Production Dependencies</strong></summary>

```json
{
  "react": "^19.1.1",
  "react-dom": "^19.1.1",
  "lucide-react": "^0.548.0",
  "tailwindcss": "^4.1.16",
  "@tailwindcss/vite": "^4.1.16",
  "@tailwindcss/postcss": "^4.1.17",
  "autoprefixer": "^10.4.22",
  "cssnano": "^7.1.2",
  "vite": "^7.1.7"
}
```
</details>

<details>
<summary><strong>Development Dependencies</strong></summary>

```json
{
  "@eslint/js": "^9.36.0",
  "@types/react": "^19.1.16",
  "@types/react-dom": "^19.1.9",
  "@vitejs/plugin-react": "^5.0.4",
  "eslint": "^9.36.0",
  "eslint-plugin-react-hooks": "^5.2.0",
  "eslint-plugin-react-refresh": "^0.4.22",
  "globals": "^16.4.0",
  "stylelint": "^16.25.0",
  "stylelint-config-standard": "^39.0.1"
}
```
</details>

## 🤝 Contributing

See main README for contribution guidelines.

<details>
<summary><strong>Frontend-Specific Guidelines</strong></summary>

- Use functional components with hooks
- Follow ESLint configuration
- Keep components small and focused
- Use Tailwind utilities (avoid custom CSS)
- Document complex logic
- Use environment variables for configuration
</details>

## 📄 License

Apache License 2.0 - See LICENSE file in project root.

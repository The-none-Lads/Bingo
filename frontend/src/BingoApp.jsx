import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Play, CheckCircle2, Settings, Printer, Crown, User, Shield, ExternalLink, Users, Lock, Globe } from 'lucide-react';
import { AuthModal } from './AuthModal';
import { AdminDashboard } from './AdminDashboard';
import { PlayerView } from './PlayerView';
import { config } from './config';
import { getBallTransition } from './ballHistory';

// Helper function to get letter and color for a number
const getBingoLetter = (num) => {
  if (num >= 1 && num <= 15) return { letter: 'B', color: 'bg-red-500' };
  if (num >= 16 && num <= 30) return { letter: 'I', color: 'bg-blue-500' };
  if (num >= 31 && num <= 45) return { letter: 'N', color: 'bg-yellow-500' };
  if (num >= 46 && num <= 60) return { letter: 'G', color: 'bg-green-500' };
  if (num >= 61 && num <= 75) return { letter: 'O', color: 'bg-purple-500' };
  return { letter: '', color: 'bg-gray-500' };
};

// Reusable Bingo Ball Component
const BingoBall = ({ number, isAnimating = false, size = 'large' }) => {
  const { letter, color } = getBingoLetter(number);

  const sizeClasses = {
    small: 'w-12 h-12 text-sm',
    medium: 'w-20 h-20 text-xl',
    large: 'w-32 h-32 text-4xl',
    xlarge: 'w-44 h-44 text-6xl'
  };
  const letterSizeClasses = {
    small: 'text-xs',
    medium: 'text-base',
    large: 'text-2xl',
    xlarge: 'text-4xl'
  };

  return (
    <div
      className={`${sizeClasses[size]} ${color} rounded-full flex flex-col items-center justify-center text-white font-bold shadow-2xl border-4 border-white/30 transition-transform ${
        isAnimating ? 'animate-ballPop' : ''
      }`}
      style={{
        boxShadow:
          '0 20px 40px rgba(0,0,0,0.4), inset 0 -10px 20px rgba(0,0,0,0.3), inset 0 10px 20px rgba(255,255,255,0.3)'
      }}
    >
      <div
        className={`${letterSizeClasses[size]} opacity-90 font-serif leading-none`}
        style={{ fontFamily: '"Georgia", "Times New Roman", serif' }}
      >
        {letter}
      </div>
      <div className="leading-none mt-1">{number}</div>
    </div>
  );
};

const BingoApp = () => {
  const [view, setView] = useState('display');
  const [gameId, setGameId] = useState(() => localStorage.getItem('bingo_game_id') || config.gameIdDefault || 'demo');
  const [gameState, setGameState] = useState(null);
  const [validationResult, setValidationResult] = useState(null);
  const [cardToValidate, setCardToValidate] = useState('');
  const [generatedCards, setGeneratedCards] = useState([]);
  const [celebrating, setCelebrating] = useState(false);
  const [customCount, setCustomCount] = useState(10);
  // Off by default: generated cards are ephemeral (in-memory) unless
  // the operator explicitly opts into persistent storage per batch.
  const [storePermanently, setStorePermanently] = useState(false);
  const [lastBatchWasPersistent, setLastBatchWasPersistent] = useState(false);
  const [openCard, setOpenCard] = useState(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [showAllDrawn, setShowAllDrawn] = useState(false);
  const [playerLinks, setPlayerLinks] = useState([]);
  const [playerViewToken, setPlayerViewToken] = useState(null);

  // Authentication & Access Control State
  const [currentUser, setCurrentUser] = useState(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [isPrivateGame, setIsPrivateGame] = useState(false);

  // Admin credential (never sent by the public display view; only used for
  // the privileged start/draw/stage/cards-batch/cards-list requests). This
  // is stored client-side only and is opt-in: if the backend has no
  // ADMIN_API_KEY configured, an empty value here is simply ignored.
  const [adminKey, setAdminKey] = useState(() => localStorage.getItem('bingo_admin_key') || '');

  // Authoritative Ball History State
  const [currentBall, setCurrentBall] = useState(null);
  const [historyBalls, setHistoryBalls] = useState([]);
  const [animatingBall, setAnimatingBall] = useState(null);
  const [droppingBall, setDroppingBall] = useState(null);
  const [isNewDrawAnimating, setIsNewDrawAnimating] = useState(false);

  // References for lifecycle and socket management
  const prevDrawnRef = useRef([]);
  const animationTimerRef = useRef(null);
  const confettiAnimIdRef = useRef(null);
  const confettiTimeoutRef = useRef(null);
  const confettiRef = useRef(null);
  const wsRef = useRef(null);
  const lastUpdateRef = useRef(0);
  const pollIntervalRef = useRef(null);
  const cardIntervalRef = useRef(null);

  const API_BASE = config.apiBaseUrl;
  const WS_BASE = config.wsBaseUrl;
  const POLL_INTERVAL = config.pollInterval;
  const CARD_FETCH_INTERVAL = config.cardFetchInterval;

  // Fetch current authenticated user on load
  const fetchCurrentUser = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        credentials: 'include'
      });
      if (res.ok) {
        const data = await res.json();
        setCurrentUser(data);
      } else {
        setCurrentUser(null);
      }
    } catch {
      setCurrentUser(null);
    }
  }, [API_BASE]);

  useEffect(() => {
    fetchCurrentUser();
  }, [fetchCurrentUser]);

  // Detect URL parameters for player token or view routing
  useEffect(() => {
    try {
      const pathname = window.location.pathname;
      const searchParams = new URLSearchParams(window.location.search);
      const tokenParam = searchParams.get('token');
      const gameParam = searchParams.get('game');
      const viewParam = searchParams.get('view');

      if (gameParam) {
        setGameId(gameParam);
      }

      if (pathname.startsWith('/b/')) {
        const pathToken = pathname.replace(/^\/b\//, '').split('/')[0].split('?')[0];
        if (pathToken) {
          setPlayerViewToken(pathToken);
          setView('player');
          return;
        }
      }

      if (tokenParam) {
        setPlayerViewToken(tokenParam);
        setView('player');
        return;
      }

      if (viewParam && ['display', 'admin', 'system-admin', 'player'].includes(viewParam)) {
        setView(viewParam);
      }
    } catch (e) {
      console.error('Failed to parse URL routing:', e);
    }
  }, []);

  const handleLogout = async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        headers: {
          'X-Requested-With': 'XMLHttpRequest'
        },
        credentials: 'include'
      });
      if (res.ok) {
        setCurrentUser(null);
        setIsAuthModalOpen(false);
        setTimeout(fetchGameState, 50);
      }
    } catch (err) {
      console.error('Logout error:', err);
    }
  };

  // Persist the admin key locally, mirroring the existing gameId pattern.
  useEffect(() => {
    localStorage.setItem('bingo_admin_key', adminKey);
  }, [adminKey]);

  // Header(s) to attach to requests that may require admin authorization.
  // Sending an empty/absent header is harmless: the backend only enforces
  // it when ADMIN_API_KEY is configured server-side.
  const adminHeaders = useCallback(
    () => (adminKey ? { 'X-Admin-Key': adminKey } : {}),
    [adminKey]
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (animationTimerRef.current) clearTimeout(animationTimerRef.current);
      if (confettiAnimIdRef.current) cancelAnimationFrame(confettiAnimIdRef.current);
      if (confettiTimeoutRef.current) clearTimeout(confettiTimeoutRef.current);
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
      if (cardIntervalRef.current) clearInterval(cardIntervalRef.current);
    };
  }, []);

  // Function to fetch all cards for the current game
  const fetchCardsForGame = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/cards`, {
        headers: adminHeaders(),
        credentials: 'include'
      });
      if (response.ok) {
        const data = await response.json();
        if (data.cards && data.cards.length > 0) {
          setGeneratedCards(data.cards);
        }
      }
    } catch (err) {
      console.error('Failed to fetch cards:', err);
    }
  }, [gameId, API_BASE, adminHeaders]);

  // Pure state update based on server game state
  const updateGameState = useCallback((data, source = 'unknown') => {
    if (!data) return;

    const currentDrawn = data.drawn || [];
    const transition = getBallTransition(prevDrawnRef.current, currentDrawn);

    if (transition.type === 'hydrate') {
      setCurrentBall(transition.current);
      setHistoryBalls(transition.history);
      setAnimatingBall(null);
      setDroppingBall(null);
      setIsNewDrawAnimating(false);
    } else if (transition.type === 'draw') {
      if (animationTimerRef.current) {
        clearTimeout(animationTimerRef.current);
      }

      // Show new main ball with pop effect
      setCurrentBall(transition.current);
      setIsNewDrawAnimating(true);

      // Roll old current into history position 0
      setAnimatingBall(transition.oldCurrent);
      if (transition.droppingBall !== null) {
        setDroppingBall(transition.droppingBall);
      }

      // Settle visual history after animation completes (750ms)
      animationTimerRef.current = setTimeout(() => {
        setHistoryBalls(transition.history);
        setAnimatingBall(null);
        setDroppingBall(null);
        setIsNewDrawAnimating(false);
      }, 750);
    } else if (transition.type === 'reset') {
      if (animationTimerRef.current) {
        clearTimeout(animationTimerRef.current);
      }
      setCurrentBall(null);
      setHistoryBalls([]);
      setAnimatingBall(null);
      setDroppingBall(null);
      setIsNewDrawAnimating(false);
    }

    prevDrawnRef.current = currentDrawn;
    setGameState(data);
    if (source === 'websocket') {
      lastUpdateRef.current = Date.now();
    }
  }, []);

  // Function to fetch game state
  const fetchGameState = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/state`, {
        headers: adminHeaders(),
        credentials: 'include'
      });
      if (response.status === 401 || response.status === 403) {
        setIsPrivateGame(true);
        setGameState(null);
        return;
      }
      if (response.ok) {
        setIsPrivateGame(false);
        const data = await response.json();
        const now = Date.now();
        if (!wsConnected || now - lastUpdateRef.current > 1000) {
          updateGameState(data, 'poll');
        }
      } else if (response.status === 404) {
        setIsPrivateGame(false);
      }
    } catch (err) {
      console.error('Failed to fetch game state:', err);
    }
  }, [gameId, wsConnected, updateGameState, API_BASE, adminHeaders]);

  // Refresh game state whenever current user changes (e.g. login/logout)
  useEffect(() => {
    fetchGameState();
  }, [currentUser, fetchGameState]);

  const fetchPlayerLinks = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/games/${gameId}/links`, {
        headers: adminHeaders(),
        credentials: 'include'
      });
      if (res.ok) {
        const data = await res.json();
        setPlayerLinks(data.links.map(l => ({ ...l, token: null })));
      }
    } catch (err) {
      console.error('Failed to fetch links:', err);
    }
  }, [gameId, API_BASE, adminHeaders]);

  // Handle Game ID change
  useEffect(() => {
    localStorage.setItem('bingo_game_id', gameId);
    prevDrawnRef.current = [];
    setCurrentBall(null);
    setHistoryBalls([]);
    setAnimatingBall(null);
    setDroppingBall(null);
    fetchCardsForGame();
    fetchGameState();
    // Load existing player links for this game
    fetchPlayerLinks();
  }, [gameId, fetchCardsForGame, fetchGameState, fetchPlayerLinks]);

  // Confetti Animation with safe cleanup
  const launchConfetti = useCallback(() => {
    if (!config.enableCelebration) return;

    const canvas = confettiRef.current;
    if (!canvas) return;

    if (confettiAnimIdRef.current) {
      cancelAnimationFrame(confettiAnimIdRef.current);
    }
    if (confettiTimeoutRef.current) {
      clearTimeout(confettiTimeoutRef.current);
    }

    const ctx = canvas.getContext('2d');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    const pieces = Array.from({ length: 150 }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height - canvas.height,
      size: Math.random() * 8 + 4,
      color: `hsl(${Math.random() * 360}, 100%, 50%)`,
      speed: Math.random() * 4 + 2,
      rotation: Math.random() * 360,
      rotationSpeed: Math.random() * 6 - 3
    }));

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      pieces.forEach((p) => {
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate((p.rotation * Math.PI) / 180);
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size);
        ctx.restore();

        p.y += p.speed;
        p.rotation += p.rotationSpeed;
        if (p.y > canvas.height) {
          p.y = -10;
          p.x = Math.random() * canvas.width;
        }
      });
      confettiAnimIdRef.current = requestAnimationFrame(draw);
    };

    draw();
    confettiTimeoutRef.current = setTimeout(() => {
      if (confettiAnimIdRef.current) {
        cancelAnimationFrame(confettiAnimIdRef.current);
        confettiAnimIdRef.current = null;
      }
      if (canvas && ctx) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
    }, config.confettiDuration || 5000);
  }, []);

  // WebSocket connection lifecycle
  useEffect(() => {
    const wsUrl = adminKey ? `${WS_BASE}/${gameId}?token=${encodeURIComponent(adminKey)}` : `${WS_BASE}/${gameId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
    };

    ws.onclose = () => {
      setWsConnected(false);
    };

    ws.onerror = () => {
      setWsConnected(false);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data && data.type === 'state_update' && data.state) {
          updateGameState(data.state, 'websocket');
        }

        if (data && data.type === 'celebration') {
          setCelebrating(true);
          launchConfetti();
          setTimeout(() => setCelebrating(false), config.confettiDuration || 5000);
        }
      } catch (err) {
        console.error('WebSocket message parse error:', err);
      }
    };

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [gameId, WS_BASE, adminKey, updateGameState, launchConfetti]);

  // Polling as fallback when WebSocket is inactive
  useEffect(() => {
    if (wsConnected) return;

    pollIntervalRef.current = setInterval(async () => {
      await fetchGameState();

      // Check if WebSocket is closed and attempt reconnect (skip if known private and unauthenticated)
      if ((!isPrivateGame || currentUser || adminKey) && (!wsRef.current || wsRef.current.readyState === WebSocket.CLOSED)) {
        const wsUrl = adminKey ? `${config.wsBaseUrl}/${gameId}?token=${encodeURIComponent(adminKey)}` : `${config.wsBaseUrl}/${gameId}`;
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => setWsConnected(true);
        ws.onclose = () => setWsConnected(false);
        ws.onerror = () => setWsConnected(false);
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data?.type === 'state_update' && data.state) {
              updateGameState(data.state, 'websocket');
            }
            if (data?.type === 'celebration') {
              setCelebrating(true);
              launchConfetti();
              setTimeout(() => setCelebrating(false), config.confettiDuration || 5000);
            }
          } catch (err) {
            console.error('WebSocket message parse error:', err);
          }
        };
      }
    }, POLL_INTERVAL);

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [gameId, wsConnected, isPrivateGame, currentUser, adminKey, fetchGameState, updateGameState, POLL_INTERVAL, launchConfetti]);

  // Periodic card fetch
  useEffect(() => {
    cardIntervalRef.current = setInterval(() => {
      fetchCardsForGame();
    }, CARD_FETCH_INTERVAL);

    return () => {
      if (cardIntervalRef.current) {
        clearInterval(cardIntervalRef.current);
      }
    };
  }, [fetchCardsForGame, CARD_FETCH_INTERVAL]);

  const handleAuthSuccess = (user) => {
    setCurrentUser(user);
    setIsAuthModalOpen(false);
    setTimeout(fetchGameState, 50);
  };

  const updateAccessPolicy = async (newPolicy) => {
    try {
      const res = await fetch(`${API_BASE}/games/${gameId}/access-policy`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...adminHeaders() },
        credentials: 'include',
        body: JSON.stringify({ policy: newPolicy })
      });
      if (res.ok) {
        setGameState(prev => prev ? { ...prev, access_policy: newPolicy } : prev);
        setIsPrivateGame(newPolicy !== 'PUBLIC');
      } else {
        const err = await res.json();
        console.error('Failed to update access policy:', err);
      }
    } catch (err) {
      console.error('Failed to update access policy:', err);
    }
  };

  const startGame = async (mode = 'progressive_rows', stage = 1) => {
    try {
      const currentPolicy = gameState?.access_policy || 'LINK_ONLY';
      await fetch(`${API_BASE}/games/${gameId}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...adminHeaders() },
        credentials: 'include',
        body: JSON.stringify({ mode, ball_set: 75, stage, access_policy: currentPolicy })
      });
      if (!wsConnected) {
        setTimeout(fetchGameState, 100);
      }
    } catch (err) {
      console.error('Failed to start game:', err);
    }
  };

  const drawNumber = async () => {
    try {
      await fetch(`${API_BASE}/games/${gameId}/draw`, {
        method: 'POST',
        headers: adminHeaders(),
        credentials: 'include'
      });
      if (!wsConnected) {
        setTimeout(fetchGameState, 100);
      }
    } catch (err) {
      console.error('Failed to draw:', err);
    }
  };

  const setStage = async (stage) => {
    try {
      await fetch(`${API_BASE}/games/${gameId}/stage/${stage}`, {
        method: 'POST',
        headers: adminHeaders(),
        credentials: 'include'
      });
      if (!wsConnected) {
        setTimeout(fetchGameState, 100);
      }
    } catch (err) {
      console.error('Failed to set stage:', err);
    }
  };

  const generateCards = async (count = 50) => {
    try {
      const res = await fetch(`${API_BASE}/cards/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...adminHeaders() },
        credentials: 'include',
        body: JSON.stringify({ count, game_id: gameId, persistent: storePermanently })
      });
      const data = await res.json();
      setGeneratedCards(data.cards);
      setLastBatchWasPersistent(Boolean(data.persistent));
      setTimeout(fetchCardsForGame, 100);
    } catch (err) {
      console.error('Failed to generate cards:', err);
    }
  };

  const clearGeneratedCards = () => {
    setGeneratedCards([]);
  };

  const validateCard = async () => {
    if (!cardToValidate.trim()) return;

    try {
      const res = await fetch(`${API_BASE}/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ game_id: gameId, serial: cardToValidate.trim() })
      });
      const data = await res.json();
      setValidationResult(data);

      if (data.valid) {
        setCelebrating(true);
        launchConfetti();
        setTimeout(() => setCelebrating(false), config.confettiDuration || 5000);
      }
    } catch (err) {
      console.error('Failed to validate:', err);
    }
  };

  const getModeName = (mode) => {
    const names = {
      progressive_rows: 'Progressive Rows',
      full_house: 'Full House',
      four_corners: 'Four Corners',
      diagonals: 'Diagonals'
    };
    return names[mode] || mode;
  };

  // Player link management
  const createPlayerLink = async (policy = 'LINK_ONLY', password = null) => {
    try {
      const res = await fetch(`${API_BASE}/games/${gameId}/links`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...adminHeaders() },
        credentials: 'include',
        body: JSON.stringify({ policy, password: password || undefined })
      });
      if (res.ok) {
        const data = await res.json();
        setPlayerLinks(prev => [...prev, { id: data.link_id, token: data.access_token, policy: data.policy }]);
      } else {
        const err = await res.json();
        console.error('Failed to create link:', err);
      }
    } catch (err) {
      console.error('Failed to create link:', err);
    }
  };

  const revokePlayerLink = async (linkId) => {
    try {
      await fetch(`${API_BASE}/games/${gameId}/links/${linkId}`, {
        method: 'DELETE',
        headers: adminHeaders(),
        credentials: 'include'
      });
      setPlayerLinks(prev => prev.filter(l => l.id !== linkId));
    } catch (err) {
      console.error('Failed to revoke link:', err);
    }
  };

  // Display View - Casino Style with 5-Ball History
  if (view === 'display') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-emerald-950 via-green-950 to-emerald-900 text-white p-8 relative overflow-hidden">
        <div aria-hidden="true" className="casino-background-pattern" />

        {/* Connection Status Indicator */}
        <div className="fixed top-4 right-4 z-50 flex items-center gap-2 bg-black/50 backdrop-blur-sm px-4 py-2 rounded-full border border-gray-700">
          <div className={`w-3 h-3 rounded-full ${wsConnected ? 'bg-green-500 animate-pulse' : 'bg-yellow-500'}`}></div>
          <span className="text-xs text-gray-300">{wsConnected ? 'Live' : 'Polling'}</span>
        </div>

        <canvas ref={confettiRef} className="fixed inset-0 pointer-events-none z-50" />

        <div className="max-w-7xl mx-auto relative z-10">
          {/* Header with Neon Effect */}
          <div className="flex justify-between items-center mb-12">
            <div className="relative isolate">
              <div
                aria-hidden="true"
                className="pointer-events-none absolute -inset-x-4 -inset-y-4 z-0 rounded-full"
                style={{
                  background: 'radial-gradient(ellipse at center, rgba(16, 97, 61, 0.5) 0%, rgba(202, 138, 4, 0.1) 48%, transparent 78%)'
                }}
              />
              <h1
                className="relative z-10 text-8xl font-bold tracking-wider"
              >
                <span
                  style={{
                    display: 'inline-block',
                    color: 'transparent',
                    backgroundImage: 'linear-gradient(180deg, #fff1bd 0%, #ffd65a 42%, #f5a623 78%, #d8921e 100%)',
                    WebkitBackgroundClip: 'text',
                    backgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    textShadow: '0 1px 1px rgba(8, 45, 28, 0.55), 0 0 6px rgba(234, 179, 8, 0.28)'
                  }}
                >
                  BINGO
                </span>
              </h1>
              <div
                aria-hidden="true"
                className="absolute -bottom-2 left-0 right-0 z-10 h-1 rounded bg-gradient-to-r from-amber-600 via-yellow-300 to-amber-600 opacity-90"
                style={{ boxShadow: '0 0 6px rgba(234, 179, 8, 0.35)' }}
              />
            </div>
            <div className="flex items-center gap-3">
              <input
                type="text"
                value={gameId}
                onChange={(e) => setGameId(e.target.value)}
                className="px-3 py-2 rounded bg-black/50 border border-yellow-500 text-yellow-300 focus:outline-none focus:ring-2 focus:ring-yellow-400"
                placeholder="Game ID"
              />
              <button
                onClick={() => setView('player')}
                className="px-4 py-2.5 bg-black/50 border border-yellow-500 text-yellow-300 font-bold rounded-lg hover:bg-yellow-500/20 transition-all flex items-center gap-2"
                title="Player View"
              >
                <Users className="w-5 h-5" />
                <span className="hidden md:inline">Player View</span>
              </button>
              <button
                onClick={() => setIsAuthModalOpen(true)}
                className="px-4 py-2.5 bg-black/50 border border-yellow-500 text-yellow-300 font-bold rounded-lg hover:bg-yellow-500/20 transition-all flex items-center gap-2"
                title={currentUser ? `Signed in as ${currentUser.username} (${currentUser.role})` : 'Sign In'}
              >
                <User className="w-5 h-5" />
                <span className="hidden md:inline">{currentUser ? currentUser.username : 'Sign In'}</span>
                {currentUser?.role === 'ADMIN' && <Shield className="w-4 h-4 text-red-400" />}
              </button>
              {currentUser?.role === 'ADMIN' && (
                <button
                  onClick={() => setView('system-admin')}
                  className="px-4 py-2.5 bg-red-950/70 border border-red-500 text-red-300 font-bold rounded-lg hover:bg-red-900/50 transition-all flex items-center gap-2"
                  title="System Administration"
                >
                  <Shield className="w-5 h-5 text-red-400" />
                  <span className="hidden md:inline">System Admin</span>
                </button>
              )}
              <button
                onClick={() => setView('admin')}
                className="px-5 py-2.5 bg-gradient-to-r from-yellow-400 to-yellow-600 text-black font-bold rounded-lg hover:from-yellow-300 hover:to-yellow-500 transition-all shadow-lg flex items-center gap-2"
                title="Host Controls"
              >
                <Settings className="w-5 h-5" />
                <span className="hidden lg:inline">Host Controls</span>
              </button>
            </div>
          </div>

          {/* Main Display Area */}
          {!currentUser && (isPrivateGame || (gameState && gameState.access_policy !== 'PUBLIC')) ? (
            <div className="flex flex-col items-center justify-center py-16">
              <div className="bg-gradient-to-br from-gray-900 via-black to-gray-950 border-2 border-yellow-500/60 rounded-3xl p-10 max-w-lg w-full text-center backdrop-blur-md shadow-[0_0_50px_rgba(255,215,0,0.15)] relative overflow-hidden">
                <div className="absolute inset-0 bg-yellow-500/5 pointer-events-none"></div>
                <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-yellow-500/10 border-2 border-yellow-500 flex items-center justify-center text-yellow-400 shadow-[0_0_20px_rgba(255,215,0,0.3)]">
                  <Lock className="w-10 h-10" />
                </div>
                <h2 className="text-3xl font-extrabold text-yellow-300 mb-3 tracking-wide" style={{ textShadow: '0 0 15px rgba(255,215,0,0.4)' }}>
                  Private Game
                </h2>
                <p className="text-gray-300 mb-8 leading-relaxed text-sm">
                  Game <span className="font-mono text-yellow-400 font-bold px-1.5 py-0.5 bg-yellow-400/10 rounded border border-yellow-400/20">{gameId}</span> is private. Sign in with an authorized account or join with an authorized player link to view live bingo.
                </p>
                <div className="flex flex-col sm:flex-row gap-3 justify-center">
                  <button
                    onClick={() => setIsAuthModalOpen(true)}
                    className="flex-1 px-5 py-3 bg-gradient-to-r from-yellow-400 to-yellow-600 text-black font-extrabold rounded-xl shadow-lg hover:from-yellow-300 hover:to-yellow-500 transition-all flex items-center justify-center gap-2"
                  >
                    <User className="w-5 h-5" />
                    Sign In
                  </button>
                  <button
                    onClick={() => setView('player')}
                    className="flex-1 px-5 py-3 bg-black/60 border border-yellow-500/70 text-yellow-300 font-bold rounded-xl hover:bg-yellow-500/20 transition-all flex items-center justify-center gap-2"
                  >
                    <Users className="w-5 h-5" />
                    Join as Player
                  </button>
                </div>
              </div>
            </div>
          ) : gameState ? (
            <>
              <div className="mb-12 flex flex-col items-center">
                <div className="relative w-full max-w-4xl">
                  {/* Neon pulsing glow backdrop */}
                  <div className="absolute inset-0 blur-3xl opacity-50 bg-gradient-to-r from-yellow-400 via-red-500 to-purple-500 animate-pulse pointer-events-none"></div>

                  {/* Main Casino Box */}
                  <div className="relative bg-gradient-to-br from-gray-900 via-black to-gray-950 border-4 border-yellow-500 rounded-3xl shadow-2xl p-8 flex flex-col items-center">
                    {/* CURRENT BALL (Newest Draw) */}
                    <div className="flex flex-col items-center mb-8">
                      <div className="text-2xl font-extrabold text-yellow-400 tracking-widest uppercase mb-4 flex items-center gap-2">
                        <span className="inline-block w-2.5 h-2.5 rounded-full bg-yellow-400 animate-ping"></span>
                        CURRENT BALL
                      </div>

                      {currentBall !== null ? (
                        <div className="relative flex items-center justify-center p-2">
                          <BingoBall
                            number={currentBall}
                            isAnimating={isNewDrawAnimating}
                            size="xlarge"
                          />
                        </div>
                      ) : (
                        <div className="w-44 h-44 rounded-full border-4 border-dashed border-gray-700 flex items-center justify-center text-4xl text-gray-600 font-bold">
                          —
                        </div>
                      )}
                    </div>

                    {/* RECENTLY DRAWN (Up to 5 Previous Draws) */}
                    <div className="w-full flex flex-col items-center border-t border-gray-800 pt-6">
                      <div className="text-sm font-bold text-gray-400 tracking-wider uppercase mb-4">
                        RECENTLY DRAWN
                      </div>

                      <div className="relative flex items-center justify-center gap-4 min-h-[96px] w-full px-4 overflow-visible">
                        {/* Transitioning ball rolling from main position into history slot 0 */}
                        {animatingBall !== null && (
                          <div
                            key={`anim-ball-${animatingBall}`}
                            className="animate-rollIn z-20 flex-shrink-0"
                          >
                            <BingoBall number={animatingBall} size="medium" />
                          </div>
                        )}

                        {/* Stable history balls (never includes currentBall) */}
                        {historyBalls.length > 0 ? (
                          historyBalls.map((num, idx) => {
                            const isDropping = droppingBall === num && idx === historyBalls.length - 1;
                            return (
                              <div
                                key={`hist-ball-${num}`}
                                className={`transition-all duration-700 ease-out flex-shrink-0 ${
                                  isDropping ? 'animate-dropOff' : ''
                                }`}
                                style={{
                                  opacity: isDropping ? 0.3 : Math.max(0.4, 1 - idx * 0.12),
                                  transform: `scale(${Math.max(0.75, 1 - idx * 0.05)})`,
                                }}
                              >
                                <BingoBall number={num} size="medium" />
                              </div>
                            );
                          })
                        ) : animatingBall === null ? (
                          <div className="text-gray-600 italic text-sm py-4">
                            No previous balls drawn yet
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Game Info Bar */}
              <div className="mb-8 bg-gradient-to-r from-purple-900/50 to-blue-900/50 backdrop-blur-lg rounded-2xl p-6 border-2 border-yellow-500/30">
                <div className="flex justify-between items-center">
                  <div>
                    <div className="text-3xl font-bold text-yellow-400 mb-2">
                      {getModeName(gameState.mode)}
                    </div>
                    {gameState.mode === 'progressive_rows' && (
                      <div className="text-xl text-white/80">
                        Goal: {gameState.stage} Row{gameState.stage > 1 ? 's' : ''}
                      </div>
                    )}
                  </div>
                  <div className="text-right">
                    <div className="text-xl text-white/60">Numbers Called</div>
                    <div className="text-5xl font-bold text-green-400">
                      {gameState.drawn.length}
                    </div>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="text-center py-20 text-gray-400">
              <div className="text-2xl font-bold text-yellow-500/80 mb-2">No Active Game</div>
              <p>Game "{gameId}" has not been started yet. Use Host Controls to start a game.</p>
            </div>
          )}

          {/* Celebration Overlay */}
          {celebrating && (
            <div className="fixed inset-0 flex items-center justify-center bg-black/80 backdrop-blur-sm z-40">
              <div className="text-center">
                <div className="animate-bounce">
                  <Crown
                    className="w-32 h-32 mx-auto mb-6 text-yellow-400"
                    style={{ filter: 'drop-shadow(0 0 20px #ffd700)' }}
                  />
                </div>
                <h2
                  className="text-9xl font-bold text-yellow-400 mb-4 animate-pulse"
                  style={{ textShadow: '0 0 30px #ffd700, 0 0 60px #ffd700' }}
                >
                  BINGO!
                </h2>
                <p className="text-4xl text-white animate-pulse">We have a winner!</p>
              </div>
            </div>
          )}

          {/* Auth Modal */}
          <AuthModal
            isOpen={isAuthModalOpen}
            onClose={() => setIsAuthModalOpen(false)}
            currentUser={currentUser}
            onAuthSuccess={handleAuthSuccess}
            onLogout={handleLogout}
            apiBaseUrl={API_BASE}
          />
        </div>
      </div>
    );
  }

  // System Admin Dashboard View
  if (view === 'system-admin') {
    return (
      <AdminDashboard
        currentUser={currentUser}
        onClose={() => setView('admin')}
      />
    );
  }

  // Player View
  if (view === 'player') {
    return (
      <PlayerView
        initialToken={playerViewToken || ''}
        onClose={() => setView('display')}
      />
    );
  }

  // Host Game Controls View (view === 'admin' or fallback)
  return (
    <div className="min-h-screen relative bg-gradient-to-br from-emerald-950 via-green-950 to-emerald-900 p-8">
      <div aria-hidden="true" className="casino-background-pattern" />
      <div className="max-w-7xl mx-auto relative z-10">
        <div className="flex justify-between items-center mb-8">
          <div className="flex items-center gap-4">
            <h1 className="text-4xl font-bold text-white">Host Game Controls</h1>
            <div
              className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm ${
                wsConnected ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
              }`}
            >
              <div
                className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-500' : 'bg-yellow-500'} animate-pulse`}
              ></div>
              {wsConnected ? 'Connected' : 'Polling Mode'}
            </div>
          </div>
          <div className="flex items-center gap-3">
            {currentUser?.role === 'ADMIN' && (
              <button
                onClick={() => setView('system-admin')}
                className="px-4 py-2 bg-red-50 border border-red-200 text-red-700 rounded-lg hover:bg-red-100 transition-all text-sm font-medium flex items-center gap-2"
                title="Open System Administration Dashboard"
              >
                <Shield className="w-4 h-4 text-red-600" />
                <span>System Admin</span>
              </button>
            )}
            <button
              onClick={() => setView('player')}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-100 transition-all flex items-center gap-2 text-white text-sm font-medium"
              title="Open Player View"
            >
              <Users className="w-4 h-4" />
              <span>Player View</span>
            </button>
            <button
              onClick={() => setIsAuthModalOpen(true)}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-100 transition-all flex items-center gap-2 text-white text-sm font-medium"
              title={currentUser ? `Signed in as ${currentUser.username} (${currentUser.role})` : 'Sign In'}
            >
              <User className="w-4 h-4" />
              <span>{currentUser ? currentUser.username : 'Sign In'}</span>
            </button>
            <button
              onClick={() => setView('display')}
              className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-all font-medium"
            >
              Switch to Display View
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Game Controls */}
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
            <Play className="w-6 h-6" />
            Game Controls
          </h2>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">Game ID</label>
              <input
                type="text"
                value={gameId}
                onChange={(e) => setGameId(e.target.value)}
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-purple-500 outline-none"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">
                Admin Key (optional)
                <span className="ml-2 text-xs font-normal text-gray-500">
                  Required only if ADMIN_API_KEY is configured on the server
                </span>
              </label>
              <input
                type="password"
                value={adminKey}
                onChange={(e) => setAdminKey(e.target.value)}
                placeholder="Leave empty if server doesn't require an admin key"
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-purple-500 outline-none font-mono text-sm"
                autoComplete="off"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">
                Signed in as
                <span className="ml-2 text-xs font-normal text-gray-500">
                  ({currentUser?.role || 'Guest / Unauthenticated'})
                </span>
              </label>
              <div className="flex items-center gap-2">
                <div className="px-4 py-2 bg-purple-50 border border-purple-200 rounded-lg text-purple-700 font-medium">
                  {currentUser?.username || 'Anonymous'}
                </div>
                {currentUser?.role === 'ADMIN' && (
                  <span className="px-2.5 py-1 bg-red-100 text-red-800 text-xs font-semibold rounded-full flex items-center gap-1">
                    <Shield className="w-3.5 h-3.5 text-red-600" />
                    ADMIN
                  </span>
                )}
                {currentUser?.role === 'OPERATOR' && (
                  <span className="px-2.5 py-1 bg-blue-100 text-blue-800 text-xs font-semibold rounded-full">
                    OPERATOR
                  </span>
                )}
                {currentUser?.role === 'AUDITOR' && (
                  <span className="px-2.5 py-1 bg-gray-100 text-gray-800 text-xs font-semibold rounded-full">
                    AUDITOR
                  </span>
                )}
              </div>
            </div>

            {/* Game Access Policy Toggle */}
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {gameState?.access_policy === 'PUBLIC' ? (
                    <Globe className="w-5 h-5 text-green-600 flex-shrink-0" />
                  ) : (
                    <Lock className="w-5 h-5 text-amber-600 flex-shrink-0" />
                  )}
                  <div>
                    <div className="text-sm font-bold text-gray-800">
                      Access Policy: <span className={gameState?.access_policy === 'PUBLIC' ? 'text-green-600 font-extrabold' : 'text-amber-600 font-extrabold'}>{gameState?.access_policy || 'LINK_ONLY'}</span>
                    </div>
                    <div className="text-xs text-gray-500">
                      {gameState?.access_policy === 'PUBLIC'
                        ? 'Public: Any guest can view live bingo without signing in.'
                        : 'Private (Link Only): Only signed-in users or authorized player links can view.'}
                    </div>
                  </div>
                </div>
              </div>
              <div className="flex gap-2 mt-2.5">
                <button
                  type="button"
                  onClick={() => updateAccessPolicy('PUBLIC')}
                  className={`flex-1 py-1.5 px-3 rounded text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
                    gameState?.access_policy === 'PUBLIC'
                      ? 'bg-green-600 text-white shadow-sm'
                      : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  <Globe className="w-3.5 h-3.5" />
                  Set Public
                </button>
                <button
                  type="button"
                  onClick={() => updateAccessPolicy('LINK_ONLY')}
                  className={`flex-1 py-1.5 px-3 rounded text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
                    gameState?.access_policy !== 'PUBLIC'
                      ? 'bg-amber-600 text-white shadow-sm'
                      : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  <Lock className="w-3.5 h-3.5" />
                  Set Private (Link Only)
                </button>
              </div>
            </div>

              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => startGame('progressive_rows', 1)}
                  className="px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-all"
                >
                  Start Progressive
                </button>
                <button
                  onClick={() => startGame('full_house')}
                  className="px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-all"
                >
                  Start Full House
                </button>
                <button
                  onClick={() => startGame('four_corners')}
                  className="px-4 py-3 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 transition-all"
                >
                  Start 4 Corners
                </button>
                <button
                  onClick={() => startGame('diagonals')}
                  className="px-4 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-all"
                >
                  Start Diagonals
                </button>
              </div>

              <button
                onClick={drawNumber}
                className="w-full px-6 py-4 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-all text-lg font-semibold"
              >
                Draw Number
              </button>

              {currentBall !== null && (
                <div className="bg-gradient-to-r from-purple-100 to-blue-100 rounded-lg p-4 border-2 border-purple-300">
                  <div className="text-center">
                    <div className="text-sm font-semibold text-gray-600 mb-2">Last Drawn</div>
                    <div className="flex justify-center">
                      <BingoBall number={currentBall} size="medium" />
                    </div>
                  </div>
                </div>
              )}

              {gameState?.mode === 'progressive_rows' && (
                <div>
                  <label className="block text-sm font-medium mb-2">Set Stage (Required Rows)</label>
                  <div className="grid grid-cols-5 gap-2">
                    {[1, 2, 3, 4, 5].map((stage) => (
                      <button
                        key={stage}
                        onClick={() => setStage(stage)}
                        className={`px-4 py-2 rounded-lg transition-all ${
                          gameState?.stage === stage
                            ? 'bg-purple-600 text-white'
                            : 'bg-gray-200 hover:bg-gray-300'
                        }`}
                      >
                        {stage}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Player Links */}
              <div className="border-t pt-4 mt-4">
                <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                  <ExternalLink className="w-5 h-5 text-purple-600" />
                  Player Links
                </h3>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <select
                      id="link-policy"
                      className="flex-1 px-3 py-2 border rounded-lg text-sm"
                      defaultValue="LINK_ONLY"
                    >
                      <option value="PUBLIC">Public (no link needed)</option>
                      <option value="LINK_ONLY">Link Required</option>
                      <option value="PASSWORD">Password Protected</option>
                    </select>
                  </div>
                  <input
                    type="text"
                    id="link-password"
                    placeholder="Password (optional, for PASSWORD policy)"
                    className="w-full px-3 py-2 border rounded-lg text-sm"
                  />
                  <button
                    onClick={() => {
                      const policy = document.getElementById('link-policy').value;
                      const password = document.getElementById('link-password').value || null;
                      createPlayerLink(policy, password);
                    }}
                    className="w-full px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-all text-sm font-medium"
                  >
                    Generate Player Link
                  </button>
                  {playerLinks.length > 0 && (
                    <div className="space-y-2 mt-3">
                      {playerLinks.map((link) => (
                        <div key={link.id} className="flex items-center gap-2 bg-gray-50 rounded-lg p-2">
                          <input
                            type="text"
                            readOnly
                            value={`${window.location.origin}/b/${link.token}`}
                            className="flex-1 px-2 py-1 text-xs border rounded bg-white"
                          />
                          <button
                            onClick={() => navigator.clipboard.writeText(`${window.location.origin}/b/${link.token}`)}
                            className="px-2 py-1 text-xs bg-gray-200 rounded hover:bg-gray-300"
                          >
                            Copy
                          </button>
                          <button
                            onClick={() => revokePlayerLink(link.id)}
                            className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200"
                          >
                            Revoke
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Card Generation */}
          <div className="bg-white rounded-xl shadow-lg p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-2xl font-bold flex items-center gap-2">
                <Printer className="w-6 h-6" />
                Card Generation
              </h2>
              {generatedCards.length > 0 && (
                <button
                  onClick={clearGeneratedCards}
                  className="px-3 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700"
                >
                  Clear Cards
                </button>
              )}
            </div>

            <div className="space-y-4">
              <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-lg p-3">
                <input
                  type="checkbox"
                  id="store-permanently"
                  checked={storePermanently}
                  onChange={(e) => setStorePermanently(e.target.checked)}
                  className="w-4 h-4"
                />
                <label htmlFor="store-permanently" className="text-sm">
                  <span className="font-medium">Store cards permanently</span>
                  <p className="text-xs text-gray-600 mt-0.5">
                    When enabled, generated cards are saved to the persistent database and remain
                    available after server restarts. Otherwise, cards are kept in memory and are
                    cleared when the server restarts.
                  </p>
                </label>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <button
                  onClick={() => generateCards(10)}
                  className="px-4 py-3 bg-gray-700 text-white rounded-lg hover:bg-gray-800 transition-all"
                >
                  10 Cards
                </button>
                <button
                  onClick={() => generateCards(50)}
                  className="px-4 py-3 bg-gray-700 text-white rounded-lg hover:bg-gray-800 transition-all"
                >
                  50 Cards
                </button>
                <button
                  onClick={() => generateCards(100)}
                  className="px-4 py-3 bg-gray-700 text-white rounded-lg hover:bg-gray-800 transition-all"
                >
                  100 Cards
                </button>
              </div>

              <div className="flex space-x-2">
                <input
                  type="number"
                  value={customCount}
                  onChange={(e) => setCustomCount(parseInt(e.target.value, 10) || 1)}
                  min={1}
                  max={500}
                  className="border p-2 rounded w-24"
                />
                <button
                  onClick={() => generateCards(customCount)}
                  className="bg-indigo-600 text-white px-4 py-2 rounded hover:bg-indigo-700"
                >
                  Generate Custom
                </button>
              </div>

              {generatedCards.length > 0 && (
                <div className="border rounded-lg p-4 max-h-96 overflow-y-auto">
                  <div className="flex justify-between items-center mb-3">
                    <h3 className="font-semibold">
                      Generated Cards ({generatedCards.length})
                      <span className="ml-2 text-xs text-gray-500">
                        • {lastBatchWasPersistent ? 'Saved permanently' : 'Temporary — cleared on restart'}
                      </span>
                    </h3>
                    <button
                      onClick={() => window.print()}
                      className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
                    >
                      Print All
                    </button>
                  </div>

                  <div className="space-y-2">
                    {generatedCards.map((card) => (
                      <div key={card.public_id} className="border rounded shadow">
                        <div
                          className="cursor-pointer bg-gray-100 p-2 font-bold hover:bg-gray-200"
                          onClick={() => setOpenCard(openCard === card.public_id ? null : card.public_id)}
                        >
                          Card ID: {card.public_id}
                        </div>
                        {openCard === card.public_id && (
                          <div className="p-4">
                            <div className="grid grid-cols-5 gap-1">
                              {['B', 'I', 'N', 'G', 'O'].map((letter, idx) => {
                                const colors = [
                                  'bg-red-500',
                                  'bg-blue-500',
                                  'bg-yellow-500',
                                  'bg-green-500',
                                  'bg-purple-500'
                                ];
                                return (
                                  <div
                                    key={letter}
                                    className={`${colors[idx]} text-white text-center font-bold p-1`}
                                  >
                                    {letter}
                                  </div>
                                );
                              })}
                              {card.grid.flat().map((cell, i) => (
                                <div
                                  key={i}
                                  className={`border text-center p-2 ${
                                    cell === 'FREE' ? 'bg-yellow-200 font-bold' : ''
                                  }`}
                                >
                                  {cell}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Validation */}
          <div className="bg-white rounded-xl shadow-lg p-6 lg:col-span-2">
            <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
              <CheckCircle2 className="w-6 h-6" />
              Card Validation
            </h2>

            <div className="flex gap-3 mb-4">
              <input
                type="text"
                value={cardToValidate}
                onChange={(e) => setCardToValidate(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && validateCard()}
                placeholder="Enter Card ID (e.g., A1B2C3D4)"
                className="flex-1 px-4 py-3 border rounded-lg focus:ring-2 focus:ring-purple-500 outline-none text-lg"
              />
              <button
                onClick={validateCard}
                className="px-8 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-all font-semibold"
              >
                Validate
              </button>
            </div>

            {validationResult && (
              <div
                className={`p-6 rounded-lg ${
                  validationResult.valid ? 'bg-green-50 border-2 border-green-500' : 'bg-red-50 border-2 border-red-500'
                }`}
              >
                <div className="text-center mb-4">
                  <div
                    className={`text-4xl font-bold ${
                      validationResult.valid ? 'text-green-600' : 'text-red-600'
                    }`}
                  >
                    {validationResult.valid ? '✓ BINGO!' : '✗ Not Yet'}
                  </div>
                  {validationResult.details && (
                    <div className="mt-2 text-sm text-gray-600">
                      {JSON.stringify(validationResult.details)}
                    </div>
                  )}
                </div>

                {validationResult.grid && validationResult.grid.length > 0 && (
                  <div className="grid grid-cols-5 gap-2 max-w-md mx-auto">
                    {validationResult.grid.map((row, ridx) =>
                      row.map((cell, cidx) => {
                        const marked = cell === 'FREE' || validationResult.drawn.includes(cell);
                        return (
                          <div
                            key={`${ridx}-${cidx}`}
                            className={`aspect-square flex items-center justify-center text-lg font-bold rounded ${
                              marked ? 'bg-blue-500 text-white' : 'bg-gray-200'
                            }`}
                          >
                            {cell === 'FREE' ? '★' : cell}
                          </div>
                        );
                      })
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Game Status */}
          {gameState && (
            <div className="bg-white rounded-xl shadow-lg p-6 lg:col-span-2">
              <h2 className="text-2xl font-bold mb-4">Current Game Status</h2>
              <div className="grid grid-cols-4 gap-4 mb-4">
                <div className="text-center">
                  <div className="text-3xl font-bold text-purple-600">{gameState.drawn.length}</div>
                  <div className="text-sm text-gray-600">Numbers Drawn</div>
                </div>
                <div className="text-center">
                  <div className="text-xl font-bold text-blue-600">{getModeName(gameState.mode)}</div>
                  <div className="text-sm text-gray-600">Game Mode</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold text-green-600">{gameState.stage}</div>
                  <div className="text-sm text-gray-600">Current Stage</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold text-yellow-600">{gameState.status}</div>
                  <div className="text-sm text-gray-600">Status</div>
                </div>
              </div>

              <div className="border-t pt-4">
                <button
                  onClick={() => setShowAllDrawn(!showAllDrawn)}
                  className="w-full flex justify-between items-center px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg transition-all"
                >
                  <span className="font-semibold">View All Drawn Numbers ({gameState.drawn.length})</span>
                  <span className="text-xl">{showAllDrawn ? '▲' : '▼'}</span>
                </button>

                {showAllDrawn && (
                  <div className="mt-4 max-h-96 overflow-y-auto border rounded-lg p-4 bg-gray-50">
                    <div className="grid grid-cols-10 gap-2">
                      {gameState.drawn.map((num, idx) => (
                        <div key={`${num}-${idx}`} className="flex justify-center">
                          <BingoBall number={num} size="small" />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Hidden print area */}
      <div id="print-area" className="hidden print:block">
        <div className="grid grid-cols-2 gap-4">
          {generatedCards.map((card) => (
            <div key={card.public_id} className="border p-4 shadow break-inside-avoid">
              <div className="font-bold text-center mb-2">Card ID: {card.public_id}</div>
              <div className="grid grid-cols-5 gap-1">
                {['B', 'I', 'N', 'G', 'O'].map((letter, idx) => {
                  const colors = [
                    'bg-red-500',
                    'bg-blue-500',
                    'bg-yellow-500',
                    'bg-green-500',
                    'bg-purple-500'
                  ];
                  return (
                    <div key={letter} className={`${colors[idx]} text-white text-center font-bold p-1`}>
                      {letter}
                    </div>
                  );
                })}
                {card.grid.flat().map((cell, i) => (
                  <div
                    key={i}
                    className={`border text-center p-2 aspect-square flex items-center justify-center ${
                      cell === 'FREE' ? 'bg-yellow-200 font-bold' : ''
                    }`}
                  >
                    {cell}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Auth Modal */}
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        currentUser={currentUser}
        onAuthSuccess={handleAuthSuccess}
        onLogout={handleLogout}
        apiBaseUrl={API_BASE}
      />
    </div>
  );
};

export default BingoApp;

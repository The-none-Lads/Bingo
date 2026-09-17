import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Wifi, WifiOff, Users, Trophy, CircleDot } from 'lucide-react';

const API_BASE = window.__CONFIG__?.apiBaseUrl || 'http://localhost:8000';

export function PlayerView({ onClose }) {
  const [token, setToken] = useState('');
  const [playerName, setPlayerName] = useState('');
  const [password, setPassword] = useState('');
  const [needsPassword, setNeedsPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [gameData, setGameData] = useState(null);
  const [gameState, setGameState] = useState(null);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef(null);
  const playerTokenRef = useRef(null);

  const connectWebSocket = useCallback((gameId, playerToken) => {
    const wsBase = window.__CONFIG__?.wsBaseUrl || `ws://${window.location.host}`;
    const wsUrl = `${wsBase}/ws/player/${gameId}?token=${encodeURIComponent(playerToken)}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => setWsConnected(true);
    ws.onclose = () => setWsConnected(false);
    ws.onerror = () => setWsConnected(false);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data?.type === 'state_update' && data.state) {
          setGameState(data.state);
        }
        if (data?.type === 'celebration') {
          // Show celebration briefly
          setGameState(prev => prev ? { ...prev, celebrating: true } : null);
        }
      } catch (err) {
        console.error('WebSocket message error:', err);
      }
    };

    wsRef.current = ws;
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/b/redeem`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token,
          password: needsPassword ? password : undefined,
          player_name: playerName || undefined,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        if (res.status === 401 && data.detail?.includes('Password')) {
          setNeedsPassword(true);
          setError('Password required');
        } else {
          throw new Error(data.detail || 'Failed to join game');
        }
        return;
      }

      setGameData(data);
      playerTokenRef.current = data.player_session_token;
      if (data.game_state) {
        setGameState(data.game_state);
      }
      connectWebSocket(data.game_id, data.player_session_token);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  // Token entry form
  if (!gameData) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-900 via-blue-900 to-indigo-900 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-2xl p-8 w-full max-w-md">
          <div className="text-center mb-6">
            <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Users className="w-8 h-8 text-purple-600" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900">Join Bingo Game</h1>
            <p className="text-gray-500 mt-1">Enter your access link to play</p>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Access Token or Link</label>
              <input
                type="text"
                value={token}
                onChange={(e) => setToken(e.target.value.trim())}
                placeholder="Paste your game link or token..."
                className="w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-purple-500 outline-none text-sm"
                autoFocus
              />
            </div>

            {needsPassword && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Game Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter the game password"
                  className="w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-purple-500 outline-none"
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Your Name (optional)</label>
              <input
                type="text"
                value={playerName}
                onChange={(e) => setPlayerName(e.target.value)}
                placeholder="Enter your name"
                maxLength={64}
                className="w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-purple-500 outline-none"
              />
            </div>

            <button
              type="submit"
              disabled={!token || loading}
              className="w-full py-3 bg-purple-600 text-white rounded-lg font-medium hover:bg-purple-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Joining...' : 'Join Game'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  // Game view
  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 via-blue-900 to-indigo-900 p-4">
      <div className="max-w-lg mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-4">
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${wsConnected ? 'bg-green-500 animate-pulse' : 'bg-yellow-500'}`}></div>
            <span className="text-white text-sm">{wsConnected ? 'Live' : 'Connecting...'}</span>
          </div>
          <button
            onClick={onClose}
            className="text-white/80 hover:text-white text-sm"
          >
            Leave
          </button>
        </div>

        {/* Current Ball */}
        {gameState?.drawn?.length > 0 && (
          <div className="text-center mb-6">
            <p className="text-white/60 text-sm mb-2">Current Ball</p>
            <div className="inline-flex flex-col items-center justify-center w-24 h-24 bg-white rounded-full shadow-xl">
              <span className="text-3xl font-bold text-gray-900">
                {gameState.drawn[gameState.drawn.length - 1]}
              </span>
            </div>
          </div>
        )}

        {/* Game Info */}
        <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4 mb-4">
          <div className="flex justify-between items-center text-white text-sm">
            <span>{gameState?.mode?.replace('_', ' ') || 'Game'}</span>
            <span>{gameState?.drawn?.length || 0} numbers called</span>
          </div>
        </div>

        {/* Celebration */}
        {gameState?.celebrating && (
          <div className="fixed inset-0 flex items-center justify-center bg-black/50 backdrop-blur-sm z-50">
            <div className="bg-white rounded-2xl p-8 text-center animate-bounce">
              <Trophy className="w-16 h-16 text-yellow-500 mx-auto mb-4" />
              <h2 className="text-3xl font-bold text-gray-900">BINGO!</h2>
              <p className="text-gray-500 mt-2">We have a winner!</p>
            </div>
          </div>
        )}

        {/* Drawn Numbers Grid */}
        <div className="bg-white rounded-xl p-4 shadow-xl">
          <h3 className="text-sm font-semibold text-gray-500 mb-3">
            Drawn Numbers ({gameState?.drawn?.length || 0})
          </h3>
          <div className="grid grid-cols-10 gap-2">
            {Array.from({ length: 75 }, (_, i) => i + 1).map(num => {
              const isDrawn = gameState?.drawn?.includes(num);
              return (
                <div
                  key={num}
                  className={`aspect-square flex items-center justify-center rounded-full text-xs font-medium transition-all ${
                    isDrawn
                      ? 'bg-purple-600 text-white scale-110 shadow-lg'
                      : 'bg-gray-100 text-gray-400'
                  }`}
                >
                  {num}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

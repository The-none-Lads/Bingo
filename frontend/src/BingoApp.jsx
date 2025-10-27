import React, { useState, useEffect, useRef } from 'react';
import { Play, Square, CheckCircle2, Settings, Printer, Grid3x3, Crown, X } from 'lucide-react';

const API_BASE = 'http://localhost:8000';

const BingoApp = () => {
  const [view, setView] = useState('display'); // 'display' or 'admin'
  const [gameId, setGameId] = useState('demo');
  const [gameState, setGameState] = useState(null);
  const [lastDrawn, setLastDrawn] = useState(null);
  const [validationResult, setValidationResult] = useState(null);
  const [cardToValidate, setCardToValidate] = useState('');
  const [generatedCards, setGeneratedCards] = useState([]);
  const [showSettings, setShowSettings] = useState(false);
  const [celebrating, setCelebrating] = useState(false);
  const confettiRef = useRef(null);
  const [customCount, setCustomCount] = useState(10);
  const [openCard, setOpenCard] = useState(null);

  // Fetch game state periodically
  useEffect(() => {
    const interval = setInterval(fetchGameState, 2000);
    return () => clearInterval(interval);
  }, [gameId]);

  const fetchGameState = async () => {
    try {
      const res = await fetch(`${API_BASE}/games/${gameId}/state`);
      if (res.ok) {
        const data = await res.json();
        if (gameState && data.drawn.length > gameState.drawn.length) {
          setLastDrawn(data.drawn[data.drawn.length - 1]);
        }
        setGameState(data);
      }
    } catch (err) {
      console.error('Failed to fetch game state:', err);
    }
  };

  const startGame = async (mode = 'progressive_rows', stage = 1) => {
    try {
      await fetch(`${API_BASE}/games/${gameId}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, ball_set: 75, stage })
      });
      fetchGameState();
    } catch (err) {
      console.error('Failed to start game:', err);
    }
  };

  const drawNumber = async () => {
    try {
      await fetch(`${API_BASE}/games/${gameId}/draw`, { method: 'POST' });
      fetchGameState();
    } catch (err) {
      console.error('Failed to draw number:', err);
    }
  };

  const setStage = async (stage) => {
    try {
      await fetch(`${API_BASE}/games/${gameId}/stage/${stage}`, { method: 'POST' });
      fetchGameState();
    } catch (err) {
      console.error('Failed to set stage:', err);
    }
  };

  const generateCards = async (count = 50) => {
    try {
      const res = await fetch(`${API_BASE}/cards/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ count, game_id: gameId })
      });
      const data = await res.json();
      setGeneratedCards(data.cards);
    } catch (err) {
      console.error('Failed to generate cards:', err);
    }
  };

  const validateCard = async () => {
    if (!cardToValidate.trim()) return;
    
    try {
      const res = await fetch(`${API_BASE}/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game_id: gameId, serial: cardToValidate.trim() })
      });
      const data = await res.json();
      setValidationResult(data);
      
      if (data.valid) {
        setCelebrating(true);
        launchConfetti();
        setTimeout(() => setCelebrating(false), 5000);
      }
    } catch (err) {
      console.error('Failed to validate card:', err);
    }
  };

  const launchConfetti = () => {
    const canvas = confettiRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    
    const pieces = Array.from({ length: 150 }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height - canvas.height,
      size: Math.random() * 8 + 4,
      color: `hsl(${Math.random() * 360}, 100%, 50%)`,
      speed: Math.random() * 4 + 2,
      rotation: Math.random() * 360
    }));

    let animationId;
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      pieces.forEach(p => {
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate((p.rotation * Math.PI) / 180);
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size);
        ctx.restore();
        
        p.y += p.speed;
        p.rotation += 3;
        if (p.y > canvas.height) p.y = -10;
      });
      animationId = requestAnimationFrame(draw);
    };
    
    draw();
    setTimeout(() => {
      cancelAnimationFrame(animationId);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }, 5000);
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

  // Display View - For projection
  if (view === 'display') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-900 via-blue-900 to-indigo-900 text-white p-8">
        <canvas ref={confettiRef} className="fixed inset-0 pointer-events-none z-50" />
        
        <div className="max-w-7xl mx-auto">
          <div className="flex justify-between items-center mb-12">
            <h1 className="text-7xl font-bold tracking-tight">BINGO</h1>
            <button
              onClick={() => setView('admin')}
              className="px-6 py-3 bg-white/10 hover:bg-white/20 rounded-lg backdrop-blur transition-all"
            >
              <Settings className="w-6 h-6" />
            </button>
          </div>

          {gameState && (
            <>
              <div className="mb-8 bg-white/10 backdrop-blur-lg rounded-2xl p-6">
                <div className="flex justify-between items-center">
                  <div>
                    <div className="text-2xl font-semibold mb-2">
                      {getModeName(gameState.mode)}
                    </div>
                    {gameState.mode === 'progressive_rows' && (
                      <div className="text-xl text-white/80">
                        Current Goal: {gameState.stage} Row{gameState.stage > 1 ? 's' : ''}
                      </div>
                    )}
                  </div>
                  <div className="text-right">
                    <div className="text-5xl font-bold text-yellow-300">
                      {lastDrawn || (gameState.drawn.length > 0 ? gameState.drawn[gameState.drawn.length - 1] : '—')}
                    </div>
                    <div className="text-sm text-white/60 mt-1">Last Called</div>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-10 gap-3 mb-8">
                {Array.from({ length: 75 }, (_, i) => i + 1).map(num => {
                  const drawn = gameState.drawn.includes(num);
                  const isLast = num === lastDrawn;
                  return (
                    <div
                      key={num}
                      className={`aspect-square rounded-lg flex items-center justify-center text-2xl font-bold transition-all duration-300 ${
                        drawn
                          ? isLast
                            ? 'bg-yellow-400 text-black scale-110 shadow-2xl animate-pulse'
                            : 'bg-green-500 text-white'
                          : 'bg-white/10 text-white/40'
                      }`}
                    >
                      {num}
                    </div>
                  );
                })}
              </div>
            </>
          )}

          {celebrating && (
            <div className="fixed inset-0 flex items-center justify-center bg-black/50 backdrop-blur-sm z-40">
              <div className="text-center animate-bounce">
                <Crown className="w-32 h-32 mx-auto mb-6 text-yellow-300" />
                <h2 className="text-9xl font-bold text-yellow-300 mb-4">BINGO!</h2>
                <p className="text-3xl">We have a winner!</p>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Admin View
  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900">Admin Dashboard</h1>
          <button
            onClick={() => setView('display')}
            className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-all"
          >
            Switch to Display View
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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

              {gameState?.mode === 'progressive_rows' && (
                <div>
                  <label className="block text-sm font-medium mb-2">Set Stage (Required Rows)</label>
                  <div className="grid grid-cols-5 gap-2">
                    {[1, 2, 3, 4, 5].map(stage => (
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
            </div>
          </div>

          {/* Card Generation */}
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
              <Printer className="w-6 h-6" />
              Card Generation
            </h2>
            
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
              
              <div className="flex space-x-2 mt-4">
                <input
                    type="number"
                    value={customCount}
                    onChange={e => setCustomCount(parseInt(e.target.value))}
                    min={1}
                    max={200}
                    className="border p-2 rounded w-24"
                />
                <button
                    onClick={() => generateCards(customCount)}
                    className="bg-indigo-600 text-white px-4 py-2 rounded"
                >
                    Generate Custom
                </button>
                </div>

              {generatedCards.length > 0 && (
                <div className="border rounded-lg p-4 max-h-96 overflow-y-auto">
                  <div className="flex justify-between items-center mb-3">
                    <h3 className="font-semibold">Generated Cards ({generatedCards.length})</h3>
                    <button
                      onClick={() => window.print()}
                      className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
                    >
                      Print All
                    </button>
                  </div>
                

                <div id="print-area" className="space-y-4">
                    {generatedCards.map(card => (
                    <div key={card.public_id} className="border rounded shadow">
                    <div
                        className="cursor-pointer bg-gray-100 p-2 font-bold"
                        onClick={() => setOpenCard(openCard === card.public_id ? null : card.public_id)}
                    >
                        Card ID: {card.public_id}
                    </div>
                    {openCard === card.public_id && (
                        <div className="p-4">
                        <div className="grid grid-cols-5 gap-1">
                            {["B","I","N","G","O"].map(letter => (
                            <div key={letter} className="bg-indigo-600 text-white text-center font-bold">
                                {letter}
                            </div>
                            ))}
                            {card.grid.flat().map((cell, i) => (
                            <div
                                key={i}
                                className={`border text-center p-2 ${cell === "FREE" ? "bg-yellow-200" : ""}`}
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
          {/* Hidden print area with full cards */}
          {generatedCards.length > 0 && (
            <div id="print-area" className="hidden">
              <div className="grid grid-cols-2 gap-4">
              {generatedCards.map(card => (
                  <div
                    key={card.public_id}
                  className="border p-4 shadow break-inside-avoid page-break-inside-avoid"
                  >
                    <div className="font-bold text-center mb-2">
                      Card ID: {card.public_id}
                  </div>
                  <div className="grid grid-cols-5 gap-1">
                      {["B","I","N","G","O"].map(letter => (
                        <div
                          key={letter}
                          className="bg-indigo-600 text-white text-center font-bold"
                        >
                        {letter}
                    </div>
                    ))}
                    {card.grid.flat().map((cell, i) => (
                    <div
                        key={i}
                        className={`border text-center p-2 aspect-square ${
                        cell === "FREE" ? "bg-yellow-200 font-bold" : ""
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
          )}
  
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
                onKeyPress={(e) => e.key === 'Enter' && validateCard()}
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
              <div className={`p-6 rounded-lg ${validationResult.valid ? 'bg-green-50 border-2 border-green-500' : 'bg-red-50 border-2 border-red-500'}`}>
                <div className="text-center mb-4">
                  <div className={`text-4xl font-bold ${validationResult.valid ? 'text-green-600' : 'text-red-600'}`}>
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
              <div className="grid grid-cols-4 gap-4">
                <div className="text-center">
                  <div className="text-3xl font-bold text-purple-600">{gameState.drawn.length}</div>
                  <div className="text-sm text-gray-600">Numbers Drawn</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold text-blue-600">{getModeName(gameState.mode)}</div>
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
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default BingoApp;
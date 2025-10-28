import React, { useState, useEffect, useRef } from 'react';
import { Play, CheckCircle2, Settings, Printer, Crown } from 'lucide-react';

const API_BASE = 'http://localhost:8000';

// Helper function to get letter and color for a number
const getBingoLetter = (num) => {
  if (num >= 1 && num <= 15) return { letter: 'B', color: 'bg-red-500' };
  if (num >= 16 && num <= 30) return { letter: 'I', color: 'bg-blue-500' };
  if (num >= 31 && num <= 45) return { letter: 'N', color: 'bg-yellow-500' };
  if (num >= 46 && num <= 60) return { letter: 'G', color: 'bg-green-500' };
  if (num >= 61 && num <= 75) return { letter: 'O', color: 'bg-purple-500' };
  return { letter: '', color: 'bg-gray-500' };
};

// Animated Bingo Ball Component
const BingoBall = ({ number, isAnimating = false, size = 'large' }) => {
  const { letter, color } = getBingoLetter(number);
  
  const sizeClasses = {
    small: 'w-12 h-12 text-sm',
    medium: 'w-20 h-20 text-xl',
    large: 'w-32 h-32 text-4xl',
    xlarge: 'w-48 h-48 text-6xl'
  };
  const letterSizeClasses = {
    small: 'text-xs',
    medium: 'text-sm',
    large: 'text-lg',
    xlarge: 'text-2xl',
  };
  return (
    <div
      className={`${sizeClasses[size]} ${color} rounded-full flex flex-col items-center justify-center text-white font-bold shadow-2xl border-4 border-white/30 ${isAnimating ? 'animate-bounce' : ''}`}
    >
      <div className={`${letterSizeClasses[size]} opacity-80`}>{letter}</div>
      <div>{number}</div>
    </div>
  );
};

const BingoApp = () => {
  const [view, setView] = useState('display');
  const [gameId, setGameId] = useState('demo');
  const [gameState, setGameState] = useState(null);
  const [lastDrawn, setLastDrawn] = useState(null);
  const [validationResult, setValidationResult] = useState(null);
  const [cardToValidate, setCardToValidate] = useState('');
  const [generatedCards, setGeneratedCards] = useState([]);
  const [celebrating, setCelebrating] = useState(false);
  const confettiRef = useRef(null);
  const [customCount, setCustomCount] = useState(10);
  const [openCard, setOpenCard] = useState(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const wsRef = useRef(null);

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/${gameId}`);
    wsRef.current = ws;

    ws.onopen = () => console.log('✅ WebSocket connected');

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === "state_update" && data.state) {
          const prevLength = gameState?.drawn?.length || 0;
          const newLength = data.state.drawn?.length || 0;
          
          if (newLength > prevLength && data.state.drawn.length > 0) {
            const newNum = data.state.drawn[data.state.drawn.length - 1];
            setLastDrawn(newNum);
            setIsDrawing(true);
            setTimeout(() => setIsDrawing(false), 2000);
          }
          
          setGameState(data.state);
        }
        
        if (data.type === "celebration") {
          setCelebrating(true);
          launchConfetti();
          setTimeout(() => setCelebrating(false), 5000);
        }
      } catch (err) {
        console.error('WebSocket error:', err);
      }
    };

    return () => wsRef.current?.close();
  }, [gameId]);

  const startGame = async (mode = 'progressive_rows', stage = 1) => {
    try {
      await fetch(`${API_BASE}/games/${gameId}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, ball_set: 75, stage })
      });
    } catch (err) {
      console.error('Failed to start game:', err);
    }
  };

  const drawNumber = async () => {
    try {
      await fetch(`${API_BASE}/games/${gameId}/draw`, { method: 'POST' });
    } catch (err) {
      console.error('Failed to draw:', err);
    }
  };

  const setStage = async (stage) => {
    try {
      await fetch(`${API_BASE}/games/${gameId}/stage/${stage}`, { method: 'POST' });
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
      console.error('Failed to validate:', err);
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
      rotation: Math.random() * 360,
      rotationSpeed: Math.random() * 6 - 3
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
        p.rotation += p.rotationSpeed;
        if (p.y > canvas.height) {
          p.y = -10;
          p.x = Math.random() * canvas.width;
        }
      });
      animationId = requestAnimationFrame(draw);
    };
    
    draw();
    setTimeout(() => {
      if (animationId) cancelAnimationFrame(animationId);
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

  // Display View - Casino Style
  if (view === 'display') {
    return (
      <div className="min-h-screen bg-black text-white p-8 relative overflow-hidden">
        {/* Casino Background Pattern */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute inset-0" style={{
            backgroundImage: `repeating-linear-gradient(45deg, transparent, transparent 35px, rgba(255,215,0,0.3) 35px, rgba(255,215,0,0.3) 70px)`
          }}></div>
        </div>
        
        <canvas ref={confettiRef} className="fixed inset-0 pointer-events-none z-50" />
        
        <div className="max-w-7xl mx-auto relative z-10">
          {/* Header with Neon Effect */}
          <div className="flex justify-between items-center mb-12">
            <div className="relative">
              <h1 className="text-8xl font-bold tracking-wider" style={{
                textShadow: '0 0 20px #ff0080, 0 0 40px #ff0080, 0 0 60px #ff0080',
                color: '#ffed4e'
              }}>
                BINGO
              </h1>
              <div className="absolute -bottom-2 left-0 right-0 h-1 bg-gradient-to-r from-red-500 via-yellow-500 to-purple-500 rounded"></div>
            </div>
          {/* NEW: Game ID input + Settings button */}
          <div className="flex items-center gap-4">
            <input
              type="text"
              value={gameId}
              onChange={(e) => setGameId(e.target.value)}
              className="px-3 py-2 rounded bg-black/50 border border-yellow-500 text-yellow-300 focus:outline-none focus:ring-2 focus:ring-yellow-400"
              placeholder="Game ID"
            />
            <button
              onClick={() => setView('admin')}
              className="px-6 py-3 bg-gradient-to-r from-yellow-400 to-yellow-600 text-black font-bold rounded-lg hover:from-yellow-300 hover:to-yellow-500 transition-all shadow-lg"
            >
              <Settings className="w-6 h-6" />
            </button>
          </div>
        </div>

          {gameState && (
            <>
              {/* Current Ball Display - Center Stage */}
              <div className="mb-12 flex justify-center">
                <div className="relative">
                  {/* Spotlight Effect */}
                  <div className="absolute inset-0 blur-3xl opacity-50 bg-gradient-to-r from-yellow-400 via-red-500 to-purple-500 animate-pulse"></div>
                  
                  <div className="relative bg-gradient-to-br from-gray-900 to-black border-4 border-yellow-500 rounded-3xl p-12 shadow-2xl">
                    {lastDrawn ? (
                      <div className="flex flex-col items-center space-y-4">
                        <div className="text-3xl font-bold text-yellow-400 tracking-wider">LAST CALLED</div>
                        <BingoBall number={lastDrawn} isAnimating={isDrawing} size="xlarge" />
                      </div>
                    ) : gameState.drawn.length > 0 ? (
                      <div className="flex flex-col items-center space-y-4">
                        <div className="text-3xl font-bold text-yellow-400 tracking-wider">CURRENT</div>
                        <BingoBall number={gameState.drawn[gameState.drawn.length - 1]} size="xlarge" />
                      </div>
                    ) : (
                      <div className="text-6xl font-bold text-gray-600">—</div>
                    )}
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

              {/* Bingo Board with Balls */}
              <div className="grid grid-cols-15 gap-2 mb-8">
                {['B', 'I', 'N', 'G', 'O'].map((letter, colIdx) => (
                  <React.Fragment key={letter}>
                    {Array.from({ length: 15 }, (_, i) => {
                      const num = colIdx * 15 + i + 1;
                      const drawn = gameState.drawn.includes(num);
                      const isLast = num === lastDrawn;
                      const { color } = getBingoLetter(num);
                      
                      return (
                        <div key={num} className="col-span-3 flex justify-center">
                          {drawn ? (
                            <BingoBall number={num} isAnimating={isLast} size="medium" />
                          ) : (
                            <div className="w-20 h-20 rounded-full bg-gray-800/50 border-2 border-gray-700 flex items-center justify-center text-gray-600 font-bold text-xl">
                              {num}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </React.Fragment>
                ))}
              </div>
            </>
          )}

          {celebrating && (
            <div className="fixed inset-0 flex items-center justify-center bg-black/80 backdrop-blur-sm z-40">
              <div className="text-center">
                <div className="animate-bounce">
                  <Crown className="w-32 h-32 mx-auto mb-6 text-yellow-400" style={{
                    filter: 'drop-shadow(0 0 20px #ffd700)'
                  }} />
                </div>
                <h2 className="text-9xl font-bold text-yellow-400 mb-4 animate-pulse" style={{
                  textShadow: '0 0 30px #ffd700, 0 0 60px #ffd700'
                }}>
                  BINGO!
                </h2>
                <p className="text-4xl text-white animate-pulse">We have a winner!</p>
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

              {/* Last Drawn Display in Admin */}
              {lastDrawn && (
                <div className="bg-gradient-to-r from-purple-100 to-blue-100 rounded-lg p-4 border-2 border-purple-300">
                  <div className="text-center">
                    <div className="text-sm font-semibold text-gray-600 mb-2">Last Drawn</div>
                    <div className="flex justify-center">
                      <BingoBall number={lastDrawn} size="medium" />
                    </div>
                  </div>
                </div>
              )}

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
            
            <div className="space-y-4">
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
                  onChange={e => setCustomCount(parseInt(e.target.value) || 1)}
                  min={1}
                  max={200}
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
                    <h3 className="font-semibold">Generated Cards ({generatedCards.length})</h3>
                    <button
                      onClick={() => window.print()}
                      className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
                    >
                      Print All
                    </button>
                  </div>

                  <div className="space-y-2">
                    {generatedCards.map(card => (
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
                              {["B","I","N","G","O"].map((letter, idx) => {
                                const colors = ['bg-red-500', 'bg-blue-500', 'bg-yellow-500', 'bg-green-500', 'bg-purple-500'];
                                return (
                                  <div key={letter} className={`${colors[idx]} text-white text-center font-bold p-1`}>
                                    {letter}
                                  </div>
                                );
                              })}
                              {card.grid.flat().map((cell, i) => (
                                <div
                                  key={i}
                                  className={`border text-center p-2 ${cell === "FREE" ? "bg-yellow-200 font-bold" : ""}`}
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
            </div>
          )}
        </div>
      </div>

      {/* Hidden print area */}
      <div id="print-area" className="hidden print:block">
        <div className="grid grid-cols-2 gap-4">
          {generatedCards.map(card => (
            <div
              key={card.public_id}
              className="border p-4 shadow break-inside-avoid"
            >
              <div className="font-bold text-center mb-2">
                Card ID: {card.public_id}
              </div>
              <div className="grid grid-cols-5 gap-1">
                {["B","I","N","G","O"].map((letter, idx) => {
                  const colors = ['bg-red-500', 'bg-blue-500', 'bg-yellow-500', 'bg-green-500', 'bg-purple-500'];
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
    </div>
  );
};

export default BingoApp;
const api = (path, opts={}) => fetch(`http://localhost:8000${path}`, {
  headers: { "Content-Type": "application/json" },
  ...opts
}).then(r => r.json());

const gameIdEl = document.getElementById('gameId');
const startBtn = document.getElementById('start');
const drawBtn = document.getElementById('draw');
const goalEl = document.getElementById('goal');
const drawnEl = document.getElementById('drawn');
const serialEl = document.getElementById('serial');
const checkBtn = document.getElementById('check');
const verdictEl = document.getElementById('verdict');
const cardEl = document.getElementById('card');
const winSound = document.getElementById('winSound');
const failSound = document.getElementById('failSound');

function renderDrawn(draws) {
  drawnEl.innerHTML = '';
  draws.forEach((n, i) => {
    const d = document.createElement('div');
    d.className = 'ball' + (i === draws.length - 1 ? ' new' : '');
    d.textContent = n;
    drawnEl.appendChild(d);
  });
}

function renderGoal(state) {
  if (state.mode === 'progressive_rows') {
    goalEl.textContent = `Current goal: ${state.stage} row(s)`;
  } else {
    goalEl.textContent = `Mode: ${state.mode}`;
  }
}

function renderCard(grid, draws) {
  cardEl.innerHTML = '';
  const g = document.createElement('div');
  g.className = 'grid';
  grid.forEach(row => {
    row.forEach(cell => {
      const c = document.createElement('div');
      c.className = 'cell' + ((cell === 'FREE' || draws.includes(cell)) ? ' marked' : '');
      c.textContent = cell === 'FREE' ? '★' : cell;
      g.appendChild(c);
    });
  });
  cardEl.appendChild(g);
}

startBtn.onclick = async () => {
  const game_id = gameIdEl.value;
  await api(`/games/${game_id}/start`, {
    method: 'POST',
    body: JSON.stringify({ mode: "progressive_rows", ball_set: 75, stage: 1 })
  });
  const state = await api(`/games/${game_id}/state`);
  renderDrawn(state.drawn);
  renderGoal(state);
};

drawBtn.onclick = async () => {
  const game_id = gameIdEl.value;
  await api(`/games/${game_id}/draw`, { method: 'POST' });
  const state = await api(`/games/${game_id}/state`);
  renderDrawn(state.drawn);
};

checkBtn.onclick = async () => {
  const game_id = gameIdEl.value;
  const serial = serialEl.value.trim();
  if (!serial) return;
  const res = await api(`/validate`, {
    method: 'POST',
    body: JSON.stringify({ game_id, serial })
  });
  renderCard(res.grid, res.drawn);
  verdictEl.className = 'verdict ' + (res.valid ? 'win' : 'fail');
  verdictEl.textContent = res.valid ? 'BINGO!' : 'Not yet';
  if (res.valid) {
    winSound.play();
    launchConfetti();
  } else {
    failSound.play();
  }
};

// Simple confetti effect
function launchConfetti() {
  const canvas = document.getElementById('confetti');
  const ctx = canvas.getContext('2d');
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  const pieces = Array.from({length: 100}, () => ({
    x: Math.random()*canvas.width,
    y: Math.random()*canvas.height - canvas.height,
    size: Math.random()*6+4,
    color: `hsl(${Math.random()*360},100%,50%)`,
    speed: Math.random()*3+2
  }));
  function draw() {
    ctx.clearRect(0,0,canvas.width,canvas.height);
    pieces.forEach(p => {
      ctx.fillStyle = p.color;
      ctx.fillRect(p.x,p.y,p.size,p.size);
      p.y += p.speed;
      if (p.y > canvas.height) p.y = -10;
    });
    requestAnimationFrame(draw);
  }
  draw();
  setTimeout(()=>ctx.clearRect(0,0,canvas.width,canvas.height), 5000);
}

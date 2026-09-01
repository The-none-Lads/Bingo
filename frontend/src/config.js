// src/config.js
const raw = window.__CONFIG__ || {};

export const config = {
  apiBaseUrl: raw.apiBaseUrl || 'http://localhost:8000',
  wsBaseUrl: raw.wsBaseUrl || 'ws://localhost:8000/ws',
  pollInterval: parseInt(raw.pollInterval || '20000', 10),
  cardFetchInterval: parseInt(raw.cardFetchInterval || '300000', 10),
  gameIdDefault: raw.gameIdDefault || 'demo',
  enableCelebration: raw.enableCelebration !== 'false',
  confettiDuration: parseInt(raw.confettiDuration || '5000', 10)
};


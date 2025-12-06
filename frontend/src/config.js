// src/config.js
const raw = window.__CONFIG__ || {};

export const config = {
  apiBaseUrl: raw.apiBaseUrl || '/',
  wsBaseUrl: raw.wsBaseUrl || 'ws://localhost:8000',
  pollInterval: parseInt(raw.pollInterval || '20000', 10),
  cardFetchInterval: parseInt(raw.cardFetchInterval || '300000', 10),
  gameIdDefault: raw.gameIdDefault || 'demo',
  enableCelebration: raw.enableCelebration === 'true',
  confettiDuration: parseInt(raw.confettiDuration || '5000', 10)
};

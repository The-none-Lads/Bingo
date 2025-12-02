// frontend/src/config.js
// This fetches configuration from the backend at runtime
let configCache = null;
let configPromise = null;

async function fetchConfig() {
  // Use relative URL so it works regardless of deployment
  const response = await fetch('/api/config');
  if (!response.ok) {
    throw new Error('Failed to fetch configuration');
  }
  return response.json();
}

export async function getConfig() {
  if (configCache) {
    return configCache;
  }

  if (configPromise) {
    return configPromise;
  }

  configPromise = fetchConfig().then(config => {
    configCache = config;
    configPromise = null;
    return config;
  }).catch(error => {
    console.error('Failed to load config, using defaults:', error);
    configPromise = null;
    // Return sensible defaults if backend is not available
    return {
      apiBaseUrl: '/api',
      wsBaseUrl: window.location.protocol === 'https:' 
        ? `wss://${window.location.host}/api` 
        : `ws://${window.location.host}/api`,
      pollInterval: 20000,
      reconnectDelay: 3000,
      cardFetchInterval: 300000,
      defaultCardCount: 50,
      enableCelebration: true,
      confettiDuration: 5000,
      gameIdDefault: 'demo'
    };
  });

  return configPromise;
}

// For development, you can override with environment variables
export function getConfigSync() {
  if (!configCache) {
    console.warn('Config not loaded yet, using defaults');
    return {
      apiBaseUrl: '/api',
      wsBaseUrl: window.location.protocol === 'https:' 
        ? `wss://${window.location.host}/api` 
        : `ws://${window.location.host}/api`,
      pollInterval: 20000,
      reconnectDelay: 3000,
      cardFetchInterval: 300000,
      defaultCardCount: 50,
      enableCelebration: true,
      confettiDuration: 5000,
      gameIdDefault: 'demo'
    };
  }
  return configCache;
}
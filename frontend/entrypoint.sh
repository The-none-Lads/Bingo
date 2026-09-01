#!/bin/sh
# Populate environment variables for template substitution with fallbacks
export API_BASE_URL="${API_BASE_URL:-${apiBaseUrl:-http://localhost:8000}}"
export WS_BASE_URL="${WS_BASE_URL:-${wsBaseUrl:-ws://localhost:8000/ws}}"
export POLL_INTERVAL="${POLL_INTERVAL:-${pollInterval:-20000}}"
export CARD_FETCH_INTERVAL="${CARD_FETCH_INTERVAL:-${cardFetchInterval:-300000}}"
export GAME_ID_DEFAULT="${GAME_ID_DEFAULT:-${gameIdDefault:-demo}}"
export ENABLE_CELEBRATION="${ENABLE_CELEBRATION:-${enableCelebration:-true}}"
export CONFETTI_DURATION="${CONFETTI_DURATION:-${confettiDuration:-5000}}"

# Replace placeholders in config.template.js with environment variables
if [ -f /usr/share/nginx/html/config.template.js ]; then
  envsubst '${API_BASE_URL} ${WS_BASE_URL} ${POLL_INTERVAL} ${CARD_FETCH_INTERVAL} ${GAME_ID_DEFAULT} ${ENABLE_CELEBRATION} ${CONFETTI_DURATION}' \
    < /usr/share/nginx/html/config.template.js > /usr/share/nginx/html/config.js
fi

# Start Nginx
exec "$@"


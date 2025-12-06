#!/bin/sh
# Replace placeholders in config.template.js with environment variables
if [ -f /usr/share/nginx/html/config.template.js ]; then
  envsubst < /usr/share/nginx/html/config.template.js > /usr/share/nginx/html/config.js
fi

# Start Nginx
exec "$@"

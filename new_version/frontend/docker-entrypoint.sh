#!/bin/sh
set -e

# Runtime environment variable substitution
# This allows changing env vars at container runtime

# Find and replace environment placeholders in built JS files
if [ -n "$VITE_API_URL" ]; then
    find /usr/share/nginx/html -name "*.js" -exec sed -i "s|__VITE_API_URL__|$VITE_API_URL|g" {} \;
fi

# Execute the main command
exec "$@"

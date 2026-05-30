# Webapp Dockerfile
# Multi-stage build with dev target for hot reload

FROM node:24-alpine AS base

ARG USER_ID
ARG USER_GID

WORKDIR /app

# Create non-root user with configurable USER_ID/USER_GID
# Handle case where GID already exists (e.g., GID 1000 is 'node' in Alpine)
RUN addgroup -g ${USER_GID} worker 2>/dev/null || true && \
    adduser -u ${USER_ID} -G $(getent group ${USER_GID} | cut -d: -f1) -D worker 2>/dev/null || true

# Install pnpm
RUN npm install -g pnpm@10.23.0

# Copy monorepo configuration
COPY pnpm-workspace.yaml /app/pnpm-workspace.yaml
COPY package.json /app/package.json
COPY pnpm-lock.yaml /app/pnpm-lock.yaml

# Copy webapp code
COPY webapp /app/webapp

FROM base AS build

# Install all dependencies
RUN pnpm -r install --frozen-lockfile
# Build the webapp
RUN pnpm --filter webapp run build

# Development stage with hot reload
FROM base AS dev

# Install all dependencies
RUN pnpm -r install --frozen-lockfile

# Expose Vite dev server port
EXPOSE 3000

# Change ownership and switch to non-root user
RUN chown -R ${USER_ID}:${USER_GID} /app
USER ${USER_ID}

# Run development server for webapp
# Vite will build to dist/ which is mounted to host
CMD ["pnpm", "--parallel", "--filter", "webapp", "run", "dev"]
FROM nginx:alpine AS prod

ARG USER_ID
ARG USER_GID

# Create non-root user with configurable USER_ID/USER_GID
RUN addgroup -g ${USER_GID} worker 2>/dev/null || true && \
    adduser -u ${USER_ID} -G $(getent group ${USER_GID} | cut -d: -f1) -D worker 2>/dev/null || true

# Copy built application from build stage
COPY --from=build /app/webapp/dist /usr/share/nginx/html

# Create a simple nginx configuration for SPA (listen on port 8080 for non-root)
RUN echo 'server {' > /etc/nginx/conf.d/default.conf && \
  echo '    listen 8080;' >> /etc/nginx/conf.d/default.conf && \
  echo '    listen [::]:8080;' >> /etc/nginx/conf.d/default.conf && \
  echo '    server_name localhost;' >> /etc/nginx/conf.d/default.conf && \
  echo '    root /usr/share/nginx/html;' >> /etc/nginx/conf.d/default.conf && \
  echo '    index index.html;' >> /etc/nginx/conf.d/default.conf && \
  echo '    location / {' >> /etc/nginx/conf.d/default.conf && \
  echo '        try_files $uri $uri/ /index.html;' >> /etc/nginx/conf.d/default.conf && \
  echo '    }' >> /etc/nginx/conf.d/default.conf && \
  echo '    # Security headers' >> /etc/nginx/conf.d/default.conf && \
  echo '    add_header X-Content-Type-Options nosniff;' >> /etc/nginx/conf.d/default.conf && \
  echo '    add_header X-Frame-Options DENY;' >> /etc/nginx/conf.d/default.conf && \
  echo '    add_header X-XSS-Protection "1; mode=block";' >> /etc/nginx/conf.d/default.conf && \
  echo '    # Gzip compression' >> /etc/nginx/conf.d/default.conf && \
  echo '    gzip on;' >> /etc/nginx/conf.d/default.conf && \
  echo '    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;' >> /etc/nginx/conf.d/default.conf && \
  echo '}' >> /etc/nginx/conf.d/default.conf

# Configure nginx to run as non-root user
# Move pid file to a location writable by non-root user
RUN sed -i 's/user  nginx;/user  worker;/' /etc/nginx/nginx.conf && \
    sed -i 's|/run/nginx.pid|/tmp/nginx.pid|' /etc/nginx/nginx.conf && \
    chown -R ${USER_ID}:${USER_GID} /var/cache/nginx /var/log/nginx /etc/nginx/conf.d

# Expose port 8080 (non-privileged port)
EXPOSE 8080

# Switch to non-root user
USER ${USER_ID}

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
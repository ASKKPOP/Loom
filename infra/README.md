# nginx — port 80 reverse proxy

## Install

```bash
brew install nginx
```

## Run with this config

```bash
# Copy config (or symlink)
cp infra/nginx.conf /usr/local/etc/nginx/nginx.conf

# Test config
nginx -t

# Start
brew services start nginx

# Or one-shot (foreground, easy to stop with Ctrl-C)
nginx -c $(pwd)/infra/nginx.conf
```

## Port 80 on macOS

macOS blocks ports <1024 for non-root processes. Options:

```bash
# Option A — run as root (simplest)
sudo nginx -c $(pwd)/infra/nginx.conf

# Option B — use brew services (runs under launchd with proper permissions)
sudo brew services start nginx
```

## Production mode

1. Build the web app: `cd loom/web && pnpm build`
2. In `nginx.conf`, uncomment the `PROD` block and comment the `DEV` block.
3. Set `root` to the absolute path of `loom/web/dist`.
4. Restart nginx.

## Service URLs (after nginx is running)

| Service | URL |
|---|---|
| Web UI | http://localhost |
| Chat API | http://localhost/v1/chat/completions |
| Models | http://localhost/v1/models |
| Admin | http://localhost/api/admin/* |
| Health | http://localhost/health |

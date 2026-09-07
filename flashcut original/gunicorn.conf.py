# gunicorn.conf.py — Production WSGI config for Render
import os

# ── Binding ───────────────────────────────────────────────
port = int(os.environ.get('PORT', 10000))
bind = f'0.0.0.0:{port}'

# ── Workers ───────────────────────────────────────────────
workers     = 2          # Keep low for Render free tier (512 MB RAM)
worker_class = 'sync'
threads     = 2
timeout     = 120        # Long timeout for file uploads
keepalive   = 5

# ── Logging ───────────────────────────────────────────────
accesslog  = '-'         # stdout
errorlog   = '-'         # stderr
loglevel   = 'info'

# ── App preloading ────────────────────────────────────────
preload_app = True

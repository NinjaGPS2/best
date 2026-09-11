import os

# Gunicorn configuration for Railway / Render / Production deployments
port = os.environ.get("PORT", "5000")
bind = f"0.0.0.0:{port}"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = int(os.environ.get("PYTHON_GET_THREADS", "2"))
timeout = 120
accesslog = "-"
errorlog = "-"
capture_output = True

import sys
import os

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from database import init_db
from app import app

if __name__ == '__main__':
    print("=" * 60)
    print("EDC Electricity Billing & Management System")
    print("Server running at: http://127.0.0.1:5000")
    print("=" * 60)
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=False)

"""Make ``app.*`` importable in API tests.

The FastAPI app under apps/api is not pip-installed; uvicorn runs it with ``--app-dir apps/api``.
Put that directory on sys.path so ``from app.core import whatsapp_meta`` resolves under pytest.
"""

import sys
from pathlib import Path

_API_DIR = Path(__file__).resolve().parents[1]  # apps/api
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

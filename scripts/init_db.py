import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.append(str(ROOT))

from app.db import Base, engine  # noqa: E402
from app import models  # noqa: F401,E402

Base.metadata.create_all(bind=engine)
print("Database initialized")

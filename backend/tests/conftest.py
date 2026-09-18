import os
import tempfile

# Configure before the app is imported: in-memory DB, throwaway uploads, no external AI.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="w2w")
os.environ["VAKH_TOKEN_FILE"] = os.path.join(os.environ["UPLOAD_DIR"], "none.json")
os.environ["VISION_PROVIDER"] = "mock"
os.environ["ELEVENLABS_API_KEY"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from scripts import seed  # noqa: E402


@pytest.fixture
def client():
    seed.run(do_reset=True)
    with TestClient(app) as c:
        yield c

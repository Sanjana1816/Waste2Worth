import logging
import time
from collections.abc import Iterator

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

log = logging.getLogger(__name__)


def normalise_url(url: str) -> str:
    """Supabase/Railway give postgres:// or postgresql:// URLs; SQLAlchemy needs the psycopg driver named."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def make_engine(url: str):
    url = normalise_url(url)
    if url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
        return create_engine(url, **kwargs)
    # Supabase's pooler closes idle connections, so check a connection before use and recycle often.
    return create_engine(
        url, pool_pre_ping=True, pool_recycle=280, pool_size=5, max_overflow=5,
        connect_args={"connect_timeout": 10, "keepalives": 1, "keepalives_idle": 30,
                      "keepalives_interval": 10, "keepalives_count": 3},
    )


engine = make_engine(settings.database_url)
db_ready = False


def init_db(eng=None, attempts: int = 5, delay: float = 2.0) -> bool:
    """Create missing tables, retrying briefly: a managed database can be unreachable for a few
    seconds (restart, pooler hiccup) and the API should wait rather than refuse to start."""
    global db_ready
    from app import models  # noqa: F401  (register tables)
    for attempt in range(1, attempts + 1):
        try:
            SQLModel.metadata.create_all(eng or engine)
            db_ready = True
            return True
        except SQLAlchemyError as e:
            log.warning("database not ready (attempt %s/%s): %s", attempt, attempts, str(e).splitlines()[0])
            if attempt < attempts:
                time.sleep(delay * attempt)
    db_ready = False
    return False


def get_session() -> Iterator[Session]:
    if not db_ready:          # first request after a failed start: try once more
        init_db(attempts=1)
    with Session(engine) as session:
        yield session

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import Pool, PoolItem
from app.schemas import PoolRequest
from app.services import pooling

router = APIRouter(prefix="/api/pools", tags=["pooled lots"])


def _pool_out(session: Session, pool: Pool) -> dict:
    items = session.exec(select(PoolItem).where(PoolItem.pool_id == pool.id)).all()
    return {**pool.model_dump(), "items": [i.model_dump() for i in items]}


@router.post("/quote")
def quote(body: PoolRequest, session: Session = Depends(get_session)):
    """Preview a pooled order. Nothing is reserved yet."""
    pooling.release_expired(session)
    return pooling.quote(session, body)


@router.post("", status_code=201)
def reserve(body: PoolRequest, session: Session = Depends(get_session)):
    """Reserve every lot in the pool at once (all or nothing) for a limited time."""
    return _pool_out(session, pooling.reserve(session, body))


@router.get("/{pool_id}")
def get_pool(pool_id: int, session: Session = Depends(get_session)):
    pooling.release_expired(session)
    pool = session.get(Pool, pool_id)
    if not pool:
        raise HTTPException(404, "pool not found")
    return _pool_out(session, pool)


@router.post("/{pool_id}/confirm")
def confirm(pool_id: int, session: Session = Depends(get_session)):
    pool = session.get(Pool, pool_id)
    if not pool:
        raise HTTPException(404, "pool not found")
    return _pool_out(session, pooling.confirm(session, pool))


@router.post("/{pool_id}/cancel")
def cancel(pool_id: int, session: Session = Depends(get_session)):
    pool = session.get(Pool, pool_id)
    if not pool:
        raise HTTPException(404, "pool not found")
    return _pool_out(session, pooling.cancel(session, pool))

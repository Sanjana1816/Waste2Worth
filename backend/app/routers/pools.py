from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import Pool, PoolItem, utcnow
from app.schemas import PoolRequest
from app.services import pooling, tracking as track

router = APIRouter(prefix="/api/pools", tags=["pooled lots"])


def _pool(session: Session, pool_id: int) -> Pool:
    pool = session.get(Pool, pool_id)
    if not pool:
        raise HTTPException(404, "pool not found")
    return pool


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


@router.get("/{pool_id}/tracking")
def tracking(pool_id: int, session: Session = Depends(get_session)):
    """Where the van is in the pickup run: stops in route order, progress and ETA."""
    return track.tracking(session, _pool(session, pool_id))


@router.post("/{pool_id}/stops/{listing_id}/collected")
def collect_stop(pool_id: int, listing_id: int, session: Session = Depends(get_session)):
    """Mark one seller's lot as picked up (the driver does this in the app)."""
    pool = _pool(session, pool_id)
    if pool.status not in ("confirmed", "out_for_pickup"):
        raise HTTPException(409, f"order is {pool.status}")
    item = session.exec(select(PoolItem).where(PoolItem.pool_id == pool_id,
                                               PoolItem.listing_id == listing_id)).first()
    if not item:
        raise HTTPException(404, "that lot is not part of this order")
    if not item.picked_up_at:
        item.picked_up_at = utcnow()
        session.add(item)
    pool.status = "out_for_pickup"
    session.add(pool)
    session.commit()
    return track.tracking(session, pool)


@router.post("/{pool_id}/delivered")
def deliver(pool_id: int, session: Session = Depends(get_session)):
    """Everything collected and handed to the buyer."""
    pool = _pool(session, pool_id)
    if pool.status not in ("confirmed", "out_for_pickup"):
        raise HTTPException(409, f"order is {pool.status}")
    now = utcnow()
    for item in session.exec(select(PoolItem).where(PoolItem.pool_id == pool_id)).all():
        if not item.picked_up_at:
            item.picked_up_at = now
            session.add(item)
    pool.status, pool.delivered_at = "delivered", now
    session.add(pool)
    session.commit()
    return track.tracking(session, pool)


@router.post("/{pool_id}/cancel")
def cancel(pool_id: int, session: Session = Depends(get_session)):
    pool = session.get(Pool, pool_id)
    if not pool:
        raise HTTPException(404, "pool not found")
    return _pool_out(session, pooling.cancel(session, pool))

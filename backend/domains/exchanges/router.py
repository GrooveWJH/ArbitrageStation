"""Exchange domain routes."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from db.models import Exchange
from domains.exchanges.service import default_is_unified_account, get_supported_exchanges, invalidate_instance

router = APIRouter(prefix="/api/exchanges", tags=["exchanges"])


class ExchangeCreate(BaseModel):
    name: str
    display_name: Optional[str] = None
    api_key: Optional[str] = ""
    api_secret: Optional[str] = ""
    passphrase: Optional[str] = ""
    is_testnet: bool = False
    is_unified_account: Optional[bool] = None


class ExchangeUpdate(BaseModel):
    display_name: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    passphrase: Optional[str] = None
    is_active: Optional[bool] = None
    is_testnet: Optional[bool] = None
    is_unified_account: Optional[bool] = None


@router.get("/supported")
def list_supported_exchanges():
    return get_supported_exchanges()


@router.get("/")
def list_exchanges(db: Session = Depends(get_db)):
    exchanges = db.query(Exchange).all()
    return [
        {
            "id": e.id,
            "name": e.name,
            "display_name": e.display_name or e.name,
            "is_active": e.is_active,
            "is_testnet": e.is_testnet,
            "is_unified_account": (
                bool(e.is_unified_account)
                if e.is_unified_account is not None
                else default_is_unified_account(e.name)
            ),
            "has_api_key": bool(e.api_key),
            "created_at": e.created_at,
        }
        for e in exchanges
    ]


@router.post("/")
def add_exchange(body: ExchangeCreate, db: Session = Depends(get_db)):
    existing = db.query(Exchange).filter(Exchange.name == body.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Exchange '{body.name}' already added")
    ex = Exchange(
        name=body.name,
        display_name=body.display_name or body.name.upper(),
        api_key=body.api_key or "",
        api_secret=body.api_secret or "",
        passphrase=body.passphrase or "",
        is_testnet=body.is_testnet,
        is_unified_account=(
            body.is_unified_account
            if body.is_unified_account is not None
            else default_is_unified_account(body.name)
        ),
    )
    db.add(ex)
    db.commit()
    db.refresh(ex)
    return {"success": True, "id": ex.id}


@router.put("/{exchange_id}")
def update_exchange(exchange_id: int, body: ExchangeUpdate, db: Session = Depends(get_db)):
    ex = db.query(Exchange).filter(Exchange.id == exchange_id).first()
    if not ex:
        raise HTTPException(status_code=404, detail="Exchange not found")
    if body.display_name is not None:
        ex.display_name = body.display_name
    if body.api_key is not None:
        ex.api_key = body.api_key
    if body.api_secret is not None:
        ex.api_secret = body.api_secret
    if body.passphrase is not None:
        ex.passphrase = body.passphrase
    if body.is_active is not None:
        ex.is_active = body.is_active
    if body.is_testnet is not None:
        ex.is_testnet = body.is_testnet
    if body.is_unified_account is not None:
        ex.is_unified_account = body.is_unified_account
    invalidate_instance(exchange_id)
    db.commit()
    return {"success": True}


@router.delete("/{exchange_id}")
def delete_exchange(exchange_id: int, db: Session = Depends(get_db)):
    ex = db.query(Exchange).filter(Exchange.id == exchange_id).first()
    if not ex:
        raise HTTPException(status_code=404, detail="Exchange not found")
    invalidate_instance(exchange_id)
    db.delete(ex)
    db.commit()
    return {"success": True}


__all__ = ["router"]

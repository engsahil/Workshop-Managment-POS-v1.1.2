"""Point of sale."""
from fastapi import APIRouter, Depends

from ..core.deps import get_current_user, get_db, require_pos
from ..models import User
from ..schemas.invoices import InvoiceCreateIn
from ..services import invoice_service

router = APIRouter(prefix="/api/pos", tags=["pos"])


@router.get("/search")
def search(q: str = "", limit: int = 20, db=Depends(get_db),
           _: User = Depends(require_pos)):
    return invoice_service.search_items(db, q, limit)


@router.post("/invoices")
def create_invoice(payload: InvoiceCreateIn, db=Depends(get_db),
                   user: User = Depends(require_pos)):
    try:
        return invoice_service.create_invoice(db, payload.model_dump(), user)
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail=str(e))

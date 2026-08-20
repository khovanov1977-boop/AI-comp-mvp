from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.character import Character
from app.models.memory import Memory
from app.schemas.memory import MEMORY_CATEGORIES, MemoryCreate, MemoryRead, MemoryUpdate

router = APIRouter(prefix="/memories", tags=["memories"])


@router.post("", response_model=MemoryRead)
def create_memory(payload: MemoryCreate, db: Session = Depends(get_db)) -> MemoryRead:
    character = db.get(Character, payload.character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    if payload.memory_type not in MEMORY_CATEGORIES:
        raise HTTPException(status_code=400, detail="Unsupported memory category")

    memory = Memory(
        character_id=payload.character_id,
        memory_type=payload.memory_type,
        content=payload.content.strip(),
        importance=max(1, min(payload.importance, 5)),
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


@router.patch("/{memory_id}", response_model=MemoryRead)
def update_memory(memory_id: str, payload: MemoryUpdate, db: Session = Depends(get_db)) -> MemoryRead:
    memory = db.get(Memory, memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    if payload.memory_type is not None:
        if payload.memory_type not in MEMORY_CATEGORIES:
            raise HTTPException(status_code=400, detail="Unsupported memory category")
        memory.memory_type = payload.memory_type

    if payload.content is not None:
        content = payload.content.strip()
        if not content:
            raise HTTPException(status_code=400, detail="Memory content cannot be empty")
        memory.content = content

    if payload.importance is not None:
        memory.importance = max(1, min(payload.importance, 5))

    db.commit()
    db.refresh(memory)
    return memory


@router.delete("/{memory_id}")
def delete_memory(memory_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    memory = db.get(Memory, memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    db.delete(memory)
    db.commit()
    return {"status": "deleted"}

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.preference import UserPreference
from app.schemas.preference import PreferenceUpdate, PreferenceResponse

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("/{user_id}", response_model=PreferenceResponse)
async def get_preferences(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == user_id)
    )
    pref = result.scalar_one_or_none()
    if not pref:
        raise HTTPException(status_code=404, detail="Preferences not found")
    return pref


@router.put("/{user_id}", response_model=PreferenceResponse)
async def upsert_preferences(
    user_id: str,
    payload: PreferenceUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == user_id)
    )
    pref = result.scalar_one_or_none()

    if not pref:
        pref = UserPreference(id=str(uuid.uuid4()), user_id=user_id)
        db.add(pref)

    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(pref, key, value)

    await db.commit()
    await db.refresh(pref)
    return pref
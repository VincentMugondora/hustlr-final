"""
Unit-style tests for admin route handlers with async Mongo interactions.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import HTTPException

from backend.models import ProviderVerificationRequest
from backend.routes import admin


@pytest.mark.asyncio
async def test_admin_pending_providers_requires_admin(make_user):
    with pytest.raises(HTTPException) as exc:
        await admin.get_pending_providers(current_user=make_user("u1", "customer"))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_verify_provider_and_stats(fake_db, make_user):
    await fake_db.users.insert_one({"_id": "u-1", "phone_number": "+1", "role": "customer"})
    await fake_db.service_providers.insert_one(
        {
            "_id": "prov-pending-1",
            "user_id": "u-2",
            "service_type": "plumber",
            "location": "downtown",
            "is_verified": False,
            "verification_status": "pending",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    )

    result = await admin.verify_provider(
        provider_id="prov-pending-1",
        verification_request=ProviderVerificationRequest(verified=True, notes="All good"),
        current_user=make_user("admin-7", "admin"),
    )

    assert result["verification_status"] == "verified"

    updated = await fake_db.service_providers.find_one({"_id": "prov-pending-1"})
    assert updated["is_verified"] is True
    assert updated["verified_by"] == "admin-7"

    stats = await admin.get_system_stats(current_user=make_user("admin-7", "admin"))
    assert stats["total_users"] == 1
    assert stats["total_providers"] == 1
    assert stats["pending_providers"] == 0


@pytest.mark.asyncio
async def test_admin_verify_nonexistent_provider_raises_404(fake_db, make_user):
    with pytest.raises(HTTPException) as exc:
        await admin.verify_provider(
            provider_id="missing-provider",
            verification_request=ProviderVerificationRequest(verified=False, notes="not found"),
            current_user=make_user("admin-8", "admin"),
        )
    assert exc.value.status_code == 404

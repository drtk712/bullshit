"""Share rewards and check-in stay atomic inside the SQL functions."""
from __future__ import annotations

import pytest

from app.services.share_rewards import CheckInAlreadyDoneError, ShareRewardLimitError, ShareRewardService


def test_share_claim_stops_at_three_and_check_in_is_once_per_day(db):
    service = ShareRewardService(db)
    service.user_service.ensure_user("share-user")

    for _ in range(3):
        claimed = service.claim("share-user")
        assert claimed["pointsGained"] == 1

    with pytest.raises(ShareRewardLimitError):
        service.claim("share-user")

    user = db.find_one("users", {"openid": "share-user"})
    assert user is not None
    assert user["points"] == 6
    assert db.count_documents("point_transactions", {"openid": "share-user", "reason": "share_reward"}) == 3

    checked = service.check_in("share-user")
    assert checked["pointsGained"] == 1
    assert checked["points"] == 7
    with pytest.raises(CheckInAlreadyDoneError):
        service.check_in("share-user")
    assert db.find_one("users", {"openid": "share-user"})["points"] == 7
    assert db.count_documents("point_transactions", {"openid": "share-user", "reason": "daily_check_in"}) == 1

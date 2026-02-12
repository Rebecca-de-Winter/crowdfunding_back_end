# utils.py

from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce
from rest_framework.exceptions import ValidationError

from .models import MoneyPledge, Pledge, RewardTier


# =============================================================================
# MONEY REWARD TIER RECALC
# =============================================================================

def update_reward_tiers_for_supporter_and_fundraiser(supporter, fundraiser):
    """
    Recalculate the total MONEY this supporter has pledged to this fundraiser,
    then assign the highest qualifying MONEY RewardTier to all of their
    MONEY pledges on that fundraiser.

    Does NOT touch item/time reward tiers.
    """
    total_money = MoneyPledge.objects.filter(
        pledge__supporter=supporter,
        pledge__fundraiser=fundraiser,
    ).aggregate(
        total=Coalesce(Sum("amount"), Decimal("0"))
    )["total"]

    reward_tier = (
        RewardTier.objects.filter(
            fundraiser=fundraiser,
            reward_type="money",
            minimum_contribution_value__isnull=False,
            minimum_contribution_value__lte=total_money,
        )
        .order_by("-minimum_contribution_value", "-id")
        .first()
    )

    Pledge.objects.filter(
        supporter=supporter,
        fundraiser=fundraiser,
        money_detail__isnull=False,
    ).update(reward_tier=reward_tier)


# =============================================================================
# PLEDGE STATUS TRANSITION RULES
# =============================================================================

def ensure_allowed_transition(*, current, target, actor_role):
    """
    Enforce your business rules for pledge status changes.

    actor_role:
      - "supporter" (the person who made the pledge)
      - "owner" (the organiser/fundraiser owner)

    Rules you asked for:
      - Supporter can cancel ONLY if pledge is pending
      - Owner can cancel pending OR approved
      - Owner can approve/decline ONLY if pending
    """
    if actor_role == "supporter":
        if target == "cancelled":
            if current != "pending":
                raise ValidationError(
                    {"detail": "Supporters can only cancel pending pledges."}
                )
            return

        raise ValidationError({"detail": "Supporters cannot approve/decline pledges."})

    if actor_role == "owner":
        if target == "approved":
            if current != "pending":
                raise ValidationError({"detail": "Only pending pledges can be approved."})
            return

        if target == "declined":
            if current != "pending":
                raise ValidationError({"detail": "Only pending pledges can be declined."})
            return

        if target == "cancelled":
            if current not in ["pending", "approved"]:
                raise ValidationError(
                    {"detail": "Only pending or approved pledges can be cancelled."}
                )
            return

        raise ValidationError({"detail": "Unknown target status."})

    raise ValidationError({"detail": "Invalid actor role."})

from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce

from .models import MoneyPledge, Pledge, RewardTier


from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce

from .models import MoneyPledge, Pledge, RewardTier


def update_reward_tiers_for_supporter_and_fundraiser(supporter, fundraiser):
    """
    Recalculate the total MONEY this supporter has pledged to this fundraiser,
    then assign the highest qualifying MONEY RewardTier to all of their
    MONEY pledges on that fundraiser.

    Does NOT touch item/time reward tiers.
    """
    # 1. Total money for this supporter+fundraiser
    total_money = MoneyPledge.objects.filter(
        pledge__supporter=supporter,
        pledge__fundraiser=fundraiser,
    ).aggregate(
        total=Coalesce(Sum("amount"), Decimal("0"))
    )["total"]

    # 2. Pick the highest MONEY reward tier they qualify for
    reward_tier = (
        RewardTier.objects.filter(
            fundraiser=fundraiser,
            reward_type="money",                       # <-- ONLY money tiers
            minimum_contribution_value__isnull=False,
            minimum_contribution_value__lte=total_money,
        )
        .order_by("-minimum_contribution_value", "-id")
        .first()
    )

    # 3. Apply this tier ONLY to MONEY pledges
    Pledge.objects.filter(
        supporter=supporter,
        fundraiser=fundraiser,
        money_detail__isnull=False,                  # <-- ONLY money pledges
    ).update(reward_tier=reward_tier)


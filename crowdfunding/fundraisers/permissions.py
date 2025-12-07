from rest_framework import permissions
from .models import Fundraiser, Need, MoneyNeed, TimeNeed, ItemNeed, RewardTier


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    SAFE METHODS (GET / LIST) → allowed for anyone
    WRITE METHODS (PUT / POST / DELETE) → only fundraiser owner allowed
    """

    def has_object_permission(self, request, view, obj):

        # Always allow GET/SAFE reads
        if request.method in permissions.SAFE_METHODS:
            return True

        # --- Direct fundraiser ---
        if isinstance(obj, Fundraiser):
            return obj.owner == request.user

        # --- Need links back to Fundraiser ---
        if isinstance(obj, Need):
            return obj.fundraiser.owner == request.user

        # --- Detail models ---
        if isinstance(obj, (MoneyNeed, TimeNeed, ItemNeed)):
            return obj.need.fundraiser.owner == request.user

        # --- Reward tiers also belong to a fundraiser ---
        if isinstance(obj, RewardTier):
            return obj.fundraiser.owner == request.user

        return False   # default deny


class IsSupporterOrReadOnly(permissions.BasePermission):
    """
    SAFE METHODS allowed for anyone.
    Modifying allowed only by the pledge supporter.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.supporter == request.user

from rest_framework import permissions
from .models import (
    Fundraiser, Need, MoneyNeed, TimeNeed, ItemNeed, RewardTier,
    FundraiserTemplate, TemplateNeed, TemplateRewardTier, Pledge,
)

class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):

        if request.method in permissions.SAFE_METHODS:
            return True

        if not request.user or not request.user.is_authenticated:
            return False

        # Fundraiser + its related objects
        if isinstance(obj, Fundraiser):
            return obj.owner_id == request.user.id

        if isinstance(obj, Need):
            return obj.fundraiser.owner_id == request.user.id

        if isinstance(obj, (MoneyNeed, TimeNeed, ItemNeed)):
            return obj.need.fundraiser.owner_id == request.user.id

        if isinstance(obj, RewardTier):
            return obj.fundraiser.owner_id == request.user.id

        # Templates
        if isinstance(obj, FundraiserTemplate):
            return (obj.owner_id == request.user.id) or request.user.is_staff

        if isinstance(obj, (TemplateNeed, TemplateRewardTier)):
            return (obj.template.owner_id == request.user.id) or request.user.is_staff

        return False


class IsSupporterOrReadOnly(permissions.BasePermission):
    """
    SAFE METHODS allowed for anyone.
    Modifying allowed only by the pledge supporter.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(obj, "supporter_id", None) == request.user.id
    
    
from rest_framework import permissions

class IsAdminUserOrReadOnly(permissions.BasePermission):
    """
    SAFE METHODS: anyone
    WRITE METHODS: staff only
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)

class IsFundraiserOwner(permissions.BasePermission):
    """
    Object-level: user must be the fundraiser owner.
    Intended for Pledge approve/decline.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        # Expect obj is a Pledge (or anything with fundraiser.owner_id)
        fundraiser = getattr(obj, "fundraiser", None)
        if fundraiser is None:
            return False

        return fundraiser.owner_id == request.user.id


class IsSupporterOrFundraiserOwner(permissions.BasePermission):
    """
    Object-level: user is either the pledge supporter OR the fundraiser owner.
    Intended for Pledge cancel.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        supporter_id = getattr(obj, "supporter_id", None)

        fundraiser = getattr(obj, "fundraiser", None)
        owner_id = getattr(fundraiser, "owner_id", None) if fundraiser else None

        return (supporter_id == request.user.id) or (owner_id == request.user.id)

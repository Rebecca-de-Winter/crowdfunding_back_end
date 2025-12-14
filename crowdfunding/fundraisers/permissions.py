from rest_framework import permissions
from .models import (
    Fundraiser, Need, MoneyNeed, TimeNeed, ItemNeed, RewardTier,
    FundraiserTemplate, TemplateNeed, TemplateRewardTier,
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
        return obj.supporter == request.user
    
    
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


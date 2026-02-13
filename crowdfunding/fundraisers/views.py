from django.http import Http404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from django.db import transaction
from .utils import ensure_allowed_transition
from .permissions import IsFundraiserOwner, IsSupporterOrFundraiserOwner


from django.db.models import Sum, Count
from django.db.models.functions import Coalesce
from decimal import Decimal

from .models import (
    Fundraiser,
    Pledge,
    Need,
    RewardTier,
    MoneyNeed,
    TimeNeed,
    ItemNeed,
    MoneyPledge,
    TimePledge,
    ItemPledge,
    FundraiserTemplate,
    TemplateNeed,
    TemplateRewardTier,
)
from .serializers import (
    FundraiserSerializer,
    FundraiserDetailSerializer,
    PledgeSerializer,
    PledgeDetailSerializer,
    NeedSerializer,
    NeedDetailSerializer,
    RewardTierSerializer,
    MoneyNeedSerializer,
    TimeNeedSerializer,
    ItemNeedSerializer,
    MoneyPledgeSerializer,
    TimePledgeSerializer,
    ItemPledgeSerializer,
    FundraiserTemplateSerializer,
    TemplateNeedSerializer,         
    TemplateRewardTierSerializer,  
)
from .permissions import IsOwnerOrReadOnly, IsSupporterOrReadOnly, IsAdminUserOrReadOnly


# ====================================================================================
# FUNDRAISERS
# ====================================================================================

class FundraiserList(APIView):
    """
    List all fundraisers or create a new one.
    Any authenticated user can create a fundraiser; owner is set from request.user.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request):
        fundraisers = Fundraiser.objects.all()
        serializer = FundraiserSerializer(fundraisers, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = FundraiserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(owner=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FundraiserDetail(APIView):
    """
    Retrieve, update, or delete a single fundraiser.
    Only the owner can update/delete.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get_object(self, pk):
        try:
            fundraiser = Fundraiser.objects.get(pk=pk)
        except Fundraiser.DoesNotExist:
            raise Http404
        # object-level permission: IsOwnerOrReadOnly expects an .owner attr
        self.check_object_permissions(self.request, fundraiser)
        return fundraiser

    def get(self, request, pk):
        fundraiser = self.get_object(pk)
        serializer = FundraiserDetailSerializer(fundraiser, context={"request": request})
        return Response(serializer.data)

    def put(self, request, pk):
        fundraiser = self.get_object(pk)
        serializer = FundraiserDetailSerializer(
            instance=fundraiser,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        fundraiser = self.get_object(pk)
        # Simple domain rule: don't allow deleting a fundraiser that has pledges
        if fundraiser.pledges.exists():
            return Response(
                {"detail": "Cannot delete a fundraiser that already has pledges. "
                "Set status='cancelled' instead."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        fundraiser.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ====================================================================================
# PLEDGES (BASE)
# ====================================================================================

class PledgeList(APIView):
    """
    List all pledges or create a new pledge.

    GET supports filters:
    - /pledges/?fundraiser=8
    - /pledges/?need=5
    - /pledges/?status=pending
    - /pledges/?supporter=3
    - /pledges/?type=money|time|item

    Supporter is set from request.user on creation (POST).
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request):
        fundraiser_id = request.query_params.get("fundraiser")
        need_id = request.query_params.get("need")
        status_param = request.query_params.get("status")
        supporter_id = request.query_params.get("supporter")
        pledge_type = request.query_params.get("type")  # "money", "time", "item"

        qs = Pledge.objects.all().select_related("fundraiser", "need", "supporter", "reward_tier")

        if fundraiser_id:
            qs = qs.filter(fundraiser_id=fundraiser_id)

        if need_id:
            qs = qs.filter(need_id=need_id)

        if status_param:
            qs = qs.filter(status__iexact=status_param)

        if supporter_id:
            qs = qs.filter(supporter_id=supporter_id)

        # filter by whether it has money_detail / time_detail / item_detail
        if pledge_type:
            pledge_type = pledge_type.lower()
            if pledge_type == "money":
                qs = qs.filter(money_detail__isnull=False)
            elif pledge_type == "time":
                qs = qs.filter(time_detail__isnull=False)
            elif pledge_type == "item":
                qs = qs.filter(item_detail__isnull=False)

        serializer = PledgeSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

    def post(self, request):
        serializer = PledgeSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            pledge = serializer.save(supporter=request.user)

            # ✅ Decide whether this pledge starts as pending or approved,
            # based on the fundraiser's setting.
            fundraiser = pledge.fundraiser  # already a model instance
            # (optional but safest)
            fundraiser.refresh_from_db(fields=["require_pledge_approval"])


            if getattr(fundraiser, "require_pledge_approval", True):
                new_status = "pending"
            else:
                new_status = "approved"

            # Only write if it needs changing (avoids extra DB writes)
            if pledge.status != new_status:
                pledge.status = new_status
                pledge.save(update_fields=["status"])

            # return a fresh representation (with request context)
            out = PledgeSerializer(pledge, context={"request": request}).data
            return Response(out, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)





class PledgeDetail(APIView):
    """
    View, update, or delete a single pledge.
    Only the supporter can update/delete their pledge.
    Deletion is only allowed while status == "pending".
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsSupporterOrReadOnly]

    def get_object(self, pk):
        try:
            pledge = Pledge.objects.get(pk=pk)
        except Pledge.DoesNotExist:
            raise Http404
        # IsSupporterOrReadOnly expects an object with .supporter
        self.check_object_permissions(self.request, pledge)
        return pledge

    def get(self, request, pk):
        pledge = self.get_object(pk)
        serializer = PledgeDetailSerializer(pledge, context={"request": request})
        return Response(serializer.data)

    def put(self, request, pk):
        pledge = self.get_object(pk)
        serializer = PledgeDetailSerializer(
            instance=pledge,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    def delete(self, request, pk):
        pledge = self.get_object(pk)
        # Domain decision: only allow deleting pending pledges.
        if pledge.status != "pending":
            return Response(
                {"detail": "Only pending pledges can be deleted. "
                "Change status to 'cancelled' instead if you need to withdraw."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        pledge.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class PledgeCancel(APIView):
    
    permission_classes = [permissions.IsAuthenticated, IsSupporterOrFundraiserOwner]

    def post(self, request, pk):
        try:
            pledge = Pledge.objects.select_related("fundraiser", "supporter").get(pk=pk)
        except Pledge.DoesNotExist:
            raise Http404

        self.check_object_permissions(request, pledge)

        actor_role = "owner" if pledge.fundraiser.owner_id == request.user.id else "supporter"
        ensure_allowed_transition(current=pledge.status, target="cancelled", actor_role=actor_role)

        pledge.status = "cancelled"
        pledge.save(update_fields=["status"])
        return Response(PledgeDetailSerializer(pledge, context={"request": request}).data)


class PledgeApprove(APIView):

    permission_classes = [permissions.IsAuthenticated, IsFundraiserOwner]
    
    def post(self, request, pk):
        try:
            pledge = Pledge.objects.select_related("fundraiser", "supporter").get(pk=pk)
        except Pledge.DoesNotExist:
            raise Http404

        self.check_object_permissions(request, pledge)

        ensure_allowed_transition(current=pledge.status, target="approved", actor_role="owner")
        pledge.status = "approved"
        pledge.save(update_fields=["status"])
        return Response(PledgeDetailSerializer(pledge, context={"request": request}).data)


class PledgeDecline(APIView):

    permission_classes = [permissions.IsAuthenticated, IsFundraiserOwner]

    def post(self, request, pk):
        try:
            pledge = Pledge.objects.select_related("fundraiser", "supporter").get(pk=pk)
        except Pledge.DoesNotExist:
            raise Http404

        self.check_object_permissions(request, pledge)

        ensure_allowed_transition(current=pledge.status, target="declined", actor_role="owner")
        pledge.status = "declined"
        pledge.save(update_fields=["status"])
        return Response(PledgeDetailSerializer(pledge, context={"request": request}).data)

# ====================================================================================
# NEEDS (BASE)
# ====================================================================================

class NeedList(APIView):
    """
    List all needs or create a new base Need.

    GET supports filters via query params:
    - /needs/?fundraiser=8
    - /needs/?fundraiser=8&need_type=money
    - /needs/?fundraiser=8&status=pending

    Only the owner of the associated fundraiser can create needs for it (POST).
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get(self, request):
        fundraiser_id = request.query_params.get("fundraiser")
        need_type = request.query_params.get("need_type") or request.query_params.get("type")
        status_param = request.query_params.get("status")

        qs = Need.objects.all()

        if fundraiser_id:
            qs = qs.filter(fundraiser_id=fundraiser_id)

        if need_type:
            # normalise to lower-case, matches e.g. "money", "time", "item"
            qs = qs.filter(need_type__iexact=need_type)

        if status_param:
            qs = qs.filter(status__iexact=status_param)

        serializer = NeedSerializer(qs, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer = NeedSerializer(data=request.data)
        if serializer.is_valid():
            # Pull the fundraiser from the validated data
            fundraiser = serializer.validated_data.get("fundraiser")
            # Check that the current user owns this fundraiser
            self.check_object_permissions(request, fundraiser)

            # Now it's safe to create the Need
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class NeedDetail(APIView):
    """
    Retrieve, update, or delete a single Need.
    Only the owner of the related fundraiser can update/delete.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get_object(self, pk):
        try:
            need = Need.objects.get(pk=pk)
        except Need.DoesNotExist:
            raise Http404

        # Enforce IsOwnerOrReadOnly on the Need object
        self.check_object_permissions(self.request, need)
        return need

    def get(self, request, pk):
        need = self.get_object(pk)
        serializer = NeedDetailSerializer(need, context={"request": request})
        return Response(serializer.data)

    def put(self, request, pk):
        need = self.get_object(pk)
        serializer = NeedDetailSerializer(
            instance=need,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        need = self.get_object(pk)
        # Don't allow deleting a need that already has pledges
        if need.pledges.exists():
            return Response(
                {
                    "detail": "Cannot delete a need that already has pledges. "
                    "Set status='cancelled' instead."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        need.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)



# ====================================================================================
# REWARD TIERS (owned by fundraiser owner)
# ====================================================================================

class RewardTierList(APIView):
    """
    List all reward tiers or create a new one.
    Only the owner of the linked fundraiser can create.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get(self, request):
        tiers = RewardTier.objects.all()
        serializer = RewardTierSerializer(tiers, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = RewardTierSerializer(data=request.data)
        if serializer.is_valid():
            fundraiser = serializer.validated_data.get("fundraiser")
            self.check_object_permissions(request, fundraiser)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RewardTierDetail(APIView):
    """
    Retrieve, update, or delete a single reward tier.
    Only the owner of the linked fundraiser can update/delete.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get_object(self, pk):
        try:
            tier = RewardTier.objects.get(pk=pk)
        except RewardTier.DoesNotExist:
            raise Http404
        self.check_object_permissions(self.request, tier.fundraiser)
        return tier

    def get(self, request, pk):
        tier = self.get_object(pk)
        serializer = RewardTierSerializer(tier)
        return Response(serializer.data)

    def put(self, request, pk):
        tier = self.get_object(pk)
        serializer = RewardTierSerializer(
            instance=tier,
            data=request.data,
            partial=True,
        )
        if serializer.is_valid():
            fundraiser = serializer.validated_data.get("fundraiser", tier.fundraiser)
            self.check_object_permissions(request, fundraiser)
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        tier = self.get_object(pk)
        tier.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ====================================================================================
# NEED DETAIL MODELS (MoneyNeed / TimeNeed / ItemNeed)
# ====================================================================================

class MoneyNeedList(APIView):
    """
    List or create MoneyNeed rows.
    Only the owner of need.fundraiser can create.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get(self, request):
        money_needs = MoneyNeed.objects.all()
        serializer = MoneyNeedSerializer(money_needs, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = MoneyNeedSerializer(data=request.data)
        if serializer.is_valid():
            need = serializer.validated_data.get("need")
            self.check_object_permissions(request, need.fundraiser)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MoneyNeedDetail(APIView):
    """
    Retrieve, update, or delete a MoneyNeed.
    Only the owner of the linked fundraiser can change it.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get_object(self, pk):
        try:
            money_need = MoneyNeed.objects.get(pk=pk)
        except MoneyNeed.DoesNotExist:
            raise Http404
        self.check_object_permissions(self.request, money_need.need.fundraiser)
        return money_need

    def get(self, request, pk):
        money_need = self.get_object(pk)
        serializer = MoneyNeedSerializer(money_need)
        return Response(serializer.data)

    def put(self, request, pk):
        money_need = self.get_object(pk)
        serializer = MoneyNeedSerializer(
            instance=money_need,
            data=request.data,
            partial=True,
        )
        if serializer.is_valid():
            need = serializer.validated_data.get("need", money_need.need)
            self.check_object_permissions(request, need.fundraiser)
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        money_need = self.get_object(pk)
        money_need.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TimeNeedList(APIView):
    """
    List or create TimeNeed rows.
    Only the owner of need.fundraiser can create.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get(self, request):
        time_needs = TimeNeed.objects.all()
        serializer = TimeNeedSerializer(time_needs, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = TimeNeedSerializer(data=request.data)
        if serializer.is_valid():
            need = serializer.validated_data.get("need")
            # Owner check: use the fundraiser that owns this need
            self.check_object_permissions(request, need.fundraiser)
            time_need = serializer.save()
            return Response(TimeNeedSerializer(time_need).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TimeNeedDetail(APIView):
    """
    Retrieve, update, or delete a TimeNeed.
    Only the owner of the linked fundraiser can change it.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get_object(self, pk):
        try:
            time_need = TimeNeed.objects.get(pk=pk)
        except TimeNeed.DoesNotExist:
            raise Http404
        self.check_object_permissions(self.request, time_need.need.fundraiser)
        return time_need

    def get(self, request, pk):
        time_need = self.get_object(pk)
        serializer = TimeNeedSerializer(time_need)
        return Response(serializer.data)

    def put(self, request, pk):
        time_need = self.get_object(pk)
        serializer = TimeNeedSerializer(
            instance=time_need,
            data=request.data,
            partial=True,
        )
        if serializer.is_valid():
            need = serializer.validated_data.get("need", time_need.need)
            self.check_object_permissions(request, need.fundraiser)
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        time_need = self.get_object(pk)
        time_need.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ItemNeedList(APIView):
    """
    List or create ItemNeed rows.
    Only the owner of need.fundraiser can create.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get(self, request):
        item_needs = ItemNeed.objects.all()
        serializer = ItemNeedSerializer(item_needs, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ItemNeedSerializer(data=request.data)
        if serializer.is_valid():
            need = serializer.validated_data.get("need")
            self.check_object_permissions(request, need.fundraiser)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ItemNeedDetail(APIView):
    """
    Retrieve, update, or delete an ItemNeed.
    Only the owner of the linked fundraiser can change it.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get_object(self, pk):
        try:
            item_need = ItemNeed.objects.get(pk=pk)
        except ItemNeed.DoesNotExist:
            raise Http404
        self.check_object_permissions(self.request, item_need.need.fundraiser)
        return item_need

    def get(self, request, pk):
        item_need = self.get_object(pk)
        serializer = ItemNeedSerializer(item_need)
        return Response(serializer.data)

    def put(self, request, pk):
        item_need = self.get_object(pk)
        serializer = ItemNeedSerializer(
            instance=item_need,
            data=request.data,
            partial=True,
        )
        if serializer.is_valid():
            need = serializer.validated_data.get("need", item_need.need)
            self.check_object_permissions(request, need.fundraiser)
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        item_need = self.get_object(pk)
        item_need.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ====================================================================================
# PLEDGE DETAIL MODELS (MoneyPledge / TimePledge / ItemPledge)
# ====================================================================================

class MoneyPledgeList(APIView):
    """
    List or create MoneyPledge rows.
    Only the pledge supporter can create a money detail for their pledge.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsSupporterOrReadOnly]

    def get(self, request):
        money_pledges = MoneyPledge.objects.all()
        serializer = MoneyPledgeSerializer(money_pledges, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = MoneyPledgeSerializer(data=request.data)
        if serializer.is_valid():
            pledge = serializer.validated_data.get("pledge")
            # Guard using the pledge as the "supporter-owned" object
            self.check_object_permissions(request, pledge)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MoneyPledgeDetail(APIView):
    """
    Retrieve, update, or delete a MoneyPledge.
    Only the pledge supporter can change it.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsSupporterOrReadOnly]

    def get_object(self, pk):
        try:
            money_pledge = MoneyPledge.objects.get(pk=pk)
        except MoneyPledge.DoesNotExist:
            raise Http404
        self.check_object_permissions(self.request, money_pledge.pledge)
        return money_pledge

    def get(self, request, pk):
        money_pledge = self.get_object(pk)
        serializer = MoneyPledgeSerializer(money_pledge)
        return Response(serializer.data)

    def put(self, request, pk):
        money_pledge = self.get_object(pk)
        serializer = MoneyPledgeSerializer(
            instance=money_pledge,
            data=request.data,
            partial=True,
        )
        if serializer.is_valid():
            # Re-check supporter if pledge was changed (unlikely)
            pledge = serializer.validated_data.get("pledge", money_pledge.pledge)
            self.check_object_permissions(request, pledge)
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        money_pledge = self.get_object(pk)
        # Only allow deletion while pledge is still pending
        if money_pledge.pledge.status != "pending":
            return Response(
                {"detail": "Cannot delete money details for a non-pending pledge. "
                "Change pledge status to 'cancelled' instead."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        money_pledge.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TimePledgeList(APIView):
    """
    List or create TimePledge rows.
    Only the pledge supporter can create a time detail for their pledge.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsSupporterOrReadOnly]

    def get(self, request):
        time_pledges = TimePledge.objects.all()
        serializer = TimePledgeSerializer(time_pledges, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = TimePledgeSerializer(data=request.data)
        if serializer.is_valid():
            pledge = serializer.validated_data.get("pledge")
            self.check_object_permissions(request, pledge)

            time_pledge = serializer.save()
            return Response(TimePledgeSerializer(time_pledge).data,
                        status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class TimePledgeDetail(APIView):
    """
    Retrieve, update, or delete a TimePledge.
    Only the pledge supporter can change it.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsSupporterOrReadOnly]

    def get_object(self, pk):
        try:
            time_pledge = TimePledge.objects.get(pk=pk)
        except TimePledge.DoesNotExist:
            raise Http404
        self.check_object_permissions(self.request, time_pledge.pledge)
        return time_pledge

    def get(self, request, pk):
        time_pledge = self.get_object(pk)
        serializer = TimePledgeSerializer(time_pledge)
        return Response(serializer.data)

    def put(self, request, pk):
        time_pledge = self.get_object(pk)
        serializer = TimePledgeSerializer(
            instance=time_pledge,
            data=request.data,
            partial=True,
        )
        if serializer.is_valid():
            pledge = serializer.validated_data.get("pledge", time_pledge.pledge)
            self.check_object_permissions(request, pledge)
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        time_pledge = self.get_object(pk)
        if time_pledge.pledge.status != "pending":
            return Response(
                {"detail": "Cannot delete time details for a non-pending pledge. "
                "Change pledge status to 'cancelled' instead."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        time_pledge.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ItemPledgeList(APIView):
    """
    List or create ItemPledge rows.
    Only the pledge supporter can create an item detail for their pledge.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsSupporterOrReadOnly]

    def get(self, request):
        item_pledges = ItemPledge.objects.all()
        serializer = ItemPledgeSerializer(item_pledges, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer = ItemPledgeSerializer(data=request.data)
        if serializer.is_valid():
            pledge = serializer.validated_data.get("pledge")
            # make sure current user owns this pledge
            self.check_object_permissions(request, pledge)

            # Save the ItemPledge row itself
            item_pledge = serializer.save()

            # --- NEW: auto-set pledge.reward_tier from the ItemNeed + mode ---
            need = pledge.need  # the Need this pledge is attached to

            if need is not None and need.need_type == "item":
                # item_detail is the ItemNeed row (your fog machine etc.)
                item_need = getattr(need, "item_detail", None)

                if item_need is not None:
                    chosen_mode = item_pledge.mode  # "donation" or "loan"

                    if chosen_mode == "donation":
                        tier = item_need.donation_reward_tier
                    elif chosen_mode == "loan":
                        tier = item_need.loan_reward_tier
                    else:
                        tier = None

                    if tier is not None:
                        # Sync the FK to the correct tier (e.g. Gear Loan Champion)
                        pledge.reward_tier = tier
                        pledge.save(update_fields=["reward_tier"])

            return Response(
                ItemPledgeSerializer(item_pledge).data,
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ItemPledgeDetail(APIView):
    """
    Retrieve, update, or delete an ItemPledge.
    Only the pledge supporter can change it.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsSupporterOrReadOnly]

    def get_object(self, pk):
        try:
            item_pledge = ItemPledge.objects.get(pk=pk)
        except ItemPledge.DoesNotExist:
            raise Http404
        self.check_object_permissions(self.request, item_pledge.pledge)
        return item_pledge

    def get(self, request, pk):
        item_pledge = self.get_object(pk)
        serializer = ItemPledgeSerializer(item_pledge)
        return Response(serializer.data)

    def put(self, request, pk):
        item_pledge = self.get_object(pk)
        serializer = ItemPledgeSerializer(
            instance=item_pledge,
            data=request.data,
            partial=True,
        )
        if serializer.is_valid():
            pledge = serializer.validated_data.get("pledge", item_pledge.pledge)
            self.check_object_permissions(request, pledge)

            item_pledge = serializer.save()

            # keep pledge.reward_tier in sync after updates too
            need = pledge.need
            if need is not None and need.need_type == "item":
                item_need = getattr(need, "item_detail", None)
                if item_need is not None:
                    chosen_mode = item_pledge.mode
                    if chosen_mode == "donation":
                        tier = item_need.donation_reward_tier
                    elif chosen_mode == "loan":
                        tier = item_need.loan_reward_tier
                    else:
                        tier = None

                    if tier is not None:
                        pledge.reward_tier = tier
                        pledge.save(update_fields=["reward_tier"])

            return Response(ItemPledgeSerializer(item_pledge).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        item_pledge = self.get_object(pk)
        if item_pledge.pledge.status != "pending":
            return Response(
                {"detail": "Cannot delete item details for a non-pending pledge. "
                "Change pledge status to 'cancelled' instead."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        item_pledge.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

# ====================================================================================
# REPORTS
# ====================================================================================

class FundraiserSummaryReport(APIView):
    """
    Read-only summary for a single fundraiser.

    URL: /reports/fundraisers/<pk>/summary/

    Anyone can GET it.

    Returns a big JSON text report with:
    - money: targets, pledged, remaining, percentages
    - time: shifts needed vs volunteers, with per-shift detail
    - items: quantities needed vs pledged, with per-item detail
    - needs: breakdown by type and status
    - pledges: breakdown by type
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_object(self, pk):
        try:
            return Fundraiser.objects.get(pk=pk)
        except Fundraiser.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        fundraiser = self.get_object(pk)
        active_statuses = ["pending", "approved"]

        # ------------------------------------------------------------------
        # MONEY SECTION
        # ------------------------------------------------------------------
        goal = fundraiser.goal or Decimal("0")

        # Query all MoneyNeeds for this fundraiser
        money_needs_qs = MoneyNeed.objects.filter(need__fundraiser=fundraiser).select_related(
            "need"
        )

        # Sum of all money targets from MoneyNeeds
        money_target = (
            money_needs_qs.aggregate(total=Sum("target_amount"))["total"]
            or Decimal("0")
        )
        unallocated_goal_amount = max(goal - money_target, Decimal("0"))


        # Total money pledged (for this fundraiser, any money pledge)
        money_pledged_total = (
            MoneyPledge.objects.filter(
                pledge__fundraiser=fundraiser,
                pledge__status__in=active_statuses,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )

        # Remaining against the *MoneyNeeds* themselves
        money_remaining_against_needs = max(money_target - money_pledged_total, Decimal("0"))

        # % of overall fundraiser goal covered by money pledges
        if goal > 0:
            percent_of_goal = (money_pledged_total / goal) * Decimal("100")
        else:
            percent_of_goal = None

        # % of explicit MoneyNeeds covered
        if money_target > 0:
            percent_of_money_needs = (money_pledged_total / money_target) * Decimal("100")
        else:
            percent_of_money_needs = None

        # --- Per-money-need breakdown (so you can see which bucket is which) ---
        money_needs_list = []
        for mn in money_needs_qs:
            need = mn.need

            # Money pledged specifically to this need
            pledged_for_need = (
                MoneyPledge.objects.filter(
                    pledge__need=need,
                    pledge__status__in=active_statuses,
                ).aggregate(total=Sum("amount"))["total"]
                or Decimal("0")
            )

            remaining_for_need = max(mn.target_amount - pledged_for_need, Decimal("0"))

            if pledged_for_need == 0:
                coverage_status = "unfilled"
            elif remaining_for_need == 0:
                coverage_status = "filled"
            else:
                coverage_status = "partial"

            money_needs_list.append(
                {
                    "need_id": need.id,
                    "need_title": need.title,
                    "target_amount": str(mn.target_amount),
                    "money_pledged": str(pledged_for_need),
                    "money_remaining": str(remaining_for_need),
                    "coverage_status": coverage_status,
                }
            )

        # ------------------------------------------------------------------
        # TIME SECTION (volunteer shifts, per TimeNeed)
        # ------------------------------------------------------------------
        time_needs_qs = TimeNeed.objects.filter(need__fundraiser=fundraiser).select_related(
            "need"
        )

        total_shifts_needed = 0
        total_shifts_with_volunteers = 0
        time_needs_detail = []

        for tn in time_needs_qs:
            total_shifts_needed += 1

            # All active time pledges for this specific Need
            pledges_for_need = TimePledge.objects.filter(
                pledge__need=tn.need,
                pledge__status__in=active_statuses,
            )

            volunteers_pledged = pledges_for_need.count()
            volunteers_remaining = max(tn.volunteers_needed - volunteers_pledged, 0)

            if volunteers_pledged == 0:
                coverage_status = "unfilled"
            elif volunteers_remaining == 0:
                coverage_status = "filled"
            else:
                coverage_status = "partial"

            if volunteers_pledged > 0:
                total_shifts_with_volunteers += 1

            time_needs_detail.append({
                "need_id": tn.need.id,
                "need_title": tn.need.title,
                "role_title": tn.role_title,
                "location": tn.location,
                "shift_start": tn.start_datetime,
                "shift_end": tn.end_datetime,
                "volunteers_needed": tn.volunteers_needed,
                "volunteers_pledged": volunteers_pledged,
                "volunteers_remaining": volunteers_remaining,
                "coverage_status": coverage_status,
            })

        shifts_without_volunteers = max(total_shifts_needed - total_shifts_with_volunteers, 0)

        if total_shifts_needed > 0:
            percent_shifts_filled = (
                Decimal(total_shifts_with_volunteers) / Decimal(total_shifts_needed)
            ) * Decimal("100")
        else:
            percent_shifts_filled = None

        # ------------------------------------------------------------------
        # ITEM SECTION (per ItemNeed)
        # ------------------------------------------------------------------
        item_needs_qs = ItemNeed.objects.filter(need__fundraiser=fundraiser).select_related(
            "need"
        )

        total_item_needs = 0
        total_item_qty_needed = 0
        total_item_qty_pledged = 0
        item_needs_detail = []

        for ineed in item_needs_qs:
            total_item_needs += 1

            quantity_needed = ineed.quantity_needed

            # All active item pledges for this Need
            quantity_pledged = (
                ItemPledge.objects.filter(
                    pledge__need=ineed.need,
                    pledge__status__in=active_statuses,
                ).aggregate(total=Sum("quantity"))["total"]
                or 0
            )

            total_item_qty_needed += quantity_needed
            total_item_qty_pledged += quantity_pledged

            quantity_remaining = max(quantity_needed - quantity_pledged, 0)

            if quantity_pledged == 0:
                coverage_status = "unfilled"
            elif quantity_remaining == 0:
                coverage_status = "filled"
            else:
                coverage_status = "partial"

            item_needs_detail.append({
                "need_id": ineed.need.id,
                "need_title": ineed.need.title,
                "item_name": ineed.item_name,
                "quantity_needed": quantity_needed,
                "quantity_pledged": quantity_pledged,
                "quantity_remaining": quantity_remaining,
                "mode": ineed.mode,
                "coverage_status": coverage_status,
            })

        item_qty_remaining = max(total_item_qty_needed - total_item_qty_pledged, 0)

        if total_item_qty_needed > 0:
            percent_items_filled_by_quantity = (
                Decimal(total_item_qty_pledged) / Decimal(total_item_qty_needed)
            ) * Decimal("100")
        else:
            percent_items_filled_by_quantity = None

        # ------------------------------------------------------------------
        # NEEDS: breakdown by type and status
        # ------------------------------------------------------------------
        needs_qs = Need.objects.filter(fundraiser=fundraiser)

        needs_by_type = list(
            needs_qs.values("need_type").annotate(count=Count("id")).order_by("need_type")
        )

        needs_by_status = list(
            needs_qs.values("status").annotate(count=Count("id")).order_by("status")
        )

        total_needs = needs_qs.count()

        # ------------------------------------------------------------------
        # PLEDGES: breakdown by type
        # ------------------------------------------------------------------
        pledges_qs = Pledge.objects.filter(
            fundraiser=fundraiser,
            status__in=active_statuses,
        )
        total_pledges = pledges_qs.count()

        money_pledge_count = pledges_qs.filter(money_detail__isnull=False).count()
        time_pledge_count = pledges_qs.filter(time_detail__isnull=False).count()
        item_pledge_count = pledges_qs.filter(item_detail__isnull=False).count()

        # ------------------------------------------------------------------
        # BUILD RESPONSE JSON
        # ------------------------------------------------------------------
        data = {
            "fundraiser": {
                "id": fundraiser.id,
                "title": fundraiser.title,
                "status": fundraiser.status,
                "goal": str(fundraiser.goal),
            },
            "money": {
                # Big-picture target
                "goal_target": str(goal),

                # Sum of all MoneyNeeds
                "total_target_from_money_needs": str(money_target),

                # Unallocated amount aka goal - money needs. 
                "unallocated_goal_amount": str(unallocated_goal_amount),

                # All money pledges for this fundraiser
                "total_pledged": str(money_pledged_total),

                # How far we are from fully covering the MoneyNeeds
                "remaining_against_money_needs": str(money_remaining_against_needs),

                "percent_of_goal": float(percent_of_goal) if percent_of_goal is not None else None,
                "percent_of_money_needs": float(percent_of_money_needs)
                if percent_of_money_needs is not None
                else None,

                # NEW: breakdown by each MoneyNeed (venue hire, pizza, posters, etc.)
                "money_needs": money_needs_list,
            },
            "time": {
                "total_shifts_needed": total_shifts_needed,
                "shifts_with_volunteers": total_shifts_with_volunteers,
                "shifts_without_volunteers": shifts_without_volunteers,
                "percent_shifts_filled": float(percent_shifts_filled) if percent_shifts_filled is not None else None,
                "shifts": time_needs_detail,
            },
            "items": {
                "total_item_needs": total_item_needs,
                "total_quantity_needed": total_item_qty_needed,
                "total_quantity_pledged": total_item_qty_pledged,
                "quantity_remaining": item_qty_remaining,
                "percent_items_filled_by_quantity": float(percent_items_filled_by_quantity) if percent_items_filled_by_quantity is not None else None,
                "item_needs": item_needs_detail,
            },
            "needs_summary": {
                "total_needs": total_needs,
                "by_type": needs_by_type,
                "by_status": needs_by_status,
            },
            "pledges_summary": {
                "total_pledges": total_pledges,
                "money_pledge_count": money_pledge_count,
                "time_pledge_count": time_pledge_count,
                "item_pledge_count": item_pledge_count,
            },
        }

        return Response(data)



class NeedProgressReport(APIView):
    """
    Read-only progress snapshot for a single Need.

    URL: /reports/needs/<pk>/progress/

    What it returns depends on need_type:
    - money → target, pledged, remaining
    - item  → quantity_needed, pledged, remaining
    - time  → volunteers_needed, volunteer_signups, hours_committed_total
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_object(self, pk):
        try:
            return Need.objects.get(pk=pk)
        except Need.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        need = self.get_object(pk)
        active_statuses = ["pending", "approved"]

        base = {
            "need_id": need.id,
            "title": need.title,
            "need_type": need.need_type,
            "status": need.status,
            "priority": need.priority,
            "fundraiser_id": need.fundraiser.id,
            "fundraiser_title": need.fundraiser.title,
        }

        # Common: how many pledges
        pledges_qs = need.pledges.filter(status__in=active_statuses)
        base["total_pledges"] = pledges_qs.count()

        # --- Money need ---
        if need.need_type == "money":
            money_detail = getattr(need, "money_detail", None)
            target = money_detail.target_amount if money_detail else Decimal("0")

            money_pledged = (
                MoneyPledge.objects.filter(
                    pledge__need=need,
                    pledge__status__in=active_statuses,
                ).aggregate(total=Sum("amount"))["total"]
                or Decimal("0")
            )

            base.update({
                "target_amount": str(target),
                "money_pledged": str(money_pledged),
                "money_remaining": str(max(target - money_pledged, Decimal("0"))),
            })

        # --- Item need ---
        elif need.need_type == "item":
            item_detail = getattr(need, "item_detail", None)
            quantity_needed = item_detail.quantity_needed if item_detail else 0

            quantity_pledged = (
                ItemPledge.objects.filter(
                    pledge__need=need,
                    pledge__status__in=active_statuses,
                ).aggregate(total=Sum("quantity"))["total"]
                or 0
            )

            base.update({
                "item_name": item_detail.item_name if item_detail else None,
                "quantity_needed": quantity_needed,
                "item_quantity_pledged": quantity_pledged,
                "item_quantity_remaining": max(quantity_needed - quantity_pledged, 0),
            })

        # --- Time need ---
        elif need.need_type == "time":
            time_detail = getattr(need, "time_detail", None)
            volunteers_needed = time_detail.volunteers_needed if time_detail else 0

            hours_committed_total = (
                TimePledge.objects.filter(
                    pledge__need=need,
                    pledge__status__in=active_statuses,
                ).aggregate(total=Sum("hours_committed"))["total"]
                or Decimal("0")
            )

            volunteer_signups = TimePledge.objects.filter(
                pledge__need=need,
                pledge__status__in=active_statuses,
            ).count()

            base.update({
                "volunteers_needed": volunteers_needed,
                "volunteer_signups": volunteer_signups,
                "volunteers_remaining": max(volunteers_needed - volunteer_signups, 0),
                "hours_committed_total": str(hours_committed_total),
                "shift_start": getattr(time_detail, "start_datetime", None),
                "shift_end": getattr(time_detail, "end_datetime", None),
            })

        return Response(base)
    
class MyFundraisersReport(APIView):
    """
    Dashboard-style summary for the currently logged-in owner.

    URL: /reports/my-fundraisers/

    Returns a list of fundraisers you own, each with:
    - title, status, goal
    - total_money_target, total_money_pledged, money_remaining
    - total_pledges
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        owner = request.user
        active_statuses = ["pending", "approved"]

        fundraisers = Fundraiser.objects.filter(owner=owner).order_by("-date_created")

        results = []

        for fundraiser in fundraisers:
            money_target = (
                MoneyNeed.objects.filter(need__fundraiser=fundraiser)
                .aggregate(total=Sum("target_amount"))["total"]
                or Decimal("0")
            )

            money_pledged = (
                MoneyPledge.objects.filter(
                    pledge__fundraiser=fundraiser,
                    pledge__status__in=active_statuses,
                )
                .aggregate(total=Sum("amount"))["total"]
                or Decimal("0")
            )

            total_pledges = Pledge.objects.filter(
                fundraiser=fundraiser,
                status__in=active_statuses,
            ).count()

            results.append({
                "fundraiser_id": fundraiser.id,
                "title": fundraiser.title,
                "status": fundraiser.status,
                "goal": str(fundraiser.goal),

                "total_money_target": str(money_target),
                "total_money_pledged": str(money_pledged),
                "money_remaining": str(max(money_target - money_pledged, Decimal("0"))),

                "total_pledges": total_pledges,
            })

        return Response(results)
    
class FundraiserPledgesReport(APIView):
    """
    Detailed pledge report for a single fundraiser.

    URL: /reports/fundraisers/<pk>/pledges/

    Only the fundraiser owner can access this.

    Returns:
    - fundraiser: basic info
    - totals: money, time hours, item quantities
    - pledges: list of pledges with supporter + need fields
    """
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_object(self, pk):
        try:
            fundraiser = Fundraiser.objects.get(pk=pk)
        except Fundraiser.DoesNotExist:
            raise Http404

        # Enforce that only the owner can see this report
        self.check_object_permissions(self.request, fundraiser)
        return fundraiser

    def get(self, request, pk):
        fundraiser = self.get_object(pk)
        active_statuses = ["pending", "approved"]

        # All active pledges for this fundraiser
        pledges_qs = Pledge.objects.filter(
            fundraiser=fundraiser,
            status__in=active_statuses,
        ).select_related("supporter", "need", "reward_tier")

        total_pledges = pledges_qs.count()

        # Money / time / item totals across those pledges
        total_money_pledged = (
            MoneyPledge.objects.filter(pledge__in=pledges_qs)
            .aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )
        total_time_hours = (
            TimePledge.objects.filter(pledge__in=pledges_qs)
            .aggregate(total=Sum("hours_committed"))["total"]
            or Decimal("0")
        )
        total_item_quantity = (
            ItemPledge.objects.filter(pledge__in=pledges_qs)
            .aggregate(total=Sum("quantity"))["total"]
            or 0
        )

        # Serialize each pledge with your existing PledgeSerializer
        pledges_data = PledgeSerializer(
            pledges_qs,
            many=True,
            context={"request": request},
        ).data


        data = {
            "fundraiser": {
                "id": fundraiser.id,
                "title": fundraiser.title,
                "status": fundraiser.status,
                "goal": str(fundraiser.goal),
            },
            "totals": {
                "total_pledges": total_pledges,
                "total_money_pledged": str(total_money_pledged),
                "total_time_hours_pledged": str(total_time_hours),
                "total_item_quantity_pledged": total_item_quantity,
            },
            "pledges": pledges_data,
        }

        return Response(data)
    
class MyFundraiserRewardsReport(APIView):
    """
    For the CURRENTLY LOGGED-IN SUPPORTER:
    Rewards summary for a single fundraiser.

    URL: /reports/fundraisers/<pk>/my-rewards/

    Returns:
    - fundraiser: id, title
    - supporter: id, username
    - totals: money / time / items pledged to THIS fundraiser
    - earned_money_reward_tiers: tiers unlocked based on total money pledged
    - earned_other_reward_tiers: tiers granted via time/item pledges
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk):
        try:
            return Fundraiser.objects.get(pk=pk)
        except Fundraiser.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        supporter = request.user
        fundraiser = self.get_object(pk)
        active_statuses = ["pending", "approved"]

        # All of THIS supporter’s active pledges for THIS fundraiser
        pledges_qs = (
            Pledge.objects.filter(
                fundraiser=fundraiser,
                supporter=supporter,
                status__in=active_statuses,
            )
            .select_related("reward_tier", "need")
        )

        # --- Totals across pledge detail tables, scoped to THESE pledges only ---

        # MONEY
        money_pledges_qs = MoneyPledge.objects.filter(
            pledge__in=pledges_qs,
            pledge__need__need_type="money",   # defensive: only money needs
        )
        total_money_pledged = (
            money_pledges_qs.aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )

        # TIME
        time_pledges_qs = TimePledge.objects.filter(
            pledge__in=pledges_qs,
            pledge__need__need_type="time",    # defensive: only time needs
        )
        total_time_hours = (
            time_pledges_qs.aggregate(total=Sum("hours_committed"))["total"]
            or Decimal("0")
        )

        # ITEMS
        item_pledges_qs = ItemPledge.objects.filter(
            pledge__in=pledges_qs,
            pledge__need__need_type="item",    # defensive: only item needs
        )
        total_item_quantity = (
            item_pledges_qs.aggregate(total=Sum("quantity"))["total"]
            or 0
        )

        # ------------------------------------------------------------------
        # Money-based reward tiers (threshold model)
        # ONLY reward_type = "money"
        # ------------------------------------------------------------------
        money_tiers_qs = (
            RewardTier.objects.filter(
                fundraiser=fundraiser,
                reward_type="money",
                minimum_contribution_value__isnull=False,
                minimum_contribution_value__lte=total_money_pledged,
            )
            .order_by("minimum_contribution_value", "id")
            .values("id", "name", "description", "minimum_contribution_value")
        )

        earned_money_reward_tiers = [
            {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "minimum_contribution_value": str(row["minimum_contribution_value"]),
            }
            for row in money_tiers_qs
        ]

        # ------------------------------------------------------------------
        # Time / item-based reward tiers
        # These are set directly on pledge.reward_tier.
        # We EXCLUDE reward_type="money" so Gold can't appear here.
        # ------------------------------------------------------------------
        raw_other_tiers = (
            pledges_qs
            .exclude(reward_tier__isnull=True)
            .exclude(reward_tier__reward_type="money")
            .values(
                "reward_tier__id",
                "reward_tier__name",
                "reward_tier__description",
                "reward_tier__minimum_contribution_value",
                "reward_tier__reward_type",
            )
            .distinct()
        )

        earned_other_reward_tiers = [
            {
                "id": row["reward_tier__id"],
                "name": row["reward_tier__name"],
                "description": row["reward_tier__description"],
                "reward_type": row["reward_tier__reward_type"],
                "minimum_contribution_value": (
                    str(row["reward_tier__minimum_contribution_value"])
                    if row["reward_tier__minimum_contribution_value"] is not None
                    else None
                ),
            }
            for row in raw_other_tiers
        ]

        data = {
            "fundraiser": {
                "id": fundraiser.id,
                "title": fundraiser.title,
            },
            "supporter": {
                "id": supporter.id,
                "username": supporter.username,
            },
            "totals": {
                "total_money_pledged": str(total_money_pledged),
                "total_time_hours_pledged": str(total_time_hours),
                "total_item_quantity_pledged": total_item_quantity,
            },
            "earned_money_reward_tiers": earned_money_reward_tiers,
            "earned_other_reward_tiers": earned_other_reward_tiers,
        }

        return Response(data)




class MyPledgesReport(APIView):
    """
    Dashboard-style summary of pledges for the current supporter.

    URL: /reports/my-pledges/

    Returns:
    - supporter: username / id
    - totals: across all active pledges
    - pledges: flat list of pledges with fundraiser + need info
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        supporter = request.user
        active_statuses = ["pending", "approved"]

        pledges_qs = Pledge.objects.filter(
            supporter=supporter,
            status__in=active_statuses,
        ).select_related("fundraiser", "need", "reward_tier")

        total_pledges = pledges_qs.count()

        total_money_pledged = (
            MoneyPledge.objects.filter(pledge__in=pledges_qs)
            .aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )
        total_time_hours = (
            TimePledge.objects.filter(pledge__in=pledges_qs)
            .aggregate(total=Sum("hours_committed"))["total"]
            or Decimal("0")
        )
        total_item_quantity = (
            ItemPledge.objects.filter(pledge__in=pledges_qs)
            .aggregate(total=Sum("quantity"))["total"]
            or 0
        )

        pledges_data = PledgeSerializer(
            pledges_qs,
            many=True,
            context={"request": request},
        ).data

        data = {
            "supporter": {
                "id": supporter.id,
                "username": supporter.username,
            },
            "totals": {
                "total_pledges": total_pledges,
                "total_money_pledged": str(total_money_pledged),
                "total_time_hours_pledged": str(total_time_hours),
                "total_item_quantity_pledged": total_item_quantity,
            },
            "pledges": pledges_data,
        }
        return Response(data)

###################################################################################

# ====================================================================================
# FUNDRAISER TEMPLATES
# ====================================================================================

class FundraiserTemplateListCreate(APIView):
    """
    GET: list all active fundraiser templates
    POST: create a new fundraiser template
    """
    permission_classes = [IsAdminUserOrReadOnly]

    def get(self, request):
        templates = FundraiserTemplate.objects.filter(is_active=True)
        serializer = FundraiserTemplateSerializer(templates, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = FundraiserTemplateSerializer(data=request.data)
        if serializer.is_valid():
            template = serializer.save()
            return Response(
                FundraiserTemplateSerializer(template).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FundraiserTemplateDetail(APIView):
    """
    GET: retrieve a single template (with its needs + reward tiers)
    PUT/PATCH: update template
    DELETE: delete template
    """
    permission_classes = [IsAdminUserOrReadOnly]

    def get_object(self, pk):
        try:
            template = FundraiserTemplate.objects.get(pk=pk, is_active=True)
        except FundraiserTemplate.DoesNotExist:
            raise Http404

        self.check_object_permissions(self.request, template)
        return template


    def get(self, request, pk):
        template = self.get_object(pk)
        serializer = FundraiserTemplateSerializer(template)
        return Response(serializer.data)

    def put(self, request, pk):
        template = self.get_object(pk)
        serializer = FundraiserTemplateSerializer(template, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        template = self.get_object(pk)
        serializer = FundraiserTemplateSerializer(
            template, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        template = self.get_object(pk)
        template.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class ApplyTemplateToFundraiser(APIView):
    """
    POST: Apply a FundraiserTemplate to an existing Fundraiser.

    Expected JSON body:
    {
        "fundraiser_id": 1,
        "template_id": 2
    }

    Rules:
    - Only the owner of the fundraiser can apply a template.
    - The fundraiser must be "empty" (no existing needs or reward tiers).
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        fundraiser_id = request.data.get("fundraiser_id")
        template_id = request.data.get("template_id")

        # Basic body validation
        if not fundraiser_id or not template_id:
            return Response(
                {"detail": "fundraiser_id and template_id are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 1) Fetch fundraiser (must be owned by the current user)
        try:
            fundraiser = Fundraiser.objects.get(
                pk=fundraiser_id,
                owner=request.user,
            )
        except Fundraiser.DoesNotExist:
            raise Http404("Fundraiser not found, or you do not own it.")

        # 2) Refuse to apply if fundraiser already has content
        if fundraiser.needs.exists() or fundraiser.reward_tiers.exists():
            raise ValidationError({
                "detail": (
                    "This fundraiser already has needs or reward tiers. "
                    "Templates can only be applied to an empty fundraiser."
                )
            })

        # 3) Fetch template
        try:
            template = FundraiserTemplate.objects.get(
                pk=template_id,
                is_active=True,
            )
        except FundraiserTemplate.DoesNotExist:
            raise Http404("Template not found or not active.")

        # Wrap ALL writes so it's all-or-nothing
        with transaction.atomic():

            # 4) Copy top-level fields from template onto fundraiser
            if template.title:
                fundraiser.title = template.title
            if template.description:
                fundraiser.description = template.description
            if template.goal is not None:
                fundraiser.goal = template.goal
            if template.image_url:
                fundraiser.image_url = template.image_url
            if template.location:
                fundraiser.location = template.location
            fundraiser.enable_rewards = template.enable_rewards
            fundraiser.save()

            # 5) Copy TemplateRewardTier -> RewardTier
            template_to_real_reward = {}
            for trt in template.template_reward_tiers.all():
                rt = RewardTier.objects.create(
                    fundraiser=fundraiser,
                    reward_type=trt.reward_type,
                    name=trt.name,
                    description=trt.description,
                    minimum_contribution_value=trt.minimum_contribution_value,
                    image_url=trt.image_url,
                    sort_order=trt.sort_order,
                    max_backers=trt.max_backers,
                )
                template_to_real_reward[trt.id] = rt

            # 6) Copy TemplateNeed -> Need + MoneyNeed/TimeNeed/ItemNeed
            for tneed in template.template_needs.all():
                # Base Need
                need = Need.objects.create(
                    fundraiser=fundraiser,
                    need_type=tneed.need_type,
                    title=tneed.title,
                    description=tneed.description,
                    priority=tneed.priority,
                    sort_order=tneed.sort_order,
                )

                # Money need
                if tneed.need_type == "money":
                    # Guard against missing required fields for MoneyNeed
                    if tneed.target_amount is None:
                        raise ValidationError({
                            "detail": (
                                f"Template money need '{tneed.title}' must have "
                                f"target_amount set before applying."
                            )
                        })

                    MoneyNeed.objects.create(
                        need=need,
                        target_amount=tneed.target_amount,
                        comment=tneed.comment,
                    )

                # Time need
                elif tneed.need_type == "time":
                    # Guard against missing required fields for TimeNeed
                    missing = []
                    if not tneed.start_datetime:
                        missing.append("start_datetime")
                    if not tneed.end_datetime:
                        missing.append("end_datetime")
                    if tneed.volunteers_needed is None:
                        missing.append("volunteers_needed")
                    if not tneed.role_title:
                        missing.append("role_title")
                    if not tneed.location:
                        missing.append("location")

                    if missing:
                        raise ValidationError({
                            "detail": (
                                f"Template time need '{tneed.title}' missing: "
                                f"{', '.join(missing)}. Set these before applying."
                            )
                        })

                    time_reward = None
                    if tneed.time_reward_template:
                        time_reward = template_to_real_reward.get(
                            tneed.time_reward_template.id
                        )

                    TimeNeed.objects.create(
                        need=need,
                        start_datetime=tneed.start_datetime,
                        end_datetime=tneed.end_datetime,
                        volunteers_needed=tneed.volunteers_needed,
                        role_title=tneed.role_title,
                        location=tneed.location,
                        reward_tier=time_reward,
                    )

                # Item need
                elif tneed.need_type == "item":
                    # Guard against missing required fields for ItemNeed
                    missing = []
                    if not tneed.item_name:
                        missing.append("item_name")
                    if tneed.quantity_needed is None:
                        missing.append("quantity_needed")
                    if not tneed.mode:
                        missing.append("mode")

                    if missing:
                        raise ValidationError({
                            "detail": (
                                f"Template item need '{tneed.title}' missing: "
                                f"{', '.join(missing)}. Set these before applying."
                            )
                        })

                    donation_reward = None
                    if tneed.donation_reward_template:
                        donation_reward = template_to_real_reward.get(
                            tneed.donation_reward_template.id
                        )

                    loan_reward = None
                    if tneed.loan_reward_template:
                        loan_reward = template_to_real_reward.get(
                            tneed.loan_reward_template.id
                        )

                    ItemNeed.objects.create(
                        need=need,
                        item_name=tneed.item_name,
                        quantity_needed=tneed.quantity_needed,
                        mode=tneed.mode,
                        notes=tneed.notes,
                        donation_reward_tier=donation_reward,
                        loan_reward_tier=loan_reward,
                    )

        # 7) Return the full, updated fundraiser detail
        detail_serializer = FundraiserDetailSerializer(
            fundraiser,
            context={"request": request},
        )
        return Response(detail_serializer.data, status=status.HTTP_200_OK)

    
        
# ====================================================================================
# TEMPLATE REWARD TIERS
# ====================================================================================

class TemplateRewardTierListCreate(APIView):
    """
    GET: list all template reward tiers
    POST: create a new template reward tier
    """
    permission_classes = [IsAdminUserOrReadOnly]

    def get(self, request):
        tiers = TemplateRewardTier.objects.all()
        serializer = TemplateRewardTierSerializer(tiers, many=True)
        return Response(serializer.data)

    def post(self, request):
        template_id = request.data.get("template")
        if not template_id:
            return Response({"template": "This field is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            template = FundraiserTemplate.objects.get(pk=template_id)
        except FundraiserTemplate.DoesNotExist:
            raise Http404

        serializer = TemplateRewardTierSerializer(data=request.data)
        if serializer.is_valid():
            tier = serializer.save()
            return Response(TemplateRewardTierSerializer(tier).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class TemplateRewardTierDetail(APIView):
    """
    GET: retrieve a single template reward tier
    PUT/PATCH: update it
    DELETE: delete it
    """
    permission_classes = [IsAdminUserOrReadOnly]

    def get_object(self, pk):
        try:
            tier = TemplateRewardTier.objects.get(pk=pk)
        except TemplateRewardTier.DoesNotExist:
            raise Http404

        self.check_object_permissions(self.request, tier)
        return tier


    def get(self, request, pk):
        tier = self.get_object(pk)
        serializer = TemplateRewardTierSerializer(tier)
        return Response(serializer.data)

    def put(self, request, pk):
        tier = self.get_object(pk)
        serializer = TemplateRewardTierSerializer(tier, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        tier = self.get_object(pk)
        serializer = TemplateRewardTierSerializer(tier, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        tier = self.get_object(pk)
        tier.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ====================================================================================
# TEMPLATE NEEDS
# ====================================================================================

class TemplateNeedListCreate(APIView):
    """
    GET: list all template needs
    POST: create a new template need
    """
    permission_classes = [IsAdminUserOrReadOnly]

    def get(self, request):
        needs = TemplateNeed.objects.all()
        serializer = TemplateNeedSerializer(needs, many=True)
        return Response(serializer.data)


    def post(self, request):
        template_id = request.data.get("template")
        if not template_id:
            return Response({"template": "This field is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            template = FundraiserTemplate.objects.get(pk=template_id)
        except FundraiserTemplate.DoesNotExist:
            raise Http404

        serializer = TemplateNeedSerializer(data=request.data)
        if serializer.is_valid():
            need = serializer.save()
            return Response(TemplateNeedSerializer(need).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class TemplateNeedDetail(APIView):
    """
    GET: retrieve a single template need
    PUT/PATCH: update it
    DELETE: delete it
    """
    permission_classes = [IsAdminUserOrReadOnly]

    def get_object(self, pk):
        try:
            need = TemplateNeed.objects.get(pk=pk)
        except TemplateNeed.DoesNotExist:
            raise Http404
        self.check_object_permissions(self.request, need)
        return need

    def get(self, request, pk):
        need = self.get_object(pk)
        serializer = TemplateNeedSerializer(need)
        return Response(serializer.data)

    def put(self, request, pk):
        need = self.get_object(pk)
        serializer = TemplateNeedSerializer(need, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        need = self.get_object(pk)
        serializer = TemplateNeedSerializer(need, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        need = self.get_object(pk)
        need.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
from rest_framework.permissions import IsAuthenticated

class PledgeCancel(APIView):
    """
    POST /pledges/<pk>/cancel/

    Rules:
    - Supporter can cancel ONLY while pledge.status == "pending"
    - Fundraiser owner (organiser) can cancel even if pledge is "approved"
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            pledge = Pledge.objects.select_related("fundraiser", "supporter").get(pk=pk)
        except Pledge.DoesNotExist:
            raise Http404

        is_supporter = pledge.supporter_id == request.user.id
        is_owner = pledge.fundraiser.owner_id == request.user.id

        if not (is_supporter or is_owner):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)

        # Supporter restriction
        if is_supporter and pledge.status != "pending":
            return Response(
                {"detail": "Supporters can only cancel pending pledges."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Owner can cancel pending/approved (and anything else you want)
        pledge.status = "cancelled"
        pledge.save(update_fields=["status"])

        return Response(PledgeDetailSerializer(pledge, context={"request": request}).data)


class PledgeApprove(APIView):
    """
    POST /pledges/<pk>/approve/

    Rules:
    - Only fundraiser owner can approve
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            pledge = Pledge.objects.select_related("fundraiser").get(pk=pk)
        except Pledge.DoesNotExist:
            raise Http404

        if pledge.fundraiser.owner_id != request.user.id:
            return Response({"detail": "Only the organiser can approve pledges."}, status=status.HTTP_403_FORBIDDEN)

        pledge.status = "approved"
        pledge.save(update_fields=["status"])

        return Response(PledgeDetailSerializer(pledge, context={"request": request}).data)


class PledgeDecline(APIView):
    """
    POST /pledges/<pk>/decline/

    Rules:
    - Only fundraiser owner can decline
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            pledge = Pledge.objects.select_related("fundraiser").get(pk=pk)
        except Pledge.DoesNotExist:
            raise Http404

        if pledge.fundraiser.owner_id != request.user.id:
            return Response({"detail": "Only the organiser can decline pledges."}, status=status.HTTP_403_FORBIDDEN)

        pledge.status = "declined"
        pledge.save(update_fields=["status"])

        return Response(PledgeDetailSerializer(pledge, context={"request": request}).data)

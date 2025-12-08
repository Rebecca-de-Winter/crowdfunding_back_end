from django.http import Http404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from django.db.models import Sum, Count
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
)
from .permissions import IsOwnerOrReadOnly, IsSupporterOrReadOnly


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
        serializer = FundraiserDetailSerializer(fundraiser)
        return Response(serializer.data)

    def put(self, request, pk):
        fundraiser = self.get_object(pk)
        serializer = FundraiserDetailSerializer(
            instance=fundraiser,
            data=request.data,
            partial=True,
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
    Supporter is set from request.user on creation.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request):
        pledges = Pledge.objects.all()
        serializer = PledgeSerializer(pledges, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = PledgeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(supporter=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
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
        serializer = PledgeDetailSerializer(pledge)
        return Response(serializer.data)

    def put(self, request, pk):
        pledge = self.get_object(pk)
        serializer = PledgeDetailSerializer(
            instance=pledge,
            data=request.data,
            partial=True,
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


# ====================================================================================
# NEEDS (BASE)
# ====================================================================================

class NeedList(APIView):
    """
    List all needs or create a new base Need.
    Only the owner of the associated fundraiser can create needs for it.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get(self, request):
        needs = Need.objects.all()
        serializer = NeedSerializer(needs, many=True)
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
        serializer = NeedDetailSerializer(need)
        return Response(serializer.data)

    def put(self, request, pk):
        need = self.get_object(pk)
        serializer = NeedDetailSerializer(
            instance=need,
            data=request.data,
            partial=True,
        )
        if serializer.is_valid():
            # Optional: if you *really* wanted to guard changing fundraiser,
            # you could re-check here, but for now simple is fine.
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
            # Check the supporter owns this pledge (existing behaviour)
            self.check_object_permissions(request, pledge)

            # Save the TimePledge row
            time_pledge = serializer.save()

            # --- NEW: auto-assign reward tier from the TimeNeed ---
            need = pledge.need  # the Need this pledge is attached to
            if need is not None and need.need_type == "time":
                # Get the TimeNeed detail row, if it exists
                time_need = getattr(need, "time_detail", None)
                if time_need is not None:
                    tier = time_need.reward_tier
                    # Only set if a tier is configured and pledge doesn't already have one
                    if tier is not None and pledge.reward_tier is None:
                        pledge.reward_tier = tier
                        pledge.save(update_fields=["reward_tier"])

            return Response(TimePledgeSerializer(time_pledge).data, status=status.HTTP_201_CREATED)
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
            self.check_object_permissions(request, pledge)

            # Save the ItemPledge row
            item_pledge = serializer.save()

            # === NEW: auto-set reward tier based on donation vs loan ===
            need = pledge.need
            if need is not None and need.need_type == "item":
                item_need = getattr(need, "item_detail", None)
                if item_need is not None:
                    chosen_mode = item_pledge.mode  # "donation" or "loan"

                    if chosen_mode == "donation":
                        tier = item_need.donation_reward_tier
                    elif chosen_mode == "loan":
                        tier = item_need.loan_reward_tier
                    else:
                        tier = None

                    if tier is not None and pledge.reward_tier is None:
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
            serializer.save()
            return Response(serializer.data)
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

    Returns a big JSON blob with:
    - money: targets, pledged, remaining, percentages
    - time: shifts needed vs pledged
    - items: quantities needed vs pledged
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
        # 1) Total money "target" from all MoneyNeeds for this fundraiser
        money_target = (
            MoneyNeed.objects.filter(need__fundraiser=fundraiser)
            .aggregate(total=Sum("target_amount"))["total"]
            or Decimal("0")
        )

        # 2) Total money pledged (only from active-ish pledges)
        money_pledged = (
            MoneyPledge.objects.filter(
                pledge__fundraiser=fundraiser,
                pledge__status__in=active_statuses,
            )
            .aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )

        # 3) Remaining money needed (never negative)
        money_remaining = max(money_target - money_pledged, Decimal("0"))

        # 4) Percent of fundraiser.goal filled by money pledges
        goal = fundraiser.goal or Decimal("0")
        if goal > 0:
            percent_of_goal = (money_pledged / goal) * Decimal("100")
        else:
            percent_of_goal = None  # no goal set

        # 5) Percent of total MoneyNeeds covered
        if money_target > 0:
            percent_of_money_needs = (money_pledged / money_target) * Decimal("100")
        else:
            percent_of_money_needs = None  # avoids divide-by-zero

        # ------------------------------------------------------------------
        # TIME SECTION (volunteer shifts)
        # ------------------------------------------------------------------
        time_needs_qs = TimeNeed.objects.filter(need__fundraiser=fundraiser)
        total_time_needs = time_needs_qs.count()

        time_pledges_qs = TimePledge.objects.filter(
            pledge__fundraiser=fundraiser,
            pledge__status__in=active_statuses,
        )
        total_time_pledges = time_pledges_qs.count()

        time_needs_remaining = max(total_time_needs - total_time_pledges, 0)

        # NOTE: Later we could add "hours_needed" vs "hours_committed",
        # but for now we keep it as simple "shifts".

        # ------------------------------------------------------------------
        # ITEM SECTION (quantities of stuff)
        # ------------------------------------------------------------------
        item_needs_qs = ItemNeed.objects.filter(need__fundraiser=fundraiser)
        total_item_needs = item_needs_qs.count()

        total_item_qty_needed = (
            item_needs_qs.aggregate(total=Sum("quantity_needed"))["total"] or 0
        )

        item_pledges_qs = ItemPledge.objects.filter(
            pledge__fundraiser=fundraiser,
            pledge__status__in=active_statuses,
        )
        total_item_pledges = item_pledges_qs.count()

        total_item_qty_pledged = (
            item_pledges_qs.aggregate(total=Sum("quantity"))["total"] or 0
        )

        item_qty_remaining = max(total_item_qty_needed - total_item_qty_pledged, 0)

        # ------------------------------------------------------------------
        # NEEDS: breakdown by type and status
        # ------------------------------------------------------------------
        needs_qs = Need.objects.filter(fundraiser=fundraiser)

        needs_by_type = list(
            needs_qs.values("need_type").annotate(count=Count("id")).order_by("need_type")
        )
        # Example entry: {"need_type": "money", "count": 3}

        needs_by_status = list(
            needs_qs.values("status").annotate(count=Count("id")).order_by("status")
        )
        # Example entry: {"status": "open", "count": 5}

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
                "goal": str(fundraiser.goal),  # Decimal -> string for JSON safety
            },
            "money": {
                "total_target_from_money_needs": str(money_target),
                "total_pledged": str(money_pledged),
                "remaining": str(money_remaining),
                "percent_of_goal": float(percent_of_goal) if percent_of_goal is not None else None,
                "percent_of_money_needs": float(percent_of_money_needs) if percent_of_money_needs is not None else None,
            },
            "time": {
                "total_time_needs": total_time_needs,          # number of TimeNeed rows
                "total_time_pledges": total_time_pledges,      # number of TimePledge rows
                "time_needs_remaining": time_needs_remaining,  # how many shifts still need people
            },
            "items": {
                "total_item_needs": total_item_needs,                 # number of ItemNeed rows
                "total_quantity_needed": total_item_qty_needed,       # sum of quantity_needed
                "total_quantity_pledged": total_item_qty_pledged,     # sum of ItemPledge.quantity
                "quantity_remaining": item_qty_remaining,
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

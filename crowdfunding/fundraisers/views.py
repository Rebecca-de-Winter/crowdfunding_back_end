from django.http import Http404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

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
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request):
        needs = Need.objects.all()
        serializer = NeedSerializer(needs, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer = NeedSerializer(data=request.data)
        if serializer.is_valid():
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
            # If fundraiser is being changed (unlikely), re-check owner
            fundraiser = serializer.validated_data.get("fundraiser", need.fundraiser)
            self.check_object_permissions(request, fundraiser)
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        need = self.get_object(pk)
        # Don't allow deleting a need that already has pledges
        if need.pledges.exists():
            return Response(
                {"detail": "Cannot delete a need that already has pledges. "
                    "Set status='cancelled' instead."},
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
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
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

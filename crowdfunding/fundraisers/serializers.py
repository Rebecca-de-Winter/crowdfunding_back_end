from rest_framework import serializers
from .utils import update_reward_tiers_for_supporter_and_fundraiser # Having a utility page allows you to write functions that updates rewards!!!
from .models import ( # Importing directly from models.py means you can just read the class names and import across. 
    Fundraiser,
    Pledge,
    MoneyPledge,
    TimePledge,
    ItemPledge,
    Need,
    MoneyNeed,
    TimeNeed,
    ItemNeed,
    RewardTier,
    FundraiserTemplate,
    TemplateNeed,
    TemplateRewardTier,
)

# ====================================================================================
# REWARD TIER SERIALIZER
# ====================================================================================

class RewardTierSerializer(serializers.ModelSerializer):
    """
    Basic serializer for a reward tier. Grabs all the fields. 

    Used when:
    - listing reward tiers for a fundraiser
    - creating / editing reward tiers in the admin or API
    """
    class Meta:
        model = RewardTier
        fields =  [
            "id",
            "fundraiser",
            "reward_type",
            "name",
            "description",
            "minimum_contribution_value",
            "image_url",
            "sort_order",
            "max_backers",
        ]


# ====================================================================================
# NEED DETAIL MODELS (MoneyNeed / TimeNeed / ItemNeed)
# ====================================================================================

class MoneyNeedSerializer(serializers.ModelSerializer):
    need_title = serializers.ReadOnlyField(source="need.title")
    fundraiser_id = serializers.ReadOnlyField(source="need.fundraiser.id")
    fundraiser_title = serializers.ReadOnlyField(source="need.fundraiser.title")
    """
    Extra details for money-type needs. Grabs all the fields. 
    One-to-one with Need via Need.money_detail. (Money_detail lives in models.py under "related name")
    """
    class Meta:
        model = MoneyNeed
        fields = [
            "id",
            "fundraiser_title",  # read-only
            "fundraiser_id",     # read-only
            "need_title",        # read-only
            "need",              
            "target_amount",
            "comment",
            
            
        ]

    def validate_target_amount(self, value):
        """
        Make sure target_amount is > 0.
        This runs AFTER basic type conversion but BEFORE save().
        """
        if value <= 0:
            raise serializers.ValidationError(
                "Target amount must be greater than zero."
            )
        return value


class TimeNeedSerializer(serializers.ModelSerializer):
    """
    Extra details for time-type needs.
    One-to-one with Need via Need.time_detail.
    """
    class Meta:
        model = TimeNeed
        fields = "__all__"

    def validate(self, attrs):
        """
        Object-level validation:
        Ensures end_datetime is after start_datetime. Runs after all the above fields have been cleaned. 

        Supports both CREATE and PATCH:
        - For create, both values come from attrs.
        - For PATCH, some fields may be omitted, so we fall back to instance values.
        """
        start = attrs.get("start_datetime") or getattr(
            self.instance, "start_datetime", None
        )
        end = attrs.get("end_datetime") or getattr(
            self.instance, "end_datetime", None
        )

        if start and end and end <= start:
            raise serializers.ValidationError(
                "end_datetime must be after start_datetime."
            )
        return attrs


class ItemNeedSerializer(serializers.ModelSerializer):
    """
    Extra details for item-type needs.
    One-to-one with Need via Need.item_detail. (Item_ detail lives in models.py under "related name")
    """
    class Meta:
        model = ItemNeed
        fields = "__all__"

    def validate_quantity_needed(self, value):
        """
        Ensure we don't create a need with zero or negative quantity.
        """
        if value <= 0:
            raise serializers.ValidationError(
                "Quantity needed must be at least 1."
            )
        return value


# ====================================================================================
# NEED BASE SERIALIZER
# ====================================================================================

class NeedSerializer(serializers.ModelSerializer):

    fundraiser_title = serializers.ReadOnlyField(source="fundraiser.title")
    fundraiser_owner_username = serializers.ReadOnlyField(
    source="fundraiser.owner.username"
)

    """
    Basic Need serializer:
    - used for listing needs
    - used for creating / updating a need
    """
    class Meta:
        model = Need
        fields = "__all__"
        read_only_fields = ["date_created", "date_updated"]


# ====================================================================================
# PLEDGE DETAIL MODELS (MoneyPledge / TimePledge / ItemPledge)
# ====================================================================================

class MoneyPledgeSerializer(serializers.ModelSerializer):
    """
    Extra details for a money pledge.
    One-to-one with Pledge via Pledge.money_detail.
    """

    supporter_total_for_fundraiser = serializers.SerializerMethodField()

    class Meta:
        model = MoneyPledge
        fields = "__all__"

    def _update_rewards(self, money_pledge):
        """
        After creating/updating a money pledge, recalc the MONEY reward tier
        for this supporter+fundraiser.
        """
        pledge = money_pledge.pledge
        supporter = pledge.supporter
        fundraiser = pledge.fundraiser
        update_reward_tiers_for_supporter_and_fundraiser(supporter, fundraiser)

    def create(self, validated_data):
        money_pledge = super().create(validated_data)
        self._update_rewards(money_pledge)
        return money_pledge

    def update(self, instance, validated_data):
        money_pledge = super().update(instance, validated_data)
        self._update_rewards(money_pledge)
        return money_pledge

    def validate_amount(self, value):
        """
        Ensure pledge amount is > 0.
        """
        if value <= 0:
            raise serializers.ValidationError(
                "Amount must be greater than zero."
            )
        return value
    
    def get_supporter_total_for_fundraiser(self, obj):
        """
        Total money this supporter has pledged to this fundraiser (all needs).
        """
        from django.db.models import Sum
        from django.db.models.functions import Coalesce
        from decimal import Decimal

        pledge = obj.pledge
        supporter = pledge.supporter
        fundraiser = pledge.fundraiser

        total = (
            MoneyPledge.objects
            .filter(
                pledge__supporter=supporter,
                pledge__fundraiser=fundraiser,
            )
            .aggregate(total=Coalesce(Sum("amount"), Decimal("0")))
            ["total"]
        )
        # Return as string so it serializes nicely
        return str(total)

class TimePledgeSerializer(serializers.ModelSerializer):
    """
    Extra details for a time pledge.
    One-to-one with Pledge via Pledge.time_detail.
    """

    class Meta:
        model = TimePledge
        fields = "__all__"

    def _apply_reward_tier(self, time_pledge):
        """
        Look at the related TimeNeed and apply its reward_tier
        to the underlying Pledge, if present.
        """
        pledge = getattr(time_pledge, "pledge", None)
        if not pledge:
            return

        need = getattr(pledge, "need", None)
        if not need:
            return

        # From models: Need -> TimeNeed via related_name="time_detail"
        time_need = getattr(need, "time_detail", None)
        if not time_need:
            return

        reward = getattr(time_need, "reward_tier", None)
        if reward:
            pledge.reward_tier = reward
            pledge.save(update_fields=["reward_tier"])

    def create(self, validated_data):
        """
        Create a TimePledge and then apply any reward_tier
        configured on the related TimeNeed.
        """
        time_pledge = super().create(validated_data)
        self._apply_reward_tier(time_pledge)
        return time_pledge

    def update(self, instance, validated_data):
        """
        Update a TimePledge and re-apply reward_tier logic,
        in case need/reward setup or timing changes.
        """
        time_pledge = super().update(instance, validated_data)
        self._apply_reward_tier(time_pledge)
        return time_pledge

    def validate(self, attrs):
        """
        Ensure end_datetime is after start_datetime.
        Supports both create and partial update (PATCH).
        """
        start = attrs.get("start_datetime") or getattr(
            self.instance, "start_datetime", None
        )
        end = attrs.get("end_datetime") or getattr(
            self.instance, "end_datetime", None
        )

        if start and end and end <= start:
            raise serializers.ValidationError(
                "end_datetime must be after start_datetime."
            )
        return attrs



class ItemPledgeSerializer(serializers.ModelSerializer):
    """
    Extra details for an item pledge.
    One-to-one with Pledge via Pledge.item_detail.
    """
    item_name = serializers.SerializerMethodField()

    class Meta:
        model = ItemPledge
        fields = "__all__"

    # ---------- INTERNAL HELPER ----------

    def _update_rewards(self, item_pledge):
        """
        After creating/updating an ItemPledge, set pledge.reward_tier
        based on:
          - the ItemNeed for this pledge's Need
          - fallback to ItemNeed.mode if item_pledge.mode is missing
        """
        pledge = item_pledge.pledge
        need = pledge.need
        if not need:
            return

        # Need → ItemNeed (via OneToOneField related_name="item_detail")
        item_need = getattr(need, "item_detail", None)
        if not item_need:
            return

        # Work out mode: prefer pledge.mode, fallback to item_need.mode
        mode = getattr(item_pledge, "mode", None) or getattr(item_need, "mode", None)

        tier = None
        if mode == "donation":
            tier = item_need.donation_reward_tier
        elif mode == "loan":
            tier = item_need.loan_reward_tier

        # If a tier is found, update the pledge
        if tier:
            pledge.reward_tier = tier
            pledge.save(update_fields=["reward_tier"])

    # ---------- CREATE / UPDATE ----------

    def create(self, validated_data):
        item_pledge = super().create(validated_data)
        self._update_rewards(item_pledge)
        return item_pledge

    def update(self, instance, validated_data):
        item_pledge = super().update(instance, validated_data)
        self._update_rewards(item_pledge)
        return item_pledge

    # ---------- READ-ONLY HELPER FIELD ----------

    def get_item_name(self, obj):
        """
        Safely walk pledge -> need -> item_detail.
        If anything is missing, return None instead of erroring.
        """
        need = getattr(obj.pledge, "need", None)
        if not need:
            return None

        item_detail = getattr(need, "item_detail", None)
        if not item_detail:
            return None

        return item_detail.item_name

    # ---------- VALIDATION ----------

    def validate_quantity(self, value):
        """
        Ensure pledged item quantity is > 0.
        """
        if value <= 0:
            raise serializers.ValidationError(
                "Quantity must be at least 1."
            )
        return value

# ====================================================================================
# PLEDGE BASE + DETAIL SERIALIZERS
# ====================================================================================

class PledgeSerializer(serializers.ModelSerializer):
    """
    Basic pledge serializer.

    Used for:
    - listing pledges
    - creating / updating pledges

    Notes:
    - supporter is read-only and comes from the logged-in user in the view
    - supporter_username is a convenience field for the frontend. 
    - The benefits are on the frontend, you don’t have to go look up the user’s username separately just to display “Janet pledged $50”.
    """
    supporter = serializers.ReadOnlyField(source="supporter.id")
    supporter_username = serializers.ReadOnlyField(source="supporter.username")

    # Relationship helpers
    fundraiser_title = serializers.CharField(source="fundraiser.title", read_only=True)
    fundraiser_id = serializers.IntegerField(source="fundraiser.id", read_only=True)

    need_title = serializers.CharField(source="need.title", read_only=True)
    need_id = serializers.IntegerField(source="need.id", read_only=True)
    need_type = serializers.CharField(source="need.need_type", read_only=True)
    reward_tier_name = serializers.SerializerMethodField()

    class Meta:
        model = Pledge
        # includes model fields + extra declared fields like supporter_username
        fields = "__all__"
        read_only_fields = ["date_created", "date_updated"]

    def get_reward_tier_name(self, obj):
        """
        Human-readable reward name for THIS pledge.

        - Money pledges: use the pledge.reward_tier (Bronze/Silver/Gold).
        - Item pledges: use the item need's donation/loan reward tier based on mode.
        - Time pledges: use the time need's reward_tier, if you have one.
        """
        need = obj.need
        if not need:
            # No need linked? fall back to whatever's on the pledge
            tier = obj.reward_tier
            return tier.name if tier else None

        # --- MONEY PLEDGE: show Bronze/Silver/Gold (global tier) ---
        if need.need_type == "money":
            tier = obj.reward_tier
            return tier.name if tier else None

        # --- ITEM PLEDGE: show the gear reward for THIS pledge ---
        if need.need_type == "item":
            # Need's extra info
            item_need = getattr(need, "item_detail", None)
            # Pledge's extra info
            item_pledge = getattr(obj, "item_detail", None)

            if not item_need or not item_pledge:
                return None

            mode = item_pledge.mode  # "donation" or "loan"
            if mode == "donation":
                tier = item_need.donation_reward_tier
            elif mode == "loan":
                tier = item_need.loan_reward_tier
            else:
                tier = None

            return tier.name if tier else None

        # --- TIME PLEDGE: if you have a reward_tier on the time need, show that ---
        if need.need_type == "time":
            time_need = getattr(need, "time_detail", None)
            if time_need and getattr(time_need, "reward_tier", None):
                return time_need.reward_tier.name
            return None

        return None

class PledgeDetailSerializer(PledgeSerializer):
    """
    Detailed view of a pledge.

    Includes:
    - all base pledge fields
    - money_detail / time_detail / item_detail (if present)
    - human-readable fundraiser and need labels using __str__
    - extra id/title/type fields to make relationships obvious
    """

    # Nested detail serializers 
    money_detail = MoneyPledgeSerializer(read_only=True)
    time_detail = TimePledgeSerializer(read_only=True)
    item_detail = ItemPledgeSerializer(read_only=True)

    # Keep string labels for quick readability
    fundraiser = serializers.StringRelatedField()
    need = serializers.StringRelatedField()


# ====================================================================================
# NEED DETAIL SERIALIZER (USES PLEDGE SERIALIZER)
# ====================================================================================

class NeedDetailSerializer(NeedSerializer):
    
    """
    Detailed view of a single Need.

    Includes:
    - the base Need fields (from NeedSerializer)
    - its MoneyNeed / TimeNeed / ItemNeed (via OneToOne relations)
    - the pledges linked to this need
    - extra fundraiser info for easier linking
    """

    fundraiser_id = serializers.IntegerField(source="fundraiser.id", read_only=True)
    fundraiser_title = serializers.CharField(source="fundraiser.title", read_only=True)

    money_detail = MoneyNeedSerializer(read_only=True)
    time_detail = TimeNeedSerializer(read_only=True)
    item_detail = ItemNeedSerializer(read_only=True)
    pledges = serializers.SerializerMethodField()

    class Meta(NeedSerializer.Meta):
        fields = NeedSerializer.Meta.fields

    def get_pledges(self, obj):
        return PledgeSerializer(obj.pledges.all(), many=True).data



# ====================================================================================
# FUNDRAISER SERIALIZERS
# ====================================================================================

class FundraiserSerializer(serializers.ModelSerializer):
    """
    Basic Fundraiser serializer.

    Used for:
    - fundraiser list endpoint (GET /fundraisers/)
    - fundraiser create / update

    Notes:
    - owner is read-only and set in the view as current user
    - is_open is read-only and comes from the @property on the model
    """
    owner = serializers.ReadOnlyField(source="owner.id")
    is_open = serializers.ReadOnlyField()  # uses the @property on the Fundraiser model

    class Meta:
        model = Fundraiser
        fields = "__all__"
        read_only_fields = ["date_created", "date_updated", "owner", "is_open"]


class FundraiserDetailSerializer(FundraiserSerializer):
    """
    Detailed view of a Fundraiser.

    Includes:
    - all fundraiser fields (from FundraiserSerializer)
    - its pledges (basic pledge info)
    - its needs (basic need info)
    - its reward tiers
    """
    pledges = PledgeSerializer(many=True, read_only=True)
    needs = NeedSerializer(many=True, read_only=True)
    reward_tiers = RewardTierSerializer(many=True, read_only=True)

# ====================================================================================
# TEMPLATE SERIALIZERS
# ====================================================================================

class TemplateRewardTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateRewardTier
        fields = [
            "id",
            "reward_type",
            "name",
            "description",
            "minimum_contribution_value",
            "image_url",
            "sort_order",
            "max_backers",
        ]


class TemplateNeedSerializer(serializers.ModelSerializer):
    time_reward_template = TemplateRewardTierSerializer(read_only=True)
    donation_reward_template = TemplateRewardTierSerializer(read_only=True)
    loan_reward_template = TemplateRewardTierSerializer(read_only=True)

    class Meta:
        model = TemplateNeed
        fields = [
            "id",
            "need_type",
            "title",
            "description",
            "priority",
            "sort_order",
            # money-like
            "target_amount",
            "comment",
            # time-like
            "start_datetime",
            "end_datetime",
            "volunteers_needed",
            "role_title",
            "location",
            "time_reward_template",
            # item-like
            "item_name",
            "quantity_needed",
            "mode",
            "notes",
            "donation_reward_template",
            "loan_reward_template",
        ]


class FundraiserTemplateSerializer(serializers.ModelSerializer):
    template_needs = TemplateNeedSerializer(many=True, read_only=True)
    template_reward_tiers = TemplateRewardTierSerializer(many=True, read_only=True)

    class Meta:
        model = FundraiserTemplate
        fields = [
            "id",
            "name",
            "description",
            "image_url",
            "category",
            "is_active",
            "template_needs",
            "template_reward_tiers",
        ]

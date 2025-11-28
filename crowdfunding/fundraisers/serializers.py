from rest_framework import serializers
from .models import (
    Fundraiser,
    Pledge,
    MoneyPledge,
    ItemPledge,
    TimePledge,
    Need,
    MoneyNeed,
    ItemNeed,
    TimeNeed,
    RewardTier,
)


# =========================
# PLEDGES
# =========================

class PledgeSerializer(serializers.ModelSerializer):
    supporter = serializers.ReadOnlyField(source="supporter.id")

    class Meta:
        model = Pledge
        fields = "__all__"


class PledgeDetailSerializer(PledgeSerializer):
    """
    Explicit update using validated_data, but only for fields
    that make sense to change on a Pledge.
    """
    def update(self, instance, validated_data):
        # allow updating comment, anonymous, status, need
        for field in ["comment", "anonymous", "status", "need"]:
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        # we normally do NOT allow changing supporter or fundraiser from here
        instance.save()
        return instance


# =========================
# FUNDRAISERS
# =========================

class FundraiserSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source="owner.id")
    # expose computed property from the model
    is_open = serializers.ReadOnlyField()

    class Meta:
        model = Fundraiser
        fields = "__all__"


class FundraiserDetailSerializer(FundraiserSerializer):
    pledges = PledgeSerializer(many=True, read_only=True)

    class Meta(FundraiserSerializer.Meta):
        fields = FundraiserSerializer.Meta.fields + ["pledges"]

    def update(self, instance, validated_data):
        """
        Explicit update using validated_data, but:
        - don't touch owner or created timestamps
        - don't touch is_open directly (it's a property based on status)
        """
        editable_fields = [
            "title",
            "description",
            "goal",
            "image_url",
            "location",
            "start_date",
            "end_date",
            "status",
            "enable_rewards",
            "sort_order",
        ]
        for field in editable_fields:
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        instance.save()
        return instance


# =========================
# NEEDS + DETAIL NEEDS
# =========================

class NeedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Need
        fields = "__all__"


class MoneyNeedSerializer(serializers.ModelSerializer):
    class Meta:
        model = MoneyNeed
        fields = "__all__"


class TimeNeedSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeNeed
        fields = "__all__"


class ItemNeedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemNeed
        fields = "__all__"


# =========================
# PLEDGE DETAIL TABLES
# =========================

class MoneyPledgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MoneyPledge
        fields = "__all__"


class ItemPledgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemPledge
        fields = "__all__"


class TimePledgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimePledge
        fields = "__all__"


# =========================
# REWARD TIERS
# =========================

class RewardTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = RewardTier
        fields = "__all__"

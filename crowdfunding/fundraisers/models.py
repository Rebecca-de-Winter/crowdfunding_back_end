from django.db import models
from django.contrib.auth import get_user_model

# Create your models here.

class Fundraiser(models.Model):

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
    ]
    title = models.CharField(max_length=200)
    description = models.TextField()
    goal = models.DecimalField(max_digits=10, decimal_places=2)
    image_url = models.URLField(blank=True)
    location = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )

    enable_rewards = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    owner = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name='owned_fundraisers'
    )

    class Meta:
        ordering = ["sort_order", "-date_created"]
    # This code sorts query results by default. First sort by sort_order (ascending) then date_created. 
    def __str__(self):
        return self.title
    # Human readable name for the object in admin/errors etc. 

    @property
    def is_open(self):
        """
        Backwards-compatible computed field:
        replaces the old boolean `is_open` with logic based on `status`.
        This is a virtual field, not stored in database. Links to serializer to give is_open = true even though its not in the database. 
        """
        return self.status == "active"

#######################################################################################################################

class Pledge(models.Model):

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("declined", "Declined"),
        ("cancelled", "Cancelled"),
    ]

    comment = models.TextField(blank=True)
    anonymous = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True) # add=True gives a creation timestamp
    date_updated = models.DateTimeField(auto_now=True) # updates every record
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    fundraiser = models.ForeignKey(
        'Fundraiser',
        on_delete=models.CASCADE,
        related_name='pledges'
    )
    need = models.ForeignKey(
        "Need",   
        on_delete=models.CASCADE,
        related_name="pledges",
        null=True,
        blank=True,
    )
    supporter = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name='pledges'
    )

    reward_tier = models.ForeignKey(
        "RewardTier",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pledges",
        help_text="Which reward this pledge is getting, if any.",
    )

    def __str__(self):
        return f"Pledge #{self.id} to {self.fundraiser.title}"
    # the string will tell us which pledge it is and to which fundraiser eg Pledge #1 to backyard festival.

class MoneyPledge(models.Model):
    pledge = models.OneToOneField(
        Pledge,
        on_delete=models.CASCADE,
        related_name="money_detail",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    comment = models.TextField(blank=True)

    def __str__(self):
        return f"MoneyPledge #{self.id}" # Returns string like "MoneyPledge #12"

class ItemPledge(models.Model):
    MODE_CHOICES = [
        ("donation", "Donation"),
        ("loan", "Loan"),
    ]

    pledge = models.OneToOneField(
        Pledge,
        on_delete=models.CASCADE,
        related_name="item_detail",
    )
    quantity = models.IntegerField()
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    comment = models.TextField(blank=True)

    def __str__(self):
        return f"ItemPledge #{self.id}" # Returns string like "ItemPledge #99"

class TimePledge(models.Model):
    pledge = models.OneToOneField(
        Pledge,
        on_delete=models.CASCADE,
        related_name="time_detail",
    )
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    hours_committed = models.DecimalField(max_digits=5, decimal_places=2)
    comment = models.TextField(blank=True)

    def __str__(self):
        return f"TimePledge #{self.id}" #Returns string like "TimePledge #33"
    
##################################################################################################

class Need(models.Model):
    TYPE_CHOICES = [
        ("money", "Money"),
        ("time", "Time"),
        ("item", "Item"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("partial", "Partial"),
        ("filled", "Filled"),
        ("cancelled", "Cancelled"),
    ]
    PRIORITY_CHOICES = [
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
    ]

    fundraiser = models.ForeignKey(
        Fundraiser,
        on_delete=models.CASCADE,
        related_name="needs",
    )
    need_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="open",
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default="medium",
    )
    sort_order = models.IntegerField(default=0)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.need_type})" # This returns strings like "sound tech for main stage (time)"
    
class MoneyNeed(models.Model):
    need = models.OneToOneField(
        Need,
        on_delete=models.CASCADE,
        related_name="money_detail", #OnetoOneField is a special type of foreign key with unique=True enforced.
    )
    target_amount = models.DecimalField(max_digits=10, decimal_places=2)
    comment = models.TextField(blank=True)

    def __str__(self):
        return f"MoneyNeed for {self.need}" # Returns strings like "MoneyNeed for PA hire (money)"

class TimeNeed(models.Model):
    need = models.OneToOneField(
        Need,
        on_delete=models.CASCADE,
        related_name="time_detail",
    )
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    volunteers_needed = models.IntegerField()
    role_title = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    reward_tier = models.ForeignKey(
        "RewardTier",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="time_needs",
    )

    def __str__(self):
        return f"TimeNeed for {self.need}" # Returns strings like "TimeNeed for Sound Tech (time)"


class ItemNeed(models.Model):
    MODE_CHOICES = [
        ("donation", "Donation"),
        ("loan", "Loan"),
        ("either", "Either"),
    ]

    need = models.OneToOneField(
        Need,
        on_delete=models.CASCADE,
        related_name="item_detail",
    )
    item_name = models.CharField(max_length=200)
    quantity_needed = models.IntegerField()
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    notes = models.TextField(blank=True)
    donation_reward_tier = models.ForeignKey(
        "RewardTier",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="donation_item_needs",
    )
    loan_reward_tier = models.ForeignKey(
        "RewardTier",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="loan_item_needs",
    )

    def __str__(self):
        return f"ItemNeed for {self.need}" # Returns string like "ItemNeed for Sound tech (item)"
    
###########################################################################################################   

class RewardTier(models.Model):
    fundraiser = models.ForeignKey(
        Fundraiser,
        on_delete=models.CASCADE,
        related_name="reward_tiers",
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    minimum_contribution_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Minimum cash amount for this reward (used for money pledges only).",
    )
    image_url = models.URLField(blank=True)
    sort_order = models.IntegerField(default=0)
    max_backers = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.fundraiser.title})" # Returns a string like "VIP Pass (FundraiserName)"

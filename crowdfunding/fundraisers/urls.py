from django.urls import path
from . import views

urlpatterns = [
    # Fundraisers
    path("fundraisers/", views.FundraiserList.as_view(), name="fundraiser-list"),
    path("fundraisers/<int:pk>/", views.FundraiserDetail.as_view(), name="fundraiser-detail"),

    # Base pledges
    path("pledges/", views.PledgeList.as_view(), name="pledge-list"),
    path("pledges/<int:pk>/", views.PledgeDetail.as_view(), name="pledge-detail"),

    # Base needs
    path("needs/", views.NeedList.as_view(), name="need-list"),
    path("needs/<int:pk>/", views.NeedDetail.as_view(), name="need-detail"),

    # Reward tiers
    path("reward-tiers/", views.RewardTierList.as_view(), name="rewardtier-list"),
    path("reward-tiers/<int:pk>/", views.RewardTierDetail.as_view(), name="rewardtier-detail"),

    # Need detail tables
    path("money-needs/", views.MoneyNeedList.as_view(), name="moneyneed-list"),
    path("money-needs/<int:pk>/", views.MoneyNeedDetail.as_view(), name="moneyneed-detail"),

    path("time-needs/", views.TimeNeedList.as_view(), name="timeneed-list"),
    path("time-needs/<int:pk>/", views.TimeNeedDetail.as_view(), name="timeneed-detail"),

    path("item-needs/", views.ItemNeedList.as_view(), name="itemneed-list"),
    path("item-needs/<int:pk>/", views.ItemNeedDetail.as_view(), name="itemneed-detail"),

    # Pledge detail tables
    path("money-pledges/", views.MoneyPledgeList.as_view(), name="moneypledge-list"),
    path("money-pledges/<int:pk>/", views.MoneyPledgeDetail.as_view(), name="moneypledge-detail"),

    path("time-pledges/", views.TimePledgeList.as_view(), name="timepledge-list"),
    path("time-pledges/<int:pk>/", views.TimePledgeDetail.as_view(), name="timepledge-detail"),

    path("item-pledges/", views.ItemPledgeList.as_view(), name="itempledge-list"),
    path("item-pledges/<int:pk>/", views.ItemPledgeDetail.as_view(), name="itempledge-detail"),

    # Fundraiser Templates

    path(
    "fundraiser-templates/",
    views.FundraiserTemplateListCreate.as_view(),
    name="fundraiser-template-list",
    ),

    path(
    "fundraiser-templates/<int:pk>/",
    views.FundraiserTemplateDetail.as_view(),
    name="fundraiser-template-detail",
    ),

    path(
    "fundraisers/apply-template/",
    views.ApplyTemplateToFundraiser.as_view(),
    name="apply-template-to-fundraiser",
    ),

    # Template Reward Tiers
    path(
    "template-reward-tiers/",
    views.TemplateRewardTierListCreate.as_view(),
    name="template-rewardtier-list",
    ),

    path(
    "template-reward-tiers/<int:pk>/",
    views.TemplateRewardTierDetail.as_view(),
    name="template-rewardtier-detail",
    ),

    # Template Needs
    path(
    "template-needs/",
    views.TemplateNeedListCreate.as_view(),
    name="template-need-list",
    ),

    path(
    "template-needs/<int:pk>/",
    views.TemplateNeedDetail.as_view(),
    name="template-need-detail",
    ),

    # REPORTING ENDPOINTS
    path(
        "reports/fundraisers/<int:pk>/summary/",
        views.FundraiserSummaryReport.as_view(),
        name="fundraiser-summary-report",
    ),
    path(
        "reports/needs/<int:pk>/progress/",
        views.NeedProgressReport.as_view(),
        name="need-progress-report",
    ),
    path(
        "reports/my-fundraisers/",
        views.MyFundraisersReport.as_view(),
        name="my-fundraisers-report",
    ),
        path(
        "reports/fundraisers/<int:pk>/pledges/",
        views.FundraiserPledgesReport.as_view(),
        name="fundraiser-pledges-report",
    ),
    path(
        "reports/my-pledges/",
        views.MyPledgesReport.as_view(),
        name="my-pledges-report",
    ),
    path(
        "reports/fundraisers/<int:pk>/my-rewards/",
        views.MyFundraiserRewardsReport.as_view(),
        name="fundraiser-my-rewards-report",
    ),


]

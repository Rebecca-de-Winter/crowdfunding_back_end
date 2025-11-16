from django.db import models

# Create your models here.

class Fundraiser(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    goal = models.IntegerField()
    image = models.URLField()
    is_open = models.BooleanField()
    date_created = models.DateTimeField(auto_now_add=True)

class Pledge(models.Model):
    TYPE_OF_PLEDGE = [
        ("money", "Money"),
        ("time", "Time"),
        ("loan", "Loan")
    ]
    pledge_type = models.CharField(max_length=10, choices=TYPE_OF_PLEDGE, default='money')
    amount = models.IntegerField()
    comment = models.CharField(max_length=200)
    anonymous = models.BooleanField()
    fundraiser = models.ForeignKey(
        'Fundraiser',
        on_delete=models.CASCADE,
        related_name='pledges'
    )
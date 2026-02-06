from django.urls import path
from . import views

urlpatterns = [
    path("signup/", views.SignUpView.as_view()),
    path("me/", views.CurrentUserView.as_view()),
    path('', views.CustomUserList.as_view()),
    path('<int:pk>/', views.CustomUserDetail.as_view()),
    
]
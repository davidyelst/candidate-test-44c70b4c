from django.urls import path
from . import views

urlpatterns = [
    path('auth/login/', views.login, name='login'),
    path('freelancers/', views.FreelancerListView.as_view(), name='freelancer-list'),
]

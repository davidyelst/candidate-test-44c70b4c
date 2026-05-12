from django.urls import path
from . import views

urlpatterns = [
    path('contracts/', views.ContractListView.as_view(), name='contract-list'),
    path('contracts/<int:pk>/', views.ContractDetailView.as_view(), name='contract-detail'),

    path('timesheets/', views.TimesheetListCreateView.as_view(), name='timesheet-list'),
    path('timesheets/<int:pk>/', views.TimesheetDetailView.as_view(), name='timesheet-detail'),
]

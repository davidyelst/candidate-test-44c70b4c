from django.urls import path

from . import views

urlpatterns = [
    path('webhook-endpoints/', views.WebhookEndpointListCreateView.as_view(),
         name='webhook-endpoint-list'),
    path('webhook-endpoints/<int:pk>/', views.WebhookEndpointDetailView.as_view(),
         name='webhook-endpoint-detail'),
    path('webhook-endpoints/<int:pk>/test/', views.WebhookEndpointTestView.as_view(),
         name='webhook-endpoint-test'),
    path('webhook-endpoints/<int:pk>/deliveries/', views.WebhookDeliveryListView.as_view(),
         name='webhook-endpoint-deliveries'),
]

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # Each domain app owns its slice of the /api/ surface.
    path('api/', include('accounts.urls')),
    path('api/', include('contracts.urls')),
    path('api/', include('billing.urls')),
    path('api/', include('webhooks.urls')),
]

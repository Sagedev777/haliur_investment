from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include(('client_accounts.urls', 'accounts'), namespace='accounts')),  # fixed
    path('', include('core.urls')),
    path('loans/', include(('loans.urls', 'loans'), namespace='loans')),
    # path('payments/', include(('payments.urls', 'payments'), namespace='payments')),
    path('reports/', include(('reports.urls', 'reports'), namespace='reports')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom admin site header
admin.site.site_header = "Haliqur Investments Administration"
admin.site.site_title = "Haliqur Investments"
admin.site.index_title = "Welcome to Haliqur Investments Management System"

from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from config.settings import MEDIA_ROOT, MEDIA_URL

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("user.urls")),
    path("code_cup/", include("code_cup.urls")),
] + static(MEDIA_URL, document_root=MEDIA_ROOT)

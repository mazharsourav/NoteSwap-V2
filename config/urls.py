from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

handler403 = 'core.views.pages.permission_denied'  # logs, then the normal 403 page

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('', include('core.urls')),
]

if settings.DEBUG:
    # Preview the error pages locally (with DEBUG on, Django shows its debug pages instead).
    urlpatterns += [
        path(f'__preview__/{code}/', TemplateView.as_view(template_name=f'{code}.html'))
        for code in (403, 404, 500)
    ]
    # Only profile pictures are public media. Notes and NoteSolve files are served by
    # access-checked views in core (see the /files/ routes). In production the web
    # server must likewise expose only MEDIA_ROOT/profiles/ under /media/profiles/.
    urlpatterns += static(settings.MEDIA_URL + 'profiles/', document_root=settings.MEDIA_ROOT / 'profiles')

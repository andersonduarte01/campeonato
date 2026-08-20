from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls', namespace='core')),
    # ── Módulos desativados — reativar cirurgicamente ──
    path('equipe/', include('apps.equipe.urls', namespace='equipe')),
    path('competicao/', include('apps.competicao.urls', namespace='competicao')),
    path('criterios/', include('apps.criterios.urls', namespace='criterios')),
    path('auditoria/', include('apps.auditoria.urls', namespace='auditoria')),
    path('registro/', include('apps.registro.urls', namespace='registro')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

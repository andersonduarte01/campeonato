from django.urls import path
from . import views

app_name = 'auditoria'

urlpatterns = [
    path('lgpd/',            views.lgpd_dashboard_view,      name='lgpd_dashboard'),
    path('lgpd/exportar/',   views.lgpd_exportar_dados_view, name='lgpd_exportar'),
    path('lgpd/anonimizar/', views.lgpd_anonimizar_view,     name='lgpd_anonimizar'),
    path('eventos/',         views.eventos_lista_view,        name='eventos_lista'),
]

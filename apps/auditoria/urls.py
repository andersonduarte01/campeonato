from django.urls import path
from . import views

app_name = 'auditoria'

urlpatterns = [
    path('logs/',                 views.audit_log_lista_view,    name='log_lista'),
    path('logs/<int:pk>/',        views.audit_log_detalhe_view,  name='log_detalhe'),
    path('lgpd/',                 views.lgpd_dashboard_view,     name='lgpd_dashboard'),
    path('lgpd/exportar/',        views.lgpd_exportar_dados_view, name='lgpd_exportar'),
    path('lgpd/anonimizar/',      views.lgpd_anonimizar_view,    name='lgpd_anonimizar'),
]

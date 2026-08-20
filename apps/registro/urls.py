from django.urls import path
from . import views

app_name = 'registro'

urlpatterns = [
    # Dashboard
    path('', views.dashboard_federativo, name='dashboard'),

    # 1. Registro Federativo
    path('registros/',              views.registro_lista,   name='registro_lista'),
    path('registros/novo/',         views.registro_criar,   name='registro_criar'),
    path('registros/<int:pk>/',     views.registro_detalhe, name='registro_detalhe'),
    path('registros/<int:pk>/editar/', views.registro_editar, name='registro_editar'),

    # 2. Transferências
    path('transferencias/',                            views.transferencia_lista,   name='transferencia_lista'),
    path('transferencias/nova/',                       views.transferencia_criar,   name='transferencia_criar'),
    path('transferencias/<int:pk>/',                   views.transferencia_detalhe, name='transferencia_detalhe'),
    path('transferencias/<int:pk>/analisar/',  views.transferencia_analisar, name='transferencia_analisar'),
    path('transferencias/<int:pk>/aprovar/',   views.transferencia_aprovar,  name='transferencia_aprovar'),
    path('transferencias/<int:pk>/rejeitar/',  views.transferencia_rejeitar, name='transferencia_rejeitar'),
    path('transferencias/<int:pk>/cancelar/',  views.transferencia_cancelar, name='transferencia_cancelar'),

    # Janelas de Transferência
    path('janelas/',               views.janela_lista,   name='janela_lista'),
    path('janelas/<int:pk>/editar/', views.janela_editar, name='janela_editar'),

]

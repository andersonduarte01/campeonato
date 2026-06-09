from django.urls import path
from . import views

app_name = 'federacao'

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
    path('transferencias/<int:pk>/<str:acao>/',        views.transferencia_acao,    name='transferencia_acao'),

    # Janelas de Transferência
    path('janelas/',               views.janela_lista,   name='janela_lista'),
    path('janelas/<int:pk>/editar/', views.janela_editar, name='janela_editar'),

    # 3. Perfil Federativo do Clube
    path('clubes/',                  views.clube_lista,   name='clube_lista'),
    path('clubes/novo/',             views.clube_criar,   name='clube_criar'),
    path('clubes/<int:pk>/',         views.clube_detalhe, name='clube_detalhe'),
    path('clubes/<int:pk>/editar/',  views.clube_editar,  name='clube_editar'),

    # 4. Documentos
    path('documentos/',                        views.documento_lista,   name='documento_lista'),
    path('documentos/upload/',                 views.documento_upload,  name='documento_upload'),
    path('documentos/<int:pk>/aprovar/',       views.documento_aprovar, name='documento_aprovar'),

    # Tipos de Documento
    path('documentos/tipos/',               views.tipo_documento_lista,   name='tipo_documento_lista'),
    path('documentos/tipos/<int:pk>/editar/', views.tipo_documento_editar, name='tipo_documento_editar'),
]

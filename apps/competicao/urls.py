from django.urls import path
from . import views

app_name = 'competicao'

urlpatterns = [
    path('add/', views.CompeticaoCreate.as_view(), name='competicao_add'),
    path('lista/', views.CompeticoesLista.as_view(), name='competicao_lista'),
    path('buscar/', views.buscar_equipes, name='buscar_equipes'),
    path('<int:pk>/buscar_equipes/', views.associar_equipe_view, name='buscar_equipes_view'),
    path('remover/<int:equipe_id>/<int:pk>', views.remover_equipe_view, name='remover_equipe_view'),
    path('gerar/tabela/<int:competicao_id>/', views.criar_jogos_view, name='criar_jogos'),
]

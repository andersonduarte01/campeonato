from django.urls import path
from . import views

app_name = 'competicao'

urlpatterns = [
    # Competição
    path('add/', views.CompeticaoCreate.as_view(), name='competicao_add'),
    path('lista/', views.CompeticoesLista.as_view(), name='competicao_lista'),
    path('buscar/', views.buscar_equipes, name='buscar_equipes'),
    path('<int:pk>/buscar_equipes/', views.associar_equipe_view, name='buscar_equipes_view'),
    path('remover/<int:equipe_id>/<int:pk>/', views.remover_equipe_view, name='remover_equipe_view'),
    path('gerar/tabela/<int:competicao_id>/', views.criar_jogos_view, name='criar_jogos'),

    # Classificação e rodadas
    path('<int:pk>/classificacao/', views.ClassificacaoView.as_view(), name='classificacao'),
    path('<int:pk>/rodadas/', views.RodadasView.as_view(), name='rodadas'),

    # Inscrição de atletas
    path('<int:pk>/inscricao/', views.InscricaoView.as_view(), name='inscricao'),
    path('<int:competicao_pk>/inscricao/<int:equipe_pk>/adicionar/', views.inscricao_criar_view, name='inscricao_criar'),
    path('inscricao/<int:pk>/remover/', views.inscricao_excluir_view, name='inscricao_excluir'),

    # Jogo
    path('jogo/<int:pk>/', views.JogoDetalheView.as_view(), name='jogo_detalhe'),
    path('jogo/<int:pk>/editar/', views.JogoUpdateView.as_view(), name='jogo_editar'),
    path('jogo/<int:jogo_pk>/gol/', views.gol_criar_view, name='gol_criar'),
    path('jogo/gol/<int:pk>/excluir/', views.gol_excluir_view, name='gol_excluir'),
    path('jogo/<int:jogo_pk>/cartao/', views.cartao_criar_view, name='cartao_criar'),
    path('jogo/cartao/<int:pk>/excluir/', views.cartao_excluir_view, name='cartao_excluir'),

    # Suspensões
    path('suspensao/<int:pk>/cumprir/', views.suspensao_cumprir_view, name='suspensao_cumprir'),

    # Fases
    path('<int:pk>/fases/', views.FasesView.as_view(), name='fases'),
    path('<int:competicao_pk>/fases/criar/', views.fase_criar_view, name='fase_criar'),
    path('fases/<int:pk>/excluir/', views.fase_excluir_view, name='fase_excluir'),

    # Grupos (fase de grupos)
    path('fases/<int:pk>/grupos/', views.GruposFaseView.as_view(), name='grupos_fase'),
    path('fases/<int:fase_pk>/grupos/criar/', views.grupo_criar_view, name='grupo_criar'),
    path('fases/<int:pk>/gerar-grupos/', views.gerar_jogos_grupos_view, name='gerar_jogos_grupos'),
    path('grupos/<int:pk>/excluir/', views.grupo_excluir_view, name='grupo_excluir'),
    path('grupos/<int:pk>/atribuir/', views.grupo_atribuir_equipe_view, name='grupo_atribuir_equipe'),
    path('grupos/<int:pk>/remover/<int:equipe_pk>/', views.grupo_remover_equipe_view, name='grupo_remover_equipe'),

    # Mata-mata / Chaveamento
    path('fases/<int:pk>/chaveamento/', views.ChaveamentoView.as_view(), name='chaveamento'),
    path('confronto/<int:pk>/penaltis/', views.confronto_penaltis_view, name='confronto_penaltis'),
    path('fases/<int:fase_grupos_pk>/avancar/<int:fase_mata_mata_pk>/', views.avancar_classificados_view, name='avancar_classificados'),
]

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
    path('<int:pk>/estatisticas/', views.EstatisticasView.as_view(), name='estatisticas'),

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
    path('jogo/<int:pk>/escalacao/', views.EscalacaoJogoView.as_view(), name='escalacao'),
    path('jogo/<int:jogo_pk>/escalacao/<int:equipe_pk>/adicionar/', views.escalacao_criar_view, name='escalacao_criar'),
    path('jogo/escalacao/<int:pk>/excluir/', views.escalacao_excluir_view, name='escalacao_excluir'),
    path('jogo/<int:jogo_pk>/substituicao/', views.substituicao_criar_view, name='substituicao_criar'),
    path('jogo/substituicao/<int:pk>/excluir/', views.substituicao_excluir_view, name='substituicao_excluir'),
    path('jogo/<int:jogo_pk>/arbitros/', views.arbitros_jogo_criar_view, name='arbitros_jogo_criar'),
    path('jogo/arbitros/<int:pk>/excluir/', views.arbitros_jogo_excluir_view, name='arbitros_jogo_excluir'),

    # PDF / Impressão
    path('<int:pk>/pdf/classificacao/', views.pdf_classificacao_view, name='pdf_classificacao'),
    path('jogo/<int:pk>/pdf/sumula/', views.pdf_sumula_view, name='pdf_sumula'),

    # Suspensões
    path('suspensao/<int:pk>/cumprir/', views.suspensao_cumprir_view, name='suspensao_cumprir'),

    # Fases
    path('<int:pk>/fases/', views.FasesView.as_view(), name='fases'),
    path('<int:competicao_pk>/fases/criar/', views.fase_criar_view, name='fase_criar'),
    path('fases/<int:pk>/excluir/', views.fase_excluir_view, name='fase_excluir'),
    path('fases/<int:pk>/bracket/', views.BracketView.as_view(), name='bracket'),

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

    # Local e Árbitro
    path('locais/', views.LocalListView.as_view(), name='local_lista'),
    path('locais/criar/', views.local_criar_view, name='local_criar'),
    path('locais/<int:pk>/editar/', views.local_editar_view, name='local_editar'),
    path('locais/<int:pk>/excluir/', views.local_excluir_view, name='local_excluir'),
    path('arbitros/', views.ArbitroListView.as_view(), name='arbitro_lista'),
    path('arbitros/criar/', views.arbitro_criar_view, name='arbitro_criar'),
    path('arbitros/<int:pk>/editar/', views.arbitro_editar_view, name='arbitro_editar'),
    path('arbitros/<int:pk>/excluir/', views.arbitro_excluir_view, name='arbitro_excluir'),

    # PDF extras (M)
    path('<int:competicao_pk>/equipe/<int:equipe_pk>/pdf/elenco/', views.pdf_elenco_view, name='pdf_elenco'),
    path('<int:pk>/pdf/artilheiros/', views.pdf_artilheiros_view, name='pdf_artilheiros'),

    # Avaliação árbitro (K)
    path('jogo/<int:jogo_pk>/avaliar-arbitro/', views.avaliacao_arbitro_view, name='avaliacao_arbitro'),

    # Notificações (N)
    path('notificacoes/', views.notificacoes_view, name='notificacoes'),

    # Taxa de inscrição (P)
    path('inscricao/<int:pk>/toggle-taxa/', views.inscricao_toggle_taxa_view, name='inscricao_toggle_taxa'),

    # 3º lugar (R)
    path('fases/<int:fase_pk>/terceiro-lugar/', views.terceiro_lugar_criar_view, name='terceiro_lugar_criar'),

    # Busca global (T)
    path('busca/', views.busca_global_view, name='busca_global'),

    # Calendário (G)
    path('calendario/', views.calendario_view, name='calendario'),

    # Dashboard (A)
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # Área Pública (O)
    path('public/<int:pk>/classificacao/', views.PublicClassificacaoView.as_view(), name='public_classificacao'),

    # API REST (S)
    path('api/competicoes/', views.api_competicoes_view, name='api_competicoes'),
    path('api/<int:pk>/classificacao/', views.api_classificacao_view, name='api_classificacao'),
    path('api/<int:pk>/jogos/', views.api_jogos_view, name='api_jogos'),
    path('api/<int:pk>/artilheiros/', views.api_artilheiros_view, name='api_artilheiros'),
]

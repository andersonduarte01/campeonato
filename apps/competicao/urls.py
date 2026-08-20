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
    path('<int:pk>/transicao/<str:acao>/', views.competicao_transicao_view, name='competicao_transicao'),

    # Classificação e rodadas
    path('<int:pk>/classificacao/', views.ClassificacaoView.as_view(), name='classificacao'),
    path('<int:pk>/rodadas/', views.RodadasView.as_view(), name='rodadas'),
    path('<int:pk>/estatisticas/', views.EstatisticasView.as_view(), name='estatisticas'),

    # Inscrição de atletas
    path('<int:pk>/inscricao/', views.InscricaoView.as_view(), name='inscricao'),
    path('<int:competicao_pk>/inscricao/<int:equipe_pk>/adicionar/', views.inscricao_criar_view, name='inscricao_criar'),
    path('inscricao/<int:pk>/remover/', views.inscricao_excluir_view, name='inscricao_excluir'),
    path('inscricao/<int:pk>/toggle-taxa/', views.inscricao_toggle_taxa_view, name='inscricao_toggle_taxa'),

    # Jogo
    path('jogo/<int:pk>/', views.JogoDetalheView.as_view(), name='jogo_detalhe'),
    path('jogo/<int:pk>/configurar/', views.jogo_config_view, name='jogo_configurar'),
    path('jogo/<int:pk>/editar/', views.JogoUpdateView.as_view(), name='jogo_editar'),
    path('jogo/<int:pk>/iniciar/', views.jogo_iniciar_view, name='jogo_iniciar'),
    path('jogo/<int:pk>/declarar-wo/', views.jogo_declarar_wo_view, name='jogo_declarar_wo'),
    path('jogo/<int:pk>/homologar/', views.jogo_homologar_view, name='jogo_homologar'),
    path('jogo/<int:pk>/anular/', views.jogo_anular_view, name='jogo_anular'),
    path('<int:pk>/desistencia/<int:equipe_id>/', views.registrar_desistencia_view, name='registrar_desistencia'),
    path('jogo/<int:jogo_pk>/gol/', views.gol_criar_view, name='gol_criar'),
    path('jogo/gol/<int:pk>/excluir/', views.gol_excluir_view, name='gol_excluir'),
    path('jogo/<int:jogo_pk>/cartao/', views.cartao_criar_view, name='cartao_criar'),
    path('jogo/cartao/<int:pk>/excluir/', views.cartao_excluir_view, name='cartao_excluir'),

    # PDF
    path('<int:pk>/pdf/classificacao/', views.pdf_classificacao_view, name='pdf_classificacao'),
    path('jogo/<int:pk>/pdf/sumula/', views.pdf_sumula_view, name='pdf_sumula'),
    path('<int:competicao_pk>/equipe/<int:equipe_pk>/pdf/elenco/', views.pdf_elenco_view, name='pdf_elenco'),
    path('<int:pk>/pdf/artilheiros/', views.pdf_artilheiros_view, name='pdf_artilheiros'),

    # Suspensões
    path('suspensao/<int:pk>/cumprir/', views.suspensao_cumprir_view, name='suspensao_cumprir'),

    # Etapas Knockout
    path('<int:pk>/etapas/', views.EtapasView.as_view(), name='etapas'),
    path('<int:competicao_pk>/etapas/criar/', views.etapa_criar_view, name='etapa_criar'),
    path('etapas/<int:pk>/excluir/', views.etapa_excluir_view, name='etapa_excluir'),
    path('etapas/<int:pk>/bracket/', views.BracketView.as_view(), name='bracket'),

    # Grupos
    path('<int:pk>/grupos/', views.GruposView.as_view(), name='grupos'),
    path('<int:competicao_pk>/grupos/criar/', views.grupo_criar_view, name='grupo_criar'),
    path('<int:pk>/gerar-grupos/', views.gerar_jogos_grupos_view, name='gerar_jogos_grupos'),
    path('grupos/<int:pk>/excluir/', views.grupo_excluir_view, name='grupo_excluir'),
    path('grupos/<int:pk>/atribuir/', views.grupo_atribuir_equipe_view, name='grupo_atribuir_equipe'),
    path('grupos/<int:pk>/remover/<int:equipe_pk>/', views.grupo_remover_equipe_view, name='grupo_remover_equipe'),

    # Mata-mata
    path('etapas/<int:pk>/chaveamento/', views.ChaveamentoView.as_view(), name='chaveamento'),
    path('confronto/<int:pk>/penaltis/', views.confronto_penaltis_view, name='confronto_penaltis'),
    path('<int:competicao_pk>/avancar/<int:etapa_pk>/', views.avancar_classificados_view, name='avancar_classificados'),
    path('etapas/<int:origem_pk>/avancar-vencedores/<int:destino_pk>/', views.avancar_vencedores_view, name='avancar_vencedores'),
    path('etapas/<int:etapa_pk>/terceiro-lugar/', views.terceiro_lugar_criar_view, name='terceiro_lugar_criar'),
    path('etapas/<int:pk>/seeding/', views.seeding_chaveamento_view, name='seeding_chaveamento'),

    # Local e Árbitro
    path('locais/', views.LocalListView.as_view(), name='local_lista'),
    path('locais/criar/', views.local_criar_view, name='local_criar'),
    path('locais/<int:pk>/editar/', views.local_editar_view, name='local_editar'),
    path('locais/<int:pk>/excluir/', views.local_excluir_view, name='local_excluir'),
    path('arbitros/', views.ArbitroListView.as_view(), name='arbitro_lista'),
    path('arbitros/<int:pk>/', views.arbitro_detalhe_view, name='arbitro_detalhe'),
    path('arbitros/<int:pk>/excluir/', views.arbitro_excluir_view, name='arbitro_excluir'),

    # Dashboard, Calendário, Busca
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('dashboard/jogos/', views.jogos_todos_view, name='jogos_todos'),
    path('dashboard/arbitro/', views.arbitro_dashboard_view, name='arbitro_dashboard'),
    path('dashboard/dirigente/', views.dirigente_dashboard_view, name='dirigente_dashboard'),
    path('dashboard/dirigente/jogos/', views.dirigente_jogos_view, name='dirigente_jogos'),
    path('dashboard/dirigente/competicao/<int:competicao_pk>/inscricao/', views.dirigente_inscricao_view, name='dirigente_inscricao'),
    path('dashboard/dirigente/atleta/<int:pk>/situacao/', views.atleta_situacao_view, name='atleta_situacao'),
    path('dashboard/dirigente/escalacao/', views.dirigente_escalacao_view, name='dirigente_escalacao'),
    path('dashboard/dirigente/escalacao/salvar/', views.escalacao_tatica_salvar_view, name='escalacao_tatica_salvar'),
    path('dashboard/dirigente/escalacao/jogo/<int:jogo_pk>/', views.dirigente_escalacao_jogo_view, name='dirigente_escalacao_jogo'),
    path('dashboard/dirigente/escalacao/jogo/<int:jogo_pk>/salvar/', views.escalacao_tatica_jogo_salvar_view, name='escalacao_tatica_jogo_salvar'),
    path('calendario/', views.calendario_view, name='calendario'),
    path('busca/', views.busca_global_view, name='busca_global'),

    # Área pública
    path('public/<int:pk>/classificacao/', views.PublicClassificacaoView.as_view(), name='public_classificacao'),
    path('portal/clube/<int:pk>/', views.portal_clube_view, name='portal_clube'),
    path('portal/atleta/<int:pk>/', views.portal_atleta_view, name='portal_atleta'),
    path('portal/arbitro/<int:pk>/', views.portal_arbitro_view, name='portal_arbitro'),

    # API REST (legada, sem auth)
    path('api/competicoes/', views.api_competicoes_view, name='api_competicoes'),
    path('api/<int:pk>/classificacao/', views.api_classificacao_view, name='api_classificacao'),
    path('api/<int:pk>/jogos/', views.api_jogos_view, name='api_jogos'),
    path('api/<int:pk>/artilheiros/', views.api_artilheiros_view, name='api_artilheiros'),

    # API REST v2 (autenticada por ApiKey)
    path('api/v2/competicoes/', views.api_v2_competicoes_view, name='api_v2_competicoes'),
    path('api/v2/<int:pk>/classificacao/', views.api_v2_classificacao_view, name='api_v2_classificacao'),
    path('api/v2/<int:pk>/jogos/', views.api_v2_jogos_view, name='api_v2_jogos'),
    path('api/v2/<int:pk>/artilheiros/', views.api_v2_artilheiros_view, name='api_v2_artilheiros'),
    path('api/v2/jogo/<int:jogo_pk>/sumula/', views.api_v2_sumula_view, name='api_v2_sumula'),
    path('api-keys/', views.api_keys_view, name='api_keys'),
    path('api-keys/criar/', views.api_key_criar_view, name='api_key_criar'),
    path('api-keys/<int:pk>/revogar/', views.api_key_revogar_view, name='api_key_revogar'),

    # Microsite público (H)
    path('microsite/<int:pk>/', views.microsite_view, name='microsite'),
    path('microsite/<int:pk>/widget/', views.widget_classificacao_view, name='widget_classificacao'),

    # Súmula Digital (A)
    path('jogo/<int:jogo_pk>/sumula/', views.sumula_view, name='sumula'),
    path('sumula/<int:pk>/arbitragem/', views.sumula_salvar_arbitragem_view, name='sumula_arbitragem'),
    path('sumula/<int:sumula_pk>/escalacao/<int:equipe_pk>/adicionar/', views.escalacao_adicionar_view, name='escalacao_adicionar'),
    path('escalacao/<int:pk>/remover/', views.escalacao_remover_view, name='escalacao_remover'),
    path('sumula/<int:sumula_pk>/substituicao/<int:equipe_pk>/adicionar/', views.substituicao_adicionar_view, name='substituicao_adicionar'),
    path('substituicao/<int:pk>/remover/', views.substituicao_remover_view, name='substituicao_remover'),
    path('sumula/<int:sumula_pk>/ocorrencia/adicionar/', views.ocorrencia_adicionar_view, name='ocorrencia_adicionar'),
    path('ocorrencia/<int:pk>/remover/', views.ocorrencia_remover_view, name='ocorrencia_remover'),
    path('sumula/<int:pk>/encerrar/', views.sumula_encerrar_view, name='sumula_encerrar'),
    path('sumula/<int:pk>/homologar/', views.sumula_homologar_view, name='sumula_homologar'),
    path('sumula/<int:pk>/reabrir/', views.sumula_reabrir_view, name='sumula_reabrir'),

    # Temporadas (D)
    path('temporadas/', views.temporada_lista_view, name='temporada_lista'),
    path('temporadas/criar/', views.temporada_criar_view, name='temporada_criar'),
    path('temporadas/<int:pk>/ativar/', views.temporada_ativar_view, name='temporada_ativar'),

    # Estatísticas avançadas (I)
    path('<int:pk>/fairplay/', views.estatisticas_fairplay_view, name='fairplay'),
    path('<int:pk>/historico-posicoes/', views.historico_posicoes_view, name='historico_posicoes'),
]

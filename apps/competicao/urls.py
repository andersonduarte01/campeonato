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
    path('arbitros/<int:pk>/', views.arbitro_detalhe_view, name='arbitro_detalhe'),
    path('arbitros/<int:pk>/editar/', views.arbitro_editar_view, name='arbitro_editar'),
    path('arbitros/<int:pk>/excluir/', views.arbitro_excluir_view, name='arbitro_excluir'),
    path('jogo/<int:jogo_pk>/escala-inteligente/', views.escala_inteligente_view, name='escala_inteligente'),

    # Súmula Digital — Fase 3
    path('jogo/<int:jogo_pk>/sumula/', views.sumula_digital_view, name='sumula_digital'),
    path('jogo/<int:jogo_pk>/sumula/ocorrencia/', views.sumula_ocorrencia_criar_view, name='sumula_ocorrencia_criar'),
    path('jogo/sumula/ocorrencia/<int:pk>/excluir/', views.sumula_ocorrencia_excluir_view, name='sumula_ocorrencia_excluir'),
    path('jogo/<int:jogo_pk>/sumula/anexo/', views.sumula_anexo_criar_view, name='sumula_anexo_criar'),
    path('jogo/sumula/anexo/<int:pk>/excluir/', views.sumula_anexo_excluir_view, name='sumula_anexo_excluir'),
    path('jogo/<int:jogo_pk>/sumula/assinar/<str:papel>/', views.sumula_assinar_view, name='sumula_assinar'),
    path('jogo/<int:jogo_pk>/sumula/finalizar/', views.sumula_finalizar_view, name='sumula_finalizar'),

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

    # Tribunal Desportivo — Fase 4
    path('tribunal/', views.tribunal_dashboard_view, name='tribunal_dashboard'),
    path('tribunal/processos/', views.ProcessoListView.as_view(), name='processo_lista'),
    path('tribunal/processos/criar/', views.processo_criar_view, name='processo_criar'),
    path('tribunal/processos/<int:pk>/', views.processo_detalhe_view, name='processo_detalhe'),
    path('tribunal/processos/<int:pk>/editar/', views.processo_editar_view, name='processo_editar'),
    path('tribunal/processos/<int:pk>/arquivar/', views.processo_arquivar_view, name='processo_arquivar'),
    path('tribunal/processos/<int:pk>/reabrir/', views.processo_reabrir_view, name='processo_reabrir'),
    path('tribunal/processos/<int:processo_pk>/julgar/', views.julgamento_criar_view, name='julgamento_criar'),
    path('tribunal/processos/<int:processo_pk>/recurso/', views.recurso_criar_view, name='recurso_criar'),
    path('tribunal/recurso/<int:pk>/decidir/', views.recurso_decidir_view, name='recurso_decidir'),

    # Financeiro Federativo — Fase 5
    path('financeiro/', views.financeiro_dashboard_view, name='financeiro_dashboard'),
    path('financeiro/lancamentos/', views.LancamentoListView.as_view(), name='lancamento_lista'),
    path('financeiro/lancamentos/criar/', views.lancamento_criar_view, name='lancamento_criar'),
    path('financeiro/lancamentos/criar/receita/', views.lancamento_criar_view, {'tipo': 'receita'}, name='lancamento_criar_receita'),
    path('financeiro/lancamentos/criar/despesa/', views.lancamento_criar_view, {'tipo': 'despesa'}, name='lancamento_criar_despesa'),
    path('financeiro/lancamentos/<int:pk>/', views.lancamento_detalhe_view, name='lancamento_detalhe'),
    path('financeiro/lancamentos/<int:pk>/editar/', views.lancamento_editar_view, name='lancamento_editar'),
    path('financeiro/lancamentos/<int:pk>/excluir/', views.lancamento_excluir_view, name='lancamento_excluir'),
    path('financeiro/lancamentos/<int:pk>/baixar/', views.lancamento_baixar_view, name='lancamento_baixar'),
    path('financeiro/conciliacao/', views.conciliacao_view, name='conciliacao'),
    path('financeiro/lancamentos/<int:pk>/comprovante/', views.pdf_comprovante_view, name='pdf_comprovante'),

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

    # Portal Público — Fase 6 (público, sem login)
    path('portal/', views.portal_home_view, name='portal_home'),
    path('portal/publicacoes/', views.portal_publicacao_lista_view, name='portal_publicacao_lista'),
    path('portal/publicacoes/<slug:slug>/', views.portal_publicacao_detalhe_view, name='portal_publicacao_detalhe'),
    path('portal/clube/<int:pk>/', views.portal_clube_view, name='portal_clube'),
    path('portal/atleta/<int:pk>/', views.portal_atleta_view, name='portal_atleta'),
    path('portal/arbitro/<int:pk>/', views.portal_arbitro_view, name='portal_arbitro'),

    # Portal: gestão de conteúdo (com login)
    path('portal/admin/', views.publicacao_admin_lista_view, name='publicacao_admin_lista'),
    path('portal/admin/criar/', views.publicacao_criar_view, name='publicacao_criar'),
    path('portal/admin/<int:pk>/editar/', views.publicacao_editar_view, name='publicacao_editar'),
    path('portal/admin/<int:pk>/excluir/', views.publicacao_excluir_view, name='publicacao_excluir'),
]

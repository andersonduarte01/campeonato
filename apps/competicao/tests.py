from datetime import date

from django.db.models import Q
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Federacao, Usuario, UsuarioFederacao
from apps.criterios.models import CriterioClassificacao, FormatoCompeticao
from apps.equipe.models import Atleta, Equipe

from .dominio.avancos import AvancoService
from .dominio.desistencia import DesistenciaService
from .dominio.excecoes import RegraVioladaError, TransicaoInvalida
from .dominio.fases.grupos import GruposStrategy
from .dominio.fases.liga import LigaStrategy
from .dominio.fases.mata_mata import MataMataStrategy
from .dominio.suspensoes import SuspensaoService
from .dominio.wo import WOService
from .forms import CompeticaoForm, ConfrontoPenaltisForm
from .forms import EscalacaoJogoForm
from .models import (
    Cartao, Classificacao, ClassificacaoGrupo, Competicao, ConfrontoMatamate,
    EscalacaoJogo, EtapaKnockout, Fase, Gol, Grupo, InscricaoAtleta, InscricaoEquipe,
    Jogo, ParticipacaoFase, Rodada, Sumula, Suspensao, ZonaClassificacao,
)


def criar_federacao(nome='Federação A', slug='fed-a'):
    return Federacao.objects.create(nome=nome, slug=slug)


def criar_competicao(federacao, formato=None, nome='Competição Teste', **kw):
    return Competicao.objects.create(
        federacao=federacao, nome=nome, data_inicio=date(2026, 1, 1),
        formato=formato, **kw,
    )


def criar_equipes(federacao, n, prefixo='Equipe'):
    return [
        Equipe.objects.create(federacao=federacao, nome_equipe=f'{prefixo} {i}')
        for i in range(1, n + 1)
    ]


def inscrever(competicao, equipes):
    for e in equipes:
        InscricaoEquipe.objects.create(competicao=competicao, equipe=e)


def jogo(rodada, casa, fora, gc=0, gf=0, finalizado=True, anulado=False):
    return Jogo.objects.create(
        rodada=rodada, equipe_casa=casa, equipe_fora=fora,
        gols_casa=gc, gols_fora=gf, finalizado=finalizado, anulado=anulado,
    )


def criar_admin(federacao, email='admin@teste.com'):
    usuario = Usuario.objects.create(email=email, nome='Admin Teste')
    usuario.set_password('senha123')
    usuario.save()
    UsuarioFederacao.objects.create(
        usuario=usuario, federacao=federacao, papel=UsuarioFederacao.ADMIN,
    )
    return usuario


# ---------------------------------------------------------------------------
# Passo 1.1 (P1) — classificação geral só considera jogos da fase de liga
# ---------------------------------------------------------------------------

class EscopoClassificacaoTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        self.formato = FormatoCompeticao.objects.create(
            nome='Misto', pontos_corridos=True, fase_grupos=True, mata_mata=True,
        )
        self.comp = criar_competicao(self.fed, self.formato)
        self.eq1, self.eq2 = criar_equipes(self.fed, 2)
        inscrever(self.comp, [self.eq1, self.eq2])

    def test_jogo_de_liga_atualiza_classificacao(self):
        rodada = Rodada.objects.create(competicao=self.comp, numero=1)
        jogo(rodada, self.eq1, self.eq2, 2, 0)
        cl = Classificacao.objects.get(competicao=self.comp, equipe=self.eq1)
        self.assertEqual(cl.pontos, 3)
        self.assertEqual(cl.saldo_gols, 2)

    def test_jogo_de_mata_mata_nao_polui_classificacao(self):
        etapa = EtapaKnockout.objects.create(competicao=self.comp, tipo=EtapaKnockout.FINAL)
        rodada = Rodada.objects.create(competicao=self.comp, etapa=etapa, numero=1)
        jogo(rodada, self.eq1, self.eq2, 2, 0)
        self.assertFalse(Classificacao.objects.filter(competicao=self.comp).exists())

    def test_jogo_de_grupo_so_atualiza_classificacao_do_grupo(self):
        grupo = Grupo.objects.create(competicao=self.comp, nome='A')
        grupo.equipes.set([self.eq1, self.eq2])
        rodada = Rodada.objects.create(competicao=self.comp, grupo=grupo, numero=1)
        jogo(rodada, self.eq1, self.eq2, 1, 0)
        self.assertFalse(Classificacao.objects.filter(competicao=self.comp).exists())
        clg = ClassificacaoGrupo.objects.get(grupo=grupo, equipe=self.eq1)
        self.assertEqual(clg.pontos, 3)

    def test_jogo_de_liga_ignora_jogos_de_outras_fases_no_calculo(self):
        etapa = EtapaKnockout.objects.create(competicao=self.comp, tipo=EtapaKnockout.FINAL)
        rodada_etapa = Rodada.objects.create(competicao=self.comp, etapa=etapa, numero=1)
        jogo(rodada_etapa, self.eq1, self.eq2, 5, 0)
        rodada_liga = Rodada.objects.create(competicao=self.comp, numero=1)
        jogo(rodada_liga, self.eq1, self.eq2, 1, 0)
        cl = Classificacao.objects.get(competicao=self.comp, equipe=self.eq1)
        self.assertEqual(cl.jogos, 1)
        self.assertEqual(cl.gols_pro, 1)


# ---------------------------------------------------------------------------
# Passo 1.2 (P2) — copa não gera tabela de liga por fallback
# ---------------------------------------------------------------------------

class GeracaoJogosTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        self.admin = criar_admin(self.fed)
        self.client.force_login(self.admin)

    def _gerar(self, comp):
        return self.client.get(reverse('competicao:criar_jogos', kwargs={'competicao_id': comp.pk}))

    def test_copa_pura_nao_gera_jogos_de_liga(self):
        formato = FormatoCompeticao.objects.create(nome='Copa', mata_mata=True)
        comp = criar_competicao(self.fed, formato, status=Competicao.INSCRICOES_ENCERRADAS)
        inscrever(comp, criar_equipes(self.fed, 4))
        resp = self._gerar(comp)
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Rodada.objects.filter(competicao=comp).exists())

    def test_sem_formato_nao_gera_jogos(self):
        comp = criar_competicao(self.fed, formato=None, status=Competicao.INSCRICOES_ENCERRADAS)
        inscrever(comp, criar_equipes(self.fed, 4))
        self._gerar(comp)
        self.assertFalse(Rodada.objects.filter(competicao=comp).exists())

    def test_liga_pura_gera_rodada(self):
        formato = FormatoCompeticao.objects.create(nome='Liga', pontos_corridos=True)
        comp = criar_competicao(self.fed, formato, status=Competicao.INSCRICOES_ENCERRADAS)
        inscrever(comp, criar_equipes(self.fed, 4))
        self._gerar(comp)
        self.assertEqual(
            Rodada.objects.filter(competicao=comp, grupo__isnull=True, etapa__isnull=True).count(), 1,
        )


# ---------------------------------------------------------------------------
# Passos 1.3 e 1.4 (P5/P6) — avanço usa critérios oficiais e valida estado
# ---------------------------------------------------------------------------

class AvancoClassificadosTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        formato = FormatoCompeticao.objects.create(
            nome='Grupos+Mata', fase_grupos=True, mata_mata=True,
        )
        criterio = CriterioClassificacao.objects.create(
            nome='CBF', confronto_direto=True, vitorias=True, saldo_gols=True,
        )
        self.comp = criar_competicao(self.fed, formato, criterio_classificacao=criterio)
        self.a1, self.a2, self.a3, self.a4 = criar_equipes(self.fed, 4)
        inscrever(self.comp, [self.a1, self.a2, self.a3, self.a4])
        self.grupo = Grupo.objects.create(competicao=self.comp, nome='A')
        self.grupo.equipes.set([self.a1, self.a2, self.a3, self.a4])

    def _jogos_do_grupo(self):
        # a1 e a2 empatam em 6 pts; a1 tem saldo melhor (+7 x +1),
        # mas a2 venceu o confronto direto.
        r = Rodada.objects.create(competicao=self.comp, grupo=self.grupo, numero=1)
        jogo(r, self.a1, self.a2, 0, 1)
        jogo(r, self.a1, self.a3, 4, 0)
        jogo(r, self.a1, self.a4, 4, 0)
        jogo(r, self.a2, self.a3, 1, 0)
        jogo(r, self.a2, self.a4, 0, 1)
        jogo(r, self.a3, self.a4, 0, 0)

    def test_avanco_respeita_confronto_direto(self):
        self._jogos_do_grupo()
        etapa = EtapaKnockout.objects.create(competicao=self.comp, tipo=EtapaKnockout.FINAL)
        confrontos = AvancoService().avancar_de_grupos(self.comp, etapa)
        self.assertEqual(confrontos, 1)
        confronto = ConfrontoMatamate.objects.get(etapa=etapa)
        self.assertEqual(confronto.equipe_mandante, self.a2)
        self.assertEqual(confronto.equipe_visitante, self.a1)

    def test_avanco_bloqueado_com_jogos_pendentes(self):
        self._jogos_do_grupo()
        r = Rodada.objects.create(competicao=self.comp, grupo=self.grupo, numero=2)
        jogo(r, self.a1, self.a2, finalizado=False)
        etapa = EtapaKnockout.objects.create(competicao=self.comp, tipo=EtapaKnockout.FINAL)
        with self.assertRaises(RegraVioladaError):
            AvancoService().avancar_de_grupos(self.comp, etapa)
        self.assertFalse(ConfrontoMatamate.objects.filter(etapa=etapa).exists())

    def test_numero_impar_de_classificados_gera_erro(self):
        etapa = EtapaKnockout.objects.create(competicao=self.comp, tipo=EtapaKnockout.FINAL)
        with self.assertRaises(RegraVioladaError) as cm:
            MataMataStrategy().gerar_jogos(etapa, [self.a1, self.a2, self.a3])
        self.assertIn('ímpar', str(cm.exception))

    def test_capacidade_da_etapa_e_validada(self):
        semi = EtapaKnockout.objects.create(competicao=self.comp, tipo=EtapaKnockout.SEMIFINAL)
        with self.assertRaises(RegraVioladaError):
            MataMataStrategy().gerar_jogos(semi, [self.a1, self.a2])

    def test_capacidade_correta_gera_confrontos(self):
        semi = EtapaKnockout.objects.create(competicao=self.comp, tipo=EtapaKnockout.SEMIFINAL)
        confrontos = MataMataStrategy().gerar_jogos(semi, [self.a1, self.a2, self.a3, self.a4])
        self.assertEqual(confrontos, 2)
        self.assertEqual(ConfrontoMatamate.objects.filter(etapa=semi).count(), 2)


# ---------------------------------------------------------------------------
# Passo 1.5 (P9) — equipes de outra federação ou não inscritas retornam 404
# ---------------------------------------------------------------------------

class TenantEquipeTests(TestCase):
    def setUp(self):
        self.fed_a = criar_federacao('Federação A', 'fed-a')
        self.fed_b = criar_federacao('Federação B', 'fed-b')
        self.admin = criar_admin(self.fed_a)
        self.client.force_login(self.admin)
        formato = FormatoCompeticao.objects.create(nome='Misto', fase_grupos=True, mata_mata=True)
        self.comp = criar_competicao(self.fed_a, formato, status=Competicao.INSCRICOES)
        self.eq_a1, self.eq_a2 = criar_equipes(self.fed_a, 2, 'Equipe A')
        inscrever(self.comp, [self.eq_a1, self.eq_a2])
        (self.eq_b,) = criar_equipes(self.fed_b, 1, 'Equipe B')

    def test_associar_equipe_de_outra_federacao_retorna_404(self):
        resp = self.client.post(
            reverse('competicao:buscar_equipes_view', kwargs={'pk': self.comp.pk}),
            {'equipe_id': self.eq_b.pk},
        )
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(
            InscricaoEquipe.objects.filter(competicao=self.comp, equipe=self.eq_b).exists()
        )

    def test_atribuir_equipe_nao_inscrita_a_grupo_retorna_404(self):
        grupo = Grupo.objects.create(competicao=self.comp, nome='A')
        resp = self.client.post(
            reverse('competicao:grupo_atribuir_equipe', kwargs={'pk': grupo.pk}),
            {'equipe_id': self.eq_b.pk},
        )
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(grupo.equipes.exists())

    def test_terceiro_lugar_com_equipe_de_fora_retorna_404(self):
        etapa = EtapaKnockout.objects.create(competicao=self.comp, tipo=EtapaKnockout.TERCEIRO)
        resp = self.client.post(
            reverse('competicao:terceiro_lugar_criar', kwargs={'etapa_pk': etapa.pk}),
            {'equipe_mandante': self.eq_a1.pk, 'equipe_visitante': self.eq_b.pk},
        )
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(ConfrontoMatamate.objects.filter(etapa=etapa).exists())

    def test_terceiro_lugar_com_equipes_inscritas_funciona(self):
        etapa = EtapaKnockout.objects.create(competicao=self.comp, tipo=EtapaKnockout.TERCEIRO)
        resp = self.client.post(
            reverse('competicao:terceiro_lugar_criar', kwargs={'etapa_pk': etapa.pk}),
            {'equipe_mandante': self.eq_a1.pk, 'equipe_visitante': self.eq_a2.pk},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(ConfrontoMatamate.objects.filter(etapa=etapa).exists())


# ---------------------------------------------------------------------------
# Passo 1.6 (P13) — pênaltis só com empate no agregado e sem empate no placar
# ---------------------------------------------------------------------------

class PenaltisTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        self.admin = criar_admin(self.fed)
        self.client.force_login(self.admin)
        formato = FormatoCompeticao.objects.create(
            nome='Copa', mata_mata=True, penaltis=True, permite_empate=False,
        )
        self.comp = criar_competicao(self.fed, formato)
        self.eq1, self.eq2 = criar_equipes(self.fed, 2)
        inscrever(self.comp, [self.eq1, self.eq2])
        self.etapa = EtapaKnockout.objects.create(competicao=self.comp, tipo=EtapaKnockout.FINAL)
        self.rodada = Rodada.objects.create(competicao=self.comp, etapa=self.etapa, numero=1)

    def _confronto(self, gc, gf, finalizado=True):
        j = jogo(self.rodada, self.eq1, self.eq2, gc, gf, finalizado=finalizado)
        return ConfrontoMatamate.objects.create(
            etapa=self.etapa, equipe_mandante=self.eq1, equipe_visitante=self.eq2, jogo_ida=j,
        )

    def _post(self, confronto, pm, pv):
        return self.client.post(
            reverse('competicao:confronto_penaltis', kwargs={'pk': confronto.pk}),
            {'penaltis_mandante': pm, 'penaltis_visitante': pv},
        )

    def test_form_recusa_penaltis_empatados(self):
        form = ConfrontoPenaltisForm(data={'penaltis_mandante': 4, 'penaltis_visitante': 4})
        self.assertFalse(form.is_valid())

    def test_view_recusa_penaltis_sem_empate_no_agregado(self):
        confronto = self._confronto(2, 1)
        self._post(confronto, 5, 4)
        confronto.refresh_from_db()
        self.assertIsNone(confronto.penaltis_mandante)

    def test_view_recusa_penaltis_com_confronto_nao_finalizado(self):
        confronto = self._confronto(0, 0, finalizado=False)
        self._post(confronto, 5, 4)
        confronto.refresh_from_db()
        self.assertIsNone(confronto.penaltis_mandante)

    def test_penaltis_validos_definem_vencedor(self):
        confronto = self._confronto(1, 1)
        self._post(confronto, 5, 4)
        confronto.refresh_from_db()
        self.assertEqual(confronto.penaltis_mandante, 5)
        self.assertEqual(confronto.vencedor, self.eq1)


# ---------------------------------------------------------------------------
# Passo 1.7 (P10) — cartões de jogos anulados não geram suspensão
# ---------------------------------------------------------------------------

class SuspensaoCartoesTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        formato = FormatoCompeticao.objects.create(nome='Liga', pontos_corridos=True)
        self.comp = criar_competicao(self.fed, formato)
        self.eq1, self.eq2 = criar_equipes(self.fed, 2)
        inscrever(self.comp, [self.eq1, self.eq2])
        self.atleta = Atleta.objects.create(
            nome='Jogador Teste', equipe=self.eq1, posicao='ATACANTE',
        )
        self.rodada = Rodada.objects.create(competicao=self.comp, numero=1)

    def test_amarelo_em_jogo_anulado_nao_conta(self):
        j1 = jogo(self.rodada, self.eq1, self.eq2, 1, 0)
        j2 = jogo(self.rodada, self.eq1, self.eq2, 1, 0)
        j_anulado = jogo(self.rodada, self.eq1, self.eq2, finalizado=False, anulado=True)
        Cartao.objects.create(jogo=j1, jogador=self.atleta, tipo=Cartao.AMARELO, minuto=10)
        Cartao.objects.create(jogo=j2, jogador=self.atleta, tipo=Cartao.AMARELO, minuto=10)
        Cartao.objects.create(jogo=j_anulado, jogador=self.atleta, tipo=Cartao.AMARELO, minuto=10)
        self.assertFalse(
            Suspensao.objects.filter(atleta=self.atleta, competicao=self.comp).exists()
        )

    def test_tres_amarelos_validos_geram_suspensao(self):
        for i in range(3):
            j = jogo(self.rodada, self.eq1, self.eq2, 1, 0)
            Cartao.objects.create(jogo=j, jogador=self.atleta, tipo=Cartao.AMARELO, minuto=10)
        self.assertEqual(
            Suspensao.objects.filter(
                atleta=self.atleta, competicao=self.comp, motivo=Suspensao.AMARELOS,
            ).count(), 1,
        )

    def test_vermelho_em_jogo_anulado_nao_conta(self):
        j_anulado = jogo(self.rodada, self.eq1, self.eq2, finalizado=False, anulado=True)
        Cartao.objects.create(jogo=j_anulado, jogador=self.atleta, tipo=Cartao.VERMELHO, minuto=10)
        self.assertFalse(
            Suspensao.objects.filter(atleta=self.atleta, competicao=self.comp).exists()
        )

# ---------------------------------------------------------------------------
# Passo 2.1 (P3) — máquina de estados da Competicao
# ---------------------------------------------------------------------------

class MaquinaEstadosTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        self.formato = FormatoCompeticao.objects.create(
            nome='Liga', pontos_corridos=True, qtd_times=4,
        )
        self.criterio = CriterioClassificacao.objects.create(nome='CBF')

    def test_status_padrao_e_rascunho(self):
        comp = criar_competicao(self.fed)
        self.assertEqual(comp.status, Competicao.RASCUNHO)

    def test_transicao_invalida_levanta_excecao(self):
        comp = criar_competicao(self.fed)
        with self.assertRaises(TransicaoInvalida):
            comp.transicionar(Competicao.ANDAMENTO)

    def test_configurar_exige_formato_e_criterio(self):
        comp = criar_competicao(self.fed)
        with self.assertRaises(TransicaoInvalida):
            comp.transicionar(Competicao.CONFIGURADA)
        comp.formato = self.formato
        comp.save()
        with self.assertRaises(TransicaoInvalida):
            comp.transicionar(Competicao.CONFIGURADA)
        comp.criterio_classificacao = self.criterio
        comp.save()
        comp.transicionar(Competicao.CONFIGURADA)
        comp.refresh_from_db()
        self.assertEqual(comp.status, Competicao.CONFIGURADA)

    def _comp_configurada(self):
        comp = criar_competicao(
            self.fed, self.formato, criterio_classificacao=self.criterio,
            status=Competicao.CONFIGURADA,
        )
        return comp

    def test_encerrar_inscricoes_exige_minimo_de_equipes(self):
        comp = self._comp_configurada()
        comp.transicionar(Competicao.INSCRICOES)
        with self.assertRaises(TransicaoInvalida):
            comp.transicionar(Competicao.INSCRICOES_ENCERRADAS)
        inscrever(comp, criar_equipes(self.fed, 2))
        comp.transicionar(Competicao.INSCRICOES_ENCERRADAS)
        self.assertEqual(comp.status, Competicao.INSCRICOES_ENCERRADAS)

    def test_encerrar_inscricoes_respeita_limite_do_formato(self):
        comp = self._comp_configurada()
        comp.transicionar(Competicao.INSCRICOES)
        inscrever(comp, criar_equipes(self.fed, 5))
        with self.assertRaises(TransicaoInvalida):
            comp.transicionar(Competicao.INSCRICOES_ENCERRADAS)

    def test_iniciar_exige_estrutura_gerada(self):
        comp = self._comp_configurada()
        comp.transicionar(Competicao.INSCRICOES)
        inscrever(comp, criar_equipes(self.fed, 2))
        comp.transicionar(Competicao.INSCRICOES_ENCERRADAS)
        with self.assertRaises(TransicaoInvalida):
            comp.transicionar(Competicao.ANDAMENTO)
        Rodada.objects.create(competicao=comp, numero=1)
        comp.transicionar(Competicao.ANDAMENTO)
        self.assertEqual(comp.status, Competicao.ANDAMENTO)

    def test_finalizar_bloqueado_com_jogos_pendentes_mas_force_passa(self):
        comp = self._comp_configurada()
        comp.transicionar(Competicao.INSCRICOES)
        eqs = criar_equipes(self.fed, 2)
        inscrever(comp, eqs)
        comp.transicionar(Competicao.INSCRICOES_ENCERRADAS)
        rodada = Rodada.objects.create(competicao=comp, numero=1)
        jogo(rodada, eqs[0], eqs[1], finalizado=False)
        comp.transicionar(Competicao.ANDAMENTO)
        with self.assertRaises(TransicaoInvalida):
            comp.transicionar(Competicao.FINALIZADO)
        comp.transicionar(Competicao.FINALIZADO, force=True)
        self.assertEqual(comp.status, Competicao.FINALIZADO)

    def test_arquivar_so_apos_finalizado(self):
        comp = self._comp_configurada()
        with self.assertRaises(TransicaoInvalida):
            comp.transicionar(Competicao.ARQUIVADO)
        comp.status = Competicao.FINALIZADO
        comp.save()
        comp.transicionar(Competicao.ARQUIVADO)
        self.assertEqual(comp.status, Competicao.ARQUIVADO)


# ---------------------------------------------------------------------------
# Passo 2.2 — status fora do formulário + view de transição
# ---------------------------------------------------------------------------

class TransicaoViewTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        self.admin = criar_admin(self.fed)
        self.formato = FormatoCompeticao.objects.create(
            nome='Liga', pontos_corridos=True, qtd_times=4,
        )
        self.criterio = CriterioClassificacao.objects.create(nome='CBF')
        self.comp = criar_competicao(
            self.fed, self.formato, criterio_classificacao=self.criterio,
        )
        self.client.force_login(self.admin)

    def _url(self, acao):
        return reverse(
            'competicao:competicao_transicao',
            kwargs={'pk': self.comp.pk, 'acao': acao},
        )

    def test_form_competicao_nao_expoe_status(self):
        form = CompeticaoForm(federacao=self.fed)
        self.assertNotIn('status', form.fields)

    def test_post_transicao_valida_muda_status(self):
        resp = self.client.post(self._url(Competicao.CONFIGURADA))
        self.comp.refresh_from_db()
        self.assertEqual(self.comp.status, Competicao.CONFIGURADA)
        self.assertRedirects(
            resp, reverse('competicao:classificacao', kwargs={'pk': self.comp.pk}),
        )

    def test_get_nao_muda_status(self):
        self.client.get(self._url(Competicao.CONFIGURADA))
        self.comp.refresh_from_db()
        self.assertEqual(self.comp.status, Competicao.RASCUNHO)

    def test_transicao_invalida_nao_muda_status(self):
        self.client.post(self._url(Competicao.ANDAMENTO))
        self.comp.refresh_from_db()
        self.assertEqual(self.comp.status, Competicao.RASCUNHO)

    def test_acao_desconhecida_nao_muda_status(self):
        self.client.post(self._url('inexistente'))
        self.comp.refresh_from_db()
        self.assertEqual(self.comp.status, Competicao.RASCUNHO)

    def test_post_com_force_finaliza_com_jogos_pendentes(self):
        eqs = criar_equipes(self.fed, 2)
        inscrever(self.comp, eqs)
        rodada = Rodada.objects.create(competicao=self.comp, numero=1)
        jogo(rodada, eqs[0], eqs[1], finalizado=False)
        self.comp.status = Competicao.ANDAMENTO
        self.comp.save()
        self.client.post(self._url(Competicao.FINALIZADO))
        self.comp.refresh_from_db()
        self.assertEqual(self.comp.status, Competicao.ANDAMENTO)
        self.client.post(self._url(Competicao.FINALIZADO), {'force': '1'})
        self.comp.refresh_from_db()
        self.assertEqual(self.comp.status, Competicao.FINALIZADO)

    def test_secretario_nao_pode_transicionar(self):
        sec = Usuario.objects.create(email='sec@teste.com', nome='Sec Teste')
        sec.set_password('senha123')
        sec.save()
        UsuarioFederacao.objects.create(
            usuario=sec, federacao=self.fed, papel=UsuarioFederacao.SECRETARIO,
        )
        self.client.force_login(sec)
        self.client.post(self._url(Competicao.CONFIGURADA))
        self.comp.refresh_from_db()
        self.assertEqual(self.comp.status, Competicao.RASCUNHO)

    def test_outra_federacao_retorna_404(self):
        fed_b = criar_federacao(nome='Federação B', slug='fed-b')
        admin_b = criar_admin(fed_b, email='admin-b@teste.com')
        self.client.force_login(admin_b)
        resp = self.client.post(self._url(Competicao.CONFIGURADA))
        self.assertEqual(resp.status_code, 404)
        self.comp.refresh_from_db()
        self.assertEqual(self.comp.status, Competicao.RASCUNHO)


# ---------------------------------------------------------------------------
# Passo 2.3 — guardas de operação por status da competição
# ---------------------------------------------------------------------------

class GuardasStatusTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        self.admin = criar_admin(self.fed)
        self.client.force_login(self.admin)
        self.formato = FormatoCompeticao.objects.create(
            nome='Liga', pontos_corridos=True, qtd_times=8,
        )
        self.criterio = CriterioClassificacao.objects.create(nome='CBF')

    def _comp(self, status):
        return criar_competicao(
            self.fed, self.formato, criterio_classificacao=self.criterio,
            status=status,
        )

    def test_associar_equipe_bloqueada_fora_do_periodo_de_inscricoes(self):
        comp = self._comp(Competicao.ANDAMENTO)
        (eq,) = criar_equipes(self.fed, 1)
        resp = self.client.post(
            reverse('competicao:buscar_equipes_view', kwargs={'pk': comp.pk}),
            {'equipe_id': eq.pk},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('classificacao', resp['Location'])
        self.assertFalse(InscricaoEquipe.objects.filter(competicao=comp).exists())

    def test_associar_equipe_permitida_em_inscricoes(self):
        comp = self._comp(Competicao.INSCRICOES)
        (eq,) = criar_equipes(self.fed, 1)
        self.client.post(
            reverse('competicao:buscar_equipes_view', kwargs={'pk': comp.pk}),
            {'equipe_id': eq.pk},
        )
        self.assertTrue(
            InscricaoEquipe.objects.filter(competicao=comp, equipe=eq).exists()
        )

    def test_gerar_jogos_bloqueado_antes_de_encerrar_inscricoes(self):
        comp = self._comp(Competicao.INSCRICOES)
        inscrever(comp, criar_equipes(self.fed, 4))
        resp = self.client.get(
            reverse('competicao:criar_jogos', kwargs={'competicao_id': comp.pk})
        )
        self.assertIn('classificacao', resp['Location'])
        self.assertFalse(Rodada.objects.filter(competicao=comp).exists())

    def test_lancar_gol_bloqueado_com_competicao_finalizada(self):
        comp = self._comp(Competicao.FINALIZADO)
        eqs = criar_equipes(self.fed, 2)
        inscrever(comp, eqs)
        rodada = Rodada.objects.create(competicao=comp, numero=1)
        j = jogo(rodada, eqs[0], eqs[1], finalizado=False)
        resp = self.client.post(
            reverse('competicao:gol_criar', kwargs={'jogo_pk': j.pk}), {},
        )
        self.assertIn('classificacao', resp['Location'])

    def test_editar_resultado_bloqueado_fora_de_andamento(self):
        comp = self._comp(Competicao.FINALIZADO)
        eqs = criar_equipes(self.fed, 2)
        inscrever(comp, eqs)
        rodada = Rodada.objects.create(competicao=comp, numero=1)
        j = jogo(rodada, eqs[0], eqs[1], finalizado=False)
        resp = self.client.post(
            reverse('competicao:jogo_editar', kwargs={'pk': j.pk}),
            {'gols_casa': 3, 'gols_fora': 0, 'finalizado': 'on'},
        )
        self.assertEqual(resp.status_code, 302)
        j.refresh_from_db()
        self.assertEqual(j.gols_casa, 0)
        self.assertFalse(j.finalizado)

    def test_editar_resultado_permitido_em_andamento(self):
        comp = self._comp(Competicao.ANDAMENTO)
        eqs = criar_equipes(self.fed, 2)
        inscrever(comp, eqs)
        rodada = Rodada.objects.create(competicao=comp, numero=1)
        j = jogo(rodada, eqs[0], eqs[1], finalizado=False)
        self.client.post(
            reverse('competicao:jogo_editar', kwargs={'pk': j.pk}),
            {'gols_casa': 3, 'gols_fora': 0},
        )
        j.refresh_from_db()
        self.assertEqual(j.gols_casa, 3)
        self.assertEqual(j.status, 'provisorio')
        self.assertTrue(j.finalizado)

    def test_inscricao_de_atleta_bloqueada_fora_de_inscricoes(self):
        comp = self._comp(Competicao.INSCRICOES_ENCERRADAS)
        (eq,) = criar_equipes(self.fed, 1)
        inscrever(comp, [eq])
        atleta = Atleta.objects.create(nome='Atleta X', equipe=eq, posicao='ATACANTE')
        resp = self.client.post(
            reverse('competicao:inscricao_criar', kwargs={
                'competicao_pk': comp.pk, 'equipe_pk': eq.pk,
            }),
            {'atleta': atleta.pk},
        )
        self.assertIn('classificacao', resp['Location'])


# ---------------------------------------------------------------------------
# Passo 2.4 — snapshot de regras + PROTECT em formato/critério
# ---------------------------------------------------------------------------

class SnapshotTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        self.formato = FormatoCompeticao.objects.create(
            nome='Liga', pontos_corridos=True, qtd_times=8,
            pontos_por_vitoria=3, pontos_por_empate=1,
        )
        self.criterio = CriterioClassificacao.objects.create(
            nome='CBF', confronto_direto=True, vitorias=True, saldo_gols=True,
        )
        self.comp = criar_competicao(
            self.fed, self.formato, criterio_classificacao=self.criterio,
            status=Competicao.INSCRICOES,
        )
        self.eqs = criar_equipes(self.fed, 2)
        inscrever(self.comp, self.eqs)

    def test_encerrar_inscricoes_captura_snapshot(self):
        self.comp.transicionar(Competicao.INSCRICOES_ENCERRADAS)
        self.comp.refresh_from_db()
        self.assertEqual(self.comp.pontos_vitoria_snap, 3)
        self.assertEqual(self.comp.pontos_empate_snap, 1)
        self.assertTrue(self.comp.permite_empate_snap)
        self.assertEqual(self.comp.turnos_snap, 1)
        self.assertTrue(self.comp.criterio_snap['confronto_direto'])

    def test_mudanca_no_formato_nao_afeta_competicao_lancada(self):
        self.comp.transicionar(Competicao.INSCRICOES_ENCERRADAS)
        self.formato.pontos_por_vitoria = 10
        self.formato.save()
        self.comp.refresh_from_db()
        rodada = Rodada.objects.create(competicao=self.comp, numero=1)
        jogo(rodada, self.eqs[0], self.eqs[1], 2, 0)
        cl = Classificacao.objects.get(competicao=self.comp, equipe=self.eqs[0])
        self.assertEqual(cl.pontos, 3)

    def test_sem_snapshot_usa_formato_atual(self):
        self.formato.pontos_por_vitoria = 5
        self.formato.save()
        rodada = Rodada.objects.create(competicao=self.comp, numero=1)
        jogo(rodada, self.eqs[0], self.eqs[1], 2, 0)
        cl = Classificacao.objects.get(competicao=self.comp, equipe=self.eqs[0])
        self.assertEqual(cl.pontos, 5)

    def test_mudanca_no_criterio_nao_afeta_desempate_apos_snapshot(self):
        self.comp.transicionar(Competicao.INSCRICOES_ENCERRADAS)
        self.criterio.confronto_direto = False
        self.criterio.saldo_gols = False
        self.criterio.vitorias = False
        self.criterio.save()
        self.comp.refresh_from_db()
        criterio = self.comp.criterio_efetivo
        self.assertTrue(criterio.confronto_direto)
        self.assertTrue(criterio.saldo_gols)

    def test_formato_em_uso_nao_pode_ser_apagado(self):
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            self.formato.delete()

    def test_criterio_em_uso_nao_pode_ser_apagado(self):
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            self.criterio.delete()


# ---------------------------------------------------------------------------
# Passo 2.5 — constraints de Jogo + integridade referencial de Rodada
# ---------------------------------------------------------------------------

class IntegridadeJogoTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        formato = FormatoCompeticao.objects.create(nome='Liga', pontos_corridos=True)
        self.comp = criar_competicao(self.fed, formato)
        self.eq1, self.eq2 = criar_equipes(self.fed, 2)
        inscrever(self.comp, [self.eq1, self.eq2])
        self.rodada = Rodada.objects.create(competicao=self.comp, numero=1)

    def _criar(self, **kwargs):
        return Jogo.objects.create(
            rodada=self.rodada, equipe_casa=self.eq1, equipe_fora=self.eq2,
            **kwargs,
        )

    def test_status_default_e_agendado_com_booleans_zero(self):
        j = self._criar()
        self.assertEqual(j.status, Jogo.STATUS_AGENDADO)
        self.assertFalse(j.finalizado)
        self.assertFalse(j.em_andamento)
        self.assertFalse(j.anulado)

    def test_setar_status_finalizado_deriva_booleans(self):
        j = self._criar(status=Jogo.STATUS_FINALIZADO)
        self.assertTrue(j.finalizado)
        self.assertFalse(j.em_andamento)
        self.assertFalse(j.anulado)

    def test_status_anulado_derruba_finalizado(self):
        j = self._criar(finalizado=True)
        j.status = Jogo.STATUS_ANULADO
        j.save()
        j.refresh_from_db()
        self.assertEqual(j.status, Jogo.STATUS_ANULADO)
        self.assertFalse(j.finalizado)
        self.assertTrue(j.anulado)

    def test_apagar_competicao_apaga_rodadas_e_jogos(self):
        j = jogo(self.rodada, self.eq1, self.eq2, 1, 0)
        self.comp.delete()
        self.assertFalse(Rodada.objects.filter(pk=self.rodada.pk).exists())
        self.assertFalse(Jogo.objects.filter(pk=j.pk).exists())


class ExclusaoEtapaGrupoTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        self.admin = criar_admin(self.fed)
        self.client.force_login(self.admin)
        formato = FormatoCompeticao.objects.create(
            nome='Misto', fase_grupos=True, mata_mata=True,
        )
        self.comp = criar_competicao(self.fed, formato)
        self.eq1, self.eq2 = criar_equipes(self.fed, 2)
        inscrever(self.comp, [self.eq1, self.eq2])

    def test_etapa_com_jogo_finalizado_nao_e_excluida(self):
        etapa = EtapaKnockout.objects.create(competicao=self.comp, tipo=EtapaKnockout.FINAL)
        rodada = Rodada.objects.create(competicao=self.comp, etapa=etapa, numero=1)
        jogo(rodada, self.eq1, self.eq2, 1, 0)
        self.client.post(reverse('competicao:etapa_excluir', kwargs={'pk': etapa.pk}))
        self.assertTrue(EtapaKnockout.objects.filter(pk=etapa.pk).exists())

    def test_etapa_sem_jogo_finalizado_e_excluida_com_rodadas(self):
        etapa = EtapaKnockout.objects.create(competicao=self.comp, tipo=EtapaKnockout.FINAL)
        rodada = Rodada.objects.create(competicao=self.comp, etapa=etapa, numero=1)
        j = jogo(rodada, self.eq1, self.eq2, finalizado=False)
        self.client.post(reverse('competicao:etapa_excluir', kwargs={'pk': etapa.pk}))
        self.assertFalse(EtapaKnockout.objects.filter(pk=etapa.pk).exists())
        self.assertFalse(Rodada.objects.filter(pk=rodada.pk).exists())
        self.assertFalse(Jogo.objects.filter(pk=j.pk).exists())

    def test_grupo_com_jogo_finalizado_nao_e_excluido(self):
        grupo = Grupo.objects.create(competicao=self.comp, nome='A')
        grupo.equipes.set([self.eq1, self.eq2])
        rodada = Rodada.objects.create(competicao=self.comp, grupo=grupo, numero=1)
        jogo(rodada, self.eq1, self.eq2, 1, 0)
        self.client.post(reverse('competicao:grupo_excluir', kwargs={'pk': grupo.pk}))
        self.assertTrue(Grupo.objects.filter(pk=grupo.pk).exists())

    def test_grupo_sem_jogo_finalizado_e_excluido_com_rodadas(self):
        grupo = Grupo.objects.create(competicao=self.comp, nome='A')
        grupo.equipes.set([self.eq1, self.eq2])
        rodada = Rodada.objects.create(competicao=self.comp, grupo=grupo, numero=1)
        j = jogo(rodada, self.eq1, self.eq2, finalizado=False)
        self.client.post(reverse('competicao:grupo_excluir', kwargs={'pk': grupo.pk}))
        self.assertFalse(Grupo.objects.filter(pk=grupo.pk).exists())
        self.assertFalse(Rodada.objects.filter(pk=rodada.pk).exists())
        self.assertFalse(Jogo.objects.filter(pk=j.pk).exists())


# ---------------------------------------------------------------------------
# Passo 2.6 — EtapaKnockout.concluida mantida automaticamente
# ---------------------------------------------------------------------------

class EtapaConcluidaTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        formato = FormatoCompeticao.objects.create(nome='Copa', mata_mata=True)
        self.comp = criar_competicao(self.fed, formato)
        self.eqs = criar_equipes(self.fed, 4)
        inscrever(self.comp, self.eqs)
        self.etapa = EtapaKnockout.objects.create(
            competicao=self.comp, tipo=EtapaKnockout.SEMIFINAL,
        )
        self.rodada = Rodada.objects.create(
            competicao=self.comp, etapa=self.etapa, numero=1,
        )

    def _confronto(self, casa, fora, tipo=ConfrontoMatamate.NORMAL):
        j = jogo(self.rodada, casa, fora, finalizado=False)
        confronto = ConfrontoMatamate.objects.create(
            etapa=self.etapa, tipo_confronto=tipo,
            equipe_mandante=casa, equipe_visitante=fora, jogo_ida=j,
        )
        return confronto, j

    def _finalizar(self, j, gc, gf):
        j.gols_casa = gc
        j.gols_fora = gf
        j.finalizado = True
        j.save()

    def test_etapa_concluida_quando_todos_confrontos_normais_tem_vencedor(self):
        _, j1 = self._confronto(self.eqs[0], self.eqs[1])
        _, j2 = self._confronto(self.eqs[2], self.eqs[3])
        self._finalizar(j1, 2, 0)
        self.etapa.refresh_from_db()
        self.assertFalse(self.etapa.concluida)
        self._finalizar(j2, 0, 1)
        self.etapa.refresh_from_db()
        self.assertTrue(self.etapa.concluida)

    def test_confronto_de_terceiro_lugar_nao_conta_para_conclusao(self):
        _, j1 = self._confronto(self.eqs[0], self.eqs[1])
        self._confronto(
            self.eqs[2], self.eqs[3], tipo=ConfrontoMatamate.TERCEIRO_LUGAR,
        )
        self._finalizar(j1, 3, 1)
        self.etapa.refresh_from_db()
        self.assertTrue(self.etapa.concluida)

    def test_empate_sem_penaltis_nao_conclui_etapa(self):
        _, j1 = self._confronto(self.eqs[0], self.eqs[1])
        self._finalizar(j1, 1, 1)
        self.etapa.refresh_from_db()
        self.assertFalse(self.etapa.concluida)

    def test_conclusao_revertida_quando_vencedor_e_removido(self):
        c1, j1 = self._confronto(self.eqs[0], self.eqs[1])
        self._finalizar(j1, 2, 0)
        self.etapa.refresh_from_db()
        self.assertTrue(self.etapa.concluida)
        j1.finalizado = False
        j1.save()
        self.etapa.refresh_from_db()
        c1.refresh_from_db()
        self.assertIsNone(c1.vencedor)
        self.assertFalse(self.etapa.concluida)


# ---------------------------------------------------------------------------
# Passo 3.1 — pacote de domínio (strategies levantam exceções)
# ---------------------------------------------------------------------------

class LigaStrategyTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        self.formato = FormatoCompeticao.objects.create(nome='Liga', pontos_corridos=True)
        self.comp = criar_competicao(self.fed, self.formato)

    def _rodadas(self):
        return Rodada.objects.filter(
            competicao=self.comp, grupo__isnull=True, etapa__isnull=True,
        )

    def test_round_robin_com_numero_impar_gera_folga(self):
        inscrever(self.comp, criar_equipes(self.fed, 3))
        rodadas = LigaStrategy().gerar_jogos(self.comp)
        self.assertEqual(rodadas, 3)
        self.assertEqual(Jogo.objects.filter(rodada__competicao=self.comp).count(), 3)
        for eq in self.comp.equipes.all():
            jogos = Jogo.objects.filter(rodada__competicao=self.comp).filter(
                Q(equipe_casa=eq) | Q(equipe_fora=eq)
            ).count()
            self.assertEqual(jogos, 2)

    def test_gerar_duas_vezes_levanta_erro(self):
        inscrever(self.comp, criar_equipes(self.fed, 4))
        LigaStrategy().gerar_jogos(self.comp)
        with self.assertRaises(RegraVioladaError):
            LigaStrategy().gerar_jogos(self.comp)

    def test_menos_de_duas_equipes_levanta_erro(self):
        inscrever(self.comp, criar_equipes(self.fed, 1))
        with self.assertRaises(RegraVioladaError):
            LigaStrategy().gerar_jogos(self.comp)

    def test_proxima_rodada_incremental_ate_o_limite(self):
        inscrever(self.comp, criar_equipes(self.fed, 4))
        estrategia = LigaStrategy()
        for esperado in (1, 2, 3):
            numero, total = estrategia.gerar_proxima_rodada(self.comp)
            self.assertEqual((numero, total), (esperado, 3))
        self.assertEqual(self._rodadas().count(), 3)
        for rodada in self._rodadas():
            self.assertEqual(rodada.jogo_set.count(), 2)
        with self.assertRaises(RegraVioladaError):
            estrategia.gerar_proxima_rodada(self.comp)

    def test_duas_equipes_gera_rodada_unica(self):
        inscrever(self.comp, criar_equipes(self.fed, 2))
        rodadas = LigaStrategy().gerar_jogos(self.comp)
        self.assertEqual(rodadas, 1)
        self.assertEqual(Jogo.objects.filter(rodada__competicao=self.comp).count(), 1)

    def test_turno_unico_nao_favorece_o_time_fixo_do_circulo(self):
        """O time na posição 0 do círculo não pode jogar 100% em casa.

        Regressão do viés clássico do método do círculo: sem a correção,
        o time fixo do círculo manda todos os seus jogos, enquanto os
        demais alternam naturalmente.
        """
        for n in (5, 6, 7, 8, 9, 20):
            with self.subTest(n=n):
                comp = criar_competicao(self.fed, self.formato, nome=f'Liga {n}')
                equipes = criar_equipes(self.fed, n, prefixo=f'T{n}-')
                inscrever(comp, equipes)
                LigaStrategy().gerar_jogos(comp)
                jogos = Jogo.objects.filter(rodada__competicao=comp)
                mando = {
                    eq: (jogos.filter(equipe_casa=eq).count(), jogos.filter(equipe_fora=eq).count())
                    for eq in equipes
                }
                for eq, (casa, fora) in mando.items():
                    self.assertLessEqual(
                        abs(casa - fora), 1,
                        f'{eq} com mando desbalanceado em n={n}: casa={casa} fora={fora}',
                    )

    def test_ida_e_volta_equilibra_mando_perfeitamente(self):
        formato_iv = FormatoCompeticao.objects.create(
            nome='Liga Ida e Volta', pontos_corridos=True, turnos=2,
        )
        for n in (5, 6, 7, 8):
            with self.subTest(n=n):
                comp = criar_competicao(self.fed, formato_iv, nome=f'Liga IV {n}')
                equipes = criar_equipes(self.fed, n, prefixo=f'IV{n}-')
                inscrever(comp, equipes)
                LigaStrategy().gerar_jogos(comp)
                jogos = Jogo.objects.filter(rodada__competicao=comp)
                for eq in equipes:
                    casa = jogos.filter(equipe_casa=eq).count()
                    fora = jogos.filter(equipe_fora=eq).count()
                    self.assertEqual(casa, fora, f'{eq} com mando desbalanceado em ida/volta n={n}')


class GruposStrategyTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        formato = FormatoCompeticao.objects.create(nome='Grupos', fase_grupos=True)
        self.comp = criar_competicao(self.fed, formato)

    def test_sem_grupos_levanta_erro(self):
        with self.assertRaises(RegraVioladaError):
            GruposStrategy().gerar_jogos(self.comp)

    def test_grupos_desiguais_geram_rodadas_proprias(self):
        eqs = criar_equipes(self.fed, 7)
        inscrever(self.comp, eqs)
        grupo_a = Grupo.objects.create(competicao=self.comp, nome='A')
        grupo_a.equipes.set(eqs[:4])
        grupo_b = Grupo.objects.create(competicao=self.comp, nome='B')
        grupo_b.equipes.set(eqs[4:])
        rodadas = GruposStrategy().gerar_jogos(self.comp)
        self.assertEqual(rodadas, 6)  # 3 do grupo de 4 + 3 do grupo de 3
        self.assertEqual(Jogo.objects.filter(rodada__grupo=grupo_a).count(), 6)
        self.assertEqual(Jogo.objects.filter(rodada__grupo=grupo_b).count(), 3)

    def test_gerar_duas_vezes_levanta_erro(self):
        eqs = criar_equipes(self.fed, 4)
        inscrever(self.comp, eqs)
        grupo = Grupo.objects.create(competicao=self.comp, nome='A')
        grupo.equipes.set(eqs)
        GruposStrategy().gerar_jogos(self.comp)
        with self.assertRaises(RegraVioladaError):
            GruposStrategy().gerar_jogos(self.comp)


# ---------------------------------------------------------------------------
# Passo 3.2 — modelo Fase (derivação automática e integridade)
# ---------------------------------------------------------------------------

class FaseTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        formato = FormatoCompeticao.objects.create(
            nome='Misto', pontos_corridos=True, fase_grupos=True, mata_mata=True,
        )
        self.comp = criar_competicao(self.fed, formato)
        self.eq1, self.eq2 = criar_equipes(self.fed, 2)
        inscrever(self.comp, [self.eq1, self.eq2])

    def test_rodada_solta_cria_e_vincula_fase_liga(self):
        rodada = Rodada.objects.create(competicao=self.comp, numero=1)
        self.assertEqual(rodada.fase.tipo, Fase.LIGA)
        self.assertEqual(rodada.fase.competicao, self.comp)
        # segunda rodada reutiliza a mesma fase
        rodada2 = Rodada.objects.create(competicao=self.comp, numero=2)
        self.assertEqual(rodada2.fase, rodada.fase)

    def test_grupo_e_suas_rodadas_usam_fase_grupos(self):
        grupo = Grupo.objects.create(competicao=self.comp, nome='A')
        self.assertEqual(grupo.fase.tipo, Fase.GRUPOS)
        rodada = Rodada.objects.create(competicao=self.comp, grupo=grupo, numero=1)
        self.assertEqual(rodada.fase, grupo.fase)

    def test_etapas_compartilham_fase_mata_mata(self):
        semi = EtapaKnockout.objects.create(competicao=self.comp, tipo=EtapaKnockout.SEMIFINAL)
        final = EtapaKnockout.objects.create(competicao=self.comp, tipo=EtapaKnockout.FINAL)
        self.assertEqual(semi.fase.tipo, Fase.MATA_MATA)
        self.assertEqual(semi.fase, final.fase)
        rodada = Rodada.objects.create(competicao=self.comp, etapa=semi, numero=1)
        self.assertEqual(rodada.fase, semi.fase)

    def test_origem_da_primeira_etapa_com_grupos(self):
        Grupo.objects.create(competicao=self.comp, nome='A')
        semi = EtapaKnockout.objects.create(competicao=self.comp, tipo=EtapaKnockout.SEMIFINAL)
        final = EtapaKnockout.objects.create(competicao=self.comp, tipo=EtapaKnockout.FINAL)
        self.assertEqual(semi.origem, EtapaKnockout.ORIGEM_GRUPOS)
        self.assertEqual(final.origem, EtapaKnockout.ORIGEM_ETAPA_ANTERIOR)

    def test_origem_da_primeira_etapa_sem_grupos(self):
        final = EtapaKnockout.objects.create(competicao=self.comp, tipo=EtapaKnockout.FINAL)
        self.assertEqual(final.origem, EtapaKnockout.ORIGEM_LIGA)

    def test_classificacao_recebe_fase_liga(self):
        rodada = Rodada.objects.create(competicao=self.comp, numero=1)
        jogo(rodada, self.eq1, self.eq2, 2, 0)
        cl = Classificacao.objects.get(competicao=self.comp, equipe=self.eq1)
        self.assertEqual(cl.fase, rodada.fase)

    def test_fase_com_rodadas_nao_pode_ser_apagada(self):
        from django.db.models import ProtectedError
        rodada = Rodada.objects.create(competicao=self.comp, numero=1)
        with self.assertRaises(ProtectedError):
            rodada.fase.delete()

    def test_apagar_competicao_com_fases_e_rodadas(self):
        rodada = Rodada.objects.create(competicao=self.comp, numero=1)
        grupo = Grupo.objects.create(competicao=self.comp, nome='A')
        Rodada.objects.create(competicao=self.comp, grupo=grupo, numero=1)
        etapa = EtapaKnockout.objects.create(competicao=self.comp, tipo=EtapaKnockout.FINAL)
        Rodada.objects.create(competicao=self.comp, etapa=etapa, numero=1)
        j = jogo(rodada, self.eq1, self.eq2, 1, 0)
        self.comp.delete()
        self.assertFalse(Fase.objects.filter(competicao_id=self.comp.pk).exists())
        self.assertFalse(Rodada.objects.filter(competicao_id=self.comp.pk).exists())
        self.assertFalse(Jogo.objects.filter(pk=j.pk).exists())


# ---------------------------------------------------------------------------
# Passo 3.3 — progressão de knockout (AvancoService.avancar)
# ---------------------------------------------------------------------------

class AvancoVencedoresTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        formato = FormatoCompeticao.objects.create(nome='Copa', mata_mata=True)
        self.comp = criar_competicao(self.fed, formato)
        self.eqs = criar_equipes(self.fed, 4)
        inscrever(self.comp, self.eqs)
        self.semi = EtapaKnockout.objects.create(
            competicao=self.comp, tipo=EtapaKnockout.SEMIFINAL,
        )
        self.final = EtapaKnockout.objects.create(
            competicao=self.comp, tipo=EtapaKnockout.FINAL,
        )
        MataMataStrategy().gerar_jogos(self.semi, self.eqs)

    def _finalizar_semis(self):
        """Finaliza as semifinais: vencem eqs[0] (1º confronto) e eqs[2] (2º)."""
        for confronto, gols in zip(
            self.semi.confrontos.order_by('ordem'), [(2, 0), (0, 1)],
        ):
            j = confronto.jogo_ida
            j.gols_casa, j.gols_fora = gols
            j.finalizado = True
            j.save()
        self.semi.refresh_from_db()

    def test_avancar_cria_final_com_vencedores(self):
        self._finalizar_semis()
        criados = AvancoService().avancar(self.semi, self.final)
        self.assertEqual(criados, 1)
        confronto = self.final.confrontos.get()
        self.assertEqual(confronto.equipe_mandante, self.eqs[0])
        self.assertEqual(confronto.equipe_visitante, self.eqs[2])

    def test_origem_nao_concluida_bloqueia(self):
        with self.assertRaises(RegraVioladaError):
            AvancoService().avancar(self.semi, self.final)
        self.assertFalse(self.final.confrontos.exists())

    def test_destino_com_confrontos_bloqueia(self):
        self._finalizar_semis()
        AvancoService().avancar(self.semi, self.final)
        with self.assertRaises(RegraVioladaError):
            AvancoService().avancar(self.semi, self.final)

    def test_destino_terceiro_lugar_bloqueado(self):
        terceiro = EtapaKnockout.objects.create(
            competicao=self.comp, tipo=EtapaKnockout.TERCEIRO,
        )
        self._finalizar_semis()
        with self.assertRaises(RegraVioladaError):
            AvancoService().avancar(self.semi, terceiro)

    def test_destino_anterior_a_origem_bloqueado(self):
        self._finalizar_semis()
        with self.assertRaises(RegraVioladaError):
            AvancoService().avancar(self.final, self.semi)

    def test_competicoes_diferentes_bloqueadas(self):
        outra = criar_competicao(self.fed, self.comp.formato, nome='Outra')
        final_outra = EtapaKnockout.objects.create(
            competicao=outra, tipo=EtapaKnockout.FINAL,
        )
        self._finalizar_semis()
        with self.assertRaises(RegraVioladaError):
            AvancoService().avancar(self.semi, final_outra)

    def test_avanco_automatico_via_config_da_fase(self):
        fase = self.semi.fase
        fase.config['avanco_automatico'] = True
        fase.save()
        self._finalizar_semis()
        confronto = self.final.confrontos.get()
        self.assertEqual(confronto.equipe_mandante, self.eqs[0])
        self.assertEqual(confronto.equipe_visitante, self.eqs[2])

    def test_sem_config_nao_avanca_automaticamente(self):
        self._finalizar_semis()
        self.assertFalse(self.final.confrontos.exists())

    def test_view_avancar_vencedores(self):
        admin = criar_admin(self.fed)
        self.client.force_login(admin)
        self._finalizar_semis()
        resp = self.client.post(
            reverse(
                'competicao:avancar_vencedores',
                kwargs={'origem_pk': self.semi.pk, 'destino_pk': self.final.pk},
            ),
        )
        self.assertRedirects(
            resp, reverse('competicao:chaveamento', kwargs={'pk': self.final.pk}),
        )
        self.assertEqual(self.final.confrontos.count(), 1)


# ---------------------------------------------------------------------------
# Passo 3.4 — Jogo com status único + W.O.
# ---------------------------------------------------------------------------

class JogoStatusTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        formato = FormatoCompeticao.objects.create(nome='Liga', pontos_corridos=True)
        self.comp = criar_competicao(self.fed, formato)
        self.eq1, self.eq2 = criar_equipes(self.fed, 2)
        inscrever(self.comp, [self.eq1, self.eq2])
        self.rodada = Rodada.objects.create(competicao=self.comp, numero=1)

    def _jogo(self, **kwargs):
        return Jogo.objects.create(
            rodada=self.rodada, equipe_casa=self.eq1, equipe_fora=self.eq2, **kwargs,
        )

    def test_boolean_finalizado_deriva_status(self):
        j = self._jogo(finalizado=True)
        self.assertEqual(j.status, Jogo.STATUS_FINALIZADO)

    def test_boolean_em_andamento_deriva_status(self):
        j = self._jogo(em_andamento=True)
        self.assertEqual(j.status, Jogo.STATUS_EM_ANDAMENTO)

    def test_status_homologado_marca_finalizado(self):
        j = self._jogo(status=Jogo.STATUS_HOMOLOGADO)
        self.assertTrue(j.finalizado)
        self.assertTrue(j.homologado)

    def test_alterar_status_atualiza_booleans_no_banco(self):
        j = self._jogo()
        j.status = Jogo.STATUS_EM_ANDAMENTO
        j.save(update_fields=['status'])
        j.refresh_from_db()
        self.assertTrue(j.em_andamento)
        self.assertEqual(j.status, Jogo.STATUS_EM_ANDAMENTO)

    def test_wo_derruba_resultado_tipo(self):
        j = self._jogo(gols_casa=3, gols_fora=0, wo=True)
        self.assertEqual(j.resultado_tipo, Jogo.RESULTADO_WO_FORA)
        self.assertTrue(j.por_wo)

    def test_combinacao_invalida_de_booleans_na_criacao_levanta_erro(self):
        """finalizado e em_andamento juntos não fazem sentido — antes o
        save() descartava a mudança em silêncio; agora levanta erro."""
        with self.assertRaises(RegraVioladaError):
            self._jogo(finalizado=True, em_andamento=True)

    def test_combinacao_invalida_de_booleans_na_atualizacao_levanta_erro(self):
        j = self._jogo()
        j.finalizado = True
        j.anulado = True
        with self.assertRaises(RegraVioladaError):
            j.save()


class WOServiceTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        formato = FormatoCompeticao.objects.create(nome='Liga', pontos_corridos=True)
        self.comp = criar_competicao(self.fed, formato)
        self.eq1, self.eq2 = criar_equipes(self.fed, 2)
        inscrever(self.comp, [self.eq1, self.eq2])
        self.rodada = Rodada.objects.create(competicao=self.comp, numero=1)
        self.atleta = Atleta.objects.create(
            nome='Atleta X', equipe=self.eq1, posicao='ATACANTE',
        )

    def _jogo(self, **kw):
        return Jogo.objects.create(
            rodada=self.rodada, equipe_casa=self.eq1, equipe_fora=self.eq2, **kw,
        )

    def test_declarar_wo_com_vencedor_casa(self):
        j = self._jogo()
        WOService().declarar(j, self.eq1)
        j.refresh_from_db()
        self.assertEqual((j.gols_casa, j.gols_fora), WOService.PLACAR_REGULAMENTAR)
        self.assertEqual(j.resultado_tipo, Jogo.RESULTADO_WO_FORA)
        self.assertEqual(j.status, Jogo.STATUS_FINALIZADO)
        self.assertTrue(j.por_wo)

    def test_declarar_wo_com_vencedor_fora(self):
        j = self._jogo()
        WOService().declarar(j, self.eq2)
        j.refresh_from_db()
        self.assertEqual((j.gols_casa, j.gols_fora), (0, 3))
        self.assertEqual(j.resultado_tipo, Jogo.RESULTADO_WO_CASA)

    def test_vencedor_precisa_ser_equipe_do_jogo(self):
        outra = Equipe.objects.create(federacao=self.fed, nome_equipe='Estranha')
        j = self._jogo()
        with self.assertRaises(RegraVioladaError):
            WOService().declarar(j, outra)

    def test_jogo_homologado_nao_pode_receber_wo(self):
        j = self._jogo(status=Jogo.STATUS_HOMOLOGADO)
        with self.assertRaises(RegraVioladaError):
            WOService().declarar(j, self.eq1)

    def test_wo_apaga_gols_e_cartoes(self):
        from .models import Cartao, Gol
        j = self._jogo(status=Jogo.STATUS_EM_ANDAMENTO)
        Gol.objects.create(jogo=j, atleta=self.atleta, equipe=self.eq1, minuto=10)
        Cartao.objects.create(jogo=j, jogador=self.atleta, tipo=Cartao.AMARELO, minuto=20)
        WOService().declarar(j, self.eq2)
        self.assertFalse(Gol.objects.filter(jogo=j).exists())
        self.assertFalse(Cartao.objects.filter(jogo=j).exists())

    def test_bloqueio_gol_em_jogo_wo(self):
        from django.core.exceptions import ValidationError
        from .models import Gol
        j = self._jogo()
        WOService().declarar(j, self.eq1)
        gol = Gol(jogo=j, atleta=self.atleta, equipe=self.eq1, minuto=10)
        with self.assertRaises(ValidationError):
            gol.full_clean()

    def test_bloqueio_cartao_em_jogo_wo(self):
        from django.core.exceptions import ValidationError
        from .models import Cartao
        j = self._jogo()
        WOService().declarar(j, self.eq1)
        cartao = Cartao(jogo=j, jogador=self.atleta, tipo=Cartao.AMARELO, minuto=20)
        with self.assertRaises(ValidationError):
            cartao.full_clean()

    def test_view_declarar_wo(self):
        admin = criar_admin(self.fed)
        self.client.force_login(admin)
        Competicao.objects.filter(pk=self.comp.pk).update(status=Competicao.ANDAMENTO)
        self.comp.refresh_from_db()
        j = self._jogo()
        resp = self.client.post(
            reverse('competicao:jogo_declarar_wo', kwargs={'pk': j.pk}),
            {'vencedor': str(self.eq1.pk)},
        )
        self.assertRedirects(
            resp, reverse('competicao:jogo_detalhe', kwargs={'pk': j.pk}),
        )
        j.refresh_from_db()
        self.assertTrue(j.por_wo)
        self.assertEqual(j.gols_casa, 3)


# ---------------------------------------------------------------------------
# Passo 3.5 — ParticipacaoFase e desistência
# ---------------------------------------------------------------------------

class ParticipacaoFaseTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        self.formato = FormatoCompeticao.objects.create(nome='Liga', pontos_corridos=True)
        self.comp = criar_competicao(self.fed, self.formato)
        self.eqs = criar_equipes(self.fed, 4)
        inscrever(self.comp, self.eqs)

    def test_gerar_jogos_persiste_participacoes(self):
        LigaStrategy().gerar_jogos(self.comp)
        fase = Fase.objects.get(competicao=self.comp, tipo=Fase.LIGA)
        participacoes = list(fase.participacoes.order_by('seed'))
        self.assertEqual(len(participacoes), 4)
        self.assertEqual([p.equipe for p in participacoes], self.eqs)
        self.assertTrue(all(p.ativo for p in participacoes))

    def test_participacao_unica_por_equipe_na_fase(self):
        from django.db import IntegrityError, transaction
        LigaStrategy().gerar_jogos(self.comp)
        fase = Fase.objects.get(competicao=self.comp, tipo=Fase.LIGA)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ParticipacaoFase.objects.create(
                    fase=fase, equipe=self.eqs[0], seed=99,
                )


class DesistenciaTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        formato = FormatoCompeticao.objects.create(nome='Liga', pontos_corridos=True)
        self.comp = criar_competicao(self.fed, formato)
        self.eqs = criar_equipes(self.fed, 4)
        inscrever(self.comp, self.eqs)
        LigaStrategy().gerar_jogos(self.comp)
        self.fase = Fase.objects.get(competicao=self.comp, tipo=Fase.LIGA)

    def test_desistencia_marca_inativo_e_registra_data(self):
        DesistenciaService().registrar(self.fase, self.eqs[0])
        p = ParticipacaoFase.objects.get(fase=self.fase, equipe=self.eqs[0])
        self.assertFalse(p.ativo)
        self.assertIsNotNone(p.desistiu_em)

    def test_desistencia_aplica_wo_em_jogos_futuros(self):
        jogos_da_equipe = Jogo.objects.filter(
            rodada__competicao=self.comp,
            rodada__grupo__isnull=True, rodada__etapa__isnull=True,
        ).filter(Q(equipe_casa=self.eqs[0]) | Q(equipe_fora=self.eqs[0]))
        total = jogos_da_equipe.count()
        aplicados = DesistenciaService().registrar(self.fase, self.eqs[0])
        self.assertEqual(aplicados, total)
        for j in jogos_da_equipe:
            j.refresh_from_db()
            self.assertTrue(j.por_wo)
            vencedor_esperado = j.equipe_fora if j.equipe_casa == self.eqs[0] else j.equipe_casa
            gols_vencedor = j.gols_fora if j.equipe_casa == self.eqs[0] else j.gols_casa
            self.assertEqual(gols_vencedor, 3)
            self.assertNotEqual(vencedor_esperado, self.eqs[0])

    def test_desistencia_preserva_jogos_ja_finalizados(self):
        jogo = Jogo.objects.filter(
            rodada__competicao=self.comp, equipe_casa=self.eqs[0],
        ).first()
        jogo.gols_casa, jogo.gols_fora = 2, 1
        jogo.status = Jogo.STATUS_FINALIZADO
        jogo.save()
        DesistenciaService().registrar(self.fase, self.eqs[0])
        jogo.refresh_from_db()
        self.assertFalse(jogo.por_wo)
        self.assertEqual((jogo.gols_casa, jogo.gols_fora), (2, 1))

    def test_desistencia_bloqueada_para_equipe_fora_da_fase(self):
        outra = Equipe.objects.create(federacao=self.fed, nome_equipe='Externa')
        with self.assertRaises(RegraVioladaError):
            DesistenciaService().registrar(self.fase, outra)

    def test_desistencia_duplicada_bloqueada(self):
        DesistenciaService().registrar(self.fase, self.eqs[0])
        with self.assertRaises(RegraVioladaError):
            DesistenciaService().registrar(self.fase, self.eqs[0])

    def test_view_registrar_desistencia(self):
        admin = criar_admin(self.fed)
        self.client.force_login(admin)
        Competicao.objects.filter(pk=self.comp.pk).update(status=Competicao.ANDAMENTO)
        self.comp.refresh_from_db()
        resp = self.client.post(
            reverse(
                'competicao:registrar_desistencia',
                kwargs={'pk': self.comp.pk, 'equipe_id': self.eqs[0].pk},
            ),
        )
        self.assertRedirects(
            resp, reverse('competicao:classificacao', kwargs={'pk': self.comp.pk}),
        )
        p = ParticipacaoFase.objects.get(fase=self.fase, equipe=self.eqs[0])
        self.assertFalse(p.ativo)

    def test_remover_equipe_bloqueado_apos_inscricoes_encerradas(self):
        admin = criar_admin(self.fed)
        self.client.force_login(admin)
        Competicao.objects.filter(pk=self.comp.pk).update(status=Competicao.INSCRICOES_ENCERRADAS)
        self.comp.refresh_from_db()
        self.client.post(
            reverse(
                'competicao:remover_equipe_view',
                kwargs={'pk': self.comp.pk, 'equipe_id': self.eqs[0].pk},
            ),
        )
        self.assertTrue(
            InscricaoEquipe.objects.filter(competicao=self.comp, equipe=self.eqs[0]).exists()
        )


# ---------------------------------------------------------------------------
# Passo 4.1 — Suspensão bloqueante
# ---------------------------------------------------------------------------

class SuspensaoBloqueanteTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        formato = FormatoCompeticao.objects.create(nome='Liga', pontos_corridos=True)
        self.comp = criar_competicao(self.fed, formato)
        self.eq1, self.eq2 = criar_equipes(self.fed, 2)
        inscrever(self.comp, [self.eq1, self.eq2])
        self.rodada = Rodada.objects.create(competicao=self.comp, numero=1)
        self.atleta = Atleta.objects.create(
            nome='Atleta X', equipe=self.eq1, posicao='ATACANTE',
        )
        InscricaoAtleta.objects.create(competicao=self.comp, atleta=self.atleta)

    def _sumula_e_jogo(self):
        j = jogo(self.rodada, self.eq1, self.eq2, finalizado=False)
        sumula = Sumula.objects.create(jogo=j)
        return sumula, j

    def test_esta_suspenso_property(self):
        Suspensao.objects.create(atleta=self.atleta, competicao=self.comp)
        self.assertTrue(self.atleta.esta_suspenso(self.comp))

    def test_esta_suspenso_ignora_cumpridas(self):
        Suspensao.objects.create(
            atleta=self.atleta, competicao=self.comp, cumprida=True,
        )
        self.assertFalse(self.atleta.esta_suspenso(self.comp))

    def test_form_escala_sem_suspensao_permite(self):
        sumula, _ = self._sumula_e_jogo()
        form = EscalacaoJogoForm(
            {'atleta': self.atleta.pk, 'tipo': EscalacaoJogo.TITULAR},
            sumula=sumula, equipe=self.eq1,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_esconde_atleta_suspenso_do_queryset(self):
        Suspensao.objects.create(atleta=self.atleta, competicao=self.comp)
        sumula, _ = self._sumula_e_jogo()
        form = EscalacaoJogoForm(sumula=sumula, equipe=self.eq1)
        self.assertNotIn(self.atleta, form.fields['atleta'].queryset)

    def test_form_valida_atleta_suspenso_no_clean(self):
        Suspensao.objects.create(atleta=self.atleta, competicao=self.comp)
        sumula, _ = self._sumula_e_jogo()
        form = EscalacaoJogoForm(
            {'atleta': self.atleta.pk, 'tipo': EscalacaoJogo.TITULAR},
            sumula=sumula, equipe=self.eq1,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('atleta', form.errors)


class SuspensaoCumprimentoTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        formato = FormatoCompeticao.objects.create(nome='Liga', pontos_corridos=True)
        self.comp = criar_competicao(self.fed, formato)
        self.eq1, self.eq2 = criar_equipes(self.fed, 2)
        inscrever(self.comp, [self.eq1, self.eq2])
        self.rodada = Rodada.objects.create(competicao=self.comp, numero=1)
        self.atleta = Atleta.objects.create(
            nome='Atleta X', equipe=self.eq1, posicao='ATACANTE',
        )
        InscricaoAtleta.objects.create(competicao=self.comp, atleta=self.atleta)

    def test_cumpre_quando_atleta_nao_escalado(self):
        susp = Suspensao.objects.create(
            atleta=self.atleta, competicao=self.comp, rodadas_pendentes=1,
        )
        j = jogo(self.rodada, self.eq1, self.eq2, 1, 0)
        susp.refresh_from_db()
        self.assertTrue(susp.cumprida)
        self.assertIn(j, susp.jogos_cumpridos.all())

    def test_nao_cumpre_quando_atleta_foi_escalado(self):
        susp = Suspensao.objects.create(
            atleta=self.atleta, competicao=self.comp, rodadas_pendentes=1,
        )
        j = jogo(self.rodada, self.eq1, self.eq2, finalizado=False)
        sumula = Sumula.objects.create(jogo=j)
        EscalacaoJogo.objects.create(
            sumula=sumula, atleta=self.atleta, equipe=self.eq1,
            tipo=EscalacaoJogo.TITULAR,
        )
        j.status = Jogo.STATUS_FINALIZADO
        j.save()
        susp.refresh_from_db()
        self.assertFalse(susp.cumprida)
        self.assertEqual(susp.rodadas_pendentes, 1)

    def test_idempotente_em_saves_repetidos(self):
        susp = Suspensao.objects.create(
            atleta=self.atleta, competicao=self.comp, rodadas_pendentes=2,
        )
        j = jogo(self.rodada, self.eq1, self.eq2, 1, 0)
        j.observacoes = 'edit 1'
        j.save()
        j.observacoes = 'edit 2'
        j.save()
        susp.refresh_from_db()
        self.assertEqual(susp.rodadas_pendentes, 1)
        self.assertFalse(susp.cumprida)

    def test_processa_apenas_atletas_das_equipes_do_jogo(self):
        outra_equipe = Equipe.objects.create(federacao=self.fed, nome_equipe='Outra')
        outro_atleta = Atleta.objects.create(
            nome='Y', equipe=outra_equipe, posicao='ATACANTE',
        )
        susp = Suspensao.objects.create(
            atleta=outro_atleta, competicao=self.comp, rodadas_pendentes=1,
        )
        jogo(self.rodada, self.eq1, self.eq2, 1, 0)
        susp.refresh_from_db()
        self.assertFalse(susp.cumprida)

    def test_multiplas_rodadas_pendentes_decrementam(self):
        susp = Suspensao.objects.create(
            atleta=self.atleta, competicao=self.comp, rodadas_pendentes=3,
        )
        for i in range(1, 4):
            r = Rodada.objects.create(competicao=self.comp, numero=i + 1)
            jogo(r, self.eq1, self.eq2, 1, 0)
        susp.refresh_from_db()
        self.assertTrue(susp.cumprida)
        self.assertEqual(susp.rodadas_pendentes, 0)


# ---------------------------------------------------------------------------
# Passo 4.2 — permite_empate / pênaltis / snapshot
# ---------------------------------------------------------------------------

class PermiteEmpateTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        self.formato = FormatoCompeticao.objects.create(
            nome='Copa', mata_mata=True, penaltis=True, permite_empate=False,
        )
        self.criterio = CriterioClassificacao.objects.create(nome='Padrão')
        self.comp = criar_competicao(
            self.fed, self.formato, criterio_classificacao=self.criterio,
            status=Competicao.INSCRICOES,
        )
        self.eq1, self.eq2 = criar_equipes(self.fed, 2)
        inscrever(self.comp, [self.eq1, self.eq2])
        self.rodada = Rodada.objects.create(competicao=self.comp, numero=1)

    def test_snapshot_captura_penaltis_e_prorrogacao(self):
        self.formato.prorrogacao = True
        self.formato.save()
        self.comp.transicionar(Competicao.INSCRICOES_ENCERRADAS)
        self.comp.refresh_from_db()
        self.assertTrue(self.comp.penaltis_snap)
        self.assertTrue(self.comp.prorrogacao_snap)
        self.assertFalse(self.comp.permite_empate_snap)

    def test_permite_empate_property_usa_snap(self):
        self.comp.transicionar(Competicao.INSCRICOES_ENCERRADAS)
        # muda o formato após snapshot — o snap prevalece
        self.formato.permite_empate = True
        self.formato.save()
        self.comp.refresh_from_db()
        self.assertFalse(self.comp.permite_empate)

    def test_permite_empate_fallback_para_formato_sem_snap(self):
        self.assertFalse(self.comp.permite_empate)

    def test_jogo_exige_desempate_quando_empatado(self):
        j = Jogo.objects.create(
            rodada=self.rodada, equipe_casa=self.eq1, equipe_fora=self.eq2,
            gols_casa=1, gols_fora=1,
        )
        self.assertTrue(j.exige_desempate())

    def test_jogo_nao_exige_desempate_quando_placar_diferente(self):
        j = Jogo.objects.create(
            rodada=self.rodada, equipe_casa=self.eq1, equipe_fora=self.eq2,
            gols_casa=2, gols_fora=1,
        )
        self.assertFalse(j.exige_desempate())

    def test_jogo_wo_nao_exige_desempate(self):
        j = Jogo.objects.create(
            rodada=self.rodada, equipe_casa=self.eq1, equipe_fora=self.eq2,
        )
        WOService().declarar(j, self.eq1)
        j.refresh_from_db()
        self.assertFalse(j.exige_desempate())

    def test_mata_mata_jogo_unico_exige_desempate_mesmo_com_permite_empate(self):
        """Empate na liga/grupos é normal; num mata-mata de jogo único, nunca."""
        self.formato.permite_empate = True
        self.formato.save()
        self.comp.refresh_from_db()
        self.assertTrue(self.comp.permite_empate)

        etapa = EtapaKnockout.objects.create(competicao=self.comp, tipo=EtapaKnockout.FINAL)
        rodada = Rodada.objects.create(competicao=self.comp, etapa=etapa, numero=1)
        j = Jogo.objects.create(
            rodada=rodada, equipe_casa=self.eq1, equipe_fora=self.eq2,
            gols_casa=1, gols_fora=1,
        )
        self.assertTrue(j.exige_desempate())

    def test_mata_mata_ida_e_volta_nao_exige_desempate_por_perna(self):
        """No agregado ida/volta, cada jogo isolado pode terminar empatado —
        quem resolve o empate é o ConfrontoMatamate (gol fora/pênaltis)."""
        etapa = EtapaKnockout.objects.create(
            competicao=self.comp, tipo=EtapaKnockout.FINAL, ida_e_volta=True,
        )
        rodada = Rodada.objects.create(competicao=self.comp, etapa=etapa, numero=1)
        j = Jogo.objects.create(
            rodada=rodada, equipe_casa=self.eq1, equipe_fora=self.eq2,
            gols_casa=1, gols_fora=1,
        )
        self.assertFalse(j.exige_desempate())

    def test_gol_fora_desempata_no_ida_e_volta(self):
        criterio = CriterioClassificacao.objects.create(nome='Com gol fora', gol_fora=True)
        formato = FormatoCompeticao.objects.create(
            nome='Copa GF', mata_mata=True, turnos=2, penaltis=False,
            permite_empate=False,
        )
        comp = criar_competicao(
            self.fed, formato, criterio_classificacao=criterio, nome='Copa GF',
        )
        eqs = criar_equipes(self.fed, 2, prefixo='GF')
        inscrever(comp, eqs)
        etapa = EtapaKnockout.objects.create(
            competicao=comp, tipo=EtapaKnockout.FINAL, ida_e_volta=True,
        )
        rodada_ida = Rodada.objects.create(competicao=comp, etapa=etapa, numero=1)
        rodada_volta = Rodada.objects.create(competicao=comp, etapa=etapa, numero=2)
        # Ida: mandante=eqs[0] vence 2x1 (visitante marcou 1 gol fora)
        j_ida = jogo(rodada_ida, eqs[0], eqs[1], 2, 1)
        # Volta: mandante da volta=eqs[1] vence 1x0
        # Agregado 2x2; gols fora: mandante(0=jogo_volta.gols_fora), visitante(1=jogo_ida.gols_fora)
        j_volta = jogo(rodada_volta, eqs[1], eqs[0], 1, 0)
        confronto = ConfrontoMatamate.objects.create(
            etapa=etapa, equipe_mandante=eqs[0], equipe_visitante=eqs[1],
            jogo_ida=j_ida, jogo_volta=j_volta,
        )
        self.assertEqual(confronto.calcular_vencedor(), eqs[1])

    def test_gol_fora_ignorado_sem_criterio(self):
        criterio = CriterioClassificacao.objects.create(nome='Sem gol fora', gol_fora=False)
        formato = FormatoCompeticao.objects.create(
            nome='Copa SF', mata_mata=True, turnos=2, penaltis=True,
            permite_empate=False,
        )
        comp = criar_competicao(
            self.fed, formato, criterio_classificacao=criterio, nome='Copa SF',
        )
        eqs = criar_equipes(self.fed, 2, prefixo='SF')
        inscrever(comp, eqs)
        etapa = EtapaKnockout.objects.create(
            competicao=comp, tipo=EtapaKnockout.FINAL, ida_e_volta=True,
        )
        rodada_ida = Rodada.objects.create(competicao=comp, etapa=etapa, numero=1)
        rodada_volta = Rodada.objects.create(competicao=comp, etapa=etapa, numero=2)
        j_ida = jogo(rodada_ida, eqs[0], eqs[1], 2, 1)
        j_volta = jogo(rodada_volta, eqs[1], eqs[0], 1, 0)
        confronto = ConfrontoMatamate.objects.create(
            etapa=etapa, equipe_mandante=eqs[0], equipe_visitante=eqs[1],
            jogo_ida=j_ida, jogo_volta=j_volta,
        )
        # Sem gol fora aplicado e sem pênaltis → ainda empatado, vencedor None
        self.assertIsNone(confronto.calcular_vencedor())

    def test_formato_turnos_property_derivadas(self):
        f1 = FormatoCompeticao.objects.create(nome='F1', turnos=1)
        f2 = FormatoCompeticao.objects.create(nome='F2', turnos=2)
        self.assertTrue(f1.turno_unico)
        self.assertFalse(f1.ida_e_volta)
        self.assertFalse(f2.turno_unico)
        self.assertTrue(f2.ida_e_volta)


# ---------------------------------------------------------------------------
# Passo 4.5 — Zonas de classificação (rebaixamento/acesso/vaga externa)
# ---------------------------------------------------------------------------

class ZonaClassificacaoTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        formato = FormatoCompeticao.objects.create(nome='Serie A', pontos_corridos=True)
        self.comp = criar_competicao(self.fed, formato, nome='Série A 2026')
        self.eqs = criar_equipes(self.fed, 4)
        inscrever(self.comp, self.eqs)
        Rodada.objects.create(competicao=self.comp, numero=1)
        self.fase = Fase.objects.get(competicao=self.comp, tipo=Fase.LIGA)

    def test_contem_verifica_posicao(self):
        z = ZonaClassificacao.objects.create(
            fase=self.fase, nome='Rebaixamento',
            tipo=ZonaClassificacao.REBAIXAMENTO,
            faixa_inicio=3, faixa_fim=4,
        )
        self.assertFalse(z.contem(1))
        self.assertFalse(z.contem(2))
        self.assertTrue(z.contem(3))
        self.assertTrue(z.contem(4))
        self.assertFalse(z.contem(5))

    def test_zona_referencia_competicao_destino(self):
        formato_b = FormatoCompeticao.objects.create(nome='Serie B', pontos_corridos=True)
        serie_b = criar_competicao(self.fed, formato_b, nome='Série B 2026')
        z = ZonaClassificacao.objects.create(
            fase=self.fase, nome='Rebaixamento',
            tipo=ZonaClassificacao.REBAIXAMENTO,
            faixa_inicio=3, faixa_fim=4,
            competicao_destino=serie_b,
        )
        self.assertEqual(z.competicao_destino, serie_b)

    def test_todos_tipos_suportam_promocao_e_rebaixamento(self):
        tipos = {c[0] for c in ZonaClassificacao.TIPO_CHOICES}
        self.assertIn(ZonaClassificacao.ACESSO, tipos)
        self.assertIn(ZonaClassificacao.REBAIXAMENTO, tipos)
        self.assertIn(ZonaClassificacao.VAGA_EXTERNA, tipos)

    def test_view_expoe_zonas_no_contexto(self):
        admin = criar_admin(self.fed)
        self.client.force_login(admin)
        ZonaClassificacao.objects.create(
            fase=self.fase, nome='Campeão',
            tipo=ZonaClassificacao.CAMPEAO,
            faixa_inicio=1, faixa_fim=1, cor='#f59e0b',
        )
        ZonaClassificacao.objects.create(
            fase=self.fase, nome='Rebaixamento',
            tipo=ZonaClassificacao.REBAIXAMENTO,
            faixa_inicio=3, faixa_fim=4, cor='#ef4444',
        )
        resp = self.client.get(
            reverse('competicao:classificacao', kwargs={'pk': self.comp.pk}),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context['zonas']), 2)

    def test_zona_apagada_com_fase(self):
        z = ZonaClassificacao.objects.create(
            fase=self.fase, nome='Campeão',
            tipo=ZonaClassificacao.CAMPEAO,
            faixa_inicio=1, faixa_fim=1,
        )
        self.comp.delete()
        self.assertFalse(ZonaClassificacao.objects.filter(pk=z.pk).exists())

    def test_confronto_penaltis_view_bloqueada_sem_penaltis_no_snap(self):
        formato_sem = FormatoCompeticao.objects.create(
            nome='Simples', mata_mata=True, penaltis=False, permite_empate=True,
        )
        comp = criar_competicao(self.fed, formato_sem, nome='Amistoso')
        eqs = criar_equipes(self.fed, 2, prefixo='Amistoso')
        inscrever(comp, eqs)
        etapa = EtapaKnockout.objects.create(competicao=comp, tipo=EtapaKnockout.FINAL)
        r = Rodada.objects.create(competicao=comp, etapa=etapa, numero=1)
        j = jogo(r, eqs[0], eqs[1], 1, 1)
        confronto = ConfrontoMatamate.objects.create(
            etapa=etapa, equipe_mandante=eqs[0], equipe_visitante=eqs[1], jogo_ida=j,
        )
        admin = criar_admin(self.fed, email='outro@teste.com')
        self.client.force_login(admin)
        self.client.post(
            reverse('competicao:confronto_penaltis', kwargs={'pk': confronto.pk}),
            {'penaltis_mandante': 5, 'penaltis_visitante': 4},
        )
        confronto.refresh_from_db()
        self.assertIsNone(confronto.penaltis_mandante)


# ---------------------------------------------------------------------------
# Homologação unificada: jogo_homologar_view e sumula_homologar_view não
# podem mais divergir sobre o status oficial da partida.
# ---------------------------------------------------------------------------

class HomologacaoUnificadaTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        self.admin = criar_admin(self.fed)
        self.formato = FormatoCompeticao.objects.create(nome='Liga', pontos_corridos=True)
        self.comp = criar_competicao(self.fed, self.formato)
        self.comp.status = Competicao.ANDAMENTO
        self.comp.save()
        self.eq1, self.eq2 = criar_equipes(self.fed, 2)
        inscrever(self.comp, [self.eq1, self.eq2])
        self.rodada = Rodada.objects.create(competicao=self.comp, numero=1)
        self.client.force_login(self.admin)

    def _jogo(self, **kwargs):
        return Jogo.objects.create(
            rodada=self.rodada, equipe_casa=self.eq1, equipe_fora=self.eq2, **kwargs,
        )

    def test_homologar_pelo_jogo_sem_sumula_funciona_como_atalho(self):
        """Sem súmula em uso, o atalho simples continua funcionando —
        preserva o caso de uso leve (liga sem súmula digital)."""
        j = self._jogo(status=Jogo.STATUS_PROVISORIO, gols_casa=2, gols_fora=1)
        self.client.post(reverse('competicao:jogo_homologar', kwargs={'pk': j.pk}))
        j.refresh_from_db()
        self.assertEqual(j.status, Jogo.STATUS_HOMOLOGADO)

    def test_homologar_pelo_jogo_com_sumula_em_aberto_e_bloqueado(self):
        """Súmula em uso (fora do rascunho) vira a autoridade — não dá
        para homologar o jogo por baixo dela enquanto ela seguir aberta."""
        j = self._jogo(status=Jogo.STATUS_FINALIZADO, gols_casa=1, gols_fora=0)
        sumula = Sumula.objects.create(jogo=j, status=Sumula.STATUS_ABERTA)
        self.client.post(reverse('competicao:jogo_homologar', kwargs={'pk': j.pk}))
        j.refresh_from_db()
        sumula.refresh_from_db()
        self.assertEqual(j.status, Jogo.STATUS_FINALIZADO)
        self.assertEqual(sumula.status, Sumula.STATUS_ABERTA)

    def test_homologar_pelo_jogo_com_sumula_encerrada_homologa_as_duas(self):
        """Regressão do bug original: homologar pelo jogo tinha que
        também homologar a súmula, nunca deixar uma desincronizada."""
        j = self._jogo(status=Jogo.STATUS_FINALIZADO, gols_casa=1, gols_fora=0)
        sumula = Sumula.objects.create(jogo=j, status=Sumula.STATUS_ENCERRADA)
        self.client.post(reverse('competicao:jogo_homologar', kwargs={'pk': j.pk}))
        j.refresh_from_db()
        sumula.refresh_from_db()
        self.assertEqual(j.status, Jogo.STATUS_HOMOLOGADO)
        self.assertEqual(sumula.status, Sumula.STATUS_HOMOLOGADA)
        self.assertEqual(sumula.homologada_por, self.admin)

    def test_homologar_pela_sumula_tambem_atualiza_o_jogo(self):
        j = self._jogo(status=Jogo.STATUS_FINALIZADO, gols_casa=3, gols_fora=1)
        sumula = Sumula.objects.create(jogo=j, status=Sumula.STATUS_ENCERRADA)
        self.client.post(reverse('competicao:sumula_homologar', kwargs={'pk': sumula.pk}))
        j.refresh_from_db()
        sumula.refresh_from_db()
        self.assertEqual(j.status, Jogo.STATUS_HOMOLOGADO)
        self.assertEqual(sumula.status, Sumula.STATUS_HOMOLOGADA)


# ---------------------------------------------------------------------------
# Placar com fonte única: uma vez que existem gols reais lançados, o
# formulário de edição manual de placar não pode mais divergir deles.
# ---------------------------------------------------------------------------

class PlacarFonteUnicaTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        self.admin = criar_admin(self.fed)
        self.formato = FormatoCompeticao.objects.create(nome='Liga', pontos_corridos=True)
        self.comp = criar_competicao(self.fed, self.formato)
        self.comp.status = Competicao.ANDAMENTO
        self.comp.save()
        self.eq1, self.eq2 = criar_equipes(self.fed, 2)
        inscrever(self.comp, [self.eq1, self.eq2])
        self.rodada = Rodada.objects.create(competicao=self.comp, numero=1)
        self.atleta = Atleta.objects.create(equipe=self.eq1, nome='Jogador 1', posicao='ATACANTE')
        self.client.force_login(self.admin)

    def test_editar_placar_manual_bloqueado_quando_ja_tem_gols(self):
        j = Jogo.objects.create(rodada=self.rodada, equipe_casa=self.eq1, equipe_fora=self.eq2)
        Gol.objects.create(jogo=j, atleta=self.atleta, equipe=self.eq1, minuto=10)
        j.refresh_from_db()
        gols_antes = (j.gols_casa, j.gols_fora)
        self.client.post(
            reverse('competicao:jogo_editar', kwargs={'pk': j.pk}),
            {'gols_casa': 9, 'gols_fora': 9, 'publico': '', 'observacoes': ''},
        )
        j.refresh_from_db()
        self.assertEqual((j.gols_casa, j.gols_fora), gols_antes)

    def test_editar_placar_manual_funciona_sem_gols_lancados(self):
        """Preserva o atalho simples: sem gol nenhum lançado, digitar o
        placar direto continua funcionando normalmente."""
        j = Jogo.objects.create(rodada=self.rodada, equipe_casa=self.eq1, equipe_fora=self.eq2)
        self.client.post(
            reverse('competicao:jogo_editar', kwargs={'pk': j.pk}),
            {'gols_casa': 3, 'gols_fora': 2, 'publico': '', 'observacoes': ''},
        )
        j.refresh_from_db()
        self.assertEqual((j.gols_casa, j.gols_fora), (3, 2))


# ---------------------------------------------------------------------------
# `tem_provisorio` precisa refletir o fluxo real de "ao vivo" (gol a gol),
# não só o atalho raro de digitar o placar manualmente.
# ---------------------------------------------------------------------------

class TemProvisorioTests(TestCase):
    def setUp(self):
        self.fed = criar_federacao()
        self.admin = criar_admin(self.fed)
        self.formato = FormatoCompeticao.objects.create(nome='Liga', pontos_corridos=True)
        self.criterio = CriterioClassificacao.objects.create(nome='Padrão')
        self.comp = criar_competicao(
            self.fed, self.formato, criterio_classificacao=self.criterio,
        )
        self.comp.status = Competicao.ANDAMENTO
        self.comp.save()
        self.eq1, self.eq2 = criar_equipes(self.fed, 2)
        inscrever(self.comp, [self.eq1, self.eq2])
        self.rodada = Rodada.objects.create(competicao=self.comp, numero=1)
        self.client.force_login(self.admin)

    def _tem_provisorio(self):
        resp = self.client.get(reverse('competicao:classificacao', kwargs={'pk': self.comp.pk}))
        return resp.context['tem_provisorio']

    def test_jogo_em_andamento_conta_como_provisorio(self):
        Jogo.objects.create(
            rodada=self.rodada, equipe_casa=self.eq1, equipe_fora=self.eq2,
            status=Jogo.STATUS_EM_ANDAMENTO,
        )
        self.assertTrue(self._tem_provisorio())

    def test_jogo_agendado_nao_conta_como_provisorio(self):
        Jogo.objects.create(
            rodada=self.rodada, equipe_casa=self.eq1, equipe_fora=self.eq2,
            status=Jogo.STATUS_AGENDADO,
        )
        self.assertFalse(self._tem_provisorio())

    def test_jogo_homologado_nao_conta_como_provisorio(self):
        Jogo.objects.create(
            rodada=self.rodada, equipe_casa=self.eq1, equipe_fora=self.eq2,
            status=Jogo.STATUS_HOMOLOGADO,
        )
        self.assertFalse(self._tem_provisorio())

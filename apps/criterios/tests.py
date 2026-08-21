from datetime import date

from django.test import TestCase

from apps.competicao.dominio.classificador import ClassificadorService
from apps.competicao.models import Classificacao, Competicao, Jogo, Rodada
from apps.core.models import Federacao
from apps.equipe.models import Equipe

from .models import CRITERIOS_PADRAO, CriterioClassificacao, FormatoCompeticao


def _jogo(rodada, casa, fora, gc, gf):
    return Jogo.objects.create(
        rodada=rodada, equipe_casa=casa, equipe_fora=fora,
        gols_casa=gc, gols_fora=gf, finalizado=True,
    )


class OrdemCriteriosTests(TestCase):
    """Prova que a ordem de prioridade dos critérios de desempate é
    realmente configurável — o mesmo conjunto de jogos produz classificações
    diferentes dependendo de qual critério vem primeiro.

    Cenário: A, B, C ficam empatados em pontos, vitórias e saldo de gols
    (um ciclo A bate B, B bate C, C bate A, todos por margem de 1, mais um
    empate de cada um contra D só para igualar os pontos). O que separa os
    três é: confronto direto (mini-liga só entre eles) e gols pró geral
    (que inclui os gols marcados contra D) — e essas duas métricas dão
    ordens diferentes de propósito.
    """

    def setUp(self):
        self.fed = Federacao.objects.create(nome='Fed Teste', slug='fed-teste')
        self.formato = FormatoCompeticao.objects.create(nome='Liga', pontos_corridos=True)
        self.comp = Competicao.objects.create(
            federacao=self.fed, nome='Liga Teste', data_inicio=date(2026, 1, 1),
            formato=self.formato,
        )
        self.a, self.b, self.c, self.d = [
            Equipe.objects.create(federacao=self.fed, nome_equipe=nome)
            for nome in ('A', 'B', 'C', 'D')
        ]
        self.rodada = Rodada.objects.create(competicao=self.comp, numero=1)

        # Ciclo A > B > C > A, margem 1 em todos — pontos, vitórias e saldo
        # geral empatam entre os três; só o gols-pró de cada confronto varia.
        _jogo(self.rodada, self.a, self.b, 2, 1)
        _jogo(self.rodada, self.b, self.c, 3, 2)
        _jogo(self.rodada, self.c, self.a, 1, 0)
        # Empates com D: mesma pontuação pra todos (+1), sem alterar saldo
        # (margem 0), mas com gols-pró bem diferentes — separa o geral do H2H.
        _jogo(self.rodada, self.a, self.d, 10, 10)
        _jogo(self.rodada, self.b, self.d, 0, 0)
        _jogo(self.rodada, self.c, self.d, 2, 2)

    def _classificacoes(self):
        return Classificacao.objects.filter(competicao=self.comp).select_related('equipe')

    def test_premissas_do_cenario_estao_empatadas(self):
        cls = {c.equipe: c for c in self._classificacoes()}
        for time in (self.a, self.b, self.c):
            self.assertEqual(cls[time].pontos, 4)
            self.assertEqual(cls[time].vitorias, 1)
            self.assertEqual(cls[time].saldo_gols, 0)
        # gols pró geral diverge do gols pró só-entre-eles (premissa do teste)
        self.assertEqual(cls[self.a].gols_pro, 12)
        self.assertEqual(cls[self.b].gols_pro, 4)
        self.assertEqual(cls[self.c].gols_pro, 5)

    def test_confronto_direto_primeiro_desempata_pelo_h2h(self):
        criterio = CriterioClassificacao.objects.create(
            nome='Estilo FIFA', confronto_direto=True, vitorias=True,
            saldo_gols=True, gols_pro=True,
            ordem_criterios=['confronto_direto', 'vitorias', 'saldo_gols', 'gols_pro'],
        )
        self.comp.criterio_classificacao = criterio
        self.comp.save()

        ordenado = ClassificadorService(self.comp).ordenar(self._classificacoes())
        nomes = [c.equipe.nome_equipe for c in ordenado if c.equipe_id in {self.a.id, self.b.id, self.c.id}]
        # H2H (só os 3 jogos entre eles): B bateu C, C bateu A, A bateu B —
        # gols pró do confronto direto: B=4, C=3, A=2 → B, C, A.
        self.assertEqual(nomes, ['B', 'C', 'A'])

    def test_confronto_direto_por_ultimo_desempata_pelo_gols_pro_geral(self):
        criterio = CriterioClassificacao.objects.create(
            nome='Estilo CBF', confronto_direto=True, vitorias=True,
            saldo_gols=True, gols_pro=True,
            ordem_criterios=['vitorias', 'saldo_gols', 'gols_pro', 'confronto_direto'],
        )
        self.comp.criterio_classificacao = criterio
        self.comp.save()

        ordenado = ClassificadorService(self.comp).ordenar(self._classificacoes())
        nomes = [c.equipe.nome_equipe for c in ordenado if c.equipe_id in {self.a.id, self.b.id, self.c.id}]
        # Vitórias e saldo empatados → decide o gols-pró GERAL: A=12, C=5, B=4.
        self.assertEqual(nomes, ['A', 'C', 'B'])

    def test_mesmo_conjunto_de_jogos_ordens_diferentes_dao_resultados_diferentes(self):
        """A prova cabal: mesmos jogos, mesmos critérios ATIVOS — só a ordem
        muda — e o 1º colocado muda de time."""
        fifa = CriterioClassificacao.objects.create(
            nome='FIFA', confronto_direto=True, vitorias=True, saldo_gols=True, gols_pro=True,
            ordem_criterios=['confronto_direto', 'vitorias', 'saldo_gols', 'gols_pro'],
        )
        cbf = CriterioClassificacao.objects.create(
            nome='CBF', confronto_direto=True, vitorias=True, saldo_gols=True, gols_pro=True,
            ordem_criterios=['vitorias', 'saldo_gols', 'gols_pro', 'confronto_direto'],
        )

        self.comp.criterio_classificacao = fifa
        self.comp.save()
        primeiro_fifa = ClassificadorService(self.comp).ordenar(self._classificacoes())[0]

        self.comp.criterio_classificacao = cbf
        self.comp.save()
        primeiro_cbf = ClassificadorService(self.comp).ordenar(self._classificacoes())[0]

        self.assertNotEqual(primeiro_fifa.equipe_id, primeiro_cbf.equipe_id)
        self.assertEqual(primeiro_fifa.equipe.nome_equipe, 'B')
        self.assertEqual(primeiro_cbf.equipe.nome_equipe, 'A')


class OrdemAtivaTests(TestCase):
    def test_ordem_ativa_ignora_criterios_desligados(self):
        criterio = CriterioClassificacao.objects.create(
            nome='Parcial', confronto_direto=False, vitorias=True,
            saldo_gols=True, gols_pro=False, gol_fora=False,
            menor_vermelho=False, menor_amarelo=False,
        )
        self.assertEqual(criterio.ordem_ativa(), ['vitorias', 'saldo_gols'])

    def test_ordem_padrao_do_model_bate_com_criterios_padrao(self):
        criterio = CriterioClassificacao.objects.create(nome='Padrão')
        self.assertEqual(criterio.ordem_criterios, CRITERIOS_PADRAO)

from django.core.validators import MinValueValidator
from django.db import models


class FormatoCompeticao(models.Model):
    federacao = models.ForeignKey(
        'core.Federacao', on_delete=models.CASCADE,
        related_name='formatos', verbose_name='Federação',
        null=True, blank=True,
    )
    nome = models.CharField(max_length=100, verbose_name='Nome')

    # Pontuação
    pontos_por_vitoria = models.PositiveSmallIntegerField(default=3, verbose_name='Pontos por vitória')
    pontos_por_empate = models.PositiveSmallIntegerField(default=1, verbose_name='Pontos por empate')
    permite_empate = models.BooleanField(default=True, verbose_name='Permite empate')

    # Fases disponíveis na competição
    pontos_corridos = models.BooleanField(default=False, verbose_name='Pontos Corridos')
    fase_grupos = models.BooleanField(default=False, verbose_name='Fase de Grupos')
    mata_mata = models.BooleanField(default=False, verbose_name='Mata-Mata')

    # Configuração dos jogos
    TURNOS_CHOICES = [(1, 'Turno único'), (2, 'Ida e volta')]
    turnos = models.PositiveSmallIntegerField(
        choices=TURNOS_CHOICES, default=1, verbose_name='Turnos',
    )
    prorrogacao = models.BooleanField(default=False, verbose_name='Prorrogação')
    penaltis = models.BooleanField(default=False, verbose_name='Disputa por Pênaltis')

    @property
    def turno_unico(self):
        return self.turnos == 1

    @property
    def ida_e_volta(self):
        return self.turnos == 2

    qtd_times = models.PositiveIntegerField(
        default=8, verbose_name='Quantidade de Times',
        validators=[MinValueValidator(2)],
    )

    class Meta:
        unique_together = [('federacao', 'nome')]
        ordering = ['nome']
        verbose_name = 'Formato de Competição'
        verbose_name_plural = 'Formatos de Competição'

    def __str__(self):
        return self.nome


#: Chaves válidas de critério de desempate e sua ordem CBF por padrão.
#: `ordem_criterios` grava uma permutação desta lista — só a ordem muda,
#: o conjunto de chaves é sempre este.
CRITERIOS_PADRAO = [
    'confronto_direto', 'vitorias', 'saldo_gols',
    'gols_pro', 'gol_fora', 'menor_vermelho', 'menor_amarelo',
]


def _ordem_padrao():
    return list(CRITERIOS_PADRAO)


class CriterioClassificacao(models.Model):
    federacao = models.ForeignKey(
        'core.Federacao', on_delete=models.CASCADE,
        related_name='criterios', verbose_name='Federação',
        null=True, blank=True,
    )
    nome = models.CharField(max_length=100, verbose_name='Nome')

    # Cada BooleanField liga/desliga o critério. A ORDEM de aplicação entre
    # os ativos vem de `ordem_criterios` — não é fixa (nem toda federação
    # segue o padrão CBF: a FIFA, por exemplo, aplica confronto direto
    # antes do saldo de gols geral; o CBF tradicional aplica depois).
    confronto_direto = models.BooleanField(default=True, verbose_name='Confronto Direto')
    vitorias = models.BooleanField(default=True, verbose_name='Número de Vitórias')
    saldo_gols = models.BooleanField(default=True, verbose_name='Saldo de Gols')
    gols_pro = models.BooleanField(default=False, verbose_name='Gols Marcados')
    gol_fora = models.BooleanField(default=False, verbose_name='Gol Fora de Casa')
    menor_vermelho = models.BooleanField(default=False, verbose_name='Menor nº de Cartões Vermelhos')
    menor_amarelo = models.BooleanField(default=False, verbose_name='Menor nº de Cartões Amarelos')

    #: Ordem de prioridade de aplicação dos critérios ativos (lista de
    #: chaves de CRITERIOS_PADRAO, da maior para a menor prioridade).
    #: Chaves desativadas na lista são simplesmente ignoradas na hora de
    #: aplicar — não precisa removê-las daqui.
    ordem_criterios = models.JSONField(default=_ordem_padrao, blank=True)

    def ordem_ativa(self):
        """Chaves de `ordem_criterios` que estão ligadas, na ordem configurada."""
        ordem = self.ordem_criterios or CRITERIOS_PADRAO
        return [c for c in ordem if c in CRITERIOS_PADRAO and getattr(self, c, False)]

    class Meta:
        unique_together = [('federacao', 'nome')]
        ordering = ['nome']
        verbose_name = 'Critério de Classificação'
        verbose_name_plural = 'Critérios de Classificação'

    def __str__(self):
        return self.nome

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


class CriterioClassificacao(models.Model):
    federacao = models.ForeignKey(
        'core.Federacao', on_delete=models.CASCADE,
        related_name='criterios', verbose_name='Federação',
        null=True, blank=True,
    )
    nome = models.CharField(max_length=100, verbose_name='Nome')

    # Critérios de desempate — ordem fixa conforme padrão CBF
    confronto_direto = models.BooleanField(default=True, verbose_name='Confronto Direto')
    vitorias = models.BooleanField(default=True, verbose_name='Número de Vitórias')
    saldo_gols = models.BooleanField(default=True, verbose_name='Saldo de Gols')
    gols_pro = models.BooleanField(default=False, verbose_name='Gols Marcados')
    gol_fora = models.BooleanField(default=False, verbose_name='Gol Fora de Casa')
    menor_vermelho = models.BooleanField(default=False, verbose_name='Menor nº de Cartões Vermelhos')
    menor_amarelo = models.BooleanField(default=False, verbose_name='Menor nº de Cartões Amarelos')

    class Meta:
        unique_together = [('federacao', 'nome')]
        ordering = ['nome']
        verbose_name = 'Critério de Classificação'
        verbose_name_plural = 'Critérios de Classificação'

    def __str__(self):
        return self.nome

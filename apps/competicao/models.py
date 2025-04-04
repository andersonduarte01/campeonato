from django.db import models
from ..equipe.models import Equipe, Atleta
from ..criterios.models import *


class FaseCompeticao(models.Model):
    TIPOS_FASE = [
        ('rodada', 'Rodada'),
        ('grupos', 'Fase de Grupos'),
        ('oitavas', 'Oitavas de Final'),
        ('quartas', 'Quartas de Final'),
        ('semi', 'Semifinal'),
        ('final', 'Final'),
        ('fase', 'Fase Personalizada'),  # Opção para nome customizado
    ]

    tipo = models.CharField(max_length=20, choices=TIPOS_FASE, default="rodada")
    nome_customizado = models.CharField(max_length=50, blank=True, null=True)  # Apenas se for "fase"
    numero = models.PositiveIntegerField(default=1)  # Número da rodada ou fase
    qtd_times = models.PositiveIntegerField(default=0)  # Número de times na fase
    ativa = models.BooleanField(default=True)  # Indica se a fase está ativa
    concluida = models.BooleanField(default=False)  # Indica se a fase foi finalizada

    def __str__(self):
        return f"{self.get_nome_display()} - {self.competicao.nome} ({self.qtd_times} times)"

    def get_nome_display(self):
        """Retorna o nome correto da fase, considerando o nome customizado se necessário."""
        return self.nome_customizado if self.tipo == "fase" else dict(self.TIPOS_FASE)[self.tipo]


class Fase(models.Model):
    nome = models.CharField(max_length=100)  # Exemplo: "Fase de Pontos Corridos"
    descricao = models.TextField(blank=True, null=True)  # Descrição da fase
    data_inicio = models.DateField()  # Data de início da fase
    data_fim = models.DateField(null=True, blank=True)  # Data de término da fase

    def __str__(self):
        return self.nome


class Competicao(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, null=True)
    data_inicio = models.DateField(verbose_name='Início')
    data_fim = models.DateField(verbose_name='Final', blank=True, null=True)
    equipes = models.ManyToManyField(Equipe, related_name="equipes")
    formato = models.OneToOneField(FormatoCompeticao, on_delete=models.DO_NOTHING, related_name="formato",blank=True, null=True)
    criterio_classificacao = models.OneToOneField(CriterioClassificacao, on_delete=models.DO_NOTHING, null=True, blank=True)
    fase = models.ForeignKey(FaseCompeticao, verbose_name='Fase', on_delete=models.DO_NOTHING, null=True, blank=True)

    def __str__(self):
        return f"{self.nome}"


class Rodada(models.Model):
    competicao = models.ForeignKey(Competicao, on_delete=models.DO_NOTHING)
    numero = models.PositiveIntegerField()  # Número da rodada (1ª, 2ª, etc.)

    def __str__(self):
        return f"{self.competicao}: {self.numero}° Rodada"


class Jogo(models.Model):
    rodada = models.ForeignKey(Rodada, on_delete=models.CASCADE, null=True, blank=True)
    equipe_casa = models.ForeignKey(Equipe, on_delete=models.CASCADE, related_name="jogos_casa")
    equipe_fora = models.ForeignKey(Equipe, on_delete=models.CASCADE, related_name="jogos_fora")
    data_hora = models.DateTimeField(null=True, blank=True)
    gols_casa = models.IntegerField(default=0)
    gols_fora = models.IntegerField(default=0)
    finalizado = models.BooleanField(default=False)
    anulado = models.BooleanField(default=False)  # Permite anular o jogo

    def __str__(self):
        status = "Anulado" if self.anulado else "Finalizado" if self.finalizado else "Pendente"
        return f"{self.rodada} ==> {self.equipe_casa.nome_equipe} x {self.equipe_fora.nome_equipe} ({status})."


class Classificacao(models.Model):
    equipe = models.ForeignKey(Equipe, on_delete=models.CASCADE, related_name="classificacoes")
    competicao = models.ForeignKey(Competicao, on_delete=models.CASCADE, related_name="classificacoes")
    jogos = models.IntegerField(default=0)
    vitorias = models.IntegerField(default=0)
    empates = models.IntegerField(default=0)
    derrotas = models.IntegerField(default=0)
    gols_pro = models.IntegerField(default=0)
    gols_contra = models.IntegerField(default=0)
    saldo_gols = models.IntegerField(default=0)
    pontos = models.IntegerField(default=0)

    class Meta:
        ordering = ["-pontos", "-saldo_gols", "-vitorias"]

    def __str__(self):
        return f"{self.equipe.nome} - {self.competicao.nome} ({self.pontos} pontos)"


class Cartao(models.Model):
    jogo = models.ForeignKey(Jogo, on_delete=models.CASCADE, related_name="cartoes")
    jogador = models.ForeignKey(Atleta, on_delete=models.CASCADE, related_name="cartoes")
    tipo = models.CharField(
        max_length=10,
        choices=[
            ("Amarelo", "Cartão Amarelo"),
            ("Vermelho", "Cartão Vermelho"),
        ],
    )
    minuto = models.IntegerField()

    def __str__(self):
        return f"{self.jogador.nome} - {self.tipo} ({self.jogo})"

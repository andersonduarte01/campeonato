from django.core.validators import MinValueValidator
from django.db import models

class FormatoCompeticao(models.Model):
    nome = models.CharField(max_length=100, unique=True)  # Ex: "Pontos Corridos", "Mata-Mata"
    pontos_corridos = models.BooleanField(default=False)
    turno_unico = models.BooleanField(default=False)
    ida_e_volta = models.BooleanField(default=False)
    fase_grupos = models.BooleanField(default=False)
    mata_mata = models.BooleanField(default=False)
    qtd_times = models.PositiveIntegerField(verbose_name='Quantidade de times', default=3, validators=[MinValueValidator(3)])

    def __str__(self):
        return self.nome


class CriterioClassificacao(models.Model):
    nome = models.CharField(max_length=100, unique=True)  # Ex: "Saldo de Gols", "Gol Fora", "Pênaltis"
    vitorias = models.BooleanField(default=False)
    saldo_gols = models.BooleanField(default=False)
    gol_fora = models.BooleanField(default=False)
    disputa_penaltis = models.BooleanField(default=False)

    def __str__(self):
        return self.nome



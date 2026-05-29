from django.db import models
from stdimage import StdImageField
from ..core.models import Usuario
# Create your models here.


class Equipe(models.Model):
    nome_equipe = models.CharField(verbose_name='Nome', max_length=300)
    escudo = StdImageField(upload_to='equipe/escudo', variations={'thumbnail': {'width': 200, 'height': 200}},
                           null=True, blank=True, delete_orphans=True)
    cadastrado = models.DateTimeField(auto_now_add=True)
    atualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nome_equipe


    class Meta:
        verbose_name = 'Equipe'
        verbose_name_plural = 'Equipes'


class Atleta(models.Model):
    POSICAO = [
        ('GOLEIRO', "Goleiro(a)"),
        ('ZAGUEIRO', "Zagueiro(a)"),
        ('LATERAL_DIREIRO', "Lateral Direito(a)"),
        ('LATERAL_ESQUERDO', "Lateral Esquerdo(a)"),
        ('VOLANTE', "Volante"),
        ('MEIO_CAMPO', "Meio Campo"),
        ('MEIA_ATACANTE', "Meio Atacante"),
        ('PONTA_DIREITA', "Ponta Direita"),
        ('PONTA_ESQUERDA', "Ponta Esquerda"),
        ('ATACANTE', "Atacante"),
    ]
    nome = models.CharField(verbose_name='Nome', max_length=250)
    foto = StdImageField(upload_to='equipe/atleta', variations={'thumbnail': {'width': 200, 'height': 200}},
                         null=True, blank=True, delete_orphans=True)
    equipe = models.ForeignKey(Equipe, on_delete=models.CASCADE, related_name='equipe_jogador')
    data_nascimento = models.DateField(verbose_name='Data de Nascimento', null=True, blank=True)
    posicao = models.CharField(choices=POSICAO, verbose_name='Posição', max_length=30)

    def __str__(self):
        return self.nome

    def nome_equipe(self):
        return self.equipe.nome_equipe

    nome_equipe.short_description = 'Equipe'

    class Meta:
        verbose_name = "Atleta"
        verbose_name_plural = "Atletas"

from django.db import models
from stdimage import StdImageField
from ..core.models import Usuario
# Create your models here.


ESTADOS_BR = [
    ('AC','AC'),('AL','AL'),('AP','AP'),('AM','AM'),('BA','BA'),('CE','CE'),
    ('DF','DF'),('ES','ES'),('GO','GO'),('MA','MA'),('MT','MT'),('MS','MS'),
    ('MG','MG'),('PA','PA'),('PB','PB'),('PR','PR'),('PE','PE'),('PI','PI'),
    ('RJ','RJ'),('RN','RN'),('RS','RS'),('RO','RO'),('RR','RR'),('SC','SC'),
    ('SP','SP'),('SE','SE'),('TO','TO'),
]


class Equipe(models.Model):
    nome_equipe = models.CharField(verbose_name='Nome', max_length=300)
    escudo = StdImageField(upload_to='equipe/escudo', variations={'thumbnail': {'width': 200, 'height': 200}},
                           null=True, blank=True, delete_orphans=True)
    cidade = models.CharField(max_length=100, blank=True, null=True, verbose_name='Cidade')
    estado = models.CharField(max_length=2, choices=ESTADOS_BR, blank=True, null=True, verbose_name='Estado')
    estadio = models.CharField(max_length=200, blank=True, null=True, verbose_name='Estádio / Campo')
    tecnico = models.CharField(max_length=200, blank=True, null=True, verbose_name='Técnico')
    cor_uniforme_principal = models.CharField(max_length=30, blank=True, null=True, verbose_name='Cor Uniforme Principal')
    cor_uniforme_alternativo = models.CharField(max_length=30, blank=True, null=True, verbose_name='Cor Uniforme Alternativo')
    fundacao = models.DateField(null=True, blank=True, verbose_name='Fundação')
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
    PE_CHOICES = [
        ('DIREITO', 'Direito'),
        ('ESQUERDO', 'Esquerdo'),
        ('AMBIDESTRO', 'Ambidestro'),
    ]
    SITUACAO_CHOICES = [
        ('APTO', 'Apto'),
        ('SUSPENSO', 'Suspenso'),
        ('LESIONADO', 'Lesionado'),
        ('FORA', 'Fora do Elenco'),
    ]

    nome = models.CharField(verbose_name='Nome', max_length=250)
    foto = StdImageField(upload_to='equipe/atleta', variations={'thumbnail': {'width': 200, 'height': 200}},
                         null=True, blank=True, delete_orphans=True)
    equipe = models.ForeignKey(Equipe, on_delete=models.CASCADE, related_name='equipe_jogador')
    data_nascimento = models.DateField(verbose_name='Data de Nascimento', null=True, blank=True)
    posicao = models.CharField(choices=POSICAO, verbose_name='Posição', max_length=30)
    pe_dominante = models.CharField(
        max_length=10, choices=PE_CHOICES, blank=True, null=True, verbose_name='Pé Dominante'
    )
    altura = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
        verbose_name='Altura (m)', help_text='Ex: 1.80'
    )
    peso = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='Peso (kg)', help_text='Ex: 75.50'
    )
    situacao = models.CharField(
        max_length=10, choices=SITUACAO_CHOICES, default='APTO', verbose_name='Situação'
    )
    naturalidade = models.CharField(max_length=100, blank=True, null=True, verbose_name='Naturalidade')

    def __str__(self):
        return self.nome

    def nome_equipe(self):
        return self.equipe.nome_equipe

    nome_equipe.short_description = 'Equipe'

    class Meta:
        verbose_name = "Atleta"
        verbose_name_plural = "Atletas"

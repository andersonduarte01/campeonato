from django.db import models
from stdimage import StdImageField

from apps.core.constants import ESTADOS_BR
from ..core.models import Federacao


class Equipe(models.Model):
    SITUACAO_FILIADO       = 'filiado'
    SITUACAO_REGULARIZACAO = 'em_regularizacao'
    SITUACAO_SUSPENSO      = 'suspenso'
    SITUACAO_DESFILIADO    = 'desfiliado'

    SITUACAO_CHOICES = [
        (SITUACAO_FILIADO,       'Filiado'),
        (SITUACAO_REGULARIZACAO, 'Em Regularização'),
        (SITUACAO_SUSPENSO,      'Suspenso'),
        (SITUACAO_DESFILIADO,    'Desfiliado'),
    ]

    federacao   = models.ForeignKey(
        Federacao, on_delete=models.PROTECT,
        related_name='equipes', verbose_name='Federação',
    )
    nome_equipe = models.CharField(verbose_name='Nome', max_length=300)
    sigla       = models.CharField(max_length=10, blank=True, verbose_name='Sigla')
    escudo = StdImageField(upload_to='equipe/escudo', variations={'thumbnail': {'width': 200, 'height': 200}},
                           null=True, blank=True, delete_orphans=True)
    cidade = models.CharField(max_length=100, blank=True, null=True, verbose_name='Cidade')
    estado = models.CharField(max_length=2, choices=ESTADOS_BR, blank=True, null=True, verbose_name='Estado')
    estadio = models.CharField(max_length=200, blank=True, null=True, verbose_name='Estádio / Campo')
    tecnico = models.CharField(max_length=200, blank=True, null=True, verbose_name='Técnico')
    cor_uniforme_principal = models.CharField(max_length=30, blank=True, null=True, verbose_name='Cor Uniforme Principal')
    cor_uniforme_alternativo = models.CharField(max_length=30, blank=True, null=True, verbose_name='Cor Uniforme Alternativo')
    fundacao      = models.DateField(null=True, blank=True, verbose_name='Fundação')
    data_filiacao = models.DateField(null=True, blank=True, verbose_name='Data de Filiação')
    situacao      = models.CharField(
        max_length=20, choices=SITUACAO_CHOICES,
        default=SITUACAO_REGULARIZACAO, verbose_name='Situação',
    )
    telefone  = models.CharField(max_length=20, blank=True, verbose_name='Telefone')
    instagram = models.CharField(max_length=100, blank=True, verbose_name='Instagram')
    facebook  = models.CharField(max_length=100, blank=True, verbose_name='Facebook')
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
    # Situação física/administrativa do atleta na equipe. Suspensão
    # disciplinar é uma preocupação separada — usa Atleta.esta_suspenso(comp).
    SITUACAO_CHOICES = [
        ('APTO', 'Apto'),
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

    def esta_suspenso(self, competicao):
        from apps.competicao.models import Suspensao
        return Suspensao.objects.filter(
            atleta=self, competicao=competicao, cumprida=False,
        ).exists()

    class Meta:
        verbose_name = "Atleta"
        verbose_name_plural = "Atletas"

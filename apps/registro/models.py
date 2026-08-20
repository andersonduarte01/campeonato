import datetime

from django.core.exceptions import ValidationError
from django.db import models, transaction

from apps.core.models import Federacao
from apps.equipe.models import Atleta, Equipe


# ─────────────────────────────────────────────────────────────────────────────
# 1. REGISTRO FEDERATIVO DE ATLETAS
# ─────────────────────────────────────────────────────────────────────────────

class SequenciaRegistro(models.Model):
    """Sequência atômica de numeração federativa por (federação, ano).

    Cada RegistroFederativo consome um `proximo_seq()` desta tabela, com
    `select_for_update`. Substitui a leitura "MAX + 1" antiga, que tinha
    race condition entre requests concorrentes.
    """
    federacao = models.ForeignKey(
        Federacao, on_delete=models.CASCADE, related_name='sequencias_registro',
    )
    ano = models.PositiveIntegerField()
    ultimo_seq = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [('federacao', 'ano')]
        verbose_name = 'Sequência de Registro'
        verbose_name_plural = 'Sequências de Registro'

    def __str__(self):
        return f'{self.federacao.sigla or self.federacao.nome} — {self.ano}: {self.ultimo_seq}'

    @classmethod
    @transaction.atomic
    def proximo_seq(cls, federacao, ano):
        seq, _ = cls.objects.select_for_update().get_or_create(
            federacao=federacao, ano=ano,
        )
        seq.ultimo_seq += 1
        seq.save(update_fields=['ultimo_seq'])
        return seq.ultimo_seq


class RegistroFederativo(models.Model):
    STATUS_ATIVO       = 'ativo'
    STATUS_INATIVO     = 'inativo'
    STATUS_SUSPENSO    = 'suspenso'
    STATUS_TRANSFERIDO = 'transferido'
    STATUS_ENCERRADO   = 'encerrado'

    STATUS_CHOICES = [
        (STATUS_ATIVO,       'Ativo'),
        (STATUS_INATIVO,     'Inativo'),
        (STATUS_SUSPENSO,    'Suspenso'),
        (STATUS_TRANSFERIDO, 'Transferido'),
        (STATUS_ENCERRADO,   'Encerrado'),
    ]

    federacao         = models.ForeignKey(
        Federacao, on_delete=models.CASCADE, related_name='registros_federativos',
    )
    atleta            = models.OneToOneField(
        Atleta, on_delete=models.CASCADE, related_name='registro_federativo',
    )
    numero_federativo = models.CharField(max_length=30, editable=False)
    data_filiacao     = models.DateField(default=datetime.date.today)
    status            = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_ATIVO,
    )
    observacoes       = models.TextField(blank=True)
    criado_em         = models.DateTimeField(auto_now_add=True)
    atualizado_em     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Registro Federativo'
        verbose_name_plural = 'Registros Federativos'
        ordering            = ['numero_federativo']
        unique_together     = [('federacao', 'numero_federativo')]

    def __str__(self):
        return f'{self.numero_federativo} — {self.atleta.nome}'

    def _gerar_numero(self):
        ano = datetime.date.today().year
        sigla = (self.federacao.sigla or 'FED').upper()
        seq = SequenciaRegistro.proximo_seq(self.federacao, ano)
        return f'{sigla}-{ano}-{seq:05d}'

    def save(self, *args, **kwargs):
        if not self.numero_federativo:
            self.numero_federativo = self._gerar_numero()
        super().save(*args, **kwargs)


class HistoricoClube(models.Model):
    TIPO_TITULAR    = 'titular'
    TIPO_EMPRESTADO = 'emprestado'

    TIPO_CHOICES = [
        (TIPO_TITULAR,    'Titular'),
        (TIPO_EMPRESTADO, 'Emprestado'),
    ]

    atleta      = models.ForeignKey(
        Atleta, on_delete=models.CASCADE, related_name='historico_clubes',
    )
    equipe      = models.ForeignKey(
        Equipe, on_delete=models.CASCADE, related_name='historico_atletas',
    )
    tipo        = models.CharField(max_length=20, choices=TIPO_CHOICES, default=TIPO_TITULAR)
    data_entrada = models.DateField()
    data_saida   = models.DateField(null=True, blank=True)
    observacoes  = models.TextField(blank=True)

    class Meta:
        verbose_name        = 'Histórico de Clube'
        verbose_name_plural = 'Históricos de Clubes'
        ordering            = ['-data_entrada']

    def __str__(self):
        return f'{self.atleta.nome} → {self.equipe.nome_equipe} ({self.data_entrada})'

    @property
    def em_atividade(self):
        return self.data_saida is None


# ─────────────────────────────────────────────────────────────────────────────
# 2. SISTEMA DE TRANSFERÊNCIAS
# ─────────────────────────────────────────────────────────────────────────────

class JanelaTransferencia(models.Model):
    federacao   = models.ForeignKey(
        Federacao, on_delete=models.CASCADE, related_name='janelas_transferencia',
    )
    nome        = models.CharField(max_length=100)
    data_inicio = models.DateField()
    data_fim    = models.DateField()
    ativa       = models.BooleanField(default=True)

    class Meta:
        verbose_name        = 'Janela de Transferência'
        verbose_name_plural = 'Janelas de Transferência'
        ordering            = ['-data_inicio']

    def __str__(self):
        return f'{self.nome} ({self.data_inicio} – {self.data_fim})'

    @classmethod
    def desativar_encerradas(cls):
        hoje = datetime.date.today()
        cls.objects.filter(ativa=True, data_fim__lt=hoje).update(ativa=False)

    @property
    def is_aberta(self):
        hoje = datetime.date.today()
        return self.ativa and self.data_inicio <= hoje <= self.data_fim

    @property
    def status_display(self):
        hoje = datetime.date.today()
        if hoje < self.data_inicio:
            return 'Futura'
        if hoje > self.data_fim:
            return 'Encerrada'
        if self.ativa:
            return 'Aberta'
        return 'Inativa'


class Transferencia(models.Model):
    TIPO_DEFINITIVA        = 'definitiva'
    TIPO_EMPRESTIMO        = 'emprestimo'
    TIPO_RETORNO           = 'retorno_emprestimo'
    TIPO_INTERNACIONAL     = 'internacional'

    TIPO_CHOICES = [
        (TIPO_DEFINITIVA,    'Definitiva'),
        (TIPO_EMPRESTIMO,    'Empréstimo'),
        (TIPO_RETORNO,       'Retorno de Empréstimo'),
        (TIPO_INTERNACIONAL, 'Internacional'),
    ]

    STATUS_SOLICITADA  = 'solicitada'
    STATUS_EM_ANALISE  = 'em_analise'
    STATUS_APROVADA    = 'aprovada'
    STATUS_REJEITADA   = 'rejeitada'
    STATUS_CANCELADA   = 'cancelada'

    STATUS_CHOICES = [
        (STATUS_SOLICITADA, 'Solicitada'),
        (STATUS_EM_ANALISE, 'Em Análise'),
        (STATUS_APROVADA,   'Aprovada'),
        (STATUS_REJEITADA,  'Rejeitada'),
        (STATUS_CANCELADA,  'Cancelada'),
    ]

    atleta           = models.ForeignKey(
        Atleta, on_delete=models.CASCADE, related_name='transferencias',
    )
    clube_origem     = models.ForeignKey(
        Equipe, on_delete=models.CASCADE, related_name='transferencias_saida',
        null=True, blank=True,
        help_text='Nulo apenas quando tipo=internacional (clube estrangeiro).',
    )
    clube_origem_externo = models.CharField(
        max_length=150, blank=True,
        verbose_name='Clube externo',
        help_text='Nome do clube estrangeiro (para tipo=internacional).',
    )
    clube_destino    = models.ForeignKey(
        Equipe, on_delete=models.CASCADE, related_name='transferencias_entrada',
    )
    tipo             = models.CharField(max_length=30, choices=TIPO_CHOICES)
    janela           = models.ForeignKey(
        JanelaTransferencia, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transferencias',
    )
    data_solicitacao = models.DateField(auto_now_add=True)
    data_aprovacao   = models.DateField(null=True, blank=True)
    status           = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_SOLICITADA,
    )
    observacoes      = models.TextField(blank=True)
    solicitado_por   = models.ForeignKey(
        'core.Usuario', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transferencias_solicitadas',
    )
    criado_em        = models.DateTimeField(auto_now_add=True)
    atualizado_em    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Transferência'
        verbose_name_plural = 'Transferências'
        ordering            = ['-criado_em']

    def __str__(self):
        return (
            f'{self.atleta.nome}: {self.clube_origem.nome_equipe} → '
            f'{self.clube_destino.nome_equipe} [{self.get_status_display()}]'
        )

    def clean(self):
        super().clean()
        if self.tipo == self.TIPO_INTERNACIONAL:
            if not self.clube_origem_externo:
                raise ValidationError({
                    'clube_origem_externo':
                        'Obrigatório para transferência internacional.',
                })
            if self.clube_origem_id:
                raise ValidationError({
                    'clube_origem':
                        'Não use clube_origem em transferência internacional; '
                        'use clube_origem_externo.',
                })
        else:
            if not self.clube_origem_id:
                raise ValidationError({
                    'clube_origem': 'Obrigatório para transferências nacionais.',
                })

    def aprovar(self, usuario=None, *, ignorar_janela=False):
        from .dominio.transferencias import TransferenciaService
        return TransferenciaService().aprovar(
            self, usuario=usuario, ignorar_janela=ignorar_janela,
        )

    def rejeitar(self):
        from .dominio.transferencias import TransferenciaService
        return TransferenciaService().rejeitar(self)

    def cancelar(self):
        from .dominio.transferencias import TransferenciaService
        return TransferenciaService().cancelar(self)

    def marcar_em_analise(self):
        from .dominio.transferencias import TransferenciaService
        return TransferenciaService().marcar_em_analise(self)


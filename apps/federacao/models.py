import calendar
import datetime
import os

from django.db import models
from django.utils import timezone

from apps.equipe.models import Atleta, Equipe
from apps.competicao.models import Arbitro


def _add_months(date, months):
    """Add calendar months to a date without external dependencies."""
    month = date.month - 1 + months
    year = date.year + month // 12
    month = month % 12 + 1
    day = min(date.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


# ─────────────────────────────────────────────────────────────────────────────
# 1. REGISTRO FEDERATIVO DE ATLETAS
# ─────────────────────────────────────────────────────────────────────────────

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

    atleta            = models.OneToOneField(
        Atleta, on_delete=models.CASCADE, related_name='registro_federativo',
    )
    numero_federativo = models.CharField(max_length=30, unique=True, editable=False)
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

    def __str__(self):
        return f'{self.numero_federativo} — {self.atleta.nome}'

    def _gerar_numero(self):
        ano = datetime.date.today().year
        ultimo = (
            RegistroFederativo.objects
            .filter(numero_federativo__startswith=f'FED-{ano}-')
            .order_by('numero_federativo')
            .last()
        )
        seq = 1
        if ultimo:
            try:
                seq = int(ultimo.numero_federativo.split('-')[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        return f'FED-{ano}-{seq:05d}'

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

    def aprovar(self, usuario=None):
        """Approves the transfer, updates athlete club for definitiva type."""
        self.status = self.STATUS_APROVADA
        self.data_aprovacao = datetime.date.today()
        self.save()

        # Fecha histórico anterior se existir entrada em aberto
        HistoricoClube.objects.filter(
            atleta=self.atleta, data_saida=None,
        ).update(data_saida=self.data_aprovacao)

        # Cria novo registro no histórico
        tipo_hist = (
            HistoricoClube.TIPO_EMPRESTADO
            if self.tipo == self.TIPO_EMPRESTIMO
            else HistoricoClube.TIPO_TITULAR
        )
        HistoricoClube.objects.create(
            atleta=self.atleta,
            equipe=self.clube_destino,
            tipo=tipo_hist,
            data_entrada=self.data_aprovacao,
        )

        # Para transferência definitiva, atualiza o clube do atleta
        if self.tipo == self.TIPO_DEFINITIVA:
            self.atleta.equipe = self.clube_destino
            self.atleta.save()

    def rejeitar(self):
        self.status = self.STATUS_REJEITADA
        self.save()

    def cancelar(self):
        self.status = self.STATUS_CANCELADA
        self.save()


# ─────────────────────────────────────────────────────────────────────────────
# 3. PERFIL FEDERATIVO DO CLUBE
# ─────────────────────────────────────────────────────────────────────────────

class InfoClube(models.Model):
    SITUACAO_FILIADO       = 'filiado'
    SITUACAO_REGULARIZACAO = 'regularizacao'
    SITUACAO_SUSPENSO      = 'suspenso'
    SITUACAO_DESFILIADO    = 'desfiliado'

    SITUACAO_CHOICES = [
        (SITUACAO_FILIADO,       'Filiado'),
        (SITUACAO_REGULARIZACAO, 'Em Regularização'),
        (SITUACAO_SUSPENSO,      'Suspenso'),
        (SITUACAO_DESFILIADO,    'Desfiliado'),
    ]

    equipe           = models.OneToOneField(
        Equipe, on_delete=models.CASCADE, related_name='info_clube',
    )
    # Dados jurídicos
    cnpj             = models.CharField(max_length=18, blank=True)
    razao_social     = models.CharField(max_length=300, blank=True)
    nome_fantasia    = models.CharField(max_length=300, blank=True)
    data_fundacao    = models.DateField(null=True, blank=True)
    # Representantes
    presidente       = models.CharField(max_length=200, blank=True)
    vice_presidente  = models.CharField(max_length=200, blank=True)
    diretor_futebol  = models.CharField(max_length=200, blank=True)
    secretario       = models.CharField(max_length=200, blank=True)
    # Contato
    telefone         = models.CharField(max_length=20, blank=True)
    email_clube      = models.EmailField(blank=True)
    site             = models.URLField(blank=True)
    instagram        = models.CharField(max_length=100, blank=True)
    facebook         = models.CharField(max_length=100, blank=True)
    # Situação
    situacao         = models.CharField(
        max_length=20, choices=SITUACAO_CHOICES, default=SITUACAO_REGULARIZACAO,
    )
    criado_em        = models.DateTimeField(auto_now_add=True)
    atualizado_em    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Perfil Federativo do Clube'
        verbose_name_plural = 'Perfis Federativos dos Clubes'

    def __str__(self):
        return f'InfoClube — {self.equipe.nome_equipe}'


# ─────────────────────────────────────────────────────────────────────────────
# 4. GESTÃO DE DOCUMENTOS
# ─────────────────────────────────────────────────────────────────────────────

class TipoDocumento(models.Model):
    ENTIDADE_CLUBE   = 'clube'
    ENTIDADE_ATLETA  = 'atleta'
    ENTIDADE_ARBITRO = 'arbitro'

    ENTIDADE_CHOICES = [
        (ENTIDADE_CLUBE,   'Clube'),
        (ENTIDADE_ATLETA,  'Atleta'),
        (ENTIDADE_ARBITRO, 'Árbitro'),
    ]

    nome             = models.CharField(max_length=100)
    entidade         = models.CharField(max_length=20, choices=ENTIDADE_CHOICES)
    obrigatorio      = models.BooleanField(default=False)
    validade_meses   = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Deixe em branco para documentos sem vencimento.',
    )

    class Meta:
        verbose_name        = 'Tipo de Documento'
        verbose_name_plural = 'Tipos de Documento'
        ordering            = ['entidade', 'nome']
        unique_together     = [('nome', 'entidade')]

    def __str__(self):
        return f'{self.get_entidade_display()} — {self.nome}'


def _documento_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    if instance.atleta_id:
        pasta = f'documentos/atletas/{instance.atleta_id}'
    elif instance.clube_id:
        pasta = f'documentos/clubes/{instance.clube_id}'
    elif instance.arbitro_id:
        pasta = f'documentos/arbitros/{instance.arbitro_id}'
    else:
        pasta = 'documentos/outros'
    return f'{pasta}/{instance.tipo.nome.lower().replace(" ", "_")}{ext}'


class Documento(models.Model):
    STATUS_PENDENTE  = 'pendente'
    STATUS_APROVADO  = 'aprovado'
    STATUS_REJEITADO = 'rejeitado'
    STATUS_VENCIDO   = 'vencido'

    STATUS_CHOICES = [
        (STATUS_PENDENTE,  'Pendente'),
        (STATUS_APROVADO,  'Aprovado'),
        (STATUS_REJEITADO, 'Rejeitado'),
        (STATUS_VENCIDO,   'Vencido'),
    ]

    tipo            = models.ForeignKey(
        TipoDocumento, on_delete=models.PROTECT, related_name='documentos',
    )
    # Vinculação polimórfica (apenas um deve ser preenchido)
    clube           = models.ForeignKey(
        Equipe, on_delete=models.CASCADE,
        null=True, blank=True, related_name='documentos',
    )
    atleta          = models.ForeignKey(
        Atleta, on_delete=models.CASCADE,
        null=True, blank=True, related_name='documentos',
    )
    arbitro         = models.ForeignKey(
        Arbitro, on_delete=models.CASCADE,
        null=True, blank=True, related_name='documentos',
    )
    arquivo         = models.FileField(upload_to=_documento_upload_path)
    data_emissao    = models.DateField(null=True, blank=True)
    data_vencimento = models.DateField(null=True, blank=True)
    status          = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDENTE,
    )
    observacoes     = models.TextField(blank=True)
    aprovado_por    = models.ForeignKey(
        'core.Usuario', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='documentos_aprovados',
    )
    data_aprovacao  = models.DateTimeField(null=True, blank=True)
    enviado_em      = models.DateTimeField(auto_now_add=True)
    atualizado_em   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Documento'
        verbose_name_plural = 'Documentos'
        ordering            = ['-enviado_em']

    def __str__(self):
        entidade = self.atleta or self.clube or self.arbitro
        return f'{self.tipo.nome} — {entidade} [{self.get_status_display()}]'

    def save(self, *args, **kwargs):
        # Calcula data de vencimento automaticamente se possível
        if (
            self.data_emissao
            and self.tipo.validade_meses
            and not self.data_vencimento
        ):
            self.data_vencimento = _add_months(self.data_emissao, self.tipo.validade_meses)
        super().save(*args, **kwargs)

    def atualizar_status_vencimento(self):
        """Mark as vencido if past due date. Call via management command or cron."""
        if (
            self.status == self.STATUS_APROVADO
            and self.data_vencimento
            and self.data_vencimento < datetime.date.today()
        ):
            self.status = self.STATUS_VENCIDO
            self.save(update_fields=['status'])
            return True
        return False

    @property
    def esta_vencido(self):
        return bool(
            self.data_vencimento and self.data_vencimento < datetime.date.today()
        )

    @property
    def entidade_vinculada(self):
        return self.atleta or self.clube or self.arbitro

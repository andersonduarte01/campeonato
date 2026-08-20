from django.conf import settings
from django.db import models


class AuditoriaEvento(models.Model):
    """Registro imutável de eventos relevantes do domínio.

    Diferente do ConsentimentoLGPD (que rastreia opt-in), esta tabela é
    uma trilha de auditoria de ações administrativas e transições de
    estado importantes (Competicao.transicionar, Sumula homologada,
    Transferencia aprovada, etc.).
    """
    # Categorias de eventos previstas — outras podem ser adicionadas
    # livremente via string; não é FK, é enum informal.
    TIPO_COMPETICAO_TRANSICAO = 'competicao_transicao'
    TIPO_JOGO_STATUS          = 'jogo_status'
    TIPO_SUMULA_HOMOLOGADA    = 'sumula_homologada'
    TIPO_SUMULA_ENCERRADA     = 'sumula_encerrada'
    TIPO_SUMULA_REABERTA      = 'sumula_reaberta'
    TIPO_TRANSFERENCIA_APROVADA  = 'transferencia_aprovada'
    TIPO_TRANSFERENCIA_REJEITADA = 'transferencia_rejeitada'
    TIPO_TRANSFERENCIA_CANCELADA = 'transferencia_cancelada'
    TIPO_VINCULO_ALTERADO     = 'vinculo_alterado'
    TIPO_EQUIPE_DESATIVADA    = 'equipe_desativada'
    TIPO_FEDERACAO_ARQUIVADA  = 'federacao_arquivada'
    TIPO_ANONIMIZACAO_LGPD    = 'anonimizacao_lgpd'

    federacao = models.ForeignKey(
        'core.Federacao', on_delete=models.CASCADE,
        related_name='eventos_auditoria', null=True, blank=True,
        help_text='Federação onde o evento ocorreu (null para eventos globais).',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='eventos_auditoria',
        help_text='Quem executou a ação (null se automatizada).',
    )
    tipo = models.CharField(max_length=40, db_index=True)
    objeto_tipo = models.CharField(
        max_length=60, blank=True,
        help_text='Nome do modelo do objeto afetado (ex.: "competicao.Competicao").',
    )
    objeto_id = models.PositiveIntegerField(null=True, blank=True)
    dados = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    registrado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-registrado_em']
        verbose_name = 'Evento de Auditoria'
        verbose_name_plural = 'Eventos de Auditoria'
        indexes = [
            models.Index(fields=['federacao', '-registrado_em']),
            models.Index(fields=['tipo', '-registrado_em']),
            models.Index(fields=['objeto_tipo', 'objeto_id']),
        ]

    def __str__(self):
        quem = self.usuario.email if self.usuario_id else 'sistema'
        return f'[{self.registrado_em:%Y-%m-%d %H:%M}] {quem} · {self.tipo}'


class ConsentimentoLGPD(models.Model):
    TIPO_CHOICES = [
        ('analytics',        'Análise de uso e desempenho'),
        ('marketing',        'Comunicações e marketing'),
        ('compartilhamento', 'Compartilhamento com parceiros'),
        ('dados_sensiveis',  'Tratamento de dados sensíveis'),
    ]

    usuario       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='consentimentos_lgpd',
        verbose_name='Usuário',
    )
    tipo          = models.CharField(max_length=25, choices=TIPO_CHOICES, verbose_name='Tipo')
    aceito        = models.BooleanField(default=False, verbose_name='Aceito')
    ip_address    = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP')
    user_agent    = models.CharField(max_length=500, blank=True, verbose_name='User-Agent')
    registrado_em = models.DateTimeField(auto_now_add=True, verbose_name='Registrado em')
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')

    class Meta:
        unique_together = ('usuario', 'tipo')
        ordering = ['tipo']
        verbose_name = 'Consentimento LGPD'
        verbose_name_plural = 'Consentimentos LGPD'

    def __str__(self):
        status = 'Aceito' if self.aceito else 'Recusado'
        return f"{self.usuario.email} — {self.get_tipo_display()} ({status})"

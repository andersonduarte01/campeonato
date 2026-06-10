from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    ACAO_CHOICES = [
        ('criar',      'Criação'),
        ('editar',     'Edição'),
        ('excluir',    'Exclusão'),
        ('login',      'Login'),
        ('logout',     'Logout'),
        ('exportar',   'Exportação de Dados'),
        ('finalizar',  'Finalização'),
        ('assinar',    'Assinatura Digital'),
        ('publicar',   'Publicação'),
        ('julgar',     'Julgamento'),
        ('transferir', 'Transferência'),
        ('aprovar',    'Aprovação'),
        ('rejeitar',   'Rejeição'),
    ]

    usuario       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs',
        verbose_name='Usuário',
    )
    usuario_email = models.CharField(max_length=254, blank=True, verbose_name='E-mail do usuário')
    acao          = models.CharField(max_length=20, choices=ACAO_CHOICES, verbose_name='Ação')
    modelo        = models.CharField(max_length=100, blank=True, verbose_name='Modelo')
    objeto_id     = models.CharField(max_length=50, blank=True, verbose_name='ID do objeto')
    objeto_repr   = models.CharField(max_length=300, blank=True, verbose_name='Objeto')
    descricao     = models.TextField(blank=True, verbose_name='Descrição')
    dados_anteriores = models.JSONField(null=True, blank=True, verbose_name='Dados anteriores')
    dados_novos      = models.JSONField(null=True, blank=True, verbose_name='Dados novos')
    ip_address    = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP')
    user_agent    = models.CharField(max_length=500, blank=True, verbose_name='User-Agent')
    criado_em     = models.DateTimeField(auto_now_add=True, verbose_name='Data/hora')

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Log de Auditoria'
        verbose_name_plural = 'Logs de Auditoria'

    def __str__(self):
        return f"{self.get_acao_display()} — {self.objeto_repr or self.modelo} ({self.criado_em:%d/%m/%Y %H:%M})"

    @property
    def acao_badge_class(self):
        mapa = {
            'criar':      'badge-success',
            'editar':     'badge-info',
            'excluir':    'badge-error',
            'login':      'badge-warning',
            'logout':     'badge-ghost',
            'exportar':   'badge-warning',
            'finalizar':  'badge-success',
            'assinar':    'badge-info',
            'publicar':   'badge-success',
            'julgar':     'badge-neutral',
            'transferir': 'badge-warning',
            'aprovar':    'badge-success',
            'rejeitar':   'badge-error',
        }
        return mapa.get(self.acao, 'badge-ghost')


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

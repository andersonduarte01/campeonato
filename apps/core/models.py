from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models, transaction
from django.urls import reverse
from django.utils.text import slugify

from .excecoes import RegraVioladaError


class UsuarioManager(BaseUserManager):
    def create_user(self, email, nome, password=None):
        if not email:
            raise ValueError('Digite um email válido.')
        user = self.model(email=self.normalize_email(email), nome=nome)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, nome, password=None):
        user = self.create_user(email, password=password, nome=nome)
        user.is_admin = True
        user.save(using=self._db)
        return user


class Federacao(models.Model):
    nome          = models.CharField(max_length=150, verbose_name='Nome')
    sigla         = models.CharField(max_length=10, blank=True, verbose_name='Sigla')
    slug          = models.SlugField(unique=True, max_length=100)
    cnpj          = models.CharField(max_length=18, unique=True, null=True, blank=True)
    telefone      = models.CharField(max_length=20, null=True, blank=True)
    email         = models.EmailField(null=True, blank=True)
    logo          = models.ImageField(upload_to='federacao/logos/', null=True, blank=True)
    ativa         = models.BooleanField(default=True)
    criada_em     = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Federação'
        verbose_name_plural = 'Federações'
        ordering            = ['nome']

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nome) or 'federacao'
            slug = base
            n = 1
            while Federacao.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f'{base}-{n}'
            self.slug = slug
        super().save(*args, **kwargs)

    def arquivar(self):
        """Desativa a federação (soft-delete). Uso preferencial no lugar de delete()."""
        if not self.ativa:
            return
        self.ativa = False
        self.save(update_fields=['ativa'])

    @transaction.atomic
    def delete(self, *args, **kwargs):
        """Bloqueia deleção se houver equipes, competições ou locais.

        As FKs sensíveis (Equipe/Competicao/Local) são PROTECT — o método
        levanta uma exceção de domínio com mensagem clara antes que o
        Django dispare ProtectedError. Para desativar sem apagar dados,
        use arquivar().
        """
        obstaculos = []
        if self.equipes.exists():
            obstaculos.append(f'{self.equipes.count()} equipe(s)')
        if self.competicoes.exists():
            obstaculos.append(f'{self.competicoes.count()} competição(ões)')
        if self.locais.exists():
            obstaculos.append(f'{self.locais.count()} local(is)')
        if obstaculos:
            raise RegraVioladaError(
                'Não é possível excluir a federação com dados associados: '
                + ', '.join(obstaculos) + '. Use arquivar() para desativá-la.'
            )
        return super().delete(*args, **kwargs)


class Usuario(AbstractBaseUser):
    email         = models.EmailField(verbose_name='Email', max_length=255, unique=True)
    nome          = models.CharField(verbose_name='Nome', max_length=255)
    is_active     = models.BooleanField(default=True)
    is_admin      = models.BooleanField(default=False)  # superusuário da plataforma
    cadastrado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    # N:N com federações via tabela intermediária
    federacoes = models.ManyToManyField(
        'Federacao',
        through='UsuarioFederacao',
        related_name='usuarios',
        blank=True,
    )

    objects = UsuarioManager()

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['nome']

    class Meta:
        verbose_name        = 'Usuário'
        verbose_name_plural = 'Usuários'

    def __str__(self):
        return f"{self.nome} ({self.email})"

    def has_perm(self, perm, obj=None):
        # Só o superadmin da plataforma passa. As permissões por federação
        # vivem em UsuarioFederacao.papel e são verificadas via
        # @requer_papel / PermissaoFederacaoMixin — nunca via Django perms.
        return self.is_active and self.is_admin

    def has_module_perms(self, app_label):
        return self.is_active and self.is_admin

    @property
    def is_staff(self):
        return self.is_admin

    def get_dashboard_url(self, federacao):
        vinculo = self.usuariofederacao_set.filter(federacao=federacao, ativo=True).first()
        if not vinculo:
            return reverse('core:login')
        return reverse('core:index')


class UsuarioFederacao(models.Model):
    ADMIN      = 'ADMIN'
    SECRETARIO = 'SEC'
    ARBITRO    = 'ARB'
    DIRIGENTE  = 'DIR'

    PAPEL_CHOICES = [
        (ADMIN,      'Administrador'),
        (SECRETARIO, 'Secretário'),
        (ARBITRO,    'Árbitro'),
        (DIRIGENTE,  'Dirigente de Clube'),
    ]

    usuario      = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    federacao    = models.ForeignKey(Federacao, on_delete=models.CASCADE)
    papel        = models.CharField(max_length=5, choices=PAPEL_CHOICES, default=DIRIGENTE)
    equipe       = models.ForeignKey(
        'equipe.Equipe', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='dirigentes', verbose_name='Clube gerenciado',
    )
    ativo        = models.BooleanField(default=True)
    data_vinculo = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Vínculo Usuário-Federação'
        verbose_name_plural = 'Vínculos Usuário-Federação'
        unique_together     = ('usuario', 'federacao')

    def __str__(self):
        return f"{self.usuario.nome} — {self.federacao.nome} ({self.get_papel_display()})"

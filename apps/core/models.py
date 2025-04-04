
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser
from django.db import models

# Create your models here.


class UsuarioManager(BaseUserManager):
    def create_user(self, email, nome, password=None):
        if not email:
            raise ValueError('Digite um email válido.')

        user = self.model(
            email=self.normalize_email(email),
            nome=nome,
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, nome, password=None):
        user = self.create_user(
            email,
            password=password,
            nome=nome,
        )
        user.is_admin = True
        user.save(using=self._db)
        return user


class Usuario(AbstractBaseUser):
    email = models.EmailField(verbose_name='Email', max_length=255, unique=True)
    nome = models.CharField(verbose_name='Nome Usuario', max_length=255)
    is_active = models.BooleanField(default=True)
    is_administrator = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    cadastrado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = UsuarioManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nome']

    def __str__(self):
        return self.email

    def has_perm(self, perm, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True

    @property
    def is_staff(self):
        return self.is_admin
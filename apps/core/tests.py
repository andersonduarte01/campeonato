from django.test import TestCase

from apps.criterios.models import FormatoCompeticao

from .excecoes import RegraVioladaError
from .models import Federacao, Usuario


class UsuarioPermissoesTests(TestCase):
    """Passo 5.1 — has_perm/has_module_perms devem restringir ao
    superadmin da plataforma. Antes retornavam sempre True, o que
    escalava privilégios via qualquer view que consumisse essas hooks."""

    def test_usuario_comum_nao_tem_perm(self):
        u = Usuario.objects.create_user(email='a@b.com', nome='A', password='x')
        self.assertFalse(u.has_perm('qualquer.perm'))
        self.assertFalse(u.has_perm('outra.perm', obj=object()))

    def test_usuario_comum_nao_tem_module_perms(self):
        u = Usuario.objects.create_user(email='a@b.com', nome='A', password='x')
        self.assertFalse(u.has_module_perms('qualquer_app'))

    def test_platform_admin_tem_perm(self):
        u = Usuario.objects.create_user(email='admin@x.com', nome='Admin', password='x')
        u.is_admin = True
        u.save(update_fields=['is_admin'])
        self.assertTrue(u.has_perm('qualquer.perm'))
        self.assertTrue(u.has_module_perms('qualquer_app'))

    def test_platform_admin_inativo_perde_perm(self):
        u = Usuario.objects.create_user(email='inativo@x.com', nome='X', password='x')
        u.is_admin = True
        u.is_active = False
        u.save(update_fields=['is_admin', 'is_active'])
        self.assertFalse(u.has_perm('qualquer.perm'))
        self.assertFalse(u.has_module_perms('qualquer_app'))

    def test_is_staff_derivado_de_is_admin(self):
        u = Usuario.objects.create_user(email='s@x.com', nome='S', password='x')
        self.assertFalse(u.is_staff)
        u.is_admin = True
        self.assertTrue(u.is_staff)


# ---------------------------------------------------------------------------
# Passo 5.5 — Federacao PROTECT + safe delete
# ---------------------------------------------------------------------------

class FederacaoDeleteTests(TestCase):
    def setUp(self):
        self.fed = Federacao.objects.create(nome='Federação Delete', slug='fd')

    def test_delete_sem_dados_associados_funciona(self):
        pk = self.fed.pk
        self.fed.delete()
        self.assertFalse(Federacao.objects.filter(pk=pk).exists())

    def test_delete_com_equipes_bloqueado(self):
        from apps.equipe.models import Equipe
        Equipe.objects.create(federacao=self.fed, nome_equipe='Time X')
        with self.assertRaises(RegraVioladaError) as cm:
            self.fed.delete()
        self.assertIn('equipe', str(cm.exception).lower())
        # Federação NÃO foi apagada
        self.assertTrue(Federacao.objects.filter(pk=self.fed.pk).exists())

    def test_delete_com_competicoes_bloqueado(self):
        from apps.competicao.models import Competicao
        from datetime import date
        fmt = FormatoCompeticao.objects.create(nome='F', pontos_corridos=True)
        Competicao.objects.create(
            federacao=self.fed, nome='Copa', data_inicio=date(2026, 1, 1), formato=fmt,
        )
        with self.assertRaises(RegraVioladaError):
            self.fed.delete()

    def test_delete_com_locais_bloqueado(self):
        from apps.competicao.models import Local
        Local.objects.create(federacao=self.fed, nome='Estádio A')
        with self.assertRaises(RegraVioladaError):
            self.fed.delete()

    def test_arquivar_marca_inativa_sem_apagar(self):
        from apps.equipe.models import Equipe
        Equipe.objects.create(federacao=self.fed, nome_equipe='Time X')
        self.fed.arquivar()
        self.fed.refresh_from_db()
        self.assertFalse(self.fed.ativa)
        # dados preservados
        self.assertTrue(Federacao.objects.filter(pk=self.fed.pk).exists())
        self.assertTrue(Equipe.objects.filter(federacao=self.fed).exists())

    def test_equipe_federacao_declara_on_delete_protect(self):
        from django.db.models.deletion import PROTECT
        from apps.equipe.models import Equipe
        field = Equipe._meta.get_field('federacao')
        self.assertIs(field.remote_field.on_delete, PROTECT)

    def test_competicao_federacao_declara_on_delete_protect(self):
        from django.db.models.deletion import PROTECT
        from apps.competicao.models import Competicao
        field = Competicao._meta.get_field('federacao')
        self.assertIs(field.remote_field.on_delete, PROTECT)

    def test_local_federacao_declara_on_delete_protect(self):
        from django.db.models.deletion import PROTECT
        from apps.competicao.models import Local
        field = Local._meta.get_field('federacao')
        self.assertIs(field.remote_field.on_delete, PROTECT)


# ---------------------------------------------------------------------------
# Passo 5.6 — Isolamento de tenant (middleware)
# ---------------------------------------------------------------------------

class MiddlewareTenantTests(TestCase):
    def setUp(self):
        from apps.core.models import UsuarioFederacao
        self.fed_a = Federacao.objects.create(nome='A', slug='a', sigla='A')
        self.fed_b = Federacao.objects.create(nome='B', slug='b', sigla='B')
        self.user_a = Usuario.objects.create_user(email='a@x.com', nome='A', password='x')
        UsuarioFederacao.objects.create(
            usuario=self.user_a, federacao=self.fed_a,
            papel=UsuarioFederacao.ADMIN,
        )

    def test_middleware_seta_federacao_para_vinculo_unico(self):
        from django.urls import reverse
        self.client.force_login(self.user_a)
        # index redireciona pra dashboard — se middleware setou federação, 302
        resp = self.client.get(reverse('core:index'))
        self.assertEqual(resp.status_code, 302)

    def test_usuario_sem_vinculo_ativo_deslogado(self):
        from apps.core.models import UsuarioFederacao
        from django.urls import reverse
        user_sem = Usuario.objects.create_user(email='sem@x.com', nome='X', password='x')
        UsuarioFederacao.objects.create(
            usuario=user_sem, federacao=self.fed_a,
            papel=UsuarioFederacao.ADMIN, ativo=False,
        )
        self.client.force_login(user_sem)
        resp = self.client.get(reverse('core:index'))
        # Middleware não achou vínculo ativo → logout → redirect para login
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp.url)

    def test_federacao_inativa_bloqueia_acesso(self):
        from django.urls import reverse
        self.fed_a.arquivar()
        # Força session com federacao_id inativa
        self.client.force_login(self.user_a)
        session = self.client.session
        session['federacao_id'] = self.fed_a.id
        session.save()
        resp = self.client.get(reverse('core:index'))
        # Federação inativa → _limpar_sessao → sem vínculos ativos com fed
        # ativa → logout → login
        self.assertEqual(resp.status_code, 302)


# ---------------------------------------------------------------------------
# Passo 5.8 — TenantAwareAdminMixin
# ---------------------------------------------------------------------------

class TenantAwareAdminMixinTests(TestCase):
    def setUp(self):
        from apps.equipe.models import Equipe
        self.fed_a = Federacao.objects.create(nome='A', slug='a', sigla='A')
        self.fed_b = Federacao.objects.create(nome='B', slug='b', sigla='B')
        self.equipe_a = Equipe.objects.create(federacao=self.fed_a, nome_equipe='Time A')
        self.equipe_b = Equipe.objects.create(federacao=self.fed_b, nome_equipe='Time B')

    def _mock_request(self, federacao=None, user_is_admin=True):
        class _User:
            is_admin = user_is_admin
        class _Request:
            pass
        r = _Request()
        r.federacao = federacao
        r.user = _User()
        return r

    def test_qs_filtra_pela_federacao_do_request(self):
        from django.contrib import admin as django_admin
        from apps.equipe.models import Equipe
        model_admin = django_admin.site._registry[Equipe]
        r = self._mock_request(federacao=self.fed_a, user_is_admin=False)
        qs = model_admin.get_queryset(r)
        self.assertIn(self.equipe_a, qs)
        self.assertNotIn(self.equipe_b, qs)

    def test_qs_vazio_sem_federacao_e_sem_is_admin(self):
        from django.contrib import admin as django_admin
        from apps.equipe.models import Equipe
        model_admin = django_admin.site._registry[Equipe]
        r = self._mock_request(federacao=None, user_is_admin=False)
        qs = model_admin.get_queryset(r)
        self.assertEqual(qs.count(), 0)

    def test_qs_completo_para_superadmin_sem_federacao(self):
        from django.contrib import admin as django_admin
        from apps.equipe.models import Equipe
        model_admin = django_admin.site._registry[Equipe]
        r = self._mock_request(federacao=None, user_is_admin=True)
        qs = model_admin.get_queryset(r)
        self.assertIn(self.equipe_a, qs)
        self.assertIn(self.equipe_b, qs)

    def test_atleta_admin_usa_lookup_composto(self):
        from django.contrib import admin as django_admin
        from apps.equipe.models import Atleta, Equipe
        Atleta.objects.create(nome='A1', equipe=self.equipe_a, posicao='ATACANTE')
        Atleta.objects.create(nome='B1', equipe=self.equipe_b, posicao='ATACANTE')
        model_admin = django_admin.site._registry[Atleta]
        r = self._mock_request(federacao=self.fed_a, user_is_admin=False)
        qs = model_admin.get_queryset(r)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().nome, 'A1')


# ---------------------------------------------------------------------------
# Passo 5.11 — Convite por e-mail (sem senha em texto)
# ---------------------------------------------------------------------------

class ConviteUsuarioTests(TestCase):
    def setUp(self):
        from apps.core.models import UsuarioFederacao
        from django.urls import reverse
        self.fed = Federacao.objects.create(nome='F', slug='f', sigla='F')
        self.admin = Usuario.objects.create_user(
            email='admin@x.com', nome='Admin', password='x',
        )
        UsuarioFederacao.objects.create(
            usuario=self.admin, federacao=self.fed, papel=UsuarioFederacao.ADMIN,
        )
        self.client.force_login(self.admin)
        self.url = reverse('core:usuario_novo')

    def test_form_nao_tem_campo_senha(self):
        from .forms import UsuarioCriarForm
        form = UsuarioCriarForm()
        self.assertNotIn('senha', form.fields)

    def test_criar_usuario_novo_nao_tem_senha_utilizavel(self):
        from apps.core.models import UsuarioFederacao
        resp = self.client.post(self.url, {
            'email': 'novo@x.com', 'nome': 'Novo', 'papel': UsuarioFederacao.ARBITRO,
        })
        self.assertEqual(resp.status_code, 302)
        u = Usuario.objects.get(email='novo@x.com')
        self.assertFalse(u.has_usable_password())

    def test_criar_usuario_novo_envia_email_de_convite(self):
        from django.core import mail
        from apps.core.models import UsuarioFederacao
        mail.outbox = []
        self.client.post(self.url, {
            'email': 'convidado@x.com', 'nome': 'C', 'papel': UsuarioFederacao.ARBITRO,
        })
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('convidado@x.com', mail.outbox[0].to)
        # Mensagem tem link de reset
        self.assertIn('/auth/recuperar-senha/', mail.outbox[0].body)

    def test_vincular_usuario_existente_nao_envia_email(self):
        from django.core import mail
        from apps.core.models import UsuarioFederacao
        existente = Usuario.objects.create_user(
            email='ja@x.com', nome='Já', password='minhaSenha',
        )
        mail.outbox = []
        self.client.post(self.url, {
            'email': 'ja@x.com', 'papel': UsuarioFederacao.DIRIGENTE,
        })
        self.assertEqual(len(mail.outbox), 0)
        # Vínculo foi criado
        self.assertTrue(
            UsuarioFederacao.objects.filter(usuario=existente, federacao=self.fed).exists()
        )


# ---------------------------------------------------------------------------
# Passo 5.13 — Temporada removida (era código morto)
# ---------------------------------------------------------------------------

class TemporadaRemovidaTests(TestCase):
    def test_modelo_temporada_nao_existe_mais(self):
        from django.apps import apps as django_apps
        with self.assertRaises(LookupError):
            django_apps.get_model('core', 'Temporada')

    def test_competicao_nao_tem_campo_temporada(self):
        from apps.competicao.models import Competicao
        campos = {f.name for f in Competicao._meta.get_fields()}
        self.assertNotIn('temporada', campos)


# ---------------------------------------------------------------------------
# Passo 5.14 — Limpeza (código morto e ajustes)
# ---------------------------------------------------------------------------

class LimpezaCodigoMortoTests(TestCase):
    def test_usuario_remover_federacao_removido(self):
        self.assertFalse(hasattr(Usuario, 'remover_federacao'))

    def test_slug_colisao_gera_sufixo(self):
        f1 = Federacao.objects.create(nome='Federação X')
        f2 = Federacao.objects.create(nome='Federação X')
        self.assertNotEqual(f1.slug, f2.slug)
        self.assertTrue(f2.slug.endswith('-2'))

    def test_slug_com_nome_vazio_usa_fallback(self):
        f = Federacao.objects.create(nome='—')  # slugify vazio
        self.assertTrue(f.slug)

    def test_alterar_senha_form_aplica_validators(self):
        from django.test import override_settings
        from .forms import AlterarSenhaForm
        with override_settings(AUTH_PASSWORD_VALIDATORS=[
            {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
             'OPTIONS': {'min_length': 10}},
        ]):
            form = AlterarSenhaForm(data={
                'senha_atual': 'x', 'senha_nova': 'curta', 'senha_nova2': 'curta',
            })
            self.assertFalse(form.is_valid())
            self.assertIn('senha_nova', form.errors)

    def test_estados_br_disponivel_em_core_constants(self):
        from apps.core.constants import ESTADOS_BR
        self.assertGreater(len(ESTADOS_BR), 20)
        siglas = {c[0] for c in ESTADOS_BR}
        self.assertIn('SP', siglas)

    def test_atleta_nao_tem_metodo_nome_equipe(self):
        from apps.equipe.models import Atleta
        # Método era código morto; permanece só o field da Equipe
        self.assertFalse(callable(getattr(Atleta, 'nome_equipe', None)))

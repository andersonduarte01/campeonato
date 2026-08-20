import importlib
import os

from django.test import TestCase
from django.urls import reverse

from apps.core.models import Federacao, Usuario, UsuarioFederacao

from .models import Atleta, Equipe


def _fed(nome='F1', slug='f1'):
    return Federacao.objects.create(nome=nome, slug=slug, sigla=slug.upper()[:3])


def _admin(fed, email='a@x.com'):
    u = Usuario.objects.create_user(email=email, nome='A', password='x')
    UsuarioFederacao.objects.create(usuario=u, federacao=fed, papel=UsuarioFederacao.ADMIN)
    return u


class ImportacaoAppEquipeTests(TestCase):
    """Passo 5.4 — importar o app equipe não pode ter side effects.

    O arquivo apps/equipe/equipes.py (deletado neste passo) rodava
    Equipe.objects.get_or_create no import — poluía a base sem
    federação e quebrava unique_together.
    """

    def test_import_apps_equipe_nao_cria_registros(self):
        antes = Equipe.objects.count()
        importlib.import_module('apps.equipe')
        importlib.import_module('apps.equipe.models')
        depois = Equipe.objects.count()
        self.assertEqual(antes, depois)

    def test_arquivo_equipes_py_foi_removido(self):
        caminho = os.path.join(
            os.path.dirname(importlib.import_module('apps.equipe').__file__),
            'equipes.py',
        )
        self.assertFalse(
            os.path.exists(caminho),
            f'apps/equipe/equipes.py ainda existe em {caminho} — deveria ter sido removido no Passo 5.4.',
        )


class AtletaEstaSuspensoPropertyTests(TestCase):
    """Regressão do Passo 4.1: property depende de Suspensao pendente."""

    def setUp(self):
        self.fed = Federacao.objects.create(nome='Fed', slug='fed', sigla='F')
        self.equipe = Equipe.objects.create(federacao=self.fed, nome_equipe='X')
        self.atleta = Atleta.objects.create(
            nome='Y', equipe=self.equipe, posicao='ATACANTE',
        )

    def test_sem_suspensao_nao_esta_suspenso(self):
        from apps.criterios.models import FormatoCompeticao
        from apps.competicao.models import Competicao
        fmt = FormatoCompeticao.objects.create(nome='L', pontos_corridos=True)
        comp = Competicao.objects.create(
            federacao=self.fed, nome='Copa', data_inicio='2026-01-01', formato=fmt,
        )
        self.assertFalse(self.atleta.esta_suspenso(comp))


# ---------------------------------------------------------------------------
# Passo 5.6 — Isolamento de tenant (equipe)
# ---------------------------------------------------------------------------

class IsolamentoTenantEquipeTests(TestCase):
    def setUp(self):
        self.fed_a = _fed('Alpha', 'alpha')
        self.fed_b = _fed('Beta', 'beta')
        self.equipe_a = Equipe.objects.create(federacao=self.fed_a, nome_equipe='Time A')
        self.equipe_b = Equipe.objects.create(federacao=self.fed_b, nome_equipe='Time B')
        self.admin_a = _admin(self.fed_a, 'admin_a@x.com')
        self.client.force_login(self.admin_a)

    def test_lista_so_mostra_equipes_da_federacao(self):
        resp = self.client.get(reverse('equipe:lista'))
        self.assertEqual(resp.status_code, 200)
        equipes = list(resp.context['equipes'])
        self.assertIn(self.equipe_a, equipes)
        self.assertNotIn(self.equipe_b, equipes)

    def test_detalhe_equipe_de_outra_federacao_404(self):
        resp = self.client.get(reverse('equipe:detalhe', kwargs={'pk': self.equipe_b.pk}))
        self.assertEqual(resp.status_code, 404)

    def test_editar_equipe_de_outra_federacao_404(self):
        resp = self.client.get(reverse('equipe:editar', kwargs={'pk': self.equipe_b.pk}))
        self.assertEqual(resp.status_code, 404)

    def test_editar_equipe_da_propria_federacao_permitido(self):
        resp = self.client.get(reverse('equipe:editar', kwargs={'pk': self.equipe_a.pk}))
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# Passo 5.9 — Atleta.situacao sem 'SUSPENSO' (dupla fonte eliminada)
# ---------------------------------------------------------------------------

class AtletaSituacaoTests(TestCase):
    def test_situacao_choices_nao_contem_suspenso(self):
        valores = {c[0] for c in Atleta.SITUACAO_CHOICES}
        self.assertNotIn('SUSPENSO', valores)
        # Mas mantém as outras
        self.assertIn('APTO', valores)
        self.assertIn('LESIONADO', valores)
        self.assertIn('FORA', valores)

    def test_esta_suspenso_e_a_unica_fonte_de_verdade(self):
        from apps.competicao.models import Suspensao
        from apps.criterios.models import FormatoCompeticao
        from apps.competicao.models import Competicao
        fed = _fed('X', 'x')
        equipe = Equipe.objects.create(federacao=fed, nome_equipe='X')
        atleta = Atleta.objects.create(nome='Y', equipe=equipe, posicao='ATACANTE')
        fmt = FormatoCompeticao.objects.create(nome='F', pontos_corridos=True)
        comp = Competicao.objects.create(
            federacao=fed, nome='C', data_inicio='2026-01-01', formato=fmt,
        )
        # Atleta APTO (default) mas com Suspensao pendente → esta_suspenso True
        self.assertEqual(atleta.situacao, 'APTO')
        Suspensao.objects.create(atleta=atleta, competicao=comp)
        self.assertTrue(atleta.esta_suspenso(comp))
        # Não altera situacao (não é mais a fonte)
        atleta.refresh_from_db()
        self.assertEqual(atleta.situacao, 'APTO')


# ---------------------------------------------------------------------------
# Passo 5.15 — Refatorações menores (equipe)
# ---------------------------------------------------------------------------

class TecnicoEditarViewTests(TestCase):
    def setUp(self):
        self.fed = _fed('X', 'x')
        self.equipe = Equipe.objects.create(federacao=self.fed, nome_equipe='X')
        self.admin = _admin(self.fed, 'a@x.com')

    def test_get_sem_login_redireciona_para_login(self):
        # Sem login: decorator @requer_papel redireciona ao invés de 500
        resp = self.client.post(
            reverse('equipe:tecnico_editar', kwargs={'pk': self.equipe.pk}),
            {'tecnico': 'Novo Técnico'},
        )
        self.assertEqual(resp.status_code, 302)
        self.equipe.refresh_from_db()
        self.assertIsNone(self.equipe.tecnico)

    def test_admin_pode_editar_tecnico(self):
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse('equipe:tecnico_editar', kwargs={'pk': self.equipe.pk}),
            {'tecnico': 'Novo Técnico'},
        )
        self.assertEqual(resp.status_code, 302)
        self.equipe.refresh_from_db()
        self.assertEqual(self.equipe.tecnico, 'Novo Técnico')


# ---------------------------------------------------------------------------
# Passo 5.15 extra — URL desativar + Equipe.ativo unificado com situacao
# ---------------------------------------------------------------------------

class EquipeDesativarURLTests(TestCase):
    """URL name='desativar' (antes 'excluir') funciona corretamente."""

    def setUp(self):
        self.fed = _fed('D', 'd')
        self.equipe = Equipe.objects.create(federacao=self.fed, nome_equipe='Clube D')
        self.admin = _admin(self.fed, 'ad@x.com')
        self.client.force_login(self.admin)

    def test_url_desativar_existe(self):
        url = reverse('equipe:desativar', kwargs={'pk': self.equipe.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)

    def test_desativar_seta_situacao_desfiliado(self):
        url = reverse('equipe:desativar', kwargs={'pk': self.equipe.pk})
        self.client.post(url)
        self.equipe.refresh_from_db()
        self.assertEqual(self.equipe.situacao, Equipe.SITUACAO_DESFILIADO)

    def test_desfiliado_nao_aparece_na_lista(self):
        self.equipe.situacao = Equipe.SITUACAO_DESFILIADO
        self.equipe.save(update_fields=['situacao'])
        resp = self.client.get(reverse('equipe:lista'))
        self.assertNotIn(self.equipe, resp.context['equipes'])

    def test_filiado_aparece_na_lista(self):
        self.equipe.situacao = Equipe.SITUACAO_FILIADO
        self.equipe.save(update_fields=['situacao'])
        resp = self.client.get(reverse('equipe:lista'))
        self.assertIn(self.equipe, resp.context['equipes'])

    def test_campo_ativo_nao_existe_no_model(self):
        self.assertFalse(hasattr(self.equipe, 'ativo'))

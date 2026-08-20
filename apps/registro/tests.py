import datetime

from django.test import TestCase
from django.urls import reverse

from apps.core.models import Federacao, Usuario, UsuarioFederacao
from apps.equipe.models import Atleta, Equipe

from .dominio.excecoes import RegraVioladaError
from .dominio.transferencias import TransferenciaService
from .models import (
    HistoricoClube, JanelaTransferencia, RegistroFederativo,
    SequenciaRegistro, Transferencia,
)


def _admin(fed, email='admin@x.com'):
    u = Usuario.objects.create_user(email=email, nome='A', password='x')
    UsuarioFederacao.objects.create(usuario=u, federacao=fed, papel=UsuarioFederacao.ADMIN)
    return u


def _fed():
    return Federacao.objects.create(nome='Federação Teste', slug='fed-teste')


def _usuario(email='admin@x.com'):
    u = Usuario.objects.create_user(email=email, nome='X', password='x')
    return u


def _janela(federacao, aberta=True):
    hoje = datetime.date.today()
    if aberta:
        return JanelaTransferencia.objects.create(
            federacao=federacao, nome='Janela Teste',
            data_inicio=hoje - datetime.timedelta(days=1),
            data_fim=hoje + datetime.timedelta(days=30),
        )
    return JanelaTransferencia.objects.create(
        federacao=federacao, nome='Janela Fechada',
        data_inicio=hoje - datetime.timedelta(days=60),
        data_fim=hoje - datetime.timedelta(days=30),
    )


class TransferenciaAprovarTests(TestCase):
    def setUp(self):
        self.fed = _fed()
        self.origem = Equipe.objects.create(federacao=self.fed, nome_equipe='Origem')
        self.destino = Equipe.objects.create(federacao=self.fed, nome_equipe='Destino')
        self.atleta = Atleta.objects.create(
            nome='Jogador X', equipe=self.origem, posicao='ATACANTE',
        )
        self.janela = _janela(self.fed, aberta=True)
        self.transf = Transferencia.objects.create(
            atleta=self.atleta,
            clube_origem=self.origem,
            clube_destino=self.destino,
            tipo=Transferencia.TIPO_DEFINITIVA,
            janela=self.janela,
        )

    def test_aprovar_atualiza_equipe_do_atleta(self):
        TransferenciaService().aprovar(self.transf)
        self.atleta.refresh_from_db()
        self.transf.refresh_from_db()
        self.assertEqual(self.atleta.equipe, self.destino)
        self.assertEqual(self.transf.status, Transferencia.STATUS_APROVADA)
        self.assertEqual(self.transf.data_aprovacao, datetime.date.today())

    def test_aprovar_cria_historico_no_destino(self):
        TransferenciaService().aprovar(self.transf)
        historico = HistoricoClube.objects.filter(atleta=self.atleta, equipe=self.destino)
        self.assertEqual(historico.count(), 1)
        self.assertIsNone(historico.first().data_saida)
        self.assertEqual(historico.first().tipo, HistoricoClube.TIPO_TITULAR)

    def test_aprovar_fecha_historico_anterior(self):
        anterior = HistoricoClube.objects.create(
            atleta=self.atleta, equipe=self.origem,
            tipo=HistoricoClube.TIPO_TITULAR,
            data_entrada=datetime.date.today() - datetime.timedelta(days=100),
        )
        TransferenciaService().aprovar(self.transf)
        anterior.refresh_from_db()
        self.assertEqual(anterior.data_saida, datetime.date.today())

    def test_aprovar_emprestimo_marca_historico_como_emprestado(self):
        self.transf.tipo = Transferencia.TIPO_EMPRESTIMO
        self.transf.save()
        TransferenciaService().aprovar(self.transf)
        hist = HistoricoClube.objects.get(atleta=self.atleta, equipe=self.destino)
        self.assertEqual(hist.tipo, HistoricoClube.TIPO_EMPRESTADO)

    def test_aprovar_janela_fechada_bloqueia(self):
        fechada = _janela(self.fed, aberta=False)
        self.transf.janela = fechada
        self.transf.save()
        with self.assertRaises(RegraVioladaError):
            TransferenciaService().aprovar(self.transf)
        self.transf.refresh_from_db()
        self.assertEqual(self.transf.status, Transferencia.STATUS_SOLICITADA)
        self.atleta.refresh_from_db()
        self.assertEqual(self.atleta.equipe, self.origem)

    def test_aprovar_sem_janela_bloqueia(self):
        self.transf.janela = None
        self.transf.save()
        with self.assertRaises(RegraVioladaError):
            TransferenciaService().aprovar(self.transf)

    def test_aprovar_janela_fechada_com_ignorar_janela_passa(self):
        fechada = _janela(self.fed, aberta=False)
        self.transf.janela = fechada
        self.transf.save()
        TransferenciaService().aprovar(self.transf, ignorar_janela=True)
        self.transf.refresh_from_db()
        self.assertEqual(self.transf.status, Transferencia.STATUS_APROVADA)

    def test_aprovar_ja_aprovada_bloqueia(self):
        TransferenciaService().aprovar(self.transf)
        with self.assertRaises(RegraVioladaError):
            TransferenciaService().aprovar(self.transf)

    def test_aprovacao_atomica_se_historico_falhar(self):
        # Simula falha ao criar HistoricoClube deletando o atleta em plena
        # execução via monkey patch — o statement create() dentro do
        # service dispara IntegrityError e a transação deve reverter.
        from unittest.mock import patch

        original_create = HistoricoClube.objects.create

        def create_com_erro(*args, **kwargs):
            raise RuntimeError('boom')

        with patch.object(HistoricoClube.objects, 'create', side_effect=create_com_erro):
            with self.assertRaises(RuntimeError):
                TransferenciaService().aprovar(self.transf)
        self.transf.refresh_from_db()
        self.atleta.refresh_from_db()
        # Nada foi persistido: status ainda solicitada, atleta ainda no origem
        self.assertEqual(self.transf.status, Transferencia.STATUS_SOLICITADA)
        self.assertEqual(self.atleta.equipe, self.origem)


class TransferenciaRejeitarCancelarTests(TestCase):
    def setUp(self):
        self.fed = _fed()
        origem = Equipe.objects.create(federacao=self.fed, nome_equipe='Origem')
        destino = Equipe.objects.create(federacao=self.fed, nome_equipe='Destino')
        atleta = Atleta.objects.create(nome='X', equipe=origem, posicao='ATACANTE')
        self.transf = Transferencia.objects.create(
            atleta=atleta, clube_origem=origem, clube_destino=destino,
            tipo=Transferencia.TIPO_DEFINITIVA,
            janela=_janela(self.fed, aberta=True),
        )

    def test_rejeitar_muda_status(self):
        TransferenciaService().rejeitar(self.transf)
        self.transf.refresh_from_db()
        self.assertEqual(self.transf.status, Transferencia.STATUS_REJEITADA)

    def test_rejeitar_aprovada_bloqueia(self):
        TransferenciaService().aprovar(self.transf)
        with self.assertRaises(RegraVioladaError):
            TransferenciaService().rejeitar(self.transf)

    def test_cancelar_muda_status(self):
        TransferenciaService().cancelar(self.transf)
        self.transf.refresh_from_db()
        self.assertEqual(self.transf.status, Transferencia.STATUS_CANCELADA)

    def test_cancelar_aprovada_bloqueia(self):
        TransferenciaService().aprovar(self.transf)
        with self.assertRaises(RegraVioladaError):
            TransferenciaService().cancelar(self.transf)

    def test_marcar_em_analise(self):
        TransferenciaService().marcar_em_analise(self.transf)
        self.transf.refresh_from_db()
        self.assertEqual(self.transf.status, Transferencia.STATUS_EM_ANALISE)

    def test_marcar_em_analise_ja_em_analise_bloqueia(self):
        TransferenciaService().marcar_em_analise(self.transf)
        with self.assertRaises(RegraVioladaError):
            TransferenciaService().marcar_em_analise(self.transf)


# ---------------------------------------------------------------------------
# Passo 5.3 — SequenciaRegistro (numeração atômica)
# ---------------------------------------------------------------------------

class SequenciaRegistroTests(TestCase):
    def setUp(self):
        self.fed = Federacao.objects.create(nome='Federação Alpha', slug='fa', sigla='FA')
        self.equipe = Equipe.objects.create(federacao=self.fed, nome_equipe='Time A')

    def _atleta(self, nome):
        return Atleta.objects.create(nome=nome, equipe=self.equipe, posicao='ATACANTE')

    def test_primeira_geracao_comeca_em_00001(self):
        reg = RegistroFederativo.objects.create(
            federacao=self.fed, atleta=self._atleta('A'),
        )
        self.assertTrue(reg.numero_federativo.endswith('-00001'))

    def test_geracao_incrementa_sequencial(self):
        n1 = RegistroFederativo.objects.create(
            federacao=self.fed, atleta=self._atleta('A'),
        ).numero_federativo
        n2 = RegistroFederativo.objects.create(
            federacao=self.fed, atleta=self._atleta('B'),
        ).numero_federativo
        n3 = RegistroFederativo.objects.create(
            federacao=self.fed, atleta=self._atleta('C'),
        ).numero_federativo
        self.assertTrue(n1.endswith('-00001'))
        self.assertTrue(n2.endswith('-00002'))
        self.assertTrue(n3.endswith('-00003'))

    def test_sequencias_isoladas_por_federacao(self):
        fed_b = Federacao.objects.create(nome='Federação Beta', slug='fb', sigla='FB')
        equipe_b = Equipe.objects.create(federacao=fed_b, nome_equipe='Time B')

        RegistroFederativo.objects.create(federacao=self.fed, atleta=self._atleta('A1'))
        RegistroFederativo.objects.create(federacao=self.fed, atleta=self._atleta('A2'))

        atleta_b = Atleta.objects.create(nome='B1', equipe=equipe_b, posicao='ATACANTE')
        reg_b = RegistroFederativo.objects.create(federacao=fed_b, atleta=atleta_b)
        # federação B começa do zero
        self.assertTrue(reg_b.numero_federativo.endswith('-00001'))
        self.assertIn('FB-', reg_b.numero_federativo)

    def test_sequencia_criada_com_ultimo_seq_correto(self):
        RegistroFederativo.objects.create(federacao=self.fed, atleta=self._atleta('A'))
        RegistroFederativo.objects.create(federacao=self.fed, atleta=self._atleta('B'))
        ano = datetime.date.today().year
        seq = SequenciaRegistro.objects.get(federacao=self.fed, ano=ano)
        self.assertEqual(seq.ultimo_seq, 2)

    def test_proximo_seq_sem_criar_registro(self):
        """Serve para uso administrativo (reservar número sem criar registro)."""
        ano = datetime.date.today().year
        n1 = SequenciaRegistro.proximo_seq(self.fed, ano)
        n2 = SequenciaRegistro.proximo_seq(self.fed, ano)
        n3 = SequenciaRegistro.proximo_seq(self.fed, ano)
        self.assertEqual([n1, n2, n3], [1, 2, 3])

    def test_numero_bate_com_padrao_esperado(self):
        reg = RegistroFederativo.objects.create(
            federacao=self.fed, atleta=self._atleta('A'),
        )
        ano = datetime.date.today().year
        self.assertEqual(reg.numero_federativo, f'FA-{ano}-00001')

    def test_federacao_sem_sigla_usa_fallback_FED(self):
        fed_c = Federacao.objects.create(nome='Sem Sigla', slug='sc', sigla='')
        equipe_c = Equipe.objects.create(federacao=fed_c, nome_equipe='X')
        atleta_c = Atleta.objects.create(nome='X', equipe=equipe_c, posicao='ATACANTE')
        reg = RegistroFederativo.objects.create(federacao=fed_c, atleta=atleta_c)
        self.assertTrue(reg.numero_federativo.startswith('FED-'))


# ---------------------------------------------------------------------------
# Passo 5.6 — Isolamento de tenant (registro)
# ---------------------------------------------------------------------------

class IsolamentoTenantRegistroTests(TestCase):
    def setUp(self):
        self.fed_a = Federacao.objects.create(nome='A', slug='a', sigla='A')
        self.fed_b = Federacao.objects.create(nome='B', slug='b', sigla='B')
        equipe_a = Equipe.objects.create(federacao=self.fed_a, nome_equipe='Time A')
        equipe_b = Equipe.objects.create(federacao=self.fed_b, nome_equipe='Time B')
        self.atleta_a = Atleta.objects.create(
            nome='Jogador A', equipe=equipe_a, posicao='ATACANTE',
        )
        self.atleta_b = Atleta.objects.create(
            nome='Jogador B', equipe=equipe_b, posicao='ATACANTE',
        )
        self.reg_a = RegistroFederativo.objects.create(
            federacao=self.fed_a, atleta=self.atleta_a,
        )
        self.reg_b = RegistroFederativo.objects.create(
            federacao=self.fed_b, atleta=self.atleta_b,
        )
        # Transferências
        equipe_a2 = Equipe.objects.create(federacao=self.fed_a, nome_equipe='Outro A')
        equipe_b2 = Equipe.objects.create(federacao=self.fed_b, nome_equipe='Outro B')
        self.janela_a = _janela(self.fed_a, aberta=True)
        self.janela_b = _janela(self.fed_b, aberta=True)
        self.transf_a = Transferencia.objects.create(
            atleta=self.atleta_a, clube_origem=equipe_a, clube_destino=equipe_a2,
            tipo=Transferencia.TIPO_DEFINITIVA, janela=self.janela_a,
        )
        self.transf_b = Transferencia.objects.create(
            atleta=self.atleta_b, clube_origem=equipe_b, clube_destino=equipe_b2,
            tipo=Transferencia.TIPO_DEFINITIVA, janela=self.janela_b,
        )
        self.admin_a = _admin(self.fed_a, 'admin_a@x.com')
        self.client.force_login(self.admin_a)

    def test_registro_lista_so_mostra_da_federacao(self):
        resp = self.client.get(reverse('registro:registro_lista'))
        self.assertEqual(resp.status_code, 200)
        regs = list(resp.context['registros'])
        self.assertIn(self.reg_a, regs)
        self.assertNotIn(self.reg_b, regs)

    def test_registro_detalhe_de_outra_federacao_404(self):
        resp = self.client.get(
            reverse('registro:registro_detalhe', kwargs={'pk': self.reg_b.pk}),
        )
        self.assertEqual(resp.status_code, 404)

    def test_transferencia_detalhe_de_outra_federacao_404(self):
        resp = self.client.get(
            reverse('registro:transferencia_detalhe', kwargs={'pk': self.transf_b.pk}),
        )
        self.assertEqual(resp.status_code, 404)

    def test_transferencia_aprovar_em_outra_federacao_404(self):
        resp = self.client.post(
            reverse('registro:transferencia_aprovar', kwargs={'pk': self.transf_b.pk}),
        )
        self.assertEqual(resp.status_code, 404)
        self.transf_b.refresh_from_db()
        self.assertEqual(self.transf_b.status, Transferencia.STATUS_SOLICITADA)

    def test_dashboard_conta_so_da_federacao(self):
        resp = self.client.get(reverse('registro:dashboard'))
        self.assertEqual(resp.status_code, 200)
        # 1 registro na fed_a
        self.assertEqual(resp.context['total_registros'], 1)


# ---------------------------------------------------------------------------
# Passo 5.10 — Transferência internacional
# ---------------------------------------------------------------------------

class TransferenciaInternacionalTests(TestCase):
    def setUp(self):
        self.fed = Federacao.objects.create(nome='F', slug='f', sigla='F')
        self.destino = Equipe.objects.create(federacao=self.fed, nome_equipe='Destino BR')
        self.atleta = Atleta.objects.create(
            nome='Estrangeiro', equipe=self.destino, posicao='ATACANTE',
        )
        self.janela = _janela(self.fed, aberta=True)

    def test_criar_internacional_sem_clube_origem(self):
        t = Transferencia(
            atleta=self.atleta,
            clube_destino=self.destino,
            tipo=Transferencia.TIPO_INTERNACIONAL,
            clube_origem_externo='Boca Juniors (ARG)',
            janela=self.janela,
        )
        t.full_clean()  # não estoura
        t.save()
        self.assertIsNone(t.clube_origem_id)
        self.assertEqual(t.clube_origem_externo, 'Boca Juniors (ARG)')

    def test_internacional_sem_clube_externo_bloqueia(self):
        from django.core.exceptions import ValidationError
        t = Transferencia(
            atleta=self.atleta,
            clube_destino=self.destino,
            tipo=Transferencia.TIPO_INTERNACIONAL,
            janela=self.janela,
        )
        with self.assertRaises(ValidationError):
            t.full_clean()

    def test_nacional_sem_clube_origem_bloqueia(self):
        from django.core.exceptions import ValidationError
        t = Transferencia(
            atleta=self.atleta,
            clube_destino=self.destino,
            tipo=Transferencia.TIPO_DEFINITIVA,
            janela=self.janela,
        )
        with self.assertRaises(ValidationError):
            t.full_clean()

    def test_internacional_com_clube_origem_bloqueia(self):
        from django.core.exceptions import ValidationError
        outra = Equipe.objects.create(federacao=self.fed, nome_equipe='Outra')
        t = Transferencia(
            atleta=self.atleta,
            clube_origem=outra,
            clube_destino=self.destino,
            tipo=Transferencia.TIPO_INTERNACIONAL,
            clube_origem_externo='Chelsea',
            janela=self.janela,
        )
        with self.assertRaises(ValidationError):
            t.full_clean()

    def test_aprovar_internacional_nao_fecha_historico(self):
        t = Transferencia.objects.create(
            atleta=self.atleta,
            clube_destino=self.destino,
            tipo=Transferencia.TIPO_INTERNACIONAL,
            clube_origem_externo='Boca Juniors (ARG)',
            janela=self.janela,
        )
        # Cria histórico "aberto" (não deveria ser fechado)
        anterior = HistoricoClube.objects.create(
            atleta=self.atleta, equipe=self.destino,
            tipo=HistoricoClube.TIPO_TITULAR,
            data_entrada=datetime.date.today() - datetime.timedelta(days=100),
        )
        TransferenciaService().aprovar(t)
        anterior.refresh_from_db()
        # Transferência internacional NÃO fecha históricos anteriores
        self.assertIsNone(anterior.data_saida)
        # Mas cria novo histórico no destino
        self.assertEqual(
            HistoricoClube.objects.filter(atleta=self.atleta, equipe=self.destino).count(),
            2,
        )


# ---------------------------------------------------------------------------
# Passo 5.12 — Cron desativar_janelas
# ---------------------------------------------------------------------------

class DesativarJanelasCommandTests(TestCase):
    def setUp(self):
        self.fed = Federacao.objects.create(nome='F', slug='f', sigla='F')

    def _janela(self, ativa, inicio, fim):
        return JanelaTransferencia.objects.create(
            federacao=self.fed, nome='J', ativa=ativa,
            data_inicio=inicio, data_fim=fim,
        )

    def test_command_desativa_encerradas(self):
        from django.core.management import call_command
        from io import StringIO

        hoje = datetime.date.today()
        j_encerrada = self._janela(
            True, hoje - datetime.timedelta(days=60), hoje - datetime.timedelta(days=30),
        )
        j_ativa = self._janela(
            True, hoje - datetime.timedelta(days=1), hoje + datetime.timedelta(days=30),
        )
        out = StringIO()
        call_command('desativar_janelas', stdout=out)
        j_encerrada.refresh_from_db()
        j_ativa.refresh_from_db()
        self.assertFalse(j_encerrada.ativa)
        self.assertTrue(j_ativa.ativa)
        self.assertIn('1 janela', out.getvalue())

    def test_command_zero_desativadas(self):
        from django.core.management import call_command
        from io import StringIO

        hoje = datetime.date.today()
        self._janela(True, hoje, hoje + datetime.timedelta(days=30))
        out = StringIO()
        call_command('desativar_janelas', stdout=out)
        self.assertIn('0 janela', out.getvalue())

    def test_views_nao_chamam_mais_desativar_encerradas(self):
        """Regressão: views.py não deve mais chamar desativar_encerradas."""
        import os
        with open(os.path.join(os.path.dirname(__file__), 'views.py')) as f:
            src = f.read()
        self.assertNotIn(
            'desativar_encerradas',
            src,
            'views.py ainda chama desativar_encerradas — deveria ser feito pelo cron.',
        )


# ---------------------------------------------------------------------------
# Passo 5.15 — HistoricoClube fechado com log de warning
# ---------------------------------------------------------------------------

class HistoricoMultiploAbertoTests(TestCase):
    def setUp(self):
        self.fed = Federacao.objects.create(nome='F', slug='f', sigla='F')
        origem = Equipe.objects.create(federacao=self.fed, nome_equipe='O')
        destino = Equipe.objects.create(federacao=self.fed, nome_equipe='D')
        self.atleta = Atleta.objects.create(nome='X', equipe=origem, posicao='ATACANTE')
        self.destino = destino
        self.origem = origem
        self.transf = Transferencia.objects.create(
            atleta=self.atleta, clube_origem=origem, clube_destino=destino,
            tipo=Transferencia.TIPO_DEFINITIVA,
            janela=_janela(self.fed, aberta=True),
        )

    def test_multiplos_historicos_abertos_geram_warning(self):
        import logging
        HistoricoClube.objects.create(
            atleta=self.atleta, equipe=self.origem,
            tipo=HistoricoClube.TIPO_TITULAR,
            data_entrada=datetime.date.today() - datetime.timedelta(days=100),
        )
        HistoricoClube.objects.create(
            atleta=self.atleta, equipe=self.destino,
            tipo=HistoricoClube.TIPO_TITULAR,
            data_entrada=datetime.date.today() - datetime.timedelta(days=50),
        )
        with self.assertLogs('apps.registro.dominio.transferencias', level=logging.WARNING) as cm:
            TransferenciaService().aprovar(self.transf)
        self.assertTrue(any('históricos abertos' in m for m in cm.output))
        # Todos fechados
        self.assertEqual(
            HistoricoClube.objects.filter(atleta=self.atleta, data_saida__isnull=True).count(),
            1,  # só o novo criado na aprovação
        )


# ---------------------------------------------------------------------------
# Passo 5.15 extra — 4 views de transferência (analisar/aprovar/rejeitar/cancelar)
# ---------------------------------------------------------------------------

class TransferenciaViewsSeparadasTests(TestCase):
    def setUp(self):
        self.fed = Federacao.objects.create(nome='F', slug='f5v', sigla='F5V')
        self.admin_user = Usuario.objects.create_user(email='adm5v@x.com', nome='A', password='x')
        UsuarioFederacao.objects.create(
            usuario=self.admin_user, federacao=self.fed, papel=UsuarioFederacao.ADMIN,
        )
        self.client.force_login(self.admin_user)
        origem = Equipe.objects.create(federacao=self.fed, nome_equipe='O5V')
        destino = Equipe.objects.create(federacao=self.fed, nome_equipe='D5V')
        atleta = Atleta.objects.create(nome='At5V', equipe=origem, posicao='ATACANTE')
        janela = _janela(self.fed, aberta=True)
        self.transf = Transferencia.objects.create(
            atleta=atleta, clube_origem=origem, clube_destino=destino,
            tipo=Transferencia.TIPO_DEFINITIVA, janela=janela,
        )
        self.origem = origem

    def _url(self, acao, transf=None):
        t = transf or self.transf
        return reverse(f'registro:transferencia_{acao}', kwargs={'pk': t.pk})

    def test_analisar_muda_status(self):
        self.client.post(self._url('analisar'))
        self.transf.refresh_from_db()
        self.assertEqual(self.transf.status, Transferencia.STATUS_EM_ANALISE)

    def test_rejeitar_muda_status(self):
        self.client.post(self._url('rejeitar'))
        self.transf.refresh_from_db()
        self.assertEqual(self.transf.status, Transferencia.STATUS_REJEITADA)

    def test_cancelar_muda_status(self):
        self.client.post(self._url('cancelar'))
        self.transf.refresh_from_db()
        self.assertEqual(self.transf.status, Transferencia.STATUS_CANCELADA)

    def test_aprovar_muda_status(self):
        HistoricoClube.objects.create(
            atleta=self.transf.atleta, equipe=self.origem,
            tipo=HistoricoClube.TIPO_TITULAR,
            data_entrada=datetime.date.today() - datetime.timedelta(days=10),
        )
        self.client.post(self._url('aprovar'))
        self.transf.refresh_from_db()
        self.assertEqual(self.transf.status, Transferencia.STATUS_APROVADA)

    def test_get_nao_muda_status(self):
        self.client.get(self._url('analisar'))
        self.transf.refresh_from_db()
        self.assertEqual(self.transf.status, Transferencia.STATUS_SOLICITADA)

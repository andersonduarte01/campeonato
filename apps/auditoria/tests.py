import json

from django.test import TestCase
from django.urls import reverse

from apps.core.models import Federacao, Usuario, UsuarioFederacao

from .dominio.registrar import registrar_evento
from .models import AuditoriaEvento, ConsentimentoLGPD


def _fed(nome, slug):
    return Federacao.objects.create(nome=nome, slug=slug, sigla=slug.upper()[:3])


def _user(email, fed=None, papel=UsuarioFederacao.ADMIN):
    u = Usuario.objects.create_user(email=email, nome='X', password='x')
    if fed:
        UsuarioFederacao.objects.create(usuario=u, federacao=fed, papel=papel)
    return u


# ---------------------------------------------------------------------------
# Passo 5.6 — Isolamento de tenant (auditoria/LGPD)
# ---------------------------------------------------------------------------

class LGPDIsolamentoTests(TestCase):
    def setUp(self):
        self.fed_a = _fed('A', 'a')
        self.fed_b = _fed('B', 'b')
        self.user_a = _user('a@x.com', fed=self.fed_a)
        self.user_b = _user('b@x.com', fed=self.fed_b)
        # Consentimentos separados
        ConsentimentoLGPD.objects.create(
            usuario=self.user_a, tipo='analytics', aceito=True,
        )
        ConsentimentoLGPD.objects.create(
            usuario=self.user_b, tipo='analytics', aceito=True,
        )

    def test_dashboard_mostra_apenas_consentimentos_do_usuario(self):
        self.client.force_login(self.user_a)
        resp = self.client.get(reverse('auditoria:lgpd_dashboard'))
        self.assertEqual(resp.status_code, 200)
        # Só os consentimentos do próprio usuário aparecem no state
        estado = {c['tipo']: c['aceito'] for c in resp.context['tipo_choices_state']}
        self.assertTrue(estado['analytics'])
        # Muda o consentimento de user_b para False
        c_b = ConsentimentoLGPD.objects.get(usuario=self.user_b, tipo='analytics')
        c_b.aceito = False
        c_b.save()
        # Dashboard do user_a continua mostrando True (não é afetado pelo outro user)
        resp2 = self.client.get(reverse('auditoria:lgpd_dashboard'))
        estado2 = {c['tipo']: c['aceito'] for c in resp2.context['tipo_choices_state']}
        self.assertTrue(estado2['analytics'])

    def test_exportar_dados_so_traz_do_proprio_usuario(self):
        self.client.force_login(self.user_a)
        resp = self.client.get(reverse('auditoria:lgpd_exportar'))
        self.assertEqual(resp.status_code, 200)
        payload = json.loads(resp.content.decode('utf-8'))
        self.assertEqual(payload['usuario']['id'], self.user_a.pk)
        self.assertEqual(payload['usuario']['email'], self.user_a.email)
        # user_b não aparece
        emails = json.dumps(payload)
        self.assertNotIn(self.user_b.email, emails)

    def test_anonimizar_sem_confirmacao_nao_afeta(self):
        self.client.force_login(self.user_a)
        resp = self.client.post(
            reverse('auditoria:lgpd_anonimizar'), {'confirmacao': 'errado'},
        )
        self.user_a.refresh_from_db()
        self.assertEqual(self.user_a.email, 'a@x.com')
        self.assertTrue(self.user_a.is_active)

    def test_anonimizar_com_confirmacao_desativa_conta(self):
        pk = self.user_a.pk
        self.client.force_login(self.user_a)
        self.client.post(
            reverse('auditoria:lgpd_anonimizar'), {'confirmacao': 'CONFIRMAR'},
        )
        self.user_a.refresh_from_db()
        self.assertFalse(self.user_a.is_active)
        self.assertEqual(self.user_a.email, f'anonimizado_{pk}@champs.invalid')

    def test_endpoints_lgpd_exigem_login(self):
        # sem login → redireciona para login
        for url in [
            reverse('auditoria:lgpd_dashboard'),
            reverse('auditoria:lgpd_exportar'),
            reverse('auditoria:lgpd_anonimizar'),
        ]:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302)
            self.assertIn('/auth/login/', resp.url)


# ---------------------------------------------------------------------------
# Passo 5.7 — AuditoriaEvento + signals
# ---------------------------------------------------------------------------

class AuditoriaEventoTests(TestCase):
    def setUp(self):
        self.fed = _fed('A', 'a')
        self.admin = _user('admin@x.com', fed=self.fed)

    def test_registrar_evento_grava(self):
        registrar_evento(
            tipo='teste_evento', federacao=self.fed, usuario=self.admin,
            dados={'chave': 'valor'},
        )
        ev = AuditoriaEvento.objects.get()
        self.assertEqual(ev.tipo, 'teste_evento')
        self.assertEqual(ev.federacao, self.fed)
        self.assertEqual(ev.dados, {'chave': 'valor'})

    def test_registrar_evento_falha_silenciosamente(self):
        # tipo com mais de 40 chars poderia estourar — verifica que
        # registrar_evento não propaga exceção
        resultado = registrar_evento(
            tipo='x' * 200, federacao=self.fed,
        )
        # Ou grava (se DB truncar) ou retorna None (se validar) — não estoura
        self.assertTrue(resultado is None or resultado.pk is not None)

    def test_signal_grava_transicao_de_competicao(self):
        from datetime import date

        from apps.competicao.models import Competicao
        from apps.criterios.models import CriterioClassificacao, FormatoCompeticao

        fmt = FormatoCompeticao.objects.create(nome='F', pontos_corridos=True)
        crit = CriterioClassificacao.objects.create(nome='C')
        comp = Competicao.objects.create(
            federacao=self.fed, nome='Copa', data_inicio=date(2026, 1, 1),
            formato=fmt, criterio_classificacao=crit,
        )
        AuditoriaEvento.objects.all().delete()
        comp.transicionar(Competicao.CONFIGURADA)
        eventos = AuditoriaEvento.objects.filter(tipo='competicao_transicao')
        self.assertEqual(eventos.count(), 1)
        self.assertEqual(eventos.first().dados['de'], 'rascunho')
        self.assertEqual(eventos.first().dados['para'], 'configurada')

    def test_signal_grava_transferencia_aprovada(self):
        from apps.equipe.models import Atleta, Equipe
        from apps.registro.dominio.transferencias import TransferenciaService
        from apps.registro.models import JanelaTransferencia, Transferencia
        import datetime

        origem = Equipe.objects.create(federacao=self.fed, nome_equipe='Origem')
        destino = Equipe.objects.create(federacao=self.fed, nome_equipe='Destino')
        atleta = Atleta.objects.create(nome='X', equipe=origem, posicao='ATACANTE')
        janela = JanelaTransferencia.objects.create(
            federacao=self.fed, nome='J', ativa=True,
            data_inicio=datetime.date.today() - datetime.timedelta(days=1),
            data_fim=datetime.date.today() + datetime.timedelta(days=30),
        )
        t = Transferencia.objects.create(
            atleta=atleta, clube_origem=origem, clube_destino=destino,
            tipo=Transferencia.TIPO_DEFINITIVA, janela=janela,
        )
        AuditoriaEvento.objects.filter(tipo__startswith='transferencia_').delete()
        TransferenciaService().aprovar(t)
        eventos = AuditoriaEvento.objects.filter(tipo='transferencia_aprovada')
        self.assertEqual(eventos.count(), 1)

    def test_signal_ignora_save_sem_mudanca_de_status(self):
        from datetime import date

        from apps.competicao.models import Competicao
        from apps.criterios.models import FormatoCompeticao

        fmt = FormatoCompeticao.objects.create(nome='F', pontos_corridos=True)
        comp = Competicao.objects.create(
            federacao=self.fed, nome='Copa', data_inicio=date(2026, 1, 1),
            formato=fmt,
        )
        AuditoriaEvento.objects.all().delete()
        comp.observacoes = 'teste'
        comp.save()
        self.assertFalse(
            AuditoriaEvento.objects.filter(tipo='competicao_transicao').exists()
        )


class EventosListaViewTests(TestCase):
    def setUp(self):
        self.fed_a = _fed('A', 'a')
        self.fed_b = _fed('B', 'b')
        self.admin_a = _user('admin_a@x.com', fed=self.fed_a)
        AuditoriaEvento.objects.create(federacao=self.fed_a, tipo='x')
        AuditoriaEvento.objects.create(federacao=self.fed_a, tipo='y')
        AuditoriaEvento.objects.create(federacao=self.fed_b, tipo='x')

    def test_lista_filtra_por_federacao(self):
        self.client.force_login(self.admin_a)
        resp = self.client.get(reverse('auditoria:eventos_lista'))
        self.assertEqual(resp.status_code, 200)
        eventos = list(resp.context['page'].object_list)
        self.assertEqual(len(eventos), 2)
        for e in eventos:
            self.assertEqual(e.federacao, self.fed_a)

    def test_lista_aceita_filtro_por_tipo(self):
        self.client.force_login(self.admin_a)
        resp = self.client.get(reverse('auditoria:eventos_lista') + '?tipo=x')
        self.assertEqual(resp.status_code, 200)
        eventos = list(resp.context['page'].object_list)
        self.assertEqual(len(eventos), 1)
        self.assertEqual(eventos[0].tipo, 'x')


# ---------------------------------------------------------------------------
# Passo 5.15 — Refatorações menores (auditoria)
# ---------------------------------------------------------------------------

class GetClientIpTests(TestCase):
    def _request(self, remote='10.0.0.1', xff=None):
        class _R:
            META = {}
        r = _R()
        r.META['REMOTE_ADDR'] = remote
        if xff is not None:
            r.META['HTTP_X_FORWARDED_FOR'] = xff
        return r

    def test_ignora_xff_quando_use_x_forwarded_host_falso(self):
        from django.test import override_settings
        from .utils import get_client_ip
        r = self._request(remote='10.0.0.1', xff='1.2.3.4')
        with override_settings(USE_X_FORWARDED_HOST=False):
            self.assertEqual(get_client_ip(r), '10.0.0.1')

    def test_respeita_xff_quando_use_x_forwarded_host_verdadeiro(self):
        from django.test import override_settings
        from .utils import get_client_ip
        r = self._request(remote='10.0.0.1', xff='1.2.3.4, 5.6.7.8')
        with override_settings(USE_X_FORWARDED_HOST=True):
            self.assertEqual(get_client_ip(r), '1.2.3.4')


class AnonimizacaoInvalidaSessoesTests(TestCase):
    def test_anonimizar_apaga_todas_sessoes_do_usuario(self):
        from django.contrib.sessions.models import Session
        fed = _fed('F', 'f')
        user = _user('vitima@x.com', fed=fed)
        # Cria uma sessão em cliente "outro dispositivo"
        outro = self.client_class()
        outro.force_login(user)
        # Cliente principal loga e anonimiza
        self.client.force_login(user)
        self.client.post(
            reverse('auditoria:lgpd_anonimizar'), {'confirmacao': 'CONFIRMAR'},
        )
        # Nenhuma sessão do user_a persiste
        sobrou = False
        for sess in Session.objects.iterator():
            try:
                data = sess.get_decoded()
            except Exception:
                continue
            if str(data.get('_auth_user_id')) == str(user.pk):
                sobrou = True
                break
        self.assertFalse(sobrou)

    def test_anonimizar_torna_senha_inutilizavel(self):
        fed = _fed('G', 'g')
        user = _user('vitima2@x.com', fed=fed)
        self.assertTrue(user.has_usable_password())  # antes: senha 'x'
        self.client.force_login(user)
        self.client.post(
            reverse('auditoria:lgpd_anonimizar'), {'confirmacao': 'CONFIRMAR'},
        )
        user.refresh_from_db()
        self.assertFalse(user.has_usable_password())

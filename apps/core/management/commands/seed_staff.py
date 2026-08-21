import random
import unicodedata

from django.core.management.base import BaseCommand, CommandError
from faker import Faker

from apps.competicao.models import Local
from apps.core.models import Federacao, Usuario, UsuarioFederacao

fake = Faker('pt_BR')

SENHA_PADRAO = 'sosa1808'

TIPOS_LOCAL = [
    'Estádio Municipal', 'Arena', 'Ginásio Poliesportivo', 'Campo Society',
    'Centro Esportivo', 'Complexo Esportivo', 'Estádio', 'Parque Esportivo',
]


def _slug_email(nome):
    normalizado = unicodedata.normalize('NFKD', nome).encode('ascii', 'ignore').decode('ascii')
    partes = [
        ''.join(c for c in p.lower() if c.isalnum())
        for p in normalizado.split()
    ]
    partes = [p for p in partes if p]
    return '.'.join(partes[:2]) if len(partes) >= 2 else (partes[0] if partes else 'usuario')


def _email_unico(nome, usados):
    base = _slug_email(nome)
    email = f'{base}@champs.com.br'
    n = 1
    while email in usados or Usuario.objects.filter(email=email).exists():
        n += 1
        email = f'{base}{n}@champs.com.br'
    usados.add(email)
    return email


class Command(BaseCommand):
    help = 'Cria 1 secretário, 10 árbitros e 10 locais fictícios via Faker, vinculados à federação'

    def add_arguments(self, parser):
        parser.add_argument('--federacao', type=int, help='ID da federação (padrão: primeira ativa)')
        parser.add_argument('--arbitros', type=int, default=10, help='Quantidade de árbitros (padrão: 10)')
        parser.add_argument('--locais',   type=int, default=10, help='Quantidade de locais (padrão: 10)')

    def handle(self, *args, **options):
        fed_id = options['federacao']
        if fed_id:
            try:
                federacao = Federacao.objects.get(pk=fed_id)
            except Federacao.DoesNotExist:
                raise CommandError(f'Federação {fed_id} não encontrada.')
        else:
            federacao = Federacao.objects.filter(ativa=True).first()
            if not federacao:
                raise CommandError('Nenhuma federação ativa encontrada. Passe --federacao <id>.')

        self.stdout.write(f'Federação: {federacao.nome} (id={federacao.pk})\n')

        emails_usados = set(Usuario.objects.values_list('email', flat=True))
        credenciais = []

        # ── Secretário ──────────────────────────────────────────────────
        nome_sec = fake.name()
        email_sec = _email_unico(nome_sec, emails_usados)
        usuario_sec = Usuario.objects.create_user(email=email_sec, nome=nome_sec, password=SENHA_PADRAO)
        UsuarioFederacao.objects.create(
            usuario=usuario_sec, federacao=federacao,
            papel=UsuarioFederacao.SECRETARIO, ativo=True,
        )
        credenciais.append(('Secretário', nome_sec, email_sec))
        self.stdout.write(self.style.SUCCESS(f'+ Secretário: {nome_sec} <{email_sec}>'))

        # ── Árbitros ─────────────────────────────────────────────────────
        for _ in range(options['arbitros']):
            nome_arb = fake.name()
            email_arb = _email_unico(nome_arb, emails_usados)
            usuario_arb = Usuario.objects.create_user(email=email_arb, nome=nome_arb, password=SENHA_PADRAO)
            UsuarioFederacao.objects.create(
                usuario=usuario_arb, federacao=federacao,
                papel=UsuarioFederacao.ARBITRO, ativo=True,
            )
            credenciais.append(('Árbitro', nome_arb, email_arb))
            self.stdout.write(f'+ Árbitro: {nome_arb} <{email_arb}>')

        # ── Locais ───────────────────────────────────────────────────────
        locais_criados = 0
        for _ in range(options['locais']):
            cidade = fake.city()
            local = Local.objects.create(
                federacao=federacao,
                nome=f'{random.choice(TIPOS_LOCAL)} {fake.last_name()}',
                endereco=fake.street_address(),
                cidade=cidade,
                capacidade=random.choice([500, 1000, 2000, 5000, 8000, 12000, 20000, 35000]),
            )
            locais_criados += 1
            self.stdout.write(f'+ Local: {local.nome} ({cidade})')

        self.stdout.write(self.style.SUCCESS(
            f'\nConcluído: 1 secretário, {options["arbitros"]} árbitros, {locais_criados} locais criados.'
        ))
        self.stdout.write(self.style.WARNING(f'Senha padrão de todos os usuários criados: {SENHA_PADRAO}'))

import random
import datetime

from django.core.management.base import BaseCommand, CommandError
from faker import Faker

from apps.core.models import Federacao
from apps.equipe.models import Atleta, Equipe
from apps.registro.models import RegistroFederativo

fake = Faker('pt_BR')

NOMES_CLUBE = [
    'Sport Club', 'Atlético', 'Esporte Clube', 'Associação Desportiva',
    'Grêmio', 'América', 'Santa Cruz', 'Botafogo', 'Flamengo', 'Cruzeiro',
    'Vasco', 'Bahia', 'Fortaleza', 'Ceará', 'Náutico', 'Avaí', 'Ponte Preta',
    'Guarani', 'Goiás', 'Vila Nova', 'Remo', 'Paysandu', 'ABC', 'Sampaio',
    'Treze', 'Sousa', 'Campinense', 'Serrano', 'Perilima', 'Auto Esporte',
]

SUFIXOS_CLUBE = ['FC', 'EC', 'SC', 'AD', 'AA', 'AF', 'CA']

POSICOES = [p[0] for p in Atleta.POSICAO]
PES      = [p[0] for p in Atleta.PE_CHOICES]
ESTADOS  = [
    'AC','AL','AM','BA','CE','GO','MA','MG','PA','PB',
    'PR','PE','RJ','RN','RS','SC','SP','SE','TO',
]
CORES = [
    'Vermelho', 'Azul', 'Verde', 'Amarelo', 'Preto', 'Branco',
    'Roxo', 'Laranja', 'Cinza', 'Vinho', 'Verde e Branco', 'Azul e Branco',
]


def _nome_clube(usados):
    for _ in range(200):
        nome = f'{random.choice(NOMES_CLUBE)} {random.choice(SUFIXOS_CLUBE)}'
        if nome not in usados:
            return nome
    return f'{fake.city()} FC'


def _sigla(nome):
    partes = nome.split()
    if len(partes) >= 2:
        return ''.join(p[0] for p in partes[:3]).upper()
    return nome[:3].upper()


class Command(BaseCommand):
    help = 'Cria clubes e atletas fictícios via Faker e registra todos na federação'

    def add_arguments(self, parser):
        parser.add_argument('--federacao', type=int, help='ID da federação (padrão: primeira ativa)')
        parser.add_argument('--clubes',    type=int, default=10,  help='Quantidade de clubes (padrão: 10)')
        parser.add_argument('--atletas',   type=int, default=16,  help='Atletas por clube (padrão: 16)')
        parser.add_argument('--limpar',    action='store_true',    help='Remove clubes/registros existentes antes de criar')

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

        self.stdout.write(f'Federação: {federacao.nome} (id={federacao.pk})')

        if options['limpar']:
            deletados, _ = Equipe.objects.filter(federacao=federacao).delete()
            self.stdout.write(self.style.WARNING(f'  {deletados} registros removidos.'))

        qtd_clubes  = options['clubes']
        qtd_atletas = options['atletas']

        nomes_usados = set(
            Equipe.objects.filter(federacao=federacao).values_list('nome_equipe', flat=True)
        )

        clubes_criados   = 0
        atletas_criados  = 0
        registros_criados = 0

        for _ in range(qtd_clubes):
            nome = _nome_clube(nomes_usados)
            nomes_usados.add(nome)

            equipe = Equipe.objects.create(
                federacao=federacao,
                nome_equipe=nome,
                sigla=_sigla(nome),
                cidade=fake.city(),
                estado=random.choice(ESTADOS),
                estadio=f'Estádio {fake.last_name()}',
                tecnico=fake.name_male(),
                cor_uniforme_principal=random.choice(CORES),
                cor_uniforme_alternativo=random.choice(CORES),
                fundacao=fake.date_between(
                    start_date=datetime.date(1950, 1, 1),
                    end_date=datetime.date(2010, 12, 31),
                ),
                data_filiacao=fake.date_between(
                    start_date=datetime.date(2010, 1, 1),
                    end_date=datetime.date.today(),
                ),
                situacao=Equipe.SITUACAO_FILIADO,
                telefone=fake.phone_number(),
            )
            clubes_criados += 1

            # Garante pelo menos 1 goleiro
            posicoes = [POSICOES[0]] + random.choices(POSICOES[1:], k=qtd_atletas - 1)
            random.shuffle(posicoes)

            atletas = Atleta.objects.bulk_create([
                Atleta(
                    nome=fake.name(),
                    equipe=equipe,
                    data_nascimento=fake.date_of_birth(minimum_age=16, maximum_age=38),
                    posicao=posicoes[i],
                    pe_dominante=random.choice(PES),
                    altura=round(random.uniform(1.60, 1.95), 2),
                    peso=round(random.uniform(60.0, 95.0), 2),
                    situacao='APTO',
                    naturalidade=fake.city(),
                )
                for i in range(qtd_atletas)
            ])
            atletas_criados += qtd_atletas

            # Registrar cada atleta na federação
            for atleta in atletas:
                RegistroFederativo.objects.create(
                    federacao=federacao,
                    atleta=atleta,
                    data_filiacao=fake.date_between(
                        start_date=datetime.date(2020, 1, 1),
                        end_date=datetime.date.today(),
                    ),
                    status=RegistroFederativo.STATUS_ATIVO,
                )
                registros_criados += 1

            self.stdout.write(f'  + {nome} ({qtd_atletas} atletas registrados)')

        self.stdout.write(self.style.SUCCESS(
            f'\nConcluído: {clubes_criados} clubes, {atletas_criados} atletas, '
            f'{registros_criados} registros federativos criados.'
        ))

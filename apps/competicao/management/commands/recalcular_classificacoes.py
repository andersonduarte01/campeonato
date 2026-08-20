from django.core.management.base import BaseCommand
from django.db import transaction

from apps.competicao.models import Classificacao, ClassificacaoGrupo, Competicao
from apps.competicao.signals import recalcular_classificacao, recalcular_classificacao_grupo


class Command(BaseCommand):
    help = (
        'Apaga e reconstrói Classificacao e ClassificacaoGrupo a partir dos jogos, '
        'respeitando o escopo de fase (liga / grupos / mata-mata).'
    )

    @transaction.atomic
    def handle(self, *args, **options):
        apagadas = Classificacao.objects.all().delete()[0]
        apagadas_grupo = ClassificacaoGrupo.objects.all().delete()[0]
        self.stdout.write(f'Removidas {apagadas} linhas de Classificacao e {apagadas_grupo} de ClassificacaoGrupo.')

        for comp in Competicao.objects.all():
            tem_liga = comp.rodada_set.filter(grupo__isnull=True, etapa__isnull=True).exists()
            if tem_liga:
                for equipe in comp.equipes.all():
                    recalcular_classificacao(equipe, comp)
            for grupo in comp.grupos.all():
                for equipe in grupo.equipes.all():
                    recalcular_classificacao_grupo(equipe, grupo)
            self.stdout.write(f'  {comp.nome}: ok')

        self.stdout.write(self.style.SUCCESS('Classificações reconstruídas.'))

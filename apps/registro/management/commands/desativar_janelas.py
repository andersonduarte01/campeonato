from django.core.management.base import BaseCommand

from apps.registro.models import JanelaTransferencia


class Command(BaseCommand):
    help = 'Desativa janelas de transferência cuja data_fim já passou.'

    def handle(self, *args, **options):
        antes = JanelaTransferencia.objects.filter(ativa=True).count()
        JanelaTransferencia.desativar_encerradas()
        depois = JanelaTransferencia.objects.filter(ativa=True).count()
        desativadas = antes - depois
        self.stdout.write(self.style.SUCCESS(
            f'{desativadas} janela(s) desativada(s). {depois} continuam ativas.'
        ))

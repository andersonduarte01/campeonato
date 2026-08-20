import secrets
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils.text import slugify
from ..core.models import Federacao, UsuarioFederacao, Usuario
from ..equipe.models import Atleta, Equipe
from ..criterios.models import CriterioClassificacao, FormatoCompeticao


class Local(models.Model):
    federacao = models.ForeignKey(
        Federacao, on_delete=models.PROTECT,
        related_name='locais', verbose_name='Federação',
    )
    nome = models.CharField(max_length=200, verbose_name='Nome do local')
    endereco = models.CharField(max_length=300, blank=True, null=True, verbose_name='Endereço')
    cidade = models.CharField(max_length=100, blank=True, null=True, verbose_name='Cidade')
    capacidade = models.PositiveIntegerField(null=True, blank=True, verbose_name='Capacidade')

    class Meta:
        ordering = ['nome']
        verbose_name = 'Local'
        verbose_name_plural = 'Locais'

    def __str__(self):
        return self.nome



class Competicao(models.Model):
    CATEGORIA_CHOICES = [
        ('adulto', 'Adulto'), ('master', 'Master'),
        ('sub20', 'Sub-20'), ('sub17', 'Sub-17'),
        ('sub15', 'Sub-15'), ('sub13', 'Sub-13'), ('sub11', 'Sub-11'),
    ]
    GENERO_CHOICES = [
        ('masculino', 'Masculino'), ('feminino', 'Feminino'), ('misto', 'Misto'),
    ]
    MODALIDADE_CHOICES = [
        ('campo', 'Futebol de Campo'), ('futsal', 'Futsal'),
        ('society', 'Society'), ('beach', 'Beach Soccer'),
    ]
    RASCUNHO = 'rascunho'
    CONFIGURADA = 'configurada'
    INSCRICOES = 'inscricoes'
    INSCRICOES_ENCERRADAS = 'inscricoes_encerradas'
    ANDAMENTO = 'andamento'
    FINALIZADO = 'finalizado'
    CANCELADO = 'cancelado'
    ARQUIVADO = 'arquivado'

    STATUS_CHOICES = [
        (RASCUNHO, 'Rascunho'),
        (CONFIGURADA, 'Configurada'),
        (INSCRICOES, 'Inscrições Abertas'),
        (INSCRICOES_ENCERRADAS, 'Inscrições Encerradas'),
        (ANDAMENTO, 'Em Andamento'),
        (FINALIZADO, 'Finalizado'),
        (CANCELADO, 'Cancelado'),
        (ARQUIVADO, 'Arquivado'),
    ]

    TRANSICOES = {
        RASCUNHO: [CONFIGURADA, CANCELADO],
        CONFIGURADA: [INSCRICOES, CANCELADO],
        INSCRICOES: [INSCRICOES_ENCERRADAS, CANCELADO],
        INSCRICOES_ENCERRADAS: [ANDAMENTO, INSCRICOES, CANCELADO],
        ANDAMENTO: [FINALIZADO, CANCELADO],
        FINALIZADO: [ARQUIVADO],
        CANCELADO: [],
        ARQUIVADO: [],
    }

    federacao = models.ForeignKey(
        Federacao, on_delete=models.PROTECT,
        related_name='competicoes', verbose_name='Federação',
    )
    nome = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, blank=True)
    descricao = models.TextField(blank=True, null=True)
    data_inicio = models.DateField(verbose_name='Início')
    data_fim = models.DateField(verbose_name='Final', blank=True, null=True)
    categoria = models.CharField(max_length=10, choices=CATEGORIA_CHOICES, default='adulto', verbose_name='Categoria')
    genero = models.CharField(max_length=15, choices=GENERO_CHOICES, default='masculino', verbose_name='Gênero')
    modalidade = models.CharField(max_length=10, choices=MODALIDADE_CHOICES, default='campo', verbose_name='Modalidade')
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default=RASCUNHO, verbose_name='Status')
    data_abertura_inscricao = models.DateField(null=True, blank=True, verbose_name='Abertura de inscrições')
    data_encerramento_inscricao = models.DateField(null=True, blank=True, verbose_name='Encerramento de inscrições')
    limite_atletas = models.PositiveIntegerField(null=True, blank=True, verbose_name='Limite de atletas por equipe')
    taxa_inscricao = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name='Taxa de inscrição (R$)')
    equipes = models.ManyToManyField(Equipe, through='InscricaoEquipe', related_name='competicoes_inscritas')
    formato = models.ForeignKey(
        FormatoCompeticao, on_delete=models.PROTECT,
        related_name='competicoes', blank=True, null=True,
        verbose_name='Formato',
    )
    criterio_classificacao = models.ForeignKey(
        CriterioClassificacao, on_delete=models.PROTECT, null=True, blank=True,
        related_name='competicoes', verbose_name='Critério de Classificação',
    )
    # Snapshot das regras, congelado ao encerrar as inscrições — edições
    # posteriores no formato/critério não afetam competições já lançadas.
    pontos_vitoria_snap = models.PositiveSmallIntegerField(null=True, blank=True, editable=False)
    pontos_empate_snap = models.PositiveSmallIntegerField(null=True, blank=True, editable=False)
    permite_empate_snap = models.BooleanField(null=True, blank=True, editable=False)
    penaltis_snap = models.BooleanField(null=True, blank=True, editable=False)
    prorrogacao_snap = models.BooleanField(null=True, blank=True, editable=False)
    turnos_snap = models.PositiveSmallIntegerField(null=True, blank=True, editable=False)
    criterio_snap = models.JSONField(null=True, blank=True, editable=False)
    # Configuração de grupos
    qtd_classificados_por_grupo = models.PositiveIntegerField(
        default=2, verbose_name='Classificados por grupo',
    )
    grupos_ida_e_volta = models.BooleanField(
        default=False, verbose_name='Grupos: Ida e Volta',
    )
    # Configuração disciplinar por competição
    limite_amarelos_suspensao = models.PositiveIntegerField(
        default=3, verbose_name='Amarelos p/ suspensão',
        help_text='Quantidade de cartões amarelos que gera 1 jogo de suspensão',
    )
    jogos_suspensao_amarelos = models.PositiveIntegerField(
        default=1, verbose_name='Jogos suspenso (amarelos)',
    )
    jogos_suspensao_vermelho = models.PositiveIntegerField(
        default=1, verbose_name='Jogos suspenso (vermelho)',
    )

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nome)
            self.slug = f"{base}-{self.federacao_id}" if base else str(self.pk or '')
        super().save(*args, **kwargs)

    @property
    def status_badge_class(self):
        return {
            'rascunho': 'secondary', 'configurada': 'secondary',
            'inscricoes': 'info', 'inscricoes_encerradas': 'info',
            'andamento': 'warning', 'finalizado': 'success',
            'cancelado': 'danger', 'arquivado': 'secondary',
        }.get(self.status, 'secondary')

    # ------------------------------------------------------------------ #
    # Máquina de estados
    # ------------------------------------------------------------------ #

    def transicoes_disponiveis(self):
        return self.TRANSICOES.get(self.status, [])

    def transicionar(self, novo_status, *, force=False):
        from .dominio.excecoes import TransicaoInvalida

        if novo_status not in dict(self.STATUS_CHOICES):
            raise TransicaoInvalida(f"Status desconhecido: '{novo_status}'.")
        if novo_status not in self.transicoes_disponiveis():
            atual = self.get_status_display()
            novo = dict(self.STATUS_CHOICES)[novo_status]
            raise TransicaoInvalida(
                f"Transição de '{atual}' para '{novo}' não é permitida."
            )
        if not force:
            self._validar_precondicoes(novo_status)
        campos = ['status']
        if novo_status == self.INSCRICOES_ENCERRADAS:
            self._capturar_snapshot()
            campos += [
                'pontos_vitoria_snap', 'pontos_empate_snap',
                'permite_empate_snap', 'penaltis_snap', 'prorrogacao_snap',
                'turnos_snap', 'criterio_snap',
            ]
        self.status = novo_status
        self.save(update_fields=campos)

    def _capturar_snapshot(self):
        fmt = self.formato
        if fmt:
            self.pontos_vitoria_snap = fmt.pontos_por_vitoria
            self.pontos_empate_snap = fmt.pontos_por_empate
            self.permite_empate_snap = fmt.permite_empate
            self.penaltis_snap = fmt.penaltis
            self.prorrogacao_snap = fmt.prorrogacao
            self.turnos_snap = 2 if fmt.ida_e_volta else 1
        crit = self.criterio_classificacao
        if crit:
            self.criterio_snap = {
                'confronto_direto': crit.confronto_direto,
                'vitorias': crit.vitorias,
                'saldo_gols': crit.saldo_gols,
                'gols_pro': crit.gols_pro,
                'gol_fora': crit.gol_fora,
                'menor_vermelho': crit.menor_vermelho,
                'menor_amarelo': crit.menor_amarelo,
            }

    @property
    def pontos_vitoria(self):
        if self.pontos_vitoria_snap is not None:
            return self.pontos_vitoria_snap
        return self.formato.pontos_por_vitoria if self.formato_id else 3

    @property
    def pontos_empate(self):
        if self.pontos_empate_snap is not None:
            return self.pontos_empate_snap
        return self.formato.pontos_por_empate if self.formato_id else 1

    @property
    def criterio_efetivo(self):
        if self.criterio_snap:
            from types import SimpleNamespace
            return SimpleNamespace(**self.criterio_snap)
        return self.criterio_classificacao

    @property
    def permite_empate(self):
        if self.permite_empate_snap is not None:
            return self.permite_empate_snap
        return self.formato.permite_empate if self.formato_id else True

    @property
    def penaltis_disponiveis(self):
        if self.penaltis_snap is not None:
            return self.penaltis_snap
        return self.formato.penaltis if self.formato_id else False

    @property
    def prorrogacao_disponivel(self):
        if self.prorrogacao_snap is not None:
            return self.prorrogacao_snap
        return self.formato.prorrogacao if self.formato_id else False

    def _validar_precondicoes(self, novo_status):
        from .dominio.excecoes import TransicaoInvalida

        if novo_status == self.CONFIGURADA:
            if self.formato_id is None:
                raise TransicaoInvalida('Defina um formato antes de configurar a competição.')
            if self.criterio_classificacao_id is None:
                raise TransicaoInvalida('Defina um critério de classificação antes de configurar a competição.')

        elif novo_status == self.INSCRICOES:
            if (
                self.data_abertura_inscricao and self.data_encerramento_inscricao
                and self.data_abertura_inscricao > self.data_encerramento_inscricao
            ):
                raise TransicaoInvalida('Datas de inscrição incoerentes: abertura após o encerramento.')

        elif novo_status == self.INSCRICOES_ENCERRADAS:
            qtd = self.equipes.count()
            if qtd < 2:
                raise TransicaoInvalida('São necessárias pelo menos 2 equipes inscritas.')
            limite = self.formato.qtd_times if self.formato_id else None
            if limite and qtd > limite:
                raise TransicaoInvalida(f'Há {qtd} equipes inscritas, acima do limite de {limite} do formato.')

        elif novo_status == self.ANDAMENTO:
            if not self._estrutura_primeira_fase_gerada():
                raise TransicaoInvalida('Gere a tabela/estrutura da primeira fase antes de iniciar a competição.')

        elif novo_status == self.FINALIZADO:
            pendentes = Jogo.objects.filter(
                rodada__competicao=self, finalizado=False, anulado=False,
            ).count()
            if pendentes:
                raise TransicaoInvalida(
                    f'Há {pendentes} jogo(s) pendente(s). Finalize-os ou confirme explicitamente.'
                )

    def _estrutura_primeira_fase_gerada(self):
        fmt = self.formato
        if fmt is None:
            return False
        if fmt.pontos_corridos:
            return Rodada.objects.filter(
                competicao=self, grupo__isnull=True, etapa__isnull=True,
            ).exists()
        if fmt.fase_grupos:
            return Rodada.objects.filter(grupo__competicao=self).exists()
        if fmt.mata_mata:
            return ConfrontoMatamate.objects.filter(etapa__competicao=self).exists()
        return False

    @transaction.atomic
    def delete(self, *args, **kwargs):
        # Rodada.fase é PROTECT: apaga rodadas (e jogos, em cascata) antes
        # para liberar a cascata Competicao -> Fase.
        Rodada.objects.filter(competicao=self).delete()
        return super().delete(*args, **kwargs)


class Fase(models.Model):
    LIGA = 'liga'
    GRUPOS = 'grupos'
    MATA_MATA = 'mata_mata'
    TIPO_CHOICES = [
        (LIGA, 'Pontos Corridos'),
        (GRUPOS, 'Fase de Grupos'),
        (MATA_MATA, 'Mata-Mata'),
    ]

    PENDENTE = 'pendente'
    EM_ANDAMENTO = 'em_andamento'
    CONCLUIDA = 'concluida'
    STATUS_CHOICES = [
        (PENDENTE, 'Pendente'),
        (EM_ANDAMENTO, 'Em andamento'),
        (CONCLUIDA, 'Concluída'),
    ]

    INSCRICAO = 'inscricao'
    FASE_ANTERIOR = 'fase_anterior'
    FONTE_CHOICES = [
        (INSCRICAO, 'Equipes inscritas'),
        (FASE_ANTERIOR, 'Classificados da fase anterior'),
    ]

    competicao = models.ForeignKey(Competicao, on_delete=models.CASCADE, related_name='fases')
    ordem = models.PositiveIntegerField(default=1)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=PENDENTE)
    config = models.JSONField(default=dict, blank=True)
    fonte_tipo = models.CharField(max_length=15, choices=FONTE_CHOICES, default=INSCRICAO)
    fonte_fase = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fases_seguintes',
    )
    qtd_classificados = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['ordem']
        unique_together = [('competicao', 'tipo')]
        verbose_name = 'Fase'
        verbose_name_plural = 'Fases'

    def __str__(self):
        return f"{self.competicao} — {self.get_tipo_display()}"

    @classmethod
    def obter_ou_criar(cls, competicao, tipo):
        fase = cls.objects.filter(competicao=competicao, tipo=tipo).first()
        if fase:
            return fase
        anterior = cls.objects.filter(competicao=competicao).order_by('-ordem').first()
        return cls.objects.create(
            competicao=competicao, tipo=tipo,
            ordem=(anterior.ordem + 1) if anterior else 1,
            fonte_fase=anterior,
            fonte_tipo=cls.FASE_ANTERIOR if anterior else cls.INSCRICAO,
        )


class ZonaClassificacao(models.Model):
    """Faixas de posições na classificação com significado esportivo.

    Serve para ligas com promoção/rebaixamento e para copas com vagas para
    outras competições. Exemplos:
      - Campeão: 1..1
      - Libertadores: 2..6 (vaga_externa, competicao_destino=None ou externa)
      - Rebaixamento: 17..20 (rebaixamento, competicao_destino=Série B)
      - Acesso: 1..4 na Série B (acesso, competicao_destino=Série A)
    """
    CAMPEAO = 'campeao'
    CLASSIFICACAO = 'classificacao'
    ACESSO = 'acesso'
    REBAIXAMENTO = 'rebaixamento'
    VAGA_EXTERNA = 'vaga_externa'
    TIPO_CHOICES = [
        (CAMPEAO, 'Campeão'),
        (CLASSIFICACAO, 'Classificação para próxima fase'),
        (ACESSO, 'Acesso (promoção à série superior)'),
        (REBAIXAMENTO, 'Rebaixamento'),
        (VAGA_EXTERNA, 'Vaga para outra competição'),
    ]

    fase = models.ForeignKey(Fase, on_delete=models.CASCADE, related_name='zonas')
    nome = models.CharField(max_length=60, verbose_name='Nome')
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES)
    faixa_inicio = models.PositiveIntegerField(verbose_name='Posição inicial')
    faixa_fim = models.PositiveIntegerField(verbose_name='Posição final')
    cor = models.CharField(
        max_length=7, default='#3b82f6',
        help_text='Cor hex para a borda na classificação (ex.: #3b82f6).',
    )
    competicao_destino = models.ForeignKey(
        'Competicao', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='zonas_de_origem',
        help_text='Competição para onde as equipes desta faixa vão (acesso, rebaixamento ou vaga externa).',
    )

    class Meta:
        ordering = ['fase', 'faixa_inicio']
        verbose_name = 'Zona de Classificação'
        verbose_name_plural = 'Zonas de Classificação'

    def __str__(self):
        return f"{self.nome} ({self.faixa_inicio}º–{self.faixa_fim}º)"

    def contem(self, posicao):
        return self.faixa_inicio <= posicao <= self.faixa_fim


class ParticipacaoFase(models.Model):
    """Congela a lista/ordem de equipes participantes de uma fase.

    Após a geração dos jogos, a lista de participantes é imutável — mesmo
    que a equipe desista, a linha permanece com `ativo=False` para preservar
    o histórico e o mapeamento seed → equipe.
    """
    fase = models.ForeignKey(Fase, on_delete=models.CASCADE, related_name='participacoes')
    equipe = models.ForeignKey(Equipe, on_delete=models.PROTECT, related_name='participacoes_fase')
    seed = models.PositiveIntegerField()
    ativo = models.BooleanField(default=True)
    desistiu_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['fase', 'seed']
        unique_together = [('fase', 'equipe'), ('fase', 'seed')]
        verbose_name = 'Participação em Fase'
        verbose_name_plural = 'Participações em Fases'

    def __str__(self):
        marca = '' if self.ativo else ' (desistiu)'
        return f"{self.equipe} — seed {self.seed}{marca}"


class EtapaKnockout(models.Model):
    OITAVAS   = 'oitavas'
    QUARTAS   = 'quartas'
    SEMIFINAL = 'semifinal'
    TERCEIRO  = 'terceiro'
    FINAL     = 'final'

    TIPO_CHOICES = [
        (OITAVAS,   'Oitavas de Final'),
        (QUARTAS,   'Quartas de Final'),
        (SEMIFINAL, 'Semifinal'),
        (TERCEIRO,  'Disputa de 3º Lugar'),
        (FINAL,     'Final'),
    ]

    ORDEM_POR_TIPO = {OITAVAS: 1, QUARTAS: 2, SEMIFINAL: 3, TERCEIRO: 4, FINAL: 5}

    ORIGEM_GRUPOS = 'grupos'
    ORIGEM_ETAPA_ANTERIOR = 'etapa_anterior'
    ORIGEM_LIGA = 'liga'
    ORIGEM_CHOICES = [
        (ORIGEM_GRUPOS, 'Classificados dos grupos'),
        (ORIGEM_ETAPA_ANTERIOR, 'Vencedores da etapa anterior'),
        (ORIGEM_LIGA, 'Classificados da liga'),
    ]

    competicao  = models.ForeignKey(Competicao, on_delete=models.CASCADE, related_name='etapas')
    fase        = models.ForeignKey(
        Fase, on_delete=models.CASCADE, null=True, blank=True, related_name='etapas',
    )
    tipo        = models.CharField(max_length=10, choices=TIPO_CHOICES)
    ida_e_volta = models.BooleanField(default=False, verbose_name='Ida e Volta')
    concluida   = models.BooleanField(default=False)
    ordem       = models.PositiveIntegerField(default=0, editable=False)
    origem      = models.CharField(
        max_length=15, choices=ORIGEM_CHOICES, blank=True, default='',
        verbose_name='Fonte de vagas',
    )

    class Meta:
        unique_together = [('competicao', 'tipo')]
        ordering = ['ordem']
        verbose_name = 'Etapa Knockout'
        verbose_name_plural = 'Etapas Knockout'

    def __str__(self):
        return self.get_tipo_display()

    @property
    def nome(self):
        return self.get_tipo_display()

    def save(self, *args, **kwargs):
        self.ordem = self.ORDEM_POR_TIPO.get(self.tipo, 99)
        if self.fase_id is None:
            self.fase = Fase.obter_ou_criar(self.competicao, Fase.MATA_MATA)
        if not self.origem:
            self.origem = self._derivar_origem()
        super().save(*args, **kwargs)

    def _derivar_origem(self):
        anterior = EtapaKnockout.objects.filter(
            competicao=self.competicao, ordem__lt=self.ordem,
        ).exclude(pk=self.pk).exists()
        if anterior:
            return self.ORIGEM_ETAPA_ANTERIOR
        if self.competicao.grupos.exists():
            return self.ORIGEM_GRUPOS
        return self.ORIGEM_LIGA


class Grupo(models.Model):
    competicao = models.ForeignKey(Competicao, on_delete=models.CASCADE, related_name='grupos')
    fase = models.ForeignKey(
        Fase, on_delete=models.CASCADE, null=True, blank=True, related_name='grupos',
    )
    nome = models.CharField(max_length=20, verbose_name='Nome do grupo')
    equipes = models.ManyToManyField(Equipe, related_name='grupos_competicao', blank=True)

    class Meta:
        ordering = ['nome']
        unique_together = [('competicao', 'nome')]

    def __str__(self):
        return f"Grupo {self.nome}"

    def save(self, *args, **kwargs):
        if self.fase_id is None:
            self.fase = Fase.obter_ou_criar(self.competicao, Fase.GRUPOS)
        super().save(*args, **kwargs)


class ClassificacaoGrupo(models.Model):
    grupo = models.ForeignKey(Grupo, on_delete=models.CASCADE, related_name='classificacao')
    equipe = models.ForeignKey(Equipe, on_delete=models.CASCADE)
    jogos = models.IntegerField(default=0)
    vitorias = models.IntegerField(default=0)
    empates = models.IntegerField(default=0)
    derrotas = models.IntegerField(default=0)
    gols_pro = models.IntegerField(default=0)
    gols_contra = models.IntegerField(default=0)
    saldo_gols = models.IntegerField(default=0)
    pontos = models.IntegerField(default=0)

    class Meta:
        unique_together = [('grupo', 'equipe')]
        ordering = ['-pontos', '-saldo_gols', '-vitorias', '-gols_pro']

    def __str__(self):
        return f"{self.equipe} — {self.grupo} ({self.pontos} pts)"


class Rodada(models.Model):
    competicao = models.ForeignKey(Competicao, on_delete=models.CASCADE)
    fase = models.ForeignKey(Fase, on_delete=models.PROTECT, related_name='rodadas')
    etapa = models.ForeignKey(
        EtapaKnockout, on_delete=models.PROTECT, null=True, blank=True, related_name='rodadas',
    )
    grupo = models.ForeignKey(
        Grupo, on_delete=models.PROTECT, null=True, blank=True, related_name='rodadas',
    )
    numero = models.PositiveIntegerField()

    def save(self, *args, **kwargs):
        if self.fase_id is None:
            self.fase = self._derivar_fase()
        super().save(*args, **kwargs)

    def _derivar_fase(self):
        if self.etapa_id:
            return self.etapa.fase or Fase.obter_ou_criar(self.competicao, Fase.MATA_MATA)
        if self.grupo_id:
            return self.grupo.fase or Fase.obter_ou_criar(self.competicao, Fase.GRUPOS)
        return Fase.obter_ou_criar(self.competicao, Fase.LIGA)

    def __str__(self):
        if self.grupo:
            return f"{self.competicao} — {self.grupo} — Rodada {self.numero}"
        if self.etapa:
            return f"{self.competicao} — {self.etapa.get_tipo_display()} — Rodada {self.numero}"
        return f"{self.competicao}: {self.numero}ª Rodada"


class Jogo(models.Model):
    STATUS_AGENDADO     = 'agendado'
    STATUS_EM_ANDAMENTO = 'em_andamento'
    STATUS_PROVISORIO   = 'provisorio'
    STATUS_FINALIZADO   = 'finalizado'
    STATUS_HOMOLOGADO   = 'homologado'
    STATUS_ANULADO      = 'anulado'
    STATUS_CHOICES = [
        (STATUS_AGENDADO,     'Agendado'),
        (STATUS_EM_ANDAMENTO, 'Em andamento'),
        (STATUS_PROVISORIO,   'Provisório'),
        (STATUS_FINALIZADO,   'Finalizado'),
        (STATUS_HOMOLOGADO,   'Homologado'),
        (STATUS_ANULADO,      'Anulado'),
    ]

    RESULTADO_NORMAL   = 'normal'
    RESULTADO_WO_CASA  = 'wo_casa'
    RESULTADO_WO_FORA  = 'wo_fora'
    RESULTADO_CHOICES = [
        (RESULTADO_NORMAL, 'Normal'),
        (RESULTADO_WO_CASA, 'W.O. da equipe mandante (visitante vence)'),
        (RESULTADO_WO_FORA, 'W.O. da equipe visitante (mandante vence)'),
    ]

    rodada = models.ForeignKey(Rodada, on_delete=models.CASCADE, null=True, blank=True)
    equipe_casa = models.ForeignKey(Equipe, on_delete=models.CASCADE, related_name='jogos_casa')
    equipe_fora = models.ForeignKey(Equipe, on_delete=models.CASCADE, related_name='jogos_fora')
    data_hora = models.DateTimeField(null=True, blank=True)
    gols_casa = models.IntegerField(default=0)
    gols_fora = models.IntegerField(default=0)
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default=STATUS_AGENDADO,
    )
    resultado_tipo = models.CharField(
        max_length=10, choices=RESULTADO_CHOICES, default=RESULTADO_NORMAL,
        verbose_name='Tipo de resultado',
    )
    finalizado = models.BooleanField(default=False)
    em_andamento = models.BooleanField(default=False, verbose_name='Em andamento')
    anulado = models.BooleanField(default=False)
    wo = models.BooleanField(default=False, verbose_name='W.O.')
    local = models.ForeignKey(
        'Local', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='jogos', verbose_name='Local',
    )
    arbitro = models.ForeignKey(
        UsuarioFederacao, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='jogos', verbose_name='Árbitro',
    )
    publico = models.PositiveIntegerField(null=True, blank=True, verbose_name='Público presente')
    observacoes = models.TextField(null=True, blank=True, verbose_name='Observações')

    class Meta:
        pass

    def __str__(self):
        return f"{self.equipe_casa} x {self.equipe_fora} ({self.get_status_display()})"

    @property
    def homologado(self):
        return self.status == self.STATUS_HOMOLOGADO

    @property
    def por_wo(self):
        return self.resultado_tipo != self.RESULTADO_NORMAL

    def exige_desempate(self):
        """Retorna True se o placar está empatado, o jogo NÃO é W.O. e a
        competição não permite empates. Nesse caso a finalização depende de
        pênaltis registrados no confronto (mata-mata) ou é bloqueada."""
        if self.por_wo:
            return False
        if self.gols_casa != self.gols_fora:
            return False
        comp = self.rodada.competicao if self.rodada_id else None
        if comp is None:
            return False
        return not comp.permite_empate

    def save(self, *args, **kwargs):
        self._reconciliar_status_e_booleans()
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            fields = set(update_fields)
            for extra in ('status', 'resultado_tipo', 'finalizado', 'em_andamento', 'anulado', 'wo'):
                if extra not in fields and any(
                    b in fields for b in ('status', 'resultado_tipo', 'finalizado', 'em_andamento', 'anulado', 'wo')
                ):
                    fields.add(extra)
            kwargs['update_fields'] = list(fields)
        super().save(*args, **kwargs)

    _MAPA_BOOLEANS_PARA_STATUS = {
        (False, False, True):  STATUS_ANULADO,
        (False, True,  False): STATUS_EM_ANDAMENTO,
        (True,  False, False): STATUS_FINALIZADO,
        (False, False, False): STATUS_AGENDADO,
    }

    def _reconciliar_status_e_booleans(self):
        """Mantém consistência entre `status` e os booleans legados.

        Regra: quando o caller alterou os booleans (padrão antigo) e não o
        `status`, deriva `status` a partir dos booleans; caso contrário,
        deriva os booleans a partir de `status`.
        """
        booleans_atuais = (bool(self.finalizado), bool(self.em_andamento), bool(self.anulado))
        antigo = None
        if self.pk:
            try:
                antigo = Jogo.objects.only(
                    'status', 'finalizado', 'em_andamento', 'anulado',
                    'resultado_tipo', 'wo',
                ).get(pk=self.pk)
            except Jogo.DoesNotExist:
                antigo = None
        if antigo is None:
            booleans_mudaram = booleans_atuais != (False, False, False)
            status_mudou = self.status != self.STATUS_AGENDADO
        else:
            booleans_mudaram = booleans_atuais != (
                bool(antigo.finalizado), bool(antigo.em_andamento), bool(antigo.anulado),
            )
            status_mudou = self.status != antigo.status
        if booleans_mudaram and not status_mudou:
            derivado = self._MAPA_BOOLEANS_PARA_STATUS.get(booleans_atuais)
            if derivado is not None:
                self.status = derivado
        if antigo is None:
            wo_mudou = bool(self.wo)
            resultado_mudou = self.resultado_tipo != self.RESULTADO_NORMAL
        else:
            wo_mudou = bool(self.wo) != bool(antigo.wo)
            resultado_mudou = self.resultado_tipo != antigo.resultado_tipo
        if wo_mudou and not resultado_mudou:
            if self.wo and self.resultado_tipo == self.RESULTADO_NORMAL:
                self.resultado_tipo = (
                    self.RESULTADO_WO_FORA if self.gols_casa >= self.gols_fora
                    else self.RESULTADO_WO_CASA
                )
            elif not self.wo:
                self.resultado_tipo = self.RESULTADO_NORMAL
        self._derivar_booleans_de_status()

    def _derivar_booleans_de_status(self):
        self.finalizado = self.status in (self.STATUS_PROVISORIO, self.STATUS_FINALIZADO, self.STATUS_HOMOLOGADO)
        self.em_andamento = self.status == self.STATUS_EM_ANDAMENTO
        self.anulado = self.status == self.STATUS_ANULADO
        self.wo = self.resultado_tipo != self.RESULTADO_NORMAL


class ConfrontoMatamate(models.Model):
    NORMAL = 'normal'
    TERCEIRO_LUGAR = 'terceiro'
    TIPO_CHOICES = [(NORMAL, 'Normal'), (TERCEIRO_LUGAR, '3º Lugar')]

    etapa = models.ForeignKey(EtapaKnockout, on_delete=models.CASCADE, related_name='confrontos')
    tipo_confronto = models.CharField(max_length=10, choices=TIPO_CHOICES, default=NORMAL, verbose_name='Tipo')
    equipe_mandante = models.ForeignKey(
        Equipe, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='confrontos_mandante',
    )
    equipe_visitante = models.ForeignKey(
        Equipe, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='confrontos_visitante',
    )
    jogo_ida = models.OneToOneField(
        Jogo, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='confronto_ida',
    )
    jogo_volta = models.OneToOneField(
        Jogo, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='confronto_volta',
    )
    penaltis_mandante = models.PositiveIntegerField(null=True, blank=True)
    penaltis_visitante = models.PositiveIntegerField(null=True, blank=True)
    vencedor = models.ForeignKey(
        Equipe, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='confrontos_vencidos',
    )
    ordem = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['ordem']

    def __str__(self):
        m = self.equipe_mandante or '?'
        v = self.equipe_visitante or '?'
        return f"{m} x {v} ({self.etapa.get_tipo_display()})"

    @property
    def gols_mandante_total(self):
        total = 0
        if self.jogo_ida and self.jogo_ida.finalizado:
            total += self.jogo_ida.gols_casa
        if self.jogo_volta and self.jogo_volta.finalizado:
            total += self.jogo_volta.gols_fora
        return total

    @property
    def gols_visitante_total(self):
        total = 0
        if self.jogo_ida and self.jogo_ida.finalizado:
            total += self.jogo_ida.gols_fora
        if self.jogo_volta and self.jogo_volta.finalizado:
            total += self.jogo_volta.gols_casa
        return total

    @property
    def totalmente_jogado(self):
        if not self.jogo_ida or not self.jogo_ida.finalizado:
            return False
        if self.etapa.ida_e_volta:
            return self.jogo_volta and self.jogo_volta.finalizado
        return True

    @property
    def gols_fora_mandante(self):
        # No jogo de volta, o mandante do confronto atua como visitante.
        if self.jogo_volta and self.jogo_volta.finalizado:
            return self.jogo_volta.gols_fora
        return 0

    @property
    def gols_fora_visitante(self):
        # No jogo de ida, o visitante do confronto atua como visitante.
        if self.jogo_ida and self.jogo_ida.finalizado:
            return self.jogo_ida.gols_fora
        return 0

    def calcular_vencedor(self):
        if not self.totalmente_jogado:
            return None
        gm = self.gols_mandante_total
        gv = self.gols_visitante_total
        if gm > gv:
            return self.equipe_mandante
        if gv > gm:
            return self.equipe_visitante
        if self.etapa.ida_e_volta:
            criterio = self.etapa.competicao.criterio_efetivo
            if criterio is not None and getattr(criterio, 'gol_fora', False):
                fm = self.gols_fora_mandante
                fv = self.gols_fora_visitante
                if fm > fv:
                    return self.equipe_mandante
                if fv > fm:
                    return self.equipe_visitante
        pm = self.penaltis_mandante
        pv = self.penaltis_visitante
        if pm is not None and pv is not None:
            if pm > pv:
                return self.equipe_mandante
            if pv > pm:
                return self.equipe_visitante
        return None

    def atualizar_vencedor(self):
        novo = self.calcular_vencedor()
        if novo != self.vencedor:
            ConfrontoMatamate.objects.filter(pk=self.pk).update(vencedor=novo)
            self.vencedor = novo
            self._atualizar_conclusao_etapa()

    def _atualizar_conclusao_etapa(self):
        etapa = self.etapa
        normais = etapa.confrontos.filter(tipo_confronto=self.NORMAL)
        concluida = normais.exists() and not normais.filter(vencedor__isnull=True).exists()
        if etapa.concluida != concluida:
            EtapaKnockout.objects.filter(pk=etapa.pk).update(concluida=concluida)
            etapa.concluida = concluida
            if concluida:
                self._tentar_avanco_automatico(etapa)

    @staticmethod
    def _tentar_avanco_automatico(etapa):
        from .dominio.avancos import AvancoService
        from .dominio.excecoes import RegraVioladaError

        if not etapa.fase or not etapa.fase.config.get('avanco_automatico'):
            return
        proxima = (
            EtapaKnockout.objects.filter(
                competicao=etapa.competicao, ordem__gt=etapa.ordem,
            )
            .exclude(tipo=EtapaKnockout.TERCEIRO)
            .order_by('ordem')
            .first()
        )
        if proxima is None:
            return
        try:
            AvancoService().avancar(etapa, proxima)
        except RegraVioladaError:
            pass


class Classificacao(models.Model):
    equipe = models.ForeignKey(Equipe, on_delete=models.CASCADE, related_name='classificacoes')
    competicao = models.ForeignKey(Competicao, on_delete=models.CASCADE, related_name='classificacoes')
    fase = models.ForeignKey(
        Fase, on_delete=models.CASCADE, null=True, blank=True, related_name='classificacoes',
    )
    jogos = models.IntegerField(default=0)
    vitorias = models.IntegerField(default=0)
    empates = models.IntegerField(default=0)
    derrotas = models.IntegerField(default=0)
    gols_pro = models.IntegerField(default=0)
    gols_contra = models.IntegerField(default=0)
    saldo_gols = models.IntegerField(default=0)
    pontos = models.IntegerField(default=0)
    tem_provisorio = models.BooleanField(default=False)

    class Meta:
        ordering = ['-pontos', '-saldo_gols', '-vitorias']

    def __str__(self):
        return f"{self.equipe} — {self.competicao} ({self.pontos} pts)"


class Cartao(models.Model):
    AMARELO = 'Amarelo'
    VERMELHO = 'Vermelho'
    TIPO_CHOICES = [(AMARELO, 'Cartão Amarelo'), (VERMELHO, 'Cartão Vermelho')]

    jogo = models.ForeignKey(Jogo, on_delete=models.CASCADE, related_name='cartoes')
    jogador = models.ForeignKey(Atleta, on_delete=models.CASCADE, related_name='cartoes')
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    minuto = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        ordering = ['minuto']

    def __str__(self):
        return f"{self.jogador.nome} — {self.tipo} ({self.minuto}')"

    def clean(self):
        super().clean()
        if self.jogo_id and self.jogo.por_wo:
            raise ValidationError('Não é possível registrar cartões em jogos declarados W.O.')


class InscricaoEquipe(models.Model):
    competicao    = models.ForeignKey(Competicao, on_delete=models.CASCADE, related_name='inscricoes_equipes')
    equipe        = models.ForeignKey(Equipe, on_delete=models.CASCADE, related_name='inscricoes_competicao')
    data_inscricao = models.DateField(auto_now_add=True)
    taxa_paga     = models.BooleanField(default=False, verbose_name='Taxa paga')
    data_pagamento = models.DateField(null=True, blank=True, verbose_name='Data do pagamento')

    class Meta:
        unique_together = [('competicao', 'equipe')]
        ordering = ['equipe__nome_equipe']
        verbose_name = 'Inscrição de Equipe'
        verbose_name_plural = 'Inscrições de Equipes'

    def __str__(self):
        return f'{self.equipe.nome_equipe} — {self.competicao.nome}'


class InscricaoAtleta(models.Model):
    competicao    = models.ForeignKey(Competicao, on_delete=models.CASCADE, related_name='inscricoes')
    atleta        = models.ForeignKey(Atleta, on_delete=models.CASCADE, related_name='inscricoes')
    numero_camisa = models.PositiveIntegerField(verbose_name='Número', null=True, blank=True)

    class Meta:
        unique_together = [('competicao', 'atleta')]
        ordering = ['numero_camisa', 'atleta__nome']
        verbose_name = 'Inscrição de Atleta'
        verbose_name_plural = 'Inscrições de Atletas'

    def __str__(self):
        num = f"#{self.numero_camisa} " if self.numero_camisa else ''
        return f"{num}{self.atleta.nome} — {self.competicao.nome}"


class Suspensao(models.Model):
    AMARELOS = 'amarelos'
    VERMELHO = 'vermelho'
    MOTIVO_CHOICES = [
        (AMARELOS, 'Acúmulo de Cartões Amarelos'),
        (VERMELHO, 'Cartão Vermelho'),
    ]
    atleta = models.ForeignKey(Atleta, on_delete=models.CASCADE, related_name='suspensoes')
    competicao = models.ForeignKey(Competicao, on_delete=models.CASCADE, related_name='suspensoes')
    motivo = models.CharField(max_length=20, choices=MOTIVO_CHOICES, default=AMARELOS)
    rodadas_pendentes = models.PositiveIntegerField(default=1, verbose_name='Rodadas pendentes')
    cumprida = models.BooleanField(default=False)
    automatica = models.BooleanField(default=True, verbose_name='Gerada automaticamente')
    jogos_cumpridos = models.ManyToManyField(
        'Jogo', related_name='suspensoes_cumpridas', blank=True,
    )

    class Meta:
        ordering = ['-pk']

    def __str__(self):
        status = 'cumprida' if self.cumprida else f'{self.rodadas_pendentes} rodada(s) pendente(s)'
        return f"{self.atleta.nome} — {self.get_motivo_display()} ({status})"


class Gol(models.Model):
    NORMAL = 'normal'
    PENALTI = 'penalti'
    CONTRA = 'contra'
    TIPO_CHOICES = [(NORMAL, 'Normal'), (PENALTI, 'Pênalti'), (CONTRA, 'Gol Contra')]

    jogo = models.ForeignKey(Jogo, on_delete=models.CASCADE, related_name='gols')
    atleta = models.ForeignKey(
        Atleta, on_delete=models.SET_NULL, null=True, blank=True, related_name='gols',
    )
    assistencia = models.ForeignKey(
        Atleta, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assistencias', verbose_name='Assistência',
    )
    equipe = models.ForeignKey(Equipe, on_delete=models.CASCADE, related_name='gols')
    minuto = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default=NORMAL)

    class Meta:
        ordering = ['minuto']

    def __str__(self):
        nome = self.atleta.nome if self.atleta else '?'
        return f"{nome} ({self.minuto}') [{self.get_tipo_display()}]"

    def clean(self):
        super().clean()
        if self.jogo_id and self.jogo.por_wo:
            raise ValidationError('Não é possível registrar gols em jogos declarados W.O.')

    def save(self, *args, **kwargs):
        if self.atleta_id and not self.equipe_id:
            jogo = self.jogo
            atleta_equipe = self.atleta.equipe
            if self.tipo == self.CONTRA:
                self.equipe = jogo.equipe_fora if atleta_equipe == jogo.equipe_casa else jogo.equipe_casa
            else:
                self.equipe = atleta_equipe
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Súmula Digital
# ---------------------------------------------------------------------------

class Sumula(models.Model):
    STATUS_RASCUNHO  = 'rascunho'
    STATUS_ABERTA    = 'aberta'
    STATUS_ENCERRADA = 'encerrada'
    STATUS_HOMOLOGADA = 'homologada'
    STATUS_ANULADA   = 'anulada'
    STATUS_CHOICES = [
        (STATUS_RASCUNHO,  'Rascunho'),
        (STATUS_ABERTA,    'Aberta'),
        (STATUS_ENCERRADA, 'Encerrada'),
        (STATUS_HOMOLOGADA, 'Homologada'),
        (STATUS_ANULADA,   'Anulada'),
    ]

    jogo = models.OneToOneField(Jogo, on_delete=models.CASCADE, related_name='sumula')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_RASCUNHO)

    arbitro_principal = models.ForeignKey(
        UsuarioFederacao, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sumulas_principal', verbose_name='Árbitro Principal',
    )
    arbitro_assistente_1 = models.ForeignKey(
        UsuarioFederacao, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sumulas_assistente1', verbose_name='1º Assistente',
    )
    arbitro_assistente_2 = models.ForeignKey(
        UsuarioFederacao, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sumulas_assistente2', verbose_name='2º Assistente',
    )
    quarto_arbitro = models.ForeignKey(
        UsuarioFederacao, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sumulas_quarto', verbose_name='4º Árbitro',
    )

    observacoes_arbitro = models.TextField(blank=True, verbose_name='Observações do árbitro')

    homologada_por = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sumulas_homologadas', verbose_name='Homologada por',
    )
    homologada_em = models.DateTimeField(null=True, blank=True)

    criada_em    = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Súmula'
        verbose_name_plural = 'Súmulas'

    def __str__(self):
        return f"Súmula #{self.pk} — {self.jogo}"

    @property
    def status_badge_class(self):
        return {
            'rascunho': 'gray',
            'aberta': 'blue',
            'encerrada': 'yellow',
            'homologada': 'green',
            'anulada': 'red',
        }.get(self.status, 'gray')

    def pode_editar(self):
        return self.status in [self.STATUS_RASCUNHO, self.STATUS_ABERTA]

    def pode_encerrar(self):
        return self.status == self.STATUS_ABERTA

    def pode_homologar(self):
        return self.status == self.STATUS_ENCERRADA

    def pode_reabrir(self):
        return self.status == self.STATUS_ENCERRADA


class EscalacaoJogo(models.Model):
    TITULAR = 'titular'
    RESERVA = 'reserva'
    TIPO_CHOICES = [(TITULAR, 'Titular'), (RESERVA, 'Reserva')]

    sumula        = models.ForeignKey(Sumula, on_delete=models.CASCADE, related_name='escalacao')
    atleta        = models.ForeignKey(Atleta, on_delete=models.CASCADE, related_name='escalacoes')
    equipe        = models.ForeignKey(Equipe, on_delete=models.CASCADE, related_name='escalacoes')
    numero_camisa = models.PositiveIntegerField(null=True, blank=True, verbose_name='Nº')
    tipo          = models.CharField(max_length=10, choices=TIPO_CHOICES, default=TITULAR)
    capitao       = models.BooleanField(default=False, verbose_name='Capitão')

    class Meta:
        unique_together = [('sumula', 'atleta')]
        ordering = ['equipe', 'tipo', 'numero_camisa', 'atleta__nome']
        verbose_name = 'Escalação'
        verbose_name_plural = 'Escalações'

    def __str__(self):
        cap = ' (C)' if self.capitao else ''
        return f"{self.atleta.nome}{cap} — {self.get_tipo_display()}"


class SubstituicaoJogo(models.Model):
    sumula        = models.ForeignKey(Sumula, on_delete=models.CASCADE, related_name='substituicoes')
    equipe        = models.ForeignKey(Equipe, on_delete=models.CASCADE, related_name='substituicoes_jogo')
    atleta_saiu   = models.ForeignKey(Atleta, on_delete=models.CASCADE, related_name='saidas_jogo', verbose_name='Saiu')
    atleta_entrou = models.ForeignKey(Atleta, on_delete=models.CASCADE, related_name='entradas_jogo', verbose_name='Entrou')
    minuto        = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        ordering = ['minuto']
        verbose_name = 'Substituição'
        verbose_name_plural = 'Substituições'

    def __str__(self):
        return f"{self.minuto}' ↕ {self.atleta_saiu.nome} → {self.atleta_entrou.nome}"


class OcorrenciaJogo(models.Model):
    INVASAO      = 'invasao'
    BRIGA        = 'briga'
    ARREMESSO    = 'arremesso'
    CANCELAMENTO = 'cancelamento'
    ATRASO       = 'atraso'
    OUTRO        = 'outro'
    TIPO_CHOICES = [
        (INVASAO,      'Invasão de campo'),
        (BRIGA,        'Briga / Tumulto'),
        (ARREMESSO,    'Arremesso de objetos'),
        (CANCELAMENTO, 'Cancelamento / Abandono'),
        (ATRASO,       'Atraso no início'),
        (OUTRO,        'Outro'),
    ]

    sumula    = models.ForeignKey(Sumula, on_delete=models.CASCADE, related_name='ocorrencias')
    tipo      = models.CharField(max_length=15, choices=TIPO_CHOICES, default=OUTRO)
    descricao = models.TextField(verbose_name='Descrição')
    minuto    = models.PositiveIntegerField(null=True, blank=True, verbose_name='Minuto')

    class Meta:
        ordering = ['minuto']
        verbose_name = 'Ocorrência'
        verbose_name_plural = 'Ocorrências'

    def __str__(self):
        return f"{self.get_tipo_display()} ({self.minuto or '—'}')"


# ---------------------------------------------------------------------------
# Histórico de Posição (Estatísticas avançadas)
# ---------------------------------------------------------------------------

class HistoricoClassificacao(models.Model):
    competicao = models.ForeignKey(Competicao, on_delete=models.CASCADE, related_name='historico_posicoes')
    equipe     = models.ForeignKey(Equipe, on_delete=models.CASCADE, related_name='historico_posicoes')
    rodada     = models.ForeignKey(Rodada, on_delete=models.CASCADE, related_name='historico_posicoes')
    posicao    = models.PositiveIntegerField()
    pontos     = models.IntegerField(default=0)

    class Meta:
        unique_together = [('competicao', 'equipe', 'rodada')]
        ordering = ['rodada__numero', 'posicao']
        verbose_name = 'Histórico de Classificação'

    def __str__(self):
        return f"{self.equipe} — Rodada {self.rodada.numero}: {self.posicao}º ({self.pontos}pts)"


# ---------------------------------------------------------------------------
# API Key (autenticação para API REST)
# ---------------------------------------------------------------------------

class ApiKey(models.Model):
    federacao   = models.ForeignKey(Federacao, on_delete=models.CASCADE, related_name='api_keys')
    nome        = models.CharField(max_length=100, verbose_name='Nome / Descrição')
    chave       = models.CharField(max_length=64, unique=True, editable=False)
    ativa       = models.BooleanField(default=True)
    criada_em   = models.DateTimeField(auto_now_add=True)
    ultimo_uso  = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Chave de API'
        verbose_name_plural = 'Chaves de API'

    def __str__(self):
        return f"{self.nome} — {self.federacao.sigla}"

    def save(self, *args, **kwargs):
        if not self.chave:
            self.chave = secrets.token_hex(32)
        super().save(*args, **kwargs)


class EscalacaoTatica(models.Model):
    equipe   = models.OneToOneField(
        'equipe.Equipe', on_delete=models.CASCADE, related_name='escalacao_tatica'
    )
    formacao = models.CharField(max_length=20, default='4-3-3', verbose_name='Formação')
    posicoes = models.JSONField(default=dict, verbose_name='Posições')
    salvo_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Escalação Tática'
        verbose_name_plural = 'Escalações Táticas'

    def __str__(self):
        return f"{self.equipe} — {self.formacao}"


class EscalacaoTaticaJogo(models.Model):
    jogo           = models.ForeignKey(
        'Jogo', on_delete=models.CASCADE, related_name='escalacoes_taticas_dirigente'
    )
    equipe         = models.ForeignKey(
        'equipe.Equipe', on_delete=models.CASCADE, related_name='escalacoes_taticas_jogo'
    )
    formacao       = models.CharField(max_length=20, default='4-3-3', verbose_name='Formação')
    posicoes       = models.JSONField(default=dict, verbose_name='Posições')
    confirmado_em  = models.DateTimeField(auto_now=True)
    confirmado_por = models.ForeignKey(
        'core.Usuario', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='escalacoes_taticas_confirmadas',
    )

    class Meta:
        unique_together     = ('jogo', 'equipe')
        verbose_name        = 'Escalação Tática de Jogo'
        verbose_name_plural = 'Escalações Táticas de Jogo'

    def __str__(self):
        return f"{self.equipe} — Jogo #{self.jogo_id}"

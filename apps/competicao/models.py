from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from stdimage import StdImageField
from ..equipe.models import Equipe, Atleta
from ..criterios.models import FormatoCompeticao, CriterioClassificacao


# ---------------------------------------------------------------------------
# Local / Campo
# ---------------------------------------------------------------------------

class Local(models.Model):
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


# ---------------------------------------------------------------------------
# Árbitro
# ---------------------------------------------------------------------------

class Arbitro(models.Model):
    ASPIRANTE  = 'aspirante'
    REGIONAL   = 'regional'
    NACIONAL   = 'nacional'
    FIFA       = 'fifa'
    CATEGORIA_CHOICES = [
        (ASPIRANTE, 'Aspirante'),
        (REGIONAL,  'Regional'),
        (NACIONAL,  'Nacional'),
        (FIFA,      'FIFA'),
    ]

    DISPONIVEL    = 'disponivel'
    INDISPONIVEL  = 'indisponivel'
    LESIONADO     = 'lesionado'
    FERIAS        = 'ferias'
    DISPONIBILIDADE_CHOICES = [
        (DISPONIVEL,   'Disponível'),
        (INDISPONIVEL, 'Indisponível'),
        (LESIONADO,    'Lesionado'),
        (FERIAS,       'Férias'),
    ]

    # — campos originais —
    nome       = models.CharField(max_length=200, verbose_name='Nome')
    categoria  = models.CharField(
        max_length=20, choices=CATEGORIA_CHOICES, default=REGIONAL,
        verbose_name='Categoria',
    )
    observacao = models.TextField(blank=True, null=True, verbose_name='Observações')
    ativo      = models.BooleanField(default=True, verbose_name='Ativo')

    # — Fase 2: dados pessoais —
    cpf              = models.CharField(max_length=14, blank=True, null=True, verbose_name='CPF')
    data_nascimento  = models.DateField(blank=True, null=True, verbose_name='Data de Nascimento')
    foto             = StdImageField(
        upload_to='arbitros/fotos/', blank=True, null=True,
        variations={'thumbnail': (80, 80, True)},
        verbose_name='Foto',
    )
    certificacoes    = models.TextField(blank=True, null=True, verbose_name='Certificações')
    disponibilidade  = models.CharField(
        max_length=20, choices=DISPONIBILIDADE_CHOICES, default=DISPONIVEL,
        verbose_name='Disponibilidade',
    )

    # — Fase 2: custos operacionais —
    taxa_por_partida = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name='Taxa por Partida (R$)')
    diaria           = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name='Diária (R$)')
    alimentacao      = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name='Alimentação (R$)')
    hospedagem       = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name='Hospedagem (R$)')
    deslocamento     = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name='Deslocamento (R$)')

    class Meta:
        ordering = ['nome']
        verbose_name = 'Árbitro'
        verbose_name_plural = 'Árbitros'

    def __str__(self):
        return self.nome

    @property
    def custo_total_estimado(self):
        campos = [self.taxa_por_partida, self.diaria, self.alimentacao, self.hospedagem, self.deslocamento]
        return sum(v for v in campos if v) or None

    @property
    def disponivel(self):
        return self.disponibilidade == self.DISPONIVEL and self.ativo


class FaseCompeticao(models.Model):
    """Legado — mantido apenas para compatibilidade com migrações existentes."""
    TIPOS_FASE = [
        ('rodada', 'Rodada'), ('grupos', 'Fase de Grupos'),
        ('oitavas', 'Oitavas de Final'), ('quartas', 'Quartas de Final'),
        ('semi', 'Semifinal'), ('final', 'Final'), ('fase', 'Fase Personalizada'),
    ]
    tipo = models.CharField(max_length=20, choices=TIPOS_FASE, default='rodada')
    nome_customizado = models.CharField(max_length=50, blank=True, null=True)
    numero = models.PositiveIntegerField(default=1)
    qtd_times = models.PositiveIntegerField(default=0)
    ativa = models.BooleanField(default=True)
    concluida = models.BooleanField(default=False)

    def __str__(self):
        return self.nome_customizado or self.get_tipo_display()


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
    STATUS_CHOICES = [
        ('inscricoes', 'Inscrições Abertas'), ('andamento', 'Em Andamento'),
        ('finalizado', 'Finalizado'), ('cancelado', 'Cancelado'),
    ]

    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, null=True)
    data_inicio = models.DateField(verbose_name='Início')
    data_fim = models.DateField(verbose_name='Final', blank=True, null=True)
    categoria = models.CharField(max_length=10, choices=CATEGORIA_CHOICES, default='adulto', verbose_name='Categoria')
    genero = models.CharField(max_length=15, choices=GENERO_CHOICES, default='masculino', verbose_name='Gênero')
    modalidade = models.CharField(max_length=10, choices=MODALIDADE_CHOICES, default='campo', verbose_name='Modalidade')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='inscricoes', verbose_name='Status')
    data_abertura_inscricao = models.DateField(null=True, blank=True, verbose_name='Abertura de inscrições')
    data_encerramento_inscricao = models.DateField(null=True, blank=True, verbose_name='Encerramento de inscrições')
    limite_atletas = models.PositiveIntegerField(null=True, blank=True, verbose_name='Limite de atletas por equipe', help_text='Deixe em branco para sem limite')
    taxa_inscricao = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name='Taxa de inscrição (R$)')
    equipes = models.ManyToManyField(Equipe, related_name='equipes')
    formato = models.OneToOneField(
        FormatoCompeticao, on_delete=models.DO_NOTHING,
        related_name='formato', blank=True, null=True,
    )
    criterio_classificacao = models.OneToOneField(
        CriterioClassificacao, on_delete=models.DO_NOTHING, null=True, blank=True,
    )
    fase_legado = models.ForeignKey(
        FaseCompeticao, verbose_name='Fase (legado)',
        on_delete=models.DO_NOTHING, null=True, blank=True,
    )

    def __str__(self):
        return self.nome

    @property
    def status_badge_class(self):
        return {
            'inscricoes': 'info', 'andamento': 'warning',
            'finalizado': 'success', 'cancelado': 'danger',
        }.get(self.status, 'secondary')


# ---------------------------------------------------------------------------
# Fases da competição
# ---------------------------------------------------------------------------

class Fase(models.Model):
    LIGA = 'liga'
    GRUPOS = 'grupos'
    MATA_MATA = 'mata_mata'
    TIPO_CHOICES = [
        (LIGA, 'Liga / Pontos Corridos'),
        (GRUPOS, 'Fase de Grupos'),
        (MATA_MATA, 'Mata-Mata'),
    ]

    competicao = models.ForeignKey(Competicao, on_delete=models.CASCADE, related_name='fases')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default=LIGA)
    nome = models.CharField(max_length=100)
    ordem = models.PositiveIntegerField(default=1)
    ida_e_volta = models.BooleanField(default=False, verbose_name='Ida e Volta')
    qtd_classificados_por_grupo = models.PositiveIntegerField(
        default=2, verbose_name='Classificados por grupo',
        help_text='Quantas equipes de cada grupo avançam (só para fase de grupos).',
    )
    concluida = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordem']

    def __str__(self):
        return f"{self.nome} — {self.competicao.nome}"

    @property
    def label_tipo(self):
        return dict(self.TIPO_CHOICES).get(self.tipo, self.tipo)


class Grupo(models.Model):
    fase = models.ForeignKey(Fase, on_delete=models.CASCADE, related_name='grupos')
    nome = models.CharField(max_length=20, verbose_name='Nome do grupo')
    equipes = models.ManyToManyField(Equipe, related_name='grupos_competicao', blank=True)

    class Meta:
        ordering = ['nome']
        unique_together = [('fase', 'nome')]

    def __str__(self):
        return f"Grupo {self.nome}"


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


# ---------------------------------------------------------------------------
# Rodada e Jogo
# ---------------------------------------------------------------------------

class Rodada(models.Model):
    competicao = models.ForeignKey(Competicao, on_delete=models.DO_NOTHING)
    fase = models.ForeignKey(
        Fase, on_delete=models.SET_NULL, null=True, blank=True, related_name='rodadas',
    )
    grupo = models.ForeignKey(
        Grupo, on_delete=models.SET_NULL, null=True, blank=True, related_name='rodadas',
    )
    numero = models.PositiveIntegerField()

    def __str__(self):
        if self.grupo:
            return f"{self.competicao} — {self.grupo} — Rodada {self.numero}"
        if self.fase:
            return f"{self.competicao} — {self.fase.nome} — Rodada {self.numero}"
        return f"{self.competicao}: {self.numero}ª Rodada"


class Jogo(models.Model):
    rodada = models.ForeignKey(Rodada, on_delete=models.CASCADE, null=True, blank=True)
    equipe_casa = models.ForeignKey(Equipe, on_delete=models.CASCADE, related_name='jogos_casa')
    equipe_fora = models.ForeignKey(Equipe, on_delete=models.CASCADE, related_name='jogos_fora')
    data_hora = models.DateTimeField(null=True, blank=True)
    gols_casa = models.IntegerField(default=0)
    gols_fora = models.IntegerField(default=0)
    finalizado = models.BooleanField(default=False)
    em_andamento = models.BooleanField(default=False, verbose_name='Em andamento')
    anulado = models.BooleanField(default=False)
    wo = models.BooleanField(default=False, verbose_name='W.O.')
    local = models.ForeignKey(
        'Local', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='jogos', verbose_name='Local',
    )
    arbitro = models.ForeignKey(
        'Arbitro', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='jogos', verbose_name='Árbitro Principal',
    )
    publico = models.PositiveIntegerField(null=True, blank=True, verbose_name='Público presente')
    observacoes = models.TextField(null=True, blank=True, verbose_name='Observações')

    def __str__(self):
        if self.em_andamento:
            status = 'Ao vivo'
        elif self.anulado:
            status = 'Anulado'
        elif self.finalizado:
            status = 'Finalizado'
        else:
            status = 'Pendente'
        return f"{self.equipe_casa} x {self.equipe_fora} ({status})"


class ArbitrosJogo(models.Model):
    PRINCIPAL = 'principal'
    ASSISTENTE1 = 'assistente1'
    ASSISTENTE2 = 'assistente2'
    QUARTO = 'quarto'
    TIPO_CHOICES = [
        (PRINCIPAL, 'Árbitro Principal'),
        (ASSISTENTE1, 'Assistente 1'),
        (ASSISTENTE2, 'Assistente 2'),
        (QUARTO, 'Quarto Árbitro'),
    ]
    jogo = models.ForeignKey(Jogo, on_delete=models.CASCADE, related_name='arbitros_jogo')
    arbitro = models.ForeignKey(Arbitro, on_delete=models.CASCADE, related_name='jogos_arbitrados')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default=PRINCIPAL)

    class Meta:
        unique_together = [('jogo', 'tipo')]
        ordering = ['tipo']
        verbose_name = 'Árbitro do Jogo'
        verbose_name_plural = 'Árbitros do Jogo'

    def __str__(self):
        return f"{self.arbitro.nome} ({self.get_tipo_display()}) — {self.jogo}"


# ---------------------------------------------------------------------------
# Mata-Mata
# ---------------------------------------------------------------------------

class ConfrontoMatamate(models.Model):
    NORMAL = 'normal'
    TERCEIRO_LUGAR = 'terceiro'
    TIPO_CHOICES = [(NORMAL, 'Normal'), (TERCEIRO_LUGAR, '3º Lugar')]

    fase = models.ForeignKey(Fase, on_delete=models.CASCADE, related_name='confrontos')
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
        return f"{m} x {v} ({self.fase.nome})"

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
        if self.fase.ida_e_volta:
            return self.jogo_volta and self.jogo_volta.finalizado
        return True

    def calcular_vencedor(self):
        if not self.totalmente_jogado:
            return None
        gm = self.gols_mandante_total
        gv = self.gols_visitante_total
        if gm > gv:
            return self.equipe_mandante
        if gv > gm:
            return self.equipe_visitante
        # Empate: pênaltis
        pm = self.penaltis_mandante
        pv = self.penaltis_visitante
        if pm is not None and pv is not None:
            if pm > pv:
                return self.equipe_mandante
            if pv > pm:
                return self.equipe_visitante
        return None  # Ainda em aberto (aguardando pênaltis)

    def atualizar_vencedor(self):
        novo = self.calcular_vencedor()
        if novo != self.vencedor:
            ConfrontoMatamate.objects.filter(pk=self.pk).update(vencedor=novo)
            self.vencedor = novo


# ---------------------------------------------------------------------------
# Classificação geral, Cartões, Inscrições, Gols
# ---------------------------------------------------------------------------

class Classificacao(models.Model):
    equipe = models.ForeignKey(Equipe, on_delete=models.CASCADE, related_name='classificacoes')
    competicao = models.ForeignKey(Competicao, on_delete=models.CASCADE, related_name='classificacoes')
    jogos = models.IntegerField(default=0)
    vitorias = models.IntegerField(default=0)
    empates = models.IntegerField(default=0)
    derrotas = models.IntegerField(default=0)
    gols_pro = models.IntegerField(default=0)
    gols_contra = models.IntegerField(default=0)
    saldo_gols = models.IntegerField(default=0)
    pontos = models.IntegerField(default=0)

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


class InscricaoAtleta(models.Model):
    competicao = models.ForeignKey(Competicao, on_delete=models.CASCADE, related_name='inscricoes')
    atleta = models.ForeignKey(Atleta, on_delete=models.CASCADE, related_name='inscricoes')
    numero_camisa = models.PositiveIntegerField(verbose_name='Número', null=True, blank=True)
    taxa_paga = models.BooleanField(default=False, verbose_name='Taxa paga')

    class Meta:
        unique_together = [('competicao', 'atleta')]
        ordering = ['numero_camisa', 'atleta__nome']
        verbose_name = 'Inscrição'
        verbose_name_plural = 'Inscrições'

    def __str__(self):
        num = f"#{self.numero_camisa} " if self.numero_camisa else ''
        return f"{num}{self.atleta.nome} — {self.competicao.nome}"


class Suspensao(models.Model):
    AMARELOS = 'amarelos'
    VERMELHO = 'vermelho'
    MOTIVO_CHOICES = [
        (AMARELOS, '3 Cartões Amarelos'),
        (VERMELHO, 'Cartão Vermelho'),
    ]
    atleta = models.ForeignKey(Atleta, on_delete=models.CASCADE, related_name='suspensoes')
    competicao = models.ForeignKey(Competicao, on_delete=models.CASCADE, related_name='suspensoes')
    motivo = models.CharField(max_length=20, choices=MOTIVO_CHOICES, default=AMARELOS)
    cumprida = models.BooleanField(default=False)

    class Meta:
        ordering = ['-pk']

    def __str__(self):
        status = 'cumprida' if self.cumprida else 'pendente'
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
# Escalação e Substituições
# ---------------------------------------------------------------------------

class EscalacaoJogo(models.Model):
    jogo = models.ForeignKey(Jogo, on_delete=models.CASCADE, related_name='escalacao')
    equipe = models.ForeignKey(Equipe, on_delete=models.CASCADE, related_name='escalacoes')
    atleta = models.ForeignKey(Atleta, on_delete=models.CASCADE, related_name='escalacoes')
    titular = models.BooleanField(default=True, verbose_name='Titular')
    numero_camisa = models.PositiveIntegerField(null=True, blank=True, verbose_name='Camisa')
    capitao = models.BooleanField(default=False, verbose_name='Capitão')

    class Meta:
        unique_together = [('jogo', 'atleta')]
        ordering = ['titular', 'numero_camisa', 'atleta__nome']
        verbose_name = 'Escalação'
        verbose_name_plural = 'Escalações'

    def __str__(self):
        papel = 'Titular' if self.titular else 'Reserva'
        return f"{self.atleta.nome} ({papel}) — {self.jogo}"


class Substituicao(models.Model):
    jogo = models.ForeignKey(Jogo, on_delete=models.CASCADE, related_name='substituicoes')
    equipe = models.ForeignKey(Equipe, on_delete=models.CASCADE, related_name='substituicoes')
    atleta_entra = models.ForeignKey(
        Atleta, on_delete=models.CASCADE, related_name='entradas',
        verbose_name='Entra',
    )
    atleta_sai = models.ForeignKey(
        Atleta, on_delete=models.CASCADE, related_name='saidas',
        verbose_name='Sai',
    )
    minuto = models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name='Minuto')

    class Meta:
        ordering = ['minuto']
        verbose_name = 'Substituição'
        verbose_name_plural = 'Substituições'

    def __str__(self):
        return f"{self.atleta_entra.nome} ↔ {self.atleta_sai.nome} ({self.minuto}')"


# ---------------------------------------------------------------------------
# Avaliação do Árbitro por Jogo  (K)
# ---------------------------------------------------------------------------

class AvaliacaoArbitro(models.Model):
    jogo = models.OneToOneField(Jogo, on_delete=models.CASCADE, related_name='avaliacao_arbitro')
    nota = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        verbose_name='Nota (1-10)',
    )
    observacoes = models.TextField(blank=True, null=True, verbose_name='Observações')
    avaliado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='avaliacoes_arbitro',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Avaliação do Árbitro'
        verbose_name_plural = 'Avaliações dos Árbitros'

    def __str__(self):
        return f"Avaliação {self.nota}/10 — {self.jogo}"


# ---------------------------------------------------------------------------
# Súmula Digital Profissional — Fase 3
# ---------------------------------------------------------------------------

class SumulaDigital(models.Model):
    CLIMATICA_CHOICES = [
        ('boa',     'Boa / Ensolarada'),
        ('chuvosa', 'Chuvosa'),
        ('fria',    'Fria'),
        ('quente',  'Quente'),
        ('ventosa', 'Ventosa'),
        ('neblina', 'Neblina'),
    ]
    CAMPO_CHOICES = [
        ('otimo',   'Ótimo'),
        ('bom',     'Bom'),
        ('regular', 'Regular'),
        ('ruim',    'Ruim'),
        ('pessimo', 'Péssimo'),
    ]

    jogo              = models.OneToOneField(Jogo, on_delete=models.CASCADE, related_name='sumula_digital')
    condicao_climatica = models.CharField(max_length=10, choices=CLIMATICA_CHOICES, default='boa', verbose_name='Condição climática')
    condicao_campo    = models.CharField(max_length=10, choices=CAMPO_CHOICES, default='bom', verbose_name='Condição do campo')
    relatorio_narrativo = models.TextField(blank=True, null=True, verbose_name='Relatório narrativo do árbitro')
    finalizada        = models.BooleanField(default=False, verbose_name='Súmula finalizada')
    finalizada_em     = models.DateTimeField(null=True, blank=True, verbose_name='Finalizada em')
    hash_integridade  = models.CharField(max_length=64, blank=True, null=True, verbose_name='Hash SHA-256')
    criada_em         = models.DateTimeField(auto_now_add=True)
    atualizada_em     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Súmula Digital'
        verbose_name_plural = 'Súmulas Digitais'

    def __str__(self):
        return f"Súmula — {self.jogo}"

    def gerar_hash(self):
        import hashlib, json
        dados = {
            'jogo_id':   self.jogo_id,
            'gols_casa': self.jogo.gols_casa,
            'gols_fora': self.jogo.gols_fora,
            'climatica': self.condicao_climatica,
            'campo':     self.condicao_campo,
            'relatorio': self.relatorio_narrativo or '',
            'ocorrencias': [
                {'tipo': o.tipo, 'minuto': o.minuto, 'descricao': o.descricao}
                for o in self.ocorrencias.order_by('id')
            ],
            'assinaturas': [
                {'papel': a.papel, 'nome': a.nome_assinante, 'em': str(a.assinado_em)}
                for a in self.assinaturas.order_by('id')
            ],
        }
        return hashlib.sha256(
            json.dumps(dados, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()


class OcorrenciaSumula(models.Model):
    TIPOS = [
        ('invasao',      'Invasão de campo'),
        ('tumulto',      'Tumulto / Briga'),
        ('objetos',      'Objetos arremessados'),
        ('interrupcao',  'Interrupção da partida'),
        ('falta_energia','Falta de energia / iluminação'),
        ('climatica',    'Ocorrência climática'),
        ('wo',           'W.O. / Abandono'),
        ('outro',        'Outro'),
    ]

    sumula    = models.ForeignKey(SumulaDigital, on_delete=models.CASCADE, related_name='ocorrencias')
    tipo      = models.CharField(max_length=20, choices=TIPOS, verbose_name='Tipo de ocorrência')
    minuto    = models.PositiveIntegerField(null=True, blank=True, verbose_name='Minuto')
    descricao = models.TextField(verbose_name='Descrição detalhada')
    registrado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['minuto', 'registrado_em']
        verbose_name = 'Ocorrência'
        verbose_name_plural = 'Ocorrências'

    def __str__(self):
        min_str = f" ({self.minuto}')" if self.minuto else ''
        return f"{self.get_tipo_display()}{min_str} — {self.sumula.jogo}"


class AnexoSumula(models.Model):
    TIPOS = [
        ('foto',      'Foto'),
        ('video',     'Vídeo'),
        ('documento', 'Documento PDF'),
    ]

    sumula    = models.ForeignKey(SumulaDigital, on_delete=models.CASCADE, related_name='anexos')
    arquivo   = models.FileField(upload_to='sumulas/anexos/', verbose_name='Arquivo')
    tipo      = models.CharField(max_length=10, choices=TIPOS, default='foto', verbose_name='Tipo')
    descricao = models.CharField(max_length=200, blank=True, verbose_name='Descrição')
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['enviado_em']
        verbose_name = 'Anexo da Súmula'
        verbose_name_plural = 'Anexos da Súmula'

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.sumula.jogo}"

    @property
    def extensao(self):
        import os
        return os.path.splitext(self.arquivo.name)[1].lower()

    @property
    def is_imagem(self):
        return self.extensao in ('.jpg', '.jpeg', '.png', '.gif', '.webp')


class AssinaturaDigital(models.Model):
    PAPEIS = [
        ('arbitro',           'Árbitro Principal'),
        ('assistente1',       'Árbitro Assistente 1'),
        ('assistente2',       'Árbitro Assistente 2'),
        ('capitao_mandante',  'Capitão Mandante'),
        ('capitao_visitante', 'Capitão Visitante'),
        ('delegado',          'Delegado'),
    ]

    sumula        = models.ForeignKey(SumulaDigital, on_delete=models.CASCADE, related_name='assinaturas')
    papel         = models.CharField(max_length=25, choices=PAPEIS, verbose_name='Papel')
    nome_assinante = models.CharField(max_length=200, verbose_name='Nome do assinante')
    assinado_em   = models.DateTimeField(auto_now_add=True)
    ip_address    = models.GenericIPAddressField(null=True, blank=True, verbose_name='Endereço IP')
    user_agent    = models.CharField(max_length=500, blank=True, verbose_name='User-Agent')

    class Meta:
        unique_together = [('sumula', 'papel')]
        ordering = ['papel']
        verbose_name = 'Assinatura Digital'
        verbose_name_plural = 'Assinaturas Digitais'

    def __str__(self):
        return f"{self.get_papel_display()} — {self.nome_assinante}"


# ---------------------------------------------------------------------------
# Tribunal Desportivo — Fase 4
# ---------------------------------------------------------------------------

class ProcessoDesportivo(models.Model):
    TIPO_CHOICES = [
        ('comportamento', 'Comportamento antidesportivo'),
        ('resultado',     'Impugnação de resultado'),
        ('irregularidade','Irregularidade de atleta/clube'),
        ('violacao',      'Violação de regulamento'),
        ('arbitral',      'Reclamação arbitral'),
        ('outro',         'Outro'),
    ]
    STATUS_CHOICES = [
        ('aberto',         'Aberto'),
        ('em_julgamento',  'Em Julgamento'),
        ('julgado',        'Julgado'),
        ('arquivado',      'Arquivado'),
    ]

    numero           = models.CharField(max_length=20, unique=True, blank=True, verbose_name='Nº do processo')
    competicao       = models.ForeignKey(Competicao, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='processos', verbose_name='Competição')
    jogo             = models.ForeignKey('Jogo', on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='processos', verbose_name='Partida relacionada')
    denunciado_atleta = models.ForeignKey('equipe.Atleta', on_delete=models.SET_NULL,
                                          null=True, blank=True, related_name='processos_desportivos',
                                          verbose_name='Atleta denunciado')
    denunciado_equipe = models.ForeignKey('equipe.Equipe', on_delete=models.SET_NULL,
                                          null=True, blank=True, related_name='processos_desportivos',
                                          verbose_name='Equipe denunciada')
    denunciante      = models.CharField(max_length=200, verbose_name='Denunciante / Requerente')
    tipo             = models.CharField(max_length=20, choices=TIPO_CHOICES, default='comportamento',
                                        verbose_name='Tipo de processo')
    descricao        = models.TextField(verbose_name='Descrição dos fatos')
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='aberto',
                                        verbose_name='Status')
    prazo_defesa     = models.DateField(null=True, blank=True, verbose_name='Prazo para defesa')
    criado_em        = models.DateTimeField(auto_now_add=True)
    atualizado_em    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Processo Desportivo'
        verbose_name_plural = 'Processos Desportivos'

    def __str__(self):
        return f"{self.numero or f'PD-{self.pk}'} — {self.get_tipo_display()}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and not self.numero:
            from datetime import date
            self.numero = f"PD-{date.today().year}-{self.pk:04d}"
            super().save(update_fields=['numero'])

    @property
    def status_badge_class(self):
        return {
            'aberto':        'badge-warning',
            'em_julgamento': 'badge-info',
            'julgado':       'badge-success',
            'arquivado':     'badge-ghost',
        }.get(self.status, 'badge-ghost')

    @property
    def denunciado_str(self):
        if self.denunciado_atleta:
            return f"{self.denunciado_atleta.nome} (atleta)"
        if self.denunciado_equipe:
            return f"{self.denunciado_equipe.nome_equipe} (equipe)"
        return '—'


class Julgamento(models.Model):
    PENALIDADE_CHOICES = [
        ('absolvido',    'Absolvido'),
        ('advertencia',  'Advertência'),
        ('multa',        'Multa'),
        ('suspensao',    'Suspensão de partidas'),
        ('perda_pontos', 'Perda de pontos'),
        ('exclusao',     'Exclusão da competição'),
    ]

    processo         = models.OneToOneField(ProcessoDesportivo, on_delete=models.CASCADE,
                                            related_name='julgamento', verbose_name='Processo')
    relator          = models.CharField(max_length=200, verbose_name='Relator / Juiz')
    descricao        = models.TextField(verbose_name='Fundamentação e decisão')
    penalidade       = models.CharField(max_length=20, choices=PENALIDADE_CHOICES, verbose_name='Penalidade aplicada')
    valor_multa      = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                           verbose_name='Valor da multa (R$)')
    jogos_suspensao  = models.PositiveIntegerField(null=True, blank=True,
                                                   verbose_name='Partidas de suspensão')
    pontos_perdidos  = models.PositiveIntegerField(null=True, blank=True,
                                                   verbose_name='Pontos a deduzir')
    aplicar_suspensao = models.BooleanField(default=True,
                                            verbose_name='Gerar suspensão automática no sistema',
                                            help_text='Cria o registro de suspensão para o atleta denunciado.')
    julgado_em       = models.DateTimeField(auto_now_add=True, verbose_name='Julgado em')

    class Meta:
        verbose_name = 'Julgamento'
        verbose_name_plural = 'Julgamentos'

    def __str__(self):
        return f"Julgamento — {self.processo}"


class RecursoDesportivo(models.Model):
    STATUS_CHOICES = [
        ('aguardando',    'Aguardando Análise'),
        ('em_analise',    'Em Análise'),
        ('provido',       'Provido'),
        ('improvido',     'Improvido'),
        ('nao_conhecido', 'Não Conhecido'),
    ]

    processo    = models.ForeignKey(ProcessoDesportivo, on_delete=models.CASCADE,
                                    related_name='recursos', verbose_name='Processo')
    recorrente  = models.CharField(max_length=200, verbose_name='Recorrente')
    motivo      = models.TextField(verbose_name='Fundamentos do recurso')
    data_prazo  = models.DateField(null=True, blank=True, verbose_name='Prazo para decisão')
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='aguardando',
                                   verbose_name='Status do recurso')
    decisao     = models.TextField(blank=True, null=True, verbose_name='Decisão do recurso')
    criado_em   = models.DateTimeField(auto_now_add=True)
    decidido_em = models.DateTimeField(null=True, blank=True, verbose_name='Decidido em')

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Recurso Desportivo'
        verbose_name_plural = 'Recursos Desportivos'

    def __str__(self):
        return f"Recurso de {self.recorrente} — {self.processo}"

    @property
    def status_badge_class(self):
        return {
            'aguardando':    'badge-warning',
            'em_analise':    'badge-info',
            'provido':       'badge-success',
            'improvido':     'badge-error',
            'nao_conhecido': 'badge-ghost',
        }.get(self.status, 'badge-ghost')


# ---------------------------------------------------------------------------
# Financeiro Federativo — Fase 5
# ---------------------------------------------------------------------------

class LancamentoFinanceiro(models.Model):
    TIPO_CHOICES = [
        ('receita', 'Receita'),
        ('despesa', 'Despesa'),
    ]

    CAT_RECEITA = [
        ('filiacao',      'Filiação'),
        ('anuidade',      'Anuidade'),
        ('inscricao',     'Inscrição em competição'),
        ('transferencia', 'Taxa de transferência'),
        ('arb_receita',   'Arbitragem'),
        ('multa',         'Multa disciplinar'),
        ('patrocinio',    'Patrocínio / Apoio'),
        ('outra_receita', 'Outra receita'),
    ]
    CAT_DESPESA = [
        ('arb_despesa',   'Arbitragem'),
        ('premiacao',     'Premiação'),
        ('transporte',    'Transporte'),
        ('infraestrutura','Infraestrutura'),
        ('evento',        'Eventos'),
        ('administrativa','Administrativa'),
        ('outra_despesa', 'Outra despesa'),
    ]
    CATEGORIA_CHOICES = CAT_RECEITA + CAT_DESPESA

    STATUS_CHOICES = [
        ('pendente',  'Pendente'),
        ('pago',      'Pago / Recebido'),
        ('cancelado', 'Cancelado'),
    ]
    FORMA_CHOICES = [
        ('pix',          'PIX'),
        ('boleto',       'Boleto Bancário'),
        ('cartao_credito','Cartão de Crédito'),
        ('cartao_debito', 'Cartão de Débito'),
        ('transferencia', 'Transferência Bancária'),
        ('dinheiro',      'Dinheiro / Espécie'),
        ('outro',         'Outro'),
    ]

    numero          = models.CharField(max_length=20, unique=True, blank=True, verbose_name='Nº')
    tipo            = models.CharField(max_length=10, choices=TIPO_CHOICES, verbose_name='Tipo')
    categoria       = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, verbose_name='Categoria')
    descricao       = models.CharField(max_length=300, verbose_name='Descrição')
    valor           = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Valor (R$)')
    data_vencimento = models.DateField(verbose_name='Vencimento')
    data_pagamento  = models.DateField(null=True, blank=True, verbose_name='Data do pagamento')
    status          = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pendente', verbose_name='Status')
    forma_pagamento = models.CharField(max_length=20, choices=FORMA_CHOICES, blank=True, null=True, verbose_name='Forma de pagamento')
    numero_referencia = models.CharField(max_length=100, blank=True, verbose_name='Nº de referência / chave PIX')
    comprovante     = models.FileField(upload_to='financeiro/comprovantes/', blank=True, null=True, verbose_name='Comprovante')
    observacoes     = models.TextField(blank=True, null=True, verbose_name='Observações')

    # Vínculos opcionais
    competicao  = models.ForeignKey(Competicao, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='lancamentos', verbose_name='Competição')
    equipe      = models.ForeignKey('equipe.Equipe', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='lancamentos_financeiros', verbose_name='Equipe')
    atleta      = models.ForeignKey('equipe.Atleta', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='lancamentos_financeiros', verbose_name='Atleta')

    criado_em   = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-data_vencimento', '-criado_em']
        verbose_name = 'Lançamento Financeiro'
        verbose_name_plural = 'Lançamentos Financeiros'

    def __str__(self):
        return f"{self.numero or self.pk} — {self.descricao} (R$ {self.valor})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and not self.numero:
            from datetime import date
            prefixo = 'REC' if self.tipo == 'receita' else 'DES'
            self.numero = f"{prefixo}-{date.today().year}-{self.pk:05d}"
            super().save(update_fields=['numero'])

    @property
    def is_atrasado(self):
        from datetime import date
        return self.status == 'pendente' and self.data_vencimento < date.today()

    @property
    def status_efetivo(self):
        if self.is_atrasado:
            return 'atrasado'
        return self.status

    @property
    def status_badge_class(self):
        return {
            'pendente':  'badge-warning',
            'atrasado':  'badge-error',
            'pago':      'badge-success',
            'cancelado': 'badge-ghost',
        }.get(self.status_efetivo, 'badge-ghost')

    @property
    def tipo_cor(self):
        return 'text-success' if self.tipo == 'receita' else 'text-error'

    @property
    def comprovante_extensao(self):
        if not self.comprovante:
            return ''
        import os
        return os.path.splitext(self.comprovante.name)[1].lower()

    @property
    def comprovante_is_imagem(self):
        return self.comprovante_extensao in ('.jpg', '.jpeg', '.png', '.gif', '.webp')



# ---------------------------------------------------------------------------
# Portal Público  (P)
# ---------------------------------------------------------------------------

class Publicacao(models.Model):
    TIPO_CHOICES = [
        ('noticia',           'Notícia'),
        ('comunicado',        'Comunicado'),
        ('regulamento',       'Regulamento'),
        ('documento_oficial', 'Documento Oficial'),
    ]

    tipo          = models.CharField(max_length=20, choices=TIPO_CHOICES, default='noticia', verbose_name='Tipo')
    titulo        = models.CharField(max_length=300, verbose_name='Título')
    slug          = models.SlugField(max_length=320, unique=True, blank=True, verbose_name='Slug')
    resumo        = models.CharField(max_length=500, blank=True, verbose_name='Resumo')
    conteudo      = models.TextField(blank=True, verbose_name='Conteúdo')
    imagem_capa   = models.ImageField(upload_to='portal/imagens/', blank=True, null=True, verbose_name='Imagem de capa')
    arquivo       = models.FileField(upload_to='portal/documentos/', blank=True, null=True, verbose_name='Arquivo')
    publicado     = models.BooleanField(default=False, verbose_name='Publicado')
    destaque      = models.BooleanField(default=False, verbose_name='Destaque')
    publicado_em  = models.DateTimeField(blank=True, null=True, verbose_name='Publicado em')
    criado_em     = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-publicado_em', '-criado_em']
        verbose_name = 'Publicação'
        verbose_name_plural = 'Publicações'

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base = slugify(self.titulo)[:300]
            slug = base or 'publicacao'
            i = 1
            while Publicacao.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        if self.publicado and not self.publicado_em:
            from django.utils import timezone
            self.publicado_em = timezone.now()
        super().save(*args, **kwargs)

    @property
    def arquivo_extensao(self):
        if not self.arquivo:
            return ''
        import os
        return os.path.splitext(self.arquivo.name)[1].lower()

    @property
    def arquivo_is_imagem(self):
        return self.arquivo_extensao in ('.jpg', '.jpeg', '.png', '.gif', '.webp')


# ---------------------------------------------------------------------------
# Notificações in-app  (N)
# ---------------------------------------------------------------------------

class Notificacao(models.Model):
    RESULTADO = 'resultado'
    SUSPENSAO = 'suspensao'
    SISTEMA = 'sistema'
    TIPO_CHOICES = [
        (RESULTADO, 'Resultado registrado'),
        (SUSPENSAO, 'Suspensão gerada'),
        (SISTEMA, 'Sistema'),
    ]
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notificacoes',
    )
    mensagem = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default=SISTEMA)
    lida = models.BooleanField(default=False)
    url = models.CharField(max_length=300, blank=True, null=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criada_em']
        verbose_name = 'Notificação'
        verbose_name_plural = 'Notificações'

    def __str__(self):
        return f"{self.usuario.email} — {self.mensagem[:50]}"

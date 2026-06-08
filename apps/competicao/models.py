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
    nome = models.CharField(max_length=200, verbose_name='Nome')
    categoria = models.CharField(max_length=100, blank=True, null=True, verbose_name='Categoria')
    observacao = models.TextField(blank=True, null=True, verbose_name='Observações')
    ativo = models.BooleanField(default=True, verbose_name='Ativo')

    class Meta:
        ordering = ['nome']
        verbose_name = 'Árbitro'
        verbose_name_plural = 'Árbitros'

    def __str__(self):
        return self.nome


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

from django import forms
from django.forms import DateInput

from ..competicao.models import (
    Competicao, Jogo, Cartao, Gol, InscricaoAtleta,
    Fase, Grupo, ConfrontoMatamate, Local, Arbitro,
    EscalacaoJogo, Substituicao, ArbitrosJogo, AvaliacaoArbitro,
    SumulaDigital, OcorrenciaSumula, AnexoSumula,
    ProcessoDesportivo, Julgamento, RecursoDesportivo,
    LancamentoFinanceiro, Publicacao,
)
from ..equipe.models import Equipe, Atleta

# ---------------------------------------------------------------------------
# Widgets reutilizáveis (DaisyUI / Tailwind)
# ---------------------------------------------------------------------------

_INPUT   = 'input input-bordered w-full'
_SELECT  = 'select select-bordered w-full'
_TEXTAREA = 'textarea textarea-bordered w-full'


# ---------------------------------------------------------------------------
# Competição
# ---------------------------------------------------------------------------

class CompeticaoForm(forms.ModelForm):
    class Meta:
        model = Competicao
        fields = (
            'nome', 'descricao', 'data_inicio', 'data_fim',
            'categoria', 'genero', 'modalidade', 'status',
            'data_abertura_inscricao', 'data_encerramento_inscricao',
            'limite_atletas', 'taxa_inscricao',
        )
        widgets = {
            'nome':                         forms.TextInput(attrs={'class': _INPUT}),
            'descricao':                    forms.Textarea(attrs={'class': _TEXTAREA, 'rows': 2}),
            'data_inicio':                  DateInput(attrs={'type': 'date', 'class': _INPUT}),
            'data_fim':                     DateInput(attrs={'type': 'date', 'class': _INPUT}),
            'categoria':                    forms.Select(attrs={'class': _SELECT}),
            'genero':                       forms.Select(attrs={'class': _SELECT}),
            'modalidade':                   forms.Select(attrs={'class': _SELECT}),
            'status':                       forms.Select(attrs={'class': _SELECT}),
            'data_abertura_inscricao':      DateInput(attrs={'type': 'date', 'class': _INPUT}),
            'data_encerramento_inscricao':  DateInput(attrs={'type': 'date', 'class': _INPUT}),
            'limite_atletas':               forms.NumberInput(attrs={'class': _INPUT, 'min': 0}),
            'taxa_inscricao':               forms.NumberInput(attrs={'class': _INPUT, 'step': '0.01', 'min': 0}),
        }


class AssociarEquipeForm(forms.Form):
    equipe_id = forms.IntegerField(widget=forms.HiddenInput())


# ---------------------------------------------------------------------------
# Jogo
# ---------------------------------------------------------------------------

class JogoResultadoForm(forms.ModelForm):
    class Meta:
        model = Jogo
        fields = (
            'data_hora', 'local', 'arbitro',
            'gols_casa', 'gols_fora',
            'em_andamento', 'finalizado', 'anulado', 'wo',
            'publico', 'observacoes',
        )
        widgets = {
            'data_hora':    forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': _INPUT}),
            'local':        forms.Select(attrs={'class': _SELECT}),
            'arbitro':      forms.Select(attrs={'class': _SELECT}),
            'gols_casa':    forms.NumberInput(attrs={'class': _INPUT, 'min': 0}),
            'gols_fora':    forms.NumberInput(attrs={'class': _INPUT, 'min': 0}),
            'publico':      forms.NumberInput(attrs={'class': _INPUT, 'min': 0}),
            'observacoes':  forms.Textarea(attrs={'class': _TEXTAREA, 'rows': 3}),
        }
        labels = {
            'gols_casa': 'Gols (mandante)',
            'gols_fora': 'Gols (visitante)',
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('finalizado') and cleaned.get('anulado'):
            raise forms.ValidationError('Um jogo não pode ser finalizado e anulado ao mesmo tempo.')
        if cleaned.get('finalizado') and cleaned.get('em_andamento'):
            raise forms.ValidationError('Um jogo não pode ser finalizado e em andamento ao mesmo tempo.')
        return cleaned


class ArbitrosJogoForm(forms.ModelForm):
    class Meta:
        model = ArbitrosJogo
        fields = ('arbitro', 'tipo')
        widgets = {
            'arbitro': forms.Select(attrs={'class': _SELECT}),
            'tipo':    forms.Select(attrs={'class': _SELECT}),
        }


# ---------------------------------------------------------------------------
# Gol e Cartão
# ---------------------------------------------------------------------------

def _atletas_do_jogo(jogo):
    """Retorna queryset de atletas inscritos ou, se não houver inscrição, todos do jogo."""
    equipes = [jogo.equipe_casa_id, jogo.equipe_fora_id]
    if jogo.rodada_id:
        inscritos_ids = InscricaoAtleta.objects.filter(
            competicao=jogo.rodada.competicao,
            atleta__equipe_id__in=equipes,
        ).values_list('atleta_id', flat=True)
        if inscritos_ids.exists():
            return Atleta.objects.filter(pk__in=inscritos_ids).select_related('equipe').order_by('equipe__nome_equipe', 'nome')
    return Atleta.objects.filter(equipe_id__in=equipes).select_related('equipe').order_by('equipe__nome_equipe', 'nome')


class GolForm(forms.ModelForm):
    class Meta:
        model = Gol
        fields = ('equipe', 'atleta', 'assistencia', 'minuto', 'tipo')
        widgets = {
            'equipe':     forms.Select(attrs={'class': _SELECT, 'id': 'id_equipe_gol'}),
            'atleta':     forms.Select(attrs={'class': _SELECT, 'id': 'id_atleta_gol'}),
            'assistencia':forms.Select(attrs={'class': _SELECT, 'id': 'id_assistencia_gol'}),
            'minuto':     forms.NumberInput(attrs={'class': _INPUT, 'min': 1, 'max': 120}),
            'tipo':       forms.Select(attrs={'class': _SELECT}),
        }

    def __init__(self, *args, jogo=None, **kwargs):
        super().__init__(*args, **kwargs)
        if jogo:
            self.fields['equipe'].queryset = Equipe.objects.filter(
                pk__in=[jogo.equipe_casa_id, jogo.equipe_fora_id]
            )
            atletas = _atletas_do_jogo(jogo)
            self.fields['atleta'].queryset = atletas
            self.fields['atleta'].required = False
            self.fields['assistencia'].queryset = atletas
            self.fields['assistencia'].required = False


class CartaoForm(forms.ModelForm):
    class Meta:
        model = Cartao
        fields = ('jogador', 'minuto', 'tipo')
        widgets = {
            'jogador': forms.Select(attrs={'class': _SELECT}),
            'minuto':  forms.NumberInput(attrs={'class': _INPUT, 'min': 1, 'max': 120}),
            'tipo':    forms.Select(attrs={'class': _SELECT}),
        }

    def __init__(self, *args, jogo=None, **kwargs):
        super().__init__(*args, **kwargs)
        if jogo:
            self.fields['jogador'].queryset = _atletas_do_jogo(jogo)


# ---------------------------------------------------------------------------
# Inscrição de Atletas
# ---------------------------------------------------------------------------

class InscricaoAtletaForm(forms.ModelForm):
    class Meta:
        model = InscricaoAtleta
        fields = ('atleta', 'numero_camisa')
        widgets = {
            'atleta':        forms.Select(attrs={'class': _SELECT}),
            'numero_camisa': forms.NumberInput(attrs={'class': _INPUT, 'min': 1, 'max': 99}),
        }


# ---------------------------------------------------------------------------
# Avaliação do Árbitro
# ---------------------------------------------------------------------------

class AvaliacaoArbitroForm(forms.ModelForm):
    class Meta:
        model = AvaliacaoArbitro
        fields = ('nota', 'observacoes')
        widgets = {
            'nota':        forms.NumberInput(attrs={'class': _INPUT, 'min': 1, 'max': 10}),
            'observacoes': forms.Textarea(attrs={'class': _TEXTAREA, 'rows': 2}),
        }


# ---------------------------------------------------------------------------
# Fases, Grupos, Mata-Mata
# ---------------------------------------------------------------------------

class FaseForm(forms.ModelForm):
    class Meta:
        model = Fase
        fields = ('nome', 'tipo', 'ordem', 'ida_e_volta', 'qtd_classificados_por_grupo')
        widgets = {
            'nome':                       forms.TextInput(attrs={'class': _INPUT}),
            'tipo':                       forms.Select(attrs={'class': _SELECT}),
            'ordem':                      forms.NumberInput(attrs={'class': _INPUT, 'min': 1}),
            'qtd_classificados_por_grupo':forms.NumberInput(attrs={'class': _INPUT, 'min': 1}),
        }
        labels = {
            'qtd_classificados_por_grupo': 'Classificados por grupo',
        }


class GrupoForm(forms.ModelForm):
    class Meta:
        model = Grupo
        fields = ('nome',)
        widgets = {
            'nome': forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Ex: A'}),
        }


class ConfrontoPenaltisForm(forms.ModelForm):
    class Meta:
        model = ConfrontoMatamate
        fields = ('penaltis_mandante', 'penaltis_visitante')
        widgets = {
            'penaltis_mandante':  forms.NumberInput(attrs={'class': _INPUT, 'min': 0}),
            'penaltis_visitante': forms.NumberInput(attrs={'class': _INPUT, 'min': 0}),
        }
        labels = {
            'penaltis_mandante':  'Pênaltis (mandante)',
            'penaltis_visitante': 'Pênaltis (visitante)',
        }


# ---------------------------------------------------------------------------
# Local e Árbitro
# ---------------------------------------------------------------------------

class LocalForm(forms.ModelForm):
    class Meta:
        model = Local
        fields = ('nome', 'endereco', 'cidade', 'capacidade')
        widgets = {
            'nome':       forms.TextInput(attrs={'class': _INPUT}),
            'endereco':   forms.TextInput(attrs={'class': _INPUT}),
            'cidade':     forms.TextInput(attrs={'class': _INPUT}),
            'capacidade': forms.NumberInput(attrs={'class': _INPUT, 'min': 0}),
        }


class ArbitroForm(forms.ModelForm):
    class Meta:
        model = Arbitro
        fields = (
            'nome', 'categoria', 'disponibilidade', 'ativo',
            'cpf', 'data_nascimento', 'foto', 'certificacoes', 'observacao',
            'taxa_por_partida', 'diaria', 'alimentacao', 'hospedagem', 'deslocamento',
        )
        widgets = {
            'nome':             forms.TextInput(attrs={'class': _INPUT}),
            'categoria':        forms.Select(attrs={'class': _SELECT}),
            'disponibilidade':  forms.Select(attrs={'class': _SELECT}),
            'cpf':              forms.TextInput(attrs={'class': _INPUT, 'placeholder': '000.000.000-00'}),
            'data_nascimento':  forms.DateInput(attrs={'type': 'date', 'class': _INPUT}),
            'certificacoes':    forms.Textarea(attrs={'class': _TEXTAREA, 'rows': 3}),
            'observacao':       forms.Textarea(attrs={'class': _TEXTAREA, 'rows': 2}),
            'taxa_por_partida': forms.NumberInput(attrs={'class': _INPUT, 'step': '0.01', 'min': 0}),
            'diaria':           forms.NumberInput(attrs={'class': _INPUT, 'step': '0.01', 'min': 0}),
            'alimentacao':      forms.NumberInput(attrs={'class': _INPUT, 'step': '0.01', 'min': 0}),
            'hospedagem':       forms.NumberInput(attrs={'class': _INPUT, 'step': '0.01', 'min': 0}),
            'deslocamento':     forms.NumberInput(attrs={'class': _INPUT, 'step': '0.01', 'min': 0}),
        }


# ---------------------------------------------------------------------------
# Escalação e Substituições
# ---------------------------------------------------------------------------

class EscalacaoJogoForm(forms.ModelForm):
    class Meta:
        model = EscalacaoJogo
        fields = ('atleta', 'titular', 'numero_camisa', 'capitao')
        widgets = {
            'atleta':        forms.Select(attrs={'class': _SELECT}),
            'numero_camisa': forms.NumberInput(attrs={'class': _INPUT, 'min': 1, 'max': 99}),
        }

    def __init__(self, *args, jogo=None, equipe=None, **kwargs):
        super().__init__(*args, **kwargs)
        if jogo and equipe:
            ja_escalados = EscalacaoJogo.objects.filter(jogo=jogo).values_list('atleta_id', flat=True)
            self.fields['atleta'].queryset = (
                _atletas_do_jogo(jogo).filter(equipe=equipe).exclude(pk__in=ja_escalados)
            )


class SubstituicaoForm(forms.ModelForm):
    class Meta:
        model = Substituicao
        fields = ('equipe', 'atleta_entra', 'atleta_sai', 'minuto')
        widgets = {
            'equipe':       forms.Select(attrs={'class': _SELECT, 'id': 'id_equipe_sub'}),
            'atleta_entra': forms.Select(attrs={'class': _SELECT, 'id': 'id_entra_sub'}),
            'atleta_sai':   forms.Select(attrs={'class': _SELECT, 'id': 'id_sai_sub'}),
            'minuto':       forms.NumberInput(attrs={'class': _INPUT, 'min': 1, 'max': 120}),
        }

    def __init__(self, *args, jogo=None, **kwargs):
        super().__init__(*args, **kwargs)
        if jogo:
            self.fields['equipe'].queryset = Equipe.objects.filter(
                pk__in=[jogo.equipe_casa_id, jogo.equipe_fora_id]
            )
            self.fields['atleta_entra'].queryset = _atletas_do_jogo(jogo)
            self.fields['atleta_sai'].queryset = _atletas_do_jogo(jogo)


# ---------------------------------------------------------------------------
# Súmula Digital — Fase 3
# ---------------------------------------------------------------------------

class SumulaDigitalForm(forms.ModelForm):
    class Meta:
        model = SumulaDigital
        fields = ('condicao_climatica', 'condicao_campo', 'relatorio_narrativo')
        widgets = {
            'condicao_climatica':   forms.Select(attrs={'class': _SELECT}),
            'condicao_campo':       forms.Select(attrs={'class': _SELECT}),
            'relatorio_narrativo':  forms.Textarea(attrs={
                'class': _TEXTAREA, 'rows': 6,
                'placeholder': 'Relate aqui o ocorrido durante a partida, incidentes, observações do árbitro...',
            }),
        }
        labels = {
            'condicao_climatica':  'Condição climática',
            'condicao_campo':      'Condição do campo',
            'relatorio_narrativo': 'Relatório narrativo',
        }


class OcorrenciaForm(forms.ModelForm):
    class Meta:
        model = OcorrenciaSumula
        fields = ('tipo', 'minuto', 'descricao')
        widgets = {
            'tipo':     forms.Select(attrs={'class': _SELECT}),
            'minuto':   forms.NumberInput(attrs={'class': _INPUT, 'min': 1, 'max': 120, 'placeholder': 'Min.'}),
            'descricao':forms.Textarea(attrs={'class': _TEXTAREA, 'rows': 2, 'placeholder': 'Descreva o ocorrido com detalhes...'}),
        }
        labels = {
            'tipo':     'Tipo de ocorrência',
            'minuto':   'Minuto (opcional)',
            'descricao':'Descrição',
        }


class AnexoSumulaForm(forms.ModelForm):
    class Meta:
        model = AnexoSumula
        fields = ('arquivo', 'tipo', 'descricao')
        widgets = {
            'arquivo':  forms.FileInput(attrs={'class': 'file-input file-input-bordered w-full'}),
            'tipo':     forms.Select(attrs={'class': _SELECT}),
            'descricao':forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Descreva o conteúdo do arquivo...'}),
        }
        labels = {
            'arquivo':  'Arquivo (foto, vídeo ou PDF)',
            'tipo':     'Tipo de arquivo',
            'descricao':'Descrição',
        }


class AssinaturaForm(forms.Form):
    nome_assinante = forms.CharField(
        max_length=200,
        label='Nome completo do assinante',
        widget=forms.TextInput(attrs={
            'class': _INPUT,
            'placeholder': 'Digite o nome completo...',
            'autocomplete': 'name',
        }),
    )


# ---------------------------------------------------------------------------
# Tribunal Desportivo — Fase 4
# ---------------------------------------------------------------------------

class ProcessoDesportivoForm(forms.ModelForm):
    class Meta:
        model = ProcessoDesportivo
        fields = (
            'tipo', 'competicao', 'jogo', 'denunciante',
            'denunciado_atleta', 'denunciado_equipe',
            'descricao', 'prazo_defesa',
        )
        widgets = {
            'tipo':              forms.Select(attrs={'class': _SELECT}),
            'competicao':        forms.Select(attrs={'class': _SELECT}),
            'jogo':              forms.Select(attrs={'class': _SELECT}),
            'denunciante':       forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Nome do denunciante / entidade...'}),
            'denunciado_atleta': forms.Select(attrs={'class': _SELECT}),
            'denunciado_equipe': forms.Select(attrs={'class': _SELECT}),
            'descricao':         forms.Textarea(attrs={'class': _TEXTAREA, 'rows': 5, 'placeholder': 'Relate os fatos em detalhes...'}),
            'prazo_defesa':      forms.DateInput(attrs={'type': 'date', 'class': _INPUT}),
        }
        labels = {
            'tipo':              'Tipo de processo',
            'competicao':        'Competição',
            'jogo':              'Partida relacionada (opcional)',
            'denunciante':       'Denunciante / Requerente',
            'denunciado_atleta': 'Atleta denunciado (opcional)',
            'denunciado_equipe': 'Equipe denunciada (opcional)',
            'descricao':         'Descrição dos fatos',
            'prazo_defesa':      'Prazo para defesa (opcional)',
        }


class JulgamentoForm(forms.ModelForm):
    class Meta:
        model = Julgamento
        fields = (
            'relator', 'penalidade', 'descricao',
            'valor_multa', 'jogos_suspensao', 'pontos_perdidos',
            'aplicar_suspensao',
        )
        widgets = {
            'relator':           forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Nome do relator / juiz...'}),
            'penalidade':        forms.Select(attrs={'class': _SELECT}),
            'descricao':         forms.Textarea(attrs={'class': _TEXTAREA, 'rows': 5, 'placeholder': 'Fundamente a decisão...'}),
            'valor_multa':       forms.NumberInput(attrs={'class': _INPUT, 'step': '0.01', 'min': 0, 'placeholder': '0,00'}),
            'jogos_suspensao':   forms.NumberInput(attrs={'class': _INPUT, 'min': 1, 'placeholder': 'Nº de partidas'}),
            'pontos_perdidos':   forms.NumberInput(attrs={'class': _INPUT, 'min': 1, 'placeholder': 'Pontos a deduzir'}),
        }
        labels = {
            'relator':           'Relator / Juiz',
            'penalidade':        'Penalidade aplicada',
            'descricao':         'Fundamentação e decisão',
            'valor_multa':       'Valor da multa (R$)',
            'jogos_suspensao':   'Partidas de suspensão',
            'pontos_perdidos':   'Pontos a deduzir',
            'aplicar_suspensao': 'Gerar suspensão automática no sistema',
        }


class RecursoDesportivoForm(forms.ModelForm):
    class Meta:
        model = RecursoDesportivo
        fields = ('recorrente', 'motivo', 'data_prazo')
        widgets = {
            'recorrente': forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Nome do recorrente...'}),
            'motivo':     forms.Textarea(attrs={'class': _TEXTAREA, 'rows': 4, 'placeholder': 'Fundamente o recurso...'}),
            'data_prazo': forms.DateInput(attrs={'type': 'date', 'class': _INPUT}),
        }
        labels = {
            'recorrente': 'Recorrente',
            'motivo':     'Fundamentos do recurso',
            'data_prazo': 'Prazo para decisão (opcional)',
        }


class RecursoDecisaoForm(forms.ModelForm):
    class Meta:
        model = RecursoDesportivo
        fields = ('status', 'decisao')
        widgets = {
            'status':  forms.Select(attrs={'class': _SELECT}),
            'decisao': forms.Textarea(attrs={'class': _TEXTAREA, 'rows': 4, 'placeholder': 'Fundamente a decisão...'}),
        }
        labels = {
            'status':  'Resultado do recurso',
            'decisao': 'Fundamentação da decisão',
        }


# ---------------------------------------------------------------------------
# Financeiro Federativo — Fase 5
# ---------------------------------------------------------------------------

class LancamentoFinanceiroForm(forms.ModelForm):
    class Meta:
        model = LancamentoFinanceiro
        fields = (
            'tipo', 'categoria', 'descricao', 'valor',
            'data_vencimento', 'forma_pagamento', 'numero_referencia',
            'competicao', 'equipe', 'atleta',
            'observacoes',
        )
        widgets = {
            'tipo':             forms.Select(attrs={'class': _SELECT, 'id': 'id_tipo_fin'}),
            'categoria':        forms.Select(attrs={'class': _SELECT, 'id': 'id_categoria_fin'}),
            'descricao':        forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Descreva o lançamento...'}),
            'valor':            forms.NumberInput(attrs={'class': _INPUT, 'step': '0.01', 'min': '0.01', 'placeholder': '0,00'}),
            'data_vencimento':  forms.DateInput(attrs={'type': 'date', 'class': _INPUT}),
            'forma_pagamento':  forms.Select(attrs={'class': _SELECT}),
            'numero_referencia':forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Chave PIX, nº boleto...'}),
            'competicao':       forms.Select(attrs={'class': _SELECT}),
            'equipe':           forms.Select(attrs={'class': _SELECT}),
            'atleta':           forms.Select(attrs={'class': _SELECT}),
            'observacoes':      forms.Textarea(attrs={'class': _TEXTAREA, 'rows': 3}),
        }
        labels = {
            'tipo':             'Tipo',
            'categoria':        'Categoria',
            'descricao':        'Descrição',
            'valor':            'Valor (R$)',
            'data_vencimento':  'Data de vencimento',
            'forma_pagamento':  'Forma de pagamento (opcional)',
            'numero_referencia':'Referência (opcional)',
            'competicao':       'Competição (opcional)',
            'equipe':           'Equipe (opcional)',
            'atleta':           'Atleta (opcional)',
            'observacoes':      'Observações',
        }


class BaixarPagamentoForm(forms.ModelForm):
    class Meta:
        model = LancamentoFinanceiro
        fields = ('data_pagamento', 'forma_pagamento', 'numero_referencia', 'comprovante', 'observacoes')
        widgets = {
            'data_pagamento':   forms.DateInput(attrs={'type': 'date', 'class': _INPUT}),
            'forma_pagamento':  forms.Select(attrs={'class': _SELECT}),
            'numero_referencia':forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'ID PIX, nº boleto...'}),
            'comprovante':      forms.FileInput(attrs={'class': 'file-input file-input-bordered w-full'}),
            'observacoes':      forms.Textarea(attrs={'class': _TEXTAREA, 'rows': 2}),
        }
        labels = {
            'data_pagamento':   'Data do pagamento',
            'forma_pagamento':  'Forma de pagamento',
            'numero_referencia':'Nº de referência / ID da transação',
            'comprovante':      'Comprovante (foto ou PDF)',
            'observacoes':      'Observações',
        }


class PublicacaoForm(forms.ModelForm):
    class Meta:
        model = Publicacao
        fields = ('tipo', 'titulo', 'resumo', 'conteudo', 'imagem_capa', 'arquivo', 'publicado', 'destaque')
        widgets = {
            'tipo':        forms.Select(attrs={'class': _SELECT}),
            'titulo':      forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Título da publicação'}),
            'resumo':      forms.Textarea(attrs={'class': _TEXTAREA, 'rows': 2, 'placeholder': 'Breve resumo (exibido na listagem)'}),
            'conteudo':    forms.Textarea(attrs={'class': _TEXTAREA, 'rows': 10, 'placeholder': 'Texto completo...'}),
            'imagem_capa': forms.FileInput(attrs={'class': 'file-input file-input-bordered w-full'}),
            'arquivo':     forms.FileInput(attrs={'class': 'file-input file-input-bordered w-full'}),
            'publicado':   forms.CheckboxInput(attrs={'class': 'toggle toggle-success'}),
            'destaque':    forms.CheckboxInput(attrs={'class': 'toggle toggle-warning'}),
        }
        labels = {
            'tipo':        'Tipo',
            'titulo':      'Título',
            'resumo':      'Resumo',
            'conteudo':    'Conteúdo',
            'imagem_capa': 'Imagem de capa',
            'arquivo':     'Arquivo (PDF, DOC…)',
            'publicado':   'Publicado',
            'destaque':    'Destaque (exibir em destaque no portal)',
        }

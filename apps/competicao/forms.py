from django import forms
from django.forms import DateInput

from ..competicao.models import (
    Competicao, Jogo, Cartao, Gol, InscricaoAtleta,
    Fase, Grupo, ConfrontoMatamate, Local, Arbitro,
    EscalacaoJogo, Substituicao, ArbitrosJogo, AvaliacaoArbitro,
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
        fields = ('nome', 'categoria')
        widgets = {
            'nome':      forms.TextInput(attrs={'class': _INPUT}),
            'categoria': forms.TextInput(attrs={'class': _INPUT}),
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

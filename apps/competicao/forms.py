from django import forms
from django.forms import DateInput

from ..competicao.models import (
    Competicao, Jogo, Cartao, Gol, InscricaoAtleta,
    EtapaKnockout, Grupo, ConfrontoMatamate, Local,
    Sumula, EscalacaoJogo, SubstituicaoJogo, OcorrenciaJogo, ApiKey,
)
from ..core.models import UsuarioFederacao
from ..criterios.models import CriterioClassificacao, FormatoCompeticao
from ..equipe.models import Equipe, Atleta

_INPUT    = 'form-input'
_SELECT   = 'form-select'
_TEXTAREA = 'form-textarea'
_CHECKBOX = 'w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 focus:ring-2 dark:bg-gray-700 dark:border-gray-600 dark:focus:ring-blue-600 dark:ring-offset-gray-800'


class CompeticaoForm(forms.ModelForm):
    class Meta:
        model = Competicao
        fields = (
            'nome', 'descricao', 'data_inicio', 'data_fim',
            'categoria', 'genero', 'modalidade',
            'data_abertura_inscricao', 'data_encerramento_inscricao',
            'limite_atletas', 'taxa_inscricao',
            'formato', 'criterio_classificacao',
        )
        widgets = {
            'nome':                         forms.TextInput(attrs={'class': _INPUT}),
            'descricao':                    forms.Textarea(attrs={'class': _TEXTAREA, 'rows': 2}),
            'data_inicio':                  DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': _INPUT}),
            'data_fim':                     DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': _INPUT}),
            'categoria':                    forms.Select(attrs={'class': _SELECT}),
            'genero':                       forms.Select(attrs={'class': _SELECT}),
            'modalidade':                   forms.Select(attrs={'class': _SELECT}),
            'data_abertura_inscricao':      DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': _INPUT}),
            'data_encerramento_inscricao':  DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': _INPUT}),
            'limite_atletas':               forms.NumberInput(attrs={'class': _INPUT, 'min': 0}),
            'taxa_inscricao':               forms.NumberInput(attrs={'class': _INPUT, 'step': '0.01', 'min': 0}),
            'formato':                      forms.Select(attrs={'class': _SELECT}),
            'criterio_classificacao':       forms.Select(attrs={'class': _SELECT}),
        }

    def __init__(self, *args, federacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        if federacao:
            self.fields['formato'].queryset = FormatoCompeticao.objects.filter(federacao=federacao)
            self.fields['criterio_classificacao'].queryset = CriterioClassificacao.objects.filter(federacao=federacao)
        else:
            self.fields['formato'].queryset = FormatoCompeticao.objects.none()
            self.fields['criterio_classificacao'].queryset = CriterioClassificacao.objects.none()
        self.fields['formato'].required = False
        self.fields['formato'].empty_label = '— Nenhum —'
        self.fields['criterio_classificacao'].required = False
        self.fields['criterio_classificacao'].empty_label = '— Nenhum —'


class AssociarEquipeForm(forms.Form):
    equipe_id = forms.IntegerField(widget=forms.HiddenInput())


class JogoResultadoForm(forms.ModelForm):
    class Meta:
        model = Jogo
        fields = ('gols_casa', 'gols_fora', 'publico', 'observacoes')
        widgets = {
            'gols_casa':   forms.NumberInput(attrs={'class': _INPUT, 'min': 0}),
            'gols_fora':   forms.NumberInput(attrs={'class': _INPUT, 'min': 0}),
            'publico':     forms.NumberInput(attrs={'class': _INPUT, 'min': 0}),
            'observacoes': forms.Textarea(attrs={'class': _TEXTAREA, 'rows': 3}),
        }

    def __init__(self, *args, federacao=None, **kwargs):
        super().__init__(*args, **kwargs)


class JogoConfigForm(forms.ModelForm):
    class Meta:
        model = Jogo
        fields = ('data_hora', 'local', 'arbitro')
        widgets = {
            'data_hora': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local', 'class': _INPUT}),
            'local':     forms.Select(attrs={'class': _SELECT}),
            'arbitro':   forms.Select(attrs={'class': _SELECT}),
        }

    def __init__(self, *args, federacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        if federacao is not None:
            self.fields['local'].queryset = Local.objects.filter(federacao=federacao)
            self.fields['arbitro'].queryset = UsuarioFederacao.objects.filter(
                federacao=federacao, papel=UsuarioFederacao.ARBITRO, ativo=True,
            ).select_related('usuario').order_by('usuario__nome')
        else:
            self.fields['local'].queryset = Local.objects.none()
            self.fields['arbitro'].queryset = UsuarioFederacao.objects.none()
        self.fields['local'].required = False
        self.fields['local'].empty_label = '— Sem local definido —'
        self.fields['arbitro'].required = False
        self.fields['arbitro'].empty_label = '— Sem árbitro definido —'


def _atletas_do_jogo(jogo):
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
            'equipe':      forms.Select(attrs={'class': _SELECT, 'id': 'id_equipe_gol'}),
            'atleta':      forms.Select(attrs={'class': _SELECT, 'id': 'id_atleta_gol'}),
            'assistencia': forms.Select(attrs={'class': _SELECT, 'id': 'id_assistencia_gol'}),
            'minuto':      forms.NumberInput(attrs={'class': _INPUT, 'min': 1, 'max': 120}),
            'tipo':        forms.Select(attrs={'class': _SELECT}),
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


class _AtletaComPosicaoField(forms.ModelChoiceField):
    _SIGLAS = {
        'GOLEIRO':          'GOL', 'ZAGUEIRO':         'ZAG',
        'LATERAL_DIREIRO':  'LD',  'LATERAL_ESQUERDO': 'LE',
        'VOLANTE':          'VOL', 'MEIO_CAMPO':        'MEI',
        'MEIA_ATACANTE':    'MAT', 'PONTA_DIREITA':     'AD',
        'PONTA_ESQUERDA':   'AE',  'ATACANTE':          'ATA',
    }

    def label_from_instance(self, obj):
        sigla = self._SIGLAS.get(obj.posicao, '—')
        return f'({sigla}) {obj.nome}'


class InscricaoAtletaForm(forms.ModelForm):
    atleta = _AtletaComPosicaoField(
        queryset=Atleta.objects.none(),
        widget=forms.Select(attrs={'class': _SELECT}),
    )

    class Meta:
        model = InscricaoAtleta
        fields = ('atleta', 'numero_camisa')
        widgets = {
            'numero_camisa': forms.NumberInput(attrs={'class': _INPUT, 'min': 1, 'max': 99}),
        }

    def __init__(self, *args, competicao=None, equipe=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._competicao = competicao
        self._equipe = equipe
        if competicao and equipe:
            ja_inscritos = InscricaoAtleta.objects.filter(competicao=competicao).values_list('atleta_id', flat=True)
            self.fields['atleta'].queryset = (
                Atleta.objects.filter(equipe=equipe).exclude(pk__in=ja_inscritos).order_by('posicao', 'nome')
            )

    def clean_numero_camisa(self):
        numero = self.cleaned_data.get('numero_camisa')
        if numero and self._competicao and self._equipe:
            duplicado = InscricaoAtleta.objects.filter(
                competicao=self._competicao,
                atleta__equipe=self._equipe,
                numero_camisa=numero,
            ).exists()
            if duplicado:
                raise forms.ValidationError(f'Camisa {numero} já está em uso nesta competição.')
        return numero


class EtapaKnockoutForm(forms.ModelForm):
    class Meta:
        model = EtapaKnockout
        fields = ('tipo', 'ida_e_volta')
        widgets = {
            'tipo': forms.Select(attrs={'class': _SELECT}),
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

    def clean(self):
        cleaned = super().clean()
        pm = cleaned.get('penaltis_mandante')
        pv = cleaned.get('penaltis_visitante')
        if pm is not None and pv is not None and pm == pv:
            raise forms.ValidationError('Pênaltis não podem terminar empatados.')
        return cleaned


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


# ---------------------------------------------------------------------------
# Súmula Digital
# ---------------------------------------------------------------------------

class SumulaArbitragemForm(forms.ModelForm):
    class Meta:
        model = Sumula
        fields = (
            'arbitro_principal', 'arbitro_assistente_1',
            'arbitro_assistente_2', 'quarto_arbitro',
            'observacoes_arbitro',
        )
        widgets = {
            'arbitro_principal':    forms.Select(attrs={'class': _SELECT}),
            'arbitro_assistente_1': forms.Select(attrs={'class': _SELECT}),
            'arbitro_assistente_2': forms.Select(attrs={'class': _SELECT}),
            'quarto_arbitro':       forms.Select(attrs={'class': _SELECT}),
            'observacoes_arbitro':  forms.Textarea(attrs={'class': _TEXTAREA, 'rows': 3}),
        }

    def __init__(self, *args, federacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        arbitros_qs = UsuarioFederacao.objects.none()
        if federacao:
            arbitros_qs = (
                UsuarioFederacao.objects
                .filter(federacao=federacao, papel=UsuarioFederacao.ARBITRO, ativo=True)
                .select_related('usuario').order_by('usuario__nome')
            )
        for field in ('arbitro_principal', 'arbitro_assistente_1', 'arbitro_assistente_2', 'quarto_arbitro'):
            self.fields[field].queryset = arbitros_qs
            self.fields[field].required = False


class EscalacaoJogoForm(forms.ModelForm):
    class Meta:
        model = EscalacaoJogo
        fields = ('atleta', 'numero_camisa', 'tipo', 'capitao')
        widgets = {
            'atleta':        forms.Select(attrs={'class': _SELECT}),
            'numero_camisa': forms.NumberInput(attrs={'class': _INPUT, 'min': 1, 'max': 99}),
            'tipo':          forms.Select(attrs={'class': _SELECT}),
        }

    def __init__(self, *args, sumula=None, equipe=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._competicao = None
        if sumula and equipe:
            jogo = sumula.jogo
            comp = jogo.rodada.competicao if jogo.rodada_id else None
            self._competicao = comp
            ja_na_sumula = sumula.escalacao.values_list('atleta_id', flat=True)
            if comp:
                from .models import Suspensao
                inscritos_ids = InscricaoAtleta.objects.filter(
                    competicao=comp, atleta__equipe=equipe,
                ).values_list('atleta_id', flat=True)
                suspensos_ids = Suspensao.objects.filter(
                    competicao=comp, cumprida=False,
                ).values_list('atleta_id', flat=True)
                qs = Atleta.objects.filter(pk__in=inscritos_ids).exclude(
                    pk__in=suspensos_ids,
                )
            else:
                qs = Atleta.objects.filter(equipe=equipe)
            self.fields['atleta'].queryset = qs.exclude(pk__in=ja_na_sumula).order_by('nome')

    def clean_atleta(self):
        atleta = self.cleaned_data['atleta']
        if self._competicao and atleta.esta_suspenso(self._competicao):
            raise forms.ValidationError(
                f'{atleta.nome} está suspenso e não pode ser escalado.'
            )
        return atleta


class SubstituicaoJogoForm(forms.ModelForm):
    class Meta:
        model = SubstituicaoJogo
        fields = ('atleta_saiu', 'atleta_entrou', 'minuto')
        widgets = {
            'atleta_saiu':   forms.Select(attrs={'class': _SELECT}),
            'atleta_entrou': forms.Select(attrs={'class': _SELECT}),
            'minuto':        forms.NumberInput(attrs={'class': _INPUT, 'min': 1, 'max': 120}),
        }

    def __init__(self, *args, sumula=None, equipe=None, **kwargs):
        super().__init__(*args, **kwargs)
        if sumula and equipe:
            jogo = sumula.jogo
            comp = jogo.rodada.competicao if jogo.rodada_id else None
            if comp:
                ids = InscricaoAtleta.objects.filter(
                    competicao=comp, atleta__equipe=equipe,
                ).values_list('atleta_id', flat=True)
                qs = Atleta.objects.filter(pk__in=ids).order_by('nome')
            else:
                qs = Atleta.objects.filter(equipe=equipe).order_by('nome')
            self.fields['atleta_saiu'].queryset = qs
            self.fields['atleta_entrou'].queryset = qs


class OcorrenciaJogoForm(forms.ModelForm):
    class Meta:
        model = OcorrenciaJogo
        fields = ('tipo', 'descricao', 'minuto')
        widgets = {
            'tipo':     forms.Select(attrs={'class': _SELECT}),
            'descricao': forms.Textarea(attrs={'class': _TEXTAREA, 'rows': 2}),
            'minuto':   forms.NumberInput(attrs={'class': _INPUT, 'min': 1, 'max': 200}),
        }


# ---------------------------------------------------------------------------
# Temporada
# ---------------------------------------------------------------------------

class TemporadaForm(forms.Form):
    ano  = forms.IntegerField(min_value=2000, max_value=2100, widget=forms.NumberInput(attrs={'class': _INPUT}))
    nome = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Ex: 2025'}))
    ativa = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': _CHECKBOX}))


# ---------------------------------------------------------------------------
# API Key
# ---------------------------------------------------------------------------

class ApiKeyForm(forms.ModelForm):
    class Meta:
        model = ApiKey
        fields = ('nome',)
        widgets = {
            'nome': forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Ex: App Mobile'}),
        }



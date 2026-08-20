from django import forms
from .models import CriterioClassificacao, FormatoCompeticao

_INPUT    = 'form-input'
_NUMBER   = 'form-input w-24'
_CHECKBOX = 'checkbox checkbox-sm'


class FormatoCompeticaoForm(forms.ModelForm):
    class Meta:
        model = FormatoCompeticao
        exclude = ['federacao']
        widgets = {
            'nome':              forms.TextInput(attrs={'class': _INPUT}),
            'pontos_por_vitoria': forms.NumberInput(attrs={'class': _NUMBER, 'min': 1, 'max': 9}),
            'pontos_por_empate':  forms.NumberInput(attrs={'class': _NUMBER, 'min': 0, 'max': 9}),
            'permite_empate':    forms.CheckboxInput(attrs={'class': _CHECKBOX}),
            'pontos_corridos':   forms.CheckboxInput(attrs={'class': _CHECKBOX}),
            'fase_grupos':       forms.CheckboxInput(attrs={'class': _CHECKBOX}),
            'mata_mata':         forms.CheckboxInput(attrs={'class': _CHECKBOX}),
            'turnos':            forms.Select(attrs={'class': 'form-select'}),
            'prorrogacao':       forms.CheckboxInput(attrs={'class': _CHECKBOX}),
            'penaltis':          forms.CheckboxInput(attrs={'class': _CHECKBOX}),
            'qtd_times':         forms.NumberInput(attrs={'class': _NUMBER, 'min': 2}),
        }


class CriterioClassificacaoForm(forms.ModelForm):
    class Meta:
        model = CriterioClassificacao
        exclude = ['federacao']
        widgets = {
            'nome':             forms.TextInput(attrs={'class': _INPUT}),
            'confronto_direto': forms.CheckboxInput(attrs={'class': _CHECKBOX}),
            'vitorias':         forms.CheckboxInput(attrs={'class': _CHECKBOX}),
            'saldo_gols':       forms.CheckboxInput(attrs={'class': _CHECKBOX}),
            'gols_pro':         forms.CheckboxInput(attrs={'class': _CHECKBOX}),
            'gol_fora':         forms.CheckboxInput(attrs={'class': _CHECKBOX}),
            'menor_vermelho':   forms.CheckboxInput(attrs={'class': _CHECKBOX}),
            'menor_amarelo':    forms.CheckboxInput(attrs={'class': _CHECKBOX}),
        }

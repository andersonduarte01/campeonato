from django import forms

from ..criterios.models import FormatoCompeticao, CriterioClassificacao

_INPUT    = 'input input-bordered w-full'
_CHECKBOX = 'checkbox checkbox-sm'


class FormatoCompeticaoForm(forms.ModelForm):
    class Meta:
        model = FormatoCompeticao
        fields = '__all__'
        widgets = {
            'nome':             forms.TextInput(attrs={'class': _INPUT}),
            'qtd_times':        forms.NumberInput(attrs={'class': _INPUT, 'min': 3}),
            'pontos_corridos':  forms.CheckboxInput(attrs={'class': _CHECKBOX}),
            'turno_unico':      forms.CheckboxInput(attrs={'class': _CHECKBOX}),
            'ida_e_volta':      forms.CheckboxInput(attrs={'class': _CHECKBOX}),
            'fase_grupos':      forms.CheckboxInput(attrs={'class': _CHECKBOX}),
            'mata_mata':        forms.CheckboxInput(attrs={'class': _CHECKBOX}),
        }


class CriterioClassificacaoForm(forms.ModelForm):
    class Meta:
        model = CriterioClassificacao
        fields = '__all__'
        widgets = {
            'nome':              forms.TextInput(attrs={'class': _INPUT}),
            'vitorias':          forms.CheckboxInput(attrs={'class': _CHECKBOX}),
            'saldo_gols':        forms.CheckboxInput(attrs={'class': _CHECKBOX}),
            'gol_fora':          forms.CheckboxInput(attrs={'class': _CHECKBOX}),
            'disputa_penaltis':  forms.CheckboxInput(attrs={'class': _CHECKBOX}),
        }

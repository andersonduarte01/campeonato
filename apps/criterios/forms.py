from django import forms
from .models import CRITERIOS_PADRAO, CriterioClassificacao, FormatoCompeticao

_LABELS_CRITERIO = {
    'confronto_direto': 'Confronto Direto',
    'vitorias':         'Número de Vitórias',
    'saldo_gols':       'Saldo de Gols',
    'gols_pro':         'Gols Marcados',
    'gol_fora':         'Gol Fora de Casa',
    'menor_vermelho':   'Menor nº de Cartões Vermelhos',
    'menor_amarelo':    'Menor nº de Cartões Amarelos',
}

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
    """Cada critério tem um checkbox (liga/desliga) e um select de
    prioridade (1..N). `ordem_criterios` não é editado diretamente — é
    derivado dos selects de prioridade no save()."""

    class Meta:
        model = CriterioClassificacao
        exclude = ['federacao', 'ordem_criterios']
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ordem_atual = (self.instance.pk and self.instance.ordem_criterios) or CRITERIOS_PADRAO
        posicao = {chave: i + 1 for i, chave in enumerate(ordem_atual)}
        opcoes = [(i, str(i)) for i in range(1, len(CRITERIOS_PADRAO) + 1)]
        for chave in CRITERIOS_PADRAO:
            self.fields[f'prioridade_{chave}'] = forms.ChoiceField(
                choices=opcoes,
                initial=posicao.get(chave, len(CRITERIOS_PADRAO)),
                label=f'Prioridade — {_LABELS_CRITERIO[chave]}',
                widget=forms.Select(attrs={'class': 'form-select w-20'}),
            )

    def _ordem_dos_campos_prioridade(self):
        pares = [
            (chave, int(self.cleaned_data.get(f'prioridade_{chave}', 99)))
            for chave in CRITERIOS_PADRAO
        ]
        pares.sort(key=lambda par: par[1])
        return [chave for chave, _ in pares]

    def save(self, commit=True):
        instancia = super().save(commit=False)
        instancia.ordem_criterios = self._ordem_dos_campos_prioridade()
        if commit:
            instancia.save()
        return instancia

from django import forms

from apps.equipe.models import Equipe, Atleta
from .models import (
    RegistroFederativo,
    JanelaTransferencia, Transferencia,
)

_INPUT    = 'form-input'
_SELECT   = 'form-select'
_TEXTAREA = 'form-textarea'
_CHECKBOX = 'w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 focus:ring-2 dark:bg-gray-700 dark:border-gray-600'
_FILE     = 'block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-white dark:bg-gray-700 dark:text-gray-400 dark:border-gray-600'


class RegistroFederativoForm(forms.ModelForm):
    class Meta:
        model  = RegistroFederativo
        fields = ['atleta', 'data_filiacao', 'status', 'observacoes']
        widgets = {
            'atleta':        forms.Select(attrs={'class': _SELECT}),
            'data_filiacao': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': _INPUT}),
            'status':        forms.Select(attrs={'class': _SELECT}),
            'observacoes':   forms.Textarea(attrs={'class': _TEXTAREA, 'rows': 3}),
        }

    def __init__(self, *args, federacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Atleta.objects.filter(
            equipe__federacao=federacao,
        ).select_related('equipe').order_by('nome')
        # Só atletas sem registro (ou o atleta do registro em edição)
        if self.instance.pk:
            qs = qs.filter(pk=self.instance.atleta_id) | qs.filter(
                registro_federativo__isnull=True
            )
        else:
            qs = qs.filter(registro_federativo__isnull=True)
        self.fields['atleta'].queryset = qs


class JanelaTransferenciaForm(forms.ModelForm):
    class Meta:
        model  = JanelaTransferencia
        fields = ['nome', 'data_inicio', 'data_fim', 'ativa']
        widgets = {
            'nome':        forms.TextInput(attrs={'class': _INPUT}),
            'data_inicio': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': _INPUT}),
            'data_fim':    forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': _INPUT}),
            'ativa':       forms.CheckboxInput(attrs={'class': _CHECKBOX}),
        }

    def clean(self):
        cleaned = super().clean()
        inicio = cleaned.get('data_inicio')
        fim    = cleaned.get('data_fim')
        if inicio and fim and fim <= inicio:
            raise forms.ValidationError('A data de fim deve ser posterior à data de início.')
        return cleaned


class TransferenciaForm(forms.ModelForm):
    class Meta:
        model  = Transferencia
        fields = ['atleta', 'clube_origem', 'clube_destino', 'tipo', 'janela', 'observacoes']
        widgets = {
            'atleta':        forms.Select(attrs={'class': _SELECT}),
            'clube_origem':  forms.Select(attrs={'class': _SELECT}),
            'clube_destino': forms.Select(attrs={'class': _SELECT}),
            'tipo':          forms.Select(attrs={'class': _SELECT}),
            'janela':        forms.Select(attrs={'class': _SELECT}),
            'observacoes':   forms.Textarea(attrs={'class': _TEXTAREA, 'rows': 3}),
        }

    def __init__(self, *args, federacao=None, **kwargs):
        import datetime
        super().__init__(*args, **kwargs)
        hoje   = datetime.date.today()
        equipes = Equipe.objects.filter(federacao=federacao).order_by('nome_equipe')
        self.fields['atleta'].queryset = Atleta.objects.filter(
            equipe__federacao=federacao,
        ).select_related('equipe').order_by('nome')
        self.fields['clube_origem'].queryset  = equipes
        self.fields['clube_destino'].queryset = equipes
        janelas_abertas = JanelaTransferencia.objects.filter(
            federacao=federacao, ativa=True,
            data_inicio__lte=hoje, data_fim__gte=hoje,
        ).order_by('-data_inicio')
        self.fields['janela'].queryset = janelas_abertas
        self.fields['janela'].required = True
        self.fields['janela'].empty_label = None

    def clean(self):
        import datetime
        cleaned = super().clean()
        origem  = cleaned.get('clube_origem')
        destino = cleaned.get('clube_destino')
        if origem and destino and origem == destino:
            raise forms.ValidationError('Clube de origem e destino não podem ser iguais.')
        atleta = cleaned.get('atleta')
        origem = cleaned.get('clube_origem')
        if atleta and origem and atleta.equipe_id != origem.pk:
            self.add_error('clube_origem', 'O clube de origem deve ser o clube atual do atleta.')
        janela = cleaned.get('janela')
        if janela:
            hoje = datetime.date.today()
            if not (janela.ativa and janela.data_inicio <= hoje <= janela.data_fim):
                raise forms.ValidationError('A janela selecionada não está aberta.')
        return cleaned

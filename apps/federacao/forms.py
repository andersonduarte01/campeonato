from django import forms

from apps.equipe.models import Equipe, Atleta
from .models import (
    RegistroFederativo, HistoricoClube,
    JanelaTransferencia, Transferencia,
    InfoClube, TipoDocumento, Documento,
)


class RegistroFederativoForm(forms.ModelForm):
    class Meta:
        model  = RegistroFederativo
        fields = ['atleta', 'data_filiacao', 'status', 'observacoes']
        widgets = {
            'atleta':       forms.Select(attrs={'class': 'select select-sm w-full bg-base-200 border-base-300'}),
            'data_filiacao': forms.DateInput(attrs={'type': 'date', 'class': 'input input-sm w-full bg-base-200 border-base-300'}),
            'status':       forms.Select(attrs={'class': 'select select-sm w-full bg-base-200 border-base-300'}),
            'observacoes':  forms.Textarea(attrs={'class': 'textarea textarea-sm w-full bg-base-200 border-base-300', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show athletes without an existing registration (or the current one)
        qs = Atleta.objects.select_related('equipe').order_by('nome')
        if self.instance.pk:
            qs = qs.filter(pk=self.instance.atleta_id) | qs.filter(
                registro_federativo__isnull=True
            )
        else:
            qs = qs.filter(registro_federativo__isnull=True)
        self.fields['atleta'].queryset = qs


class HistoricoClubeForm(forms.ModelForm):
    class Meta:
        model  = HistoricoClube
        fields = ['atleta', 'equipe', 'tipo', 'data_entrada', 'data_saida', 'observacoes']
        widgets = {
            'atleta':       forms.Select(attrs={'class': 'select select-sm w-full bg-base-200 border-base-300'}),
            'equipe':       forms.Select(attrs={'class': 'select select-sm w-full bg-base-200 border-base-300'}),
            'tipo':         forms.Select(attrs={'class': 'select select-sm w-full bg-base-200 border-base-300'}),
            'data_entrada': forms.DateInput(attrs={'type': 'date', 'class': 'input input-sm w-full bg-base-200 border-base-300'}),
            'data_saida':   forms.DateInput(attrs={'type': 'date', 'class': 'input input-sm w-full bg-base-200 border-base-300'}),
            'observacoes':  forms.Textarea(attrs={'class': 'textarea textarea-sm w-full bg-base-200 border-base-300', 'rows': 2}),
        }


class JanelaTransferenciaForm(forms.ModelForm):
    class Meta:
        model  = JanelaTransferencia
        fields = ['nome', 'data_inicio', 'data_fim', 'ativa']
        widgets = {
            'nome':        forms.TextInput(attrs={'class': 'input input-sm w-full bg-base-200 border-base-300'}),
            'data_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'input input-sm w-full bg-base-200 border-base-300'}),
            'data_fim':    forms.DateInput(attrs={'type': 'date', 'class': 'input input-sm w-full bg-base-200 border-base-300'}),
            'ativa':       forms.CheckboxInput(attrs={'class': 'checkbox checkbox-sm checkbox-warning'}),
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
            'atleta':        forms.Select(attrs={'class': 'select select-sm w-full bg-base-200 border-base-300'}),
            'clube_origem':  forms.Select(attrs={'class': 'select select-sm w-full bg-base-200 border-base-300'}),
            'clube_destino': forms.Select(attrs={'class': 'select select-sm w-full bg-base-200 border-base-300'}),
            'tipo':          forms.Select(attrs={'class': 'select select-sm w-full bg-base-200 border-base-300'}),
            'janela':        forms.Select(attrs={'class': 'select select-sm w-full bg-base-200 border-base-300'}),
            'observacoes':   forms.Textarea(attrs={'class': 'textarea textarea-sm w-full bg-base-200 border-base-300', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['janela'].queryset = JanelaTransferencia.objects.filter(ativa=True).order_by('-data_inicio')
        self.fields['janela'].required = False
        self.fields['atleta'].queryset = Atleta.objects.select_related('equipe').order_by('nome')

    def clean(self):
        cleaned = super().clean()
        origem  = cleaned.get('clube_origem')
        destino = cleaned.get('clube_destino')
        if origem and destino and origem == destino:
            raise forms.ValidationError('Clube de origem e destino não podem ser iguais.')
        return cleaned


class InfoClubeForm(forms.ModelForm):
    class Meta:
        model  = InfoClube
        fields = [
            'equipe',
            'cnpj', 'razao_social', 'nome_fantasia', 'data_fundacao',
            'presidente', 'vice_presidente', 'diretor_futebol', 'secretario',
            'telefone', 'email_clube', 'site', 'instagram', 'facebook',
            'situacao',
        ]
        widgets = {
            'equipe':          forms.Select(attrs={'class': 'select select-sm w-full bg-base-200 border-base-300'}),
            'cnpj':            forms.TextInput(attrs={'class': 'input input-sm w-full bg-base-200 border-base-300', 'placeholder': '00.000.000/0000-00'}),
            'razao_social':    forms.TextInput(attrs={'class': 'input input-sm w-full bg-base-200 border-base-300'}),
            'nome_fantasia':   forms.TextInput(attrs={'class': 'input input-sm w-full bg-base-200 border-base-300'}),
            'data_fundacao':   forms.DateInput(attrs={'type': 'date', 'class': 'input input-sm w-full bg-base-200 border-base-300'}),
            'presidente':      forms.TextInput(attrs={'class': 'input input-sm w-full bg-base-200 border-base-300'}),
            'vice_presidente': forms.TextInput(attrs={'class': 'input input-sm w-full bg-base-200 border-base-300'}),
            'diretor_futebol': forms.TextInput(attrs={'class': 'input input-sm w-full bg-base-200 border-base-300'}),
            'secretario':      forms.TextInput(attrs={'class': 'input input-sm w-full bg-base-200 border-base-300'}),
            'telefone':        forms.TextInput(attrs={'class': 'input input-sm w-full bg-base-200 border-base-300', 'placeholder': '(00) 00000-0000'}),
            'email_clube':     forms.EmailInput(attrs={'class': 'input input-sm w-full bg-base-200 border-base-300'}),
            'site':            forms.URLInput(attrs={'class': 'input input-sm w-full bg-base-200 border-base-300', 'placeholder': 'https://'}),
            'instagram':       forms.TextInput(attrs={'class': 'input input-sm w-full bg-base-200 border-base-300', 'placeholder': '@usuario'}),
            'facebook':        forms.TextInput(attrs={'class': 'input input-sm w-full bg-base-200 border-base-300'}),
            'situacao':        forms.Select(attrs={'class': 'select select-sm w-full bg-base-200 border-base-300'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Exclude clubs that already have an InfoClube (except current instance)
        qs = Equipe.objects.order_by('nome_equipe')
        if self.instance.pk:
            qs = qs.filter(pk=self.instance.equipe_id) | qs.filter(info_clube__isnull=True)
        else:
            qs = qs.filter(info_clube__isnull=True)
        self.fields['equipe'].queryset = qs


class TipoDocumentoForm(forms.ModelForm):
    class Meta:
        model  = TipoDocumento
        fields = ['nome', 'entidade', 'obrigatorio', 'validade_meses']
        widgets = {
            'nome':           forms.TextInput(attrs={'class': 'input input-sm w-full bg-base-200 border-base-300'}),
            'entidade':       forms.Select(attrs={'class': 'select select-sm w-full bg-base-200 border-base-300'}),
            'obrigatorio':    forms.CheckboxInput(attrs={'class': 'checkbox checkbox-sm checkbox-warning'}),
            'validade_meses': forms.NumberInput(attrs={'class': 'input input-sm w-full bg-base-200 border-base-300', 'min': 1, 'placeholder': 'Ex: 12'}),
        }


class DocumentoForm(forms.ModelForm):
    class Meta:
        model  = Documento
        fields = ['tipo', 'clube', 'atleta', 'arbitro', 'arquivo', 'data_emissao', 'observacoes']
        widgets = {
            'tipo':         forms.Select(attrs={'class': 'select select-sm w-full bg-base-200 border-base-300'}),
            'clube':        forms.Select(attrs={'class': 'select select-sm w-full bg-base-200 border-base-300'}),
            'atleta':       forms.Select(attrs={'class': 'select select-sm w-full bg-base-200 border-base-300'}),
            'arbitro':      forms.Select(attrs={'class': 'select select-sm w-full bg-base-200 border-base-300'}),
            'arquivo':      forms.FileInput(attrs={'class': 'file-input file-input-sm w-full bg-base-200 border-base-300'}),
            'data_emissao': forms.DateInput(attrs={'type': 'date', 'class': 'input input-sm w-full bg-base-200 border-base-300'}),
            'observacoes':  forms.Textarea(attrs={'class': 'textarea textarea-sm w-full bg-base-200 border-base-300', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['clube'].required  = False
        self.fields['atleta'].required = False
        self.fields['arbitro'].required = False

    def clean(self):
        cleaned = super().clean()
        vinculados = [
            v for v in [cleaned.get('clube'), cleaned.get('atleta'), cleaned.get('arbitro')]
            if v
        ]
        if len(vinculados) == 0:
            raise forms.ValidationError('Informe pelo menos um vínculo: clube, atleta ou árbitro.')
        if len(vinculados) > 1:
            raise forms.ValidationError('Vincule o documento a apenas um: clube, atleta ou árbitro.')
        return cleaned


class DocumentoAprovarForm(forms.Form):
    decisao     = forms.ChoiceField(
        choices=[('aprovado', 'Aprovar'), ('rejeitado', 'Rejeitar')],
        widget=forms.RadioSelect(),
    )
    observacoes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'textarea textarea-sm w-full bg-base-200 border-base-300',
            'rows': 2, 'placeholder': 'Observações (opcional)',
        }),
    )

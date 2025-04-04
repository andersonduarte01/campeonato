from django import forms

from ..criterios.models import FormatoCompeticao, CriterioClassificacao


class FormatoCompeticaoForm(forms.ModelForm):
    class Meta:
        model = FormatoCompeticao
        fields = '__all__'


class CriterioClassificacaoForm(forms.ModelForm):
    class Meta:
        model = CriterioClassificacao
        fields = '__all__'

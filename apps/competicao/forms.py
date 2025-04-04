from django import forms
from django.forms import DateInput

from ..competicao.models import Competicao
from ..equipe.models import Equipe


class CompeticaoForm(forms.ModelForm):
    class Meta:
        model = Competicao
        fields = ('nome', 'descricao', 'data_inicio', 'data_fim')

        widgets = {
            'data_inicio': DateInput(attrs={'type': 'date'}),
            'data_fim': DateInput(attrs={'type': 'date'}),
            'descricao': forms.Textarea(attrs={'rows': 3}),
        }


class AssociarEquipeForm(forms.Form):
    equipe_id = forms.IntegerField(widget=forms.HiddenInput())
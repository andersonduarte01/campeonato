from django.urls import path
from . import views

app_name = 'criterios'

urlpatterns = [
    path('formato/add/<int:pk>/', views.FormatoCompeticaoAdd.as_view(), name='formato_add'),
    path('adicionar/<int:pk>/', views.CriterioClassificacaoAdd.as_view(), name='criterio_add'),
]

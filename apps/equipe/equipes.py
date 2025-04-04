
times_brasileiros = [
    "Flamengo", "Palmeiras", "São Paulo", "Corinthians", "Santos", "Grêmio",
    "Internacional", "Cruzeiro", "Atlético Mineiro", "Vasco da Gama", "Fluminense",
    "Botafogo", "Bahia", "Vitória", "Sport Recife", "Ceará", "Fortaleza", "Athletico Paranaense",
    "Coritiba", "Goiás", "Atlético Goianiense", "América Mineiro", "Juventude", "Chapecoense",
    "Avaí", "Figueirense", "Paysandu", "Remo", "Náutico", "Santa Cruz"
]

# Criar e salvar as equipes no banco de dados
for nome in times_brasileiros:
    equipe, created = Equipe.objects.get_or_create(nome_equipe=nome)
    if created:
        print(f"Equipe '{nome}' criada com sucesso!")
    else:
        print(f"Equipe '{nome}' já existe no banco de dados.")

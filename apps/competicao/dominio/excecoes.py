class RegraVioladaError(Exception):
    """Violação de uma regra de negócio do domínio da competição."""


class TransicaoInvalida(RegraVioladaError):
    """Transição de status não permitida ou pré-condição não atendida."""

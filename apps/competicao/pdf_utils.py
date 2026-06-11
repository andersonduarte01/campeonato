"""
Geração de PDFs server-side usando xhtml2pdf.
Converte templates HTML+CSS inline para PDF sem dependências de sistema.
"""
import os
from io import BytesIO

from django.conf import settings
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa


def _link_callback(uri, rel):
    """
    Resolve URIs de mídia para caminhos absolutos no sistema de arquivos.
    URLs externas (CDN, http://) são retornadas sem alteração para
    xhtml2pdf tentar buscar normalmente.
    """
    media_url = settings.MEDIA_URL
    static_url = settings.STATIC_URL

    if uri.startswith(media_url):
        path = os.path.join(settings.MEDIA_ROOT, uri[len(media_url):])
        if os.path.isfile(path):
            return path
    elif uri.startswith(static_url):
        path = os.path.join(
            getattr(settings, 'STATIC_ROOT', ''),
            uri[len(static_url):],
        )
        if os.path.isfile(path):
            return path

    return uri


def render_pdf(template_src: str, context: dict, filename: str = 'documento.pdf', inline: bool = True) -> HttpResponse:
    """
    Renderiza um template Django como PDF e retorna HttpResponse.

    Args:
        template_src: caminho do template (ex: 'competicao/pdf_sumula.html')
        context: dicionário de contexto
        filename: nome do arquivo para o Content-Disposition
        inline: True abre no navegador, False força download

    Raises:
        RuntimeError: se xhtml2pdf reportar erro de renderização
    """
    template = get_template(template_src)
    html = template.render(context)

    buffer = BytesIO()
    result = pisa.pisaDocument(
        BytesIO(html.encode('utf-8')),
        buffer,
        link_callback=_link_callback,
        encoding='utf-8',
    )

    if result.err:
        raise RuntimeError(f'Erro ao gerar PDF ({template_src}): {result.err}')

    disposition = 'inline' if inline else 'attachment'
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    return response

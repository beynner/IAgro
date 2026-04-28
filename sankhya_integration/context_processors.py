from __future__ import annotations

import os
from typing import Dict

from django.conf import settings

def app_version_processor(request):
    """ Adiciona a variável APP_VERSION ao contexto de todos os templates. """
    return {'APP_VERSION': settings.APP_VERSION}

def environment_badge(_request) -> Dict[str, str]:
    """Expose environment metadata (label + colors) for template badges.

    Controlado pela variável de ambiente DJANGO_ENV.
    Valores válidos: 'production', 'homologacao' (padrão).
    Em produção, defina DJANGO_ENV=production no servidor.
    """
    env = os.getenv('DJANGO_ENV', 'homologacao').lower()

    if env == 'production':
        label = 'EM PRODUÇÃO'
        badge_class = 'env-badge--producao'
    elif env == 'homologacao':
        label = 'HOMOLOGAÇÃO'
        badge_class = 'env-badge--homologacao'
    else:
        label = 'DESCONHECIDO'
        badge_class = 'env-badge--desconhecido'

    return {
        'ENV_BADGE_LABEL': label,
        'ENV_BADGE_CLASS': badge_class,
    }

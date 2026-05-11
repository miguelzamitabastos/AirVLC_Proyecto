"""
AWS services package.

Nota: evitamos imports eager aquí para no forzar dependencias (boto3)
en flujos donde solo se necesita Lex, o en entornos de test.
"""

from typing import Optional, Type

PollyService: Optional[Type] = None
TranscribeService: Optional[Type] = None
LexService: Optional[Type] = None

try:  # pragma: no cover
    from .lex_service import LexService as _LexService

    LexService = _LexService
except Exception:
    LexService = None

try:  # pragma: no cover
    from .polly_service import PollyService as _PollyService

    PollyService = _PollyService
except Exception:
    PollyService = None

try:  # pragma: no cover
    from .transcribe_service import TranscribeService as _TranscribeService

    TranscribeService = _TranscribeService
except Exception:
    TranscribeService = None

__all__ = ["PollyService", "TranscribeService", "LexService"]

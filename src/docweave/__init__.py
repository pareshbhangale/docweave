"""
docweave: AI-Supervised PDF-to-Markdown with TypeSafe (Jev) System One.
"""

from .converter import convert
from .client import TypeSafePDFClient, get_typesafe_credentials

__version__ = "1.0.0"
__all__ = ["convert", "TypeSafePDFClient", "get_typesafe_credentials"]

"""
Compatibility shim for whatsapp_service.
Now located in `src.communication.whatsapp`.
"""

from src.communication.whatsapp import WhatsAppService, whatsapp_service

__all__ = ["WhatsAppService", "whatsapp_service"]

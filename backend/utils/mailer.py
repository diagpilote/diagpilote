import logging
logger = logging.getLogger("mailer_stub")

def send_email(*args, **kwargs):
    """
    Stub temporaire: enregistre l'appel et renvoie True.
    Évite l'échec d'import tant que l'implémentation réelle n'est pas branchée.
    """
    try:
        logger.warning("MAIL-STUB send_email called: args=%r kwargs=%r", args, kwargs)
    except Exception:
        pass
    return True

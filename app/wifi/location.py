"""Autorização de Localização no macOS (necessária para revelar SSID/BSSID).

Desde o macOS 10.15, o CoreWLAN só retorna SSID e BSSID das redes vizinhas se o
processo possuir autorização de Localização (TCC). Isso exige que a aplicação
rode dentro de um *bundle* ``.app`` com ``NSLocationUsageDescription`` no
``Info.plist`` e que solicite a permissão em tempo de execução.
"""

from __future__ import annotations

from app.utils.logging_config import get_logger

logger = get_logger(__name__)

# Códigos de CLAuthorizationStatus.
_NOT_DETERMINED = 0
_RESTRICTED = 1
_DENIED = 2
_AUTHORIZED_ALWAYS = 3
_AUTHORIZED_WHEN_IN_USE = 4
_AUTHORIZED = {_AUTHORIZED_ALWAYS, _AUTHORIZED_WHEN_IN_USE}


def request_location_authorization(timeout_s: float = 8.0) -> bool:
    """Solicita autorização de Localização e aguarda a resposta do usuário.

    Só tem efeito quando executado dentro de um bundle ``.app``. Em um
    interpretador de linha de comando o prompt do sistema não é exibido.

    Args:
        timeout_s: Tempo máximo de espera pela decisão do usuário.

    Returns:
        ``True`` se a aplicação está autorizada a usar Localização.
    """
    try:
        import time

        import CoreLocation
        from Foundation import NSDate, NSRunLoop
    except ImportError:
        logger.warning("CoreLocation indisponível; SSID/BSSID ficarão ocultos.")
        return False

    manager = CoreLocation.CLLocationManager.alloc().init()
    status = manager.authorizationStatus()
    if status in _AUTHORIZED:
        logger.info("Localização já autorizada.")
        return True
    if status in (_DENIED, _RESTRICTED):
        logger.warning(
            "Localização negada/restrita. Habilite em Ajustes > Privacidade e "
            "Segurança > Serviços de Localização para ver SSID/BSSID."
        )
        return False

    # status == notDetermined: dispara o prompt e processa o run loop até decidir.
    manager.requestWhenInUseAuthorization()
    deadline = time.time() + timeout_s
    run_loop = NSRunLoop.currentRunLoop()
    while time.time() < deadline:
        run_loop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.2))
        status = manager.authorizationStatus()
        if status != _NOT_DETERMINED:
            break

    authorized = status in _AUTHORIZED
    logger.info("Autorização de Localização: %s", "concedida" if authorized else "negada")
    return authorized

"""Codes de navigation générés par Chromium ; aucune exception brute exportée."""
import re

CAUSES = {
    'ERR_CERT_DATE_INVALID': 'TLS_CERTIFICATE_DATE_INVALID',
    'ERR_CERT_AUTHORITY_INVALID': 'TLS_CERTIFICATE_AUTHORITY_INVALID',
    'ERR_CERT_COMMON_NAME_INVALID': 'TLS_CERTIFICATE_NAME_INVALID',
    'ERR_SSL_PROTOCOL_ERROR': 'TLS_PROTOCOL_ERROR',
    'ERR_NAME_NOT_RESOLVED': 'DNS_NAME_NOT_RESOLVED',
    'ERR_CONNECTION_REFUSED': 'CONNECTION_REFUSED',
    'ERR_CONNECTION_RESET': 'CONNECTION_RESET',
    'ERR_EMPTY_RESPONSE': 'EMPTY_RESPONSE',
}


def navigation_error_details(message: str) -> dict | None:
    # Un message JS/title ou une mention dans le call log n'est pas une erreur goto.
    match = re.match(r'^Page\.goto: net::(ERR_[A-Z_]+)(?:\s|$)', message)
    if not match or match.group(1) not in CAUSES:
        return None
    code = match.group(1)
    return {'cause': CAUSES[code], 'stage': 'navigation', 'browser_error': code}

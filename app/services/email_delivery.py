"""Shared transport for BuildSmart transactional email."""
import logging
import re

import requests
from runtime_config import brevo_settings

LOG = logging.getLogger(__name__)
ENDPOINT = 'https://api.brevo.com/v3/smtp/email'


class EmailError(RuntimeError):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def valid_email(value):
    return isinstance(value, str) and len(value) <= 254 and bool(
        re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+', value)
    )


def settings():
    config = brevo_settings()
    return config.api_key, config.sender_email, config.sender_name


def email_configured():
    key, address, _ = settings()
    return bool(key and valid_email(address))


def send_transactional(payload):
    key, address, name = settings()
    if not key or not valid_email(address):
        raise EmailError('Email is not configured. Set a Brevo API key and sender address on the server.', 503)
    try:
        response = requests.post(
            ENDPOINT,
            json={**payload, 'sender': {'email': address, 'name': name}},
            headers={'api-key': key, 'accept': 'application/json'},
            timeout=(5, 20),
            allow_redirects=False,
        )
    except requests.Timeout as exc:
        raise EmailError('Brevo did not confirm the request in time. Check the transactional log before retrying.', 504) from exc
    except requests.RequestException as exc:
        raise EmailError('BuildSmart could not reach Brevo. Check the server network connection.') from exc

    status = response.status_code
    if status == 201:
        try:
            message_id = response.json().get('messageId')
        except (ValueError, AttributeError):
            message_id = None
        if isinstance(message_id, str) and message_id:
            return message_id
        raise EmailError('Brevo returned an incomplete response. Check the transactional log before retrying.')

    LOG.warning('Brevo rejected a transactional email (HTTP %s)', status)
    if status in (401, 403):
        raise EmailError('Brevo denied access. Check the API key and transactional email permissions.')
    if status == 429:
        raise EmailError('Brevo is rate-limiting email. Wait before retrying.', 503)
    if status in (400, 402):
        raise EmailError('Brevo rejected the email. Check the verified sender, recipients, and account limits.')
    raise EmailError('Brevo could not accept the email. Check the transactional log before retrying.')

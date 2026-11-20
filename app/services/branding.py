"""Installation identity attached to customer-facing estimates."""
import base64
import io

from PIL import Image

from services.email_delivery import valid_email
from services.local_db import metadata

FIELDS = {'name': 120, 'address': 350, 'phone': 40, 'email': 254, 'tax_id': 40}


def company_profile():
    return metadata('company_branding') or {}


def validate_branding(form, logo):
    profile = {field: form.get(field, '').strip() for field in FIELDS}
    for field, limit in FIELDS.items():
        if len(profile[field]) > limit:
            raise ValueError(f'Company {field.replace("_", " ")} is too long.')
    if not profile['name'] or not profile['address']:
        raise ValueError('Company name and address are required.')
    if profile['email'] and not valid_email(profile['email']):
        raise ValueError('Enter a valid company email address.')
    if logo and logo.filename:
        profile['logo'] = prepare_logo(logo.stream)
    return profile


def prepare_logo(stream):
    try:
        with Image.open(stream) as image:
            if image.format not in ('PNG', 'JPEG') or image.width * image.height > 4_000_000:
                raise ValueError('Choose a PNG or JPEG logo with up to 4 million pixels.')
            image.thumbnail((320, 320))
            contents = io.BytesIO()
            image.convert('RGBA').save(contents, 'PNG', optimize=True)
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError('Choose a readable PNG or JPEG logo.') from exc
    return 'data:image/png;base64,' + base64.b64encode(contents.getvalue()).decode('ascii')

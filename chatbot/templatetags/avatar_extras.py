import hashlib
from django import template

register = template.Library()

@register.filter
def cravatar(email: str, size: int = 80):
    """Return Cravatar (or Gravatar compatible) URL based on email.
    Usage: {{ user.email|cravatar:120 }}
    If email empty returns default identicon.
    """
    if not email:
        hash_str = '00000000000000000000000000000000'
    else:
        hash_str = hashlib.md5(email.strip().lower().encode('utf-8')).hexdigest()
    return f'https://cravatar.com/avatar/{hash_str}?d=identicon&s={size}'

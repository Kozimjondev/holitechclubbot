from django.core.cache import cache

from core.utils.constants import CONSTANTS


def get_user_language(user_id: int) -> str:
    """Get user language from cache, return default if not found"""
    return cache.get(f"user_lang:{user_id}", CONSTANTS.LANGUAGES.UZ)

def set_user_language(user_id: int, language: str):
    """Set user language in cache"""
    cache.set(f"user_lang:{user_id}", language, timeout=None)

def delete_user_language(user_id: int):
    """Delete user language from cache"""
    cache.delete(f"user_lang:{user_id}")

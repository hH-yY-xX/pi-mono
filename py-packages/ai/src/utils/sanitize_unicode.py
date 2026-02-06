"""
Unicode surrogate pair handling utilities.
"""

import re
from typing import str

def sanitize_surrogates(text: str) -> str:
    """
    Sanitize Unicode surrogate pairs in text.
    
    Args:
        text: Input text that may contain surrogate pairs
        
    Returns:
        Text with surrogate pairs properly handled
    """
    if not text:
        return text
        
    # Replace unmatched surrogate pairs with replacement character
    # High surrogates: U+D800 to U+DBFF
    # Low surrogates: U+DC00 to U+DFFF
    def replace_unmatched(match):
        char = match.group(0)
        if len(char) == 2:
            # Valid surrogate pair
            return char
        else:
            # Unmatched surrogate, replace with 
            return '\uFFFD'
    
    # Pattern to match potential surrogate pairs
    surrogate_pattern = re.compile(r'[\uD800-\uDBFF][\uDC00-\uDFFF]|[\uD800-\uDFFF]')
    
    return surrogate_pattern.sub(replace_unmatched, text)

def is_valid_unicode(text: str) -> bool:
    """
    Check if text contains valid Unicode.
    
    Args:
        text: Text to validate
        
    Returns:
        True if text contains only valid Unicode
    """
    try:
        text.encode('utf-8')
        return True
    except UnicodeEncodeError:
        return False

def normalize_unicode(text: str) -> str:
    """
    Normalize Unicode text to NFC form.
    
    Args:
        text: Input text
        
    Returns:
        Normalized text
    """
    import unicodedata
    return unicodedata.normalize('NFC', text)
"""Text sanitizing shared by the schemas."""
import re

# Control characters plus invisible / bidi-override characters (used to hide text from humans).
_HIDDEN_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f​-‏‪-‮⁦-⁩]")


def clean_text(value: str) -> str:
    return _HIDDEN_CHARS.sub("", value).strip()

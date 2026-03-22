from __future__ import annotations

import re

_TEMPLATE_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


class TemplateRenderError(ValueError):
    pass


def render_template(template: str, values: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise TemplateRenderError(f"missing template value: {key}")
        return values[key]

    return _TEMPLATE_PATTERN.sub(replace, template)

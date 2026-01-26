"""ZERG v2 Template Engine - Handlebars-style template rendering."""

import re
from pathlib import Path
from typing import Any


class TemplateEngine:
    """Handlebars-style template rendering for worker prompts."""

    TEMPLATE_DIR = Path(".zerg/templates")

    def __init__(self, template_dir: Path | None = None):
        """Initialize template engine.

        Args:
            template_dir: Directory containing templates. Defaults to .zerg/templates
        """
        self.template_dir = template_dir or self.TEMPLATE_DIR
        self._cache: dict[str, str] = {}

    def render(self, template_name: str, context: dict[str, Any]) -> str:
        """Render template with context variables.

        Args:
            template_name: Name of template file to render
            context: Dictionary of variables for substitution

        Returns:
            Rendered template string
        """
        template = self._load_template(template_name)
        return self._render_template(template, context)

    def _load_template(self, name: str) -> str:
        """Load template from file.

        Args:
            name: Template filename

        Returns:
            Template content
        """
        if name in self._cache:
            return self._cache[name]

        # Check custom templates first
        custom_path = self.template_dir / "custom" / name
        if custom_path.exists():
            template = custom_path.read_text()
        else:
            template = (self.template_dir / name).read_text()

        self._cache[name] = template
        return template

    def _render_template(self, template: str, context: dict) -> str:
        """Replace variables and process conditionals.

        Args:
            template: Template string
            context: Variable context

        Returns:
            Rendered template
        """
        result = template

        # Process {{#each}} blocks
        result = self._process_each(result, context)

        # Process {{#if}} blocks
        result = self._process_if(result, context)

        # Replace {{variable}} and {{nested.variable}}
        result = self._replace_variables(result, context)

        return result

    def _replace_variables(self, template: str, context: dict) -> str:
        """Replace {{var}} with values from context.

        Args:
            template: Template string
            context: Variable context

        Returns:
            Template with variables replaced
        """

        def replace(match: re.Match) -> str:
            key = match.group(1).strip()
            value = self._get_nested(context, key)
            if value is None:
                return match.group(0)  # Keep original if not found
            return str(value)

        return re.sub(r"\{\{([^#/}]+)\}\}", replace, template)

    def _get_nested(self, obj: dict, key: str) -> Any:
        """Get nested value like 'files.create'.

        Args:
            obj: Dictionary to search
            key: Dot-separated key path

        Returns:
            Value at path or None if not found
        """
        parts = key.split(".")
        value: Any = obj
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value

    def _process_each(self, template: str, context: dict) -> str:
        """Process {{#each items}}...{{/each}} blocks.

        Args:
            template: Template string
            context: Variable context

        Returns:
            Template with each blocks expanded
        """
        pattern = r"\{\{#each\s+(\w+(?:\.\w+)*)\}\}(.*?)\{\{/each\}\}"

        def replace(match: re.Match) -> str:
            key = match.group(1)
            block = match.group(2)
            items = self._get_nested(context, key)

            if not items:
                return ""

            result = []
            for item in items:
                item_context = {**context, "this": item}
                result.append(self._render_template(block, item_context))

            return "".join(result)

        return re.sub(pattern, replace, template, flags=re.DOTALL)

    def _process_if(self, template: str, context: dict) -> str:
        """Process {{#if var}}...{{/if}} blocks.

        Args:
            template: Template string
            context: Variable context

        Returns:
            Template with if blocks processed
        """
        pattern = r"\{\{#if\s+(\w+(?:\.\w+)*)\}\}(.*?)\{\{/if\}\}"

        def replace(match: re.Match) -> str:
            key = match.group(1)
            block = match.group(2)
            value = self._get_nested(context, key)

            if value:
                return self._render_template(block, context)
            return ""

        return re.sub(pattern, replace, template, flags=re.DOTALL)


def render(template_name: str, context: dict) -> str:
    """Convenience function for rendering templates.

    Args:
        template_name: Name of template file
        context: Variable context

    Returns:
        Rendered template string
    """
    engine = TemplateEngine()
    return engine.render(template_name, context)

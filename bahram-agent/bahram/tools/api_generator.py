"""
API generator.

Public objects: ``APIEndpoint``, ``APIGenerator``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class APIEndpoint:
    """
    API endpoint.

    Attributes:
        path (str): filesystem path to operate on.
        method (str): method string.
        handler (str): handler string.
        description (str): human readable description.
        parameters (list[dict]): collection of parameters.
        response_schema (dict): mapping of response schema.
    """

    path: str
    method: str
    handler: str
    description: str = ""
    parameters: list[dict] = field(default_factory=list)
    response_schema: dict = field(default_factory=dict)


class APIGenerator:
    """
    API generator.
    """

    def __init__(self) -> None:
        """
        Initialise a APIGenerator instance.
        """
        self._endpoints: list[APIEndpoint] = []
        self._templates: dict[str, str] = {
            "fastapi": self._get_fastapi_template(),
            "flask": self._get_flask_template(),
            "express": self._get_express_template(),
        }

    def add_endpoint(self, endpoint: APIEndpoint) -> None:
        """
        Add endpoint.

        Args:
            endpoint (APIEndpoint): endpoint.
        """
        self._endpoints.append(endpoint)

    def generate(self, framework: str = "fastapi") -> str:
        """
        Generate.

        Args:
            framework (str): framework string. Defaults to ``'fastapi'``.

        Returns:
            str: the rendered string.
        """
        template = self._templates.get(framework, "")
        if not template:
            return f"# Unsupported framework: {framework}"

        code = template
        for endpoint in self._endpoints:
            code += self._generate_endpoint(endpoint, framework)

        return code

    def _generate_endpoint(self, endpoint: APIEndpoint, framework: str) -> str:
        if framework == "fastapi":
            return ""
        elif framework == "flask":
            return ""
        elif framework == "express":
            return ""
        return ""

    def _get_params(self, endpoint: APIEndpoint) -> str:
        params = []
        for param in endpoint.parameters:
            if param.get("required"):
                params.append(f"{param['name']}: {param.get('type', 'str')}")
            else:
                params.append(
                    f"{param['name']}: {param.get('type', 'str')} = {param.get('default', 'None')}"
                )
        return ", ".join(params)

    def _get_fastapi_template(self) -> str:
        return ""

    def _get_flask_template(self) -> str:
        return ""

    def _get_express_template(self) -> str:
        return ""

    def generate_openapi(self) -> dict:
        """
        Generate openapi.

        Returns:
            dict: a mapping of str, Any.
        """
        paths = {}
        for endpoint in self._endpoints:
            if endpoint.path not in paths:
                paths[endpoint.path] = {}
            paths[endpoint.path][endpoint.method.lower()] = {
                "summary": endpoint.description,
                "parameters": [
                    {
                        "name": p["name"],
                        "in": "query",
                        "required": p.get("required", False),
                        "schema": {"type": p.get("type", "string")},
                    }
                    for p in endpoint.parameters
                ],
            }
        return {
            "openapi": "3.0.0",
            "info": {"title": "Generated API", "version": "1.0.0"},
            "paths": paths,
        }

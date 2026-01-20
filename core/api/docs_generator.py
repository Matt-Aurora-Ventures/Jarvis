"""
API Documentation Generator.

Automatic documentation generation for FastAPI applications including:
- OpenAPI/Swagger spec generation
- Endpoint discovery from FastAPI routes
- Request/response schema extraction
- Multiple output formats (Markdown, JSON, YAML, HTML)
"""

import inspect
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, Union, get_type_hints

from fastapi import FastAPI
from fastapi.routing import APIRoute
from pydantic import BaseModel
from pydantic_core import PydanticUndefined

logger = logging.getLogger(__name__)


def _json_serializable(obj: Any) -> Any:
    """Convert object to JSON-serializable form."""
    if obj is PydanticUndefined or obj is inspect.Parameter.empty:
        return None
    if isinstance(obj, type):
        return obj.__name__
    if hasattr(obj, "__dict__"):
        return str(obj)
    return obj


def _clean_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Clean schema of non-serializable values."""
    cleaned = {}
    for key, value in schema.items():
        if value is PydanticUndefined or value is inspect.Parameter.empty:
            continue
        if isinstance(value, dict):
            cleaned[key] = _clean_schema(value)
        elif isinstance(value, list):
            cleaned[key] = [_clean_schema(v) if isinstance(v, dict) else _json_serializable(v) for v in value]
        else:
            cleaned[key] = _json_serializable(value)
    return cleaned


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class DocsConfig:
    """Configuration for documentation generation."""

    title: str = "API Documentation"
    description: str = "Auto-generated API documentation"
    version: str = "1.0.0"
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_url: Optional[str] = None
    license_name: Optional[str] = None
    license_url: Optional[str] = None
    servers: List[Dict[str, str]] = field(default_factory=list)
    merge_existing: bool = False
    include_examples: bool = True
    openapi_version: str = "3.0.3"


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class ParameterInfo:
    """Information about an endpoint parameter."""

    name: str
    location: str  # path, query, header, cookie
    description: str = ""
    required: bool = False
    param_type: str = "string"
    default: Any = None
    validation: Dict[str, Any] = field(default_factory=dict)
    schema: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RequestBodyInfo:
    """Information about a request body."""

    description: str = ""
    required: bool = True
    content_type: str = "application/json"
    schema: Dict[str, Any] = field(default_factory=dict)
    model: Optional[Type[BaseModel]] = None


@dataclass
class ResponseInfo:
    """Information about a response."""

    status_code: int
    description: str = ""
    content_type: str = "application/json"
    schema: Dict[str, Any] = field(default_factory=dict)
    model: Optional[Type[BaseModel]] = None


@dataclass
class EndpointInfo:
    """Information about an API endpoint."""

    path: str
    method: str
    summary: str = ""
    description: str = ""
    operation_id: str = ""
    tags: List[str] = field(default_factory=list)
    parameters: List[ParameterInfo] = field(default_factory=list)
    request_body: Optional[RequestBodyInfo] = None
    responses: List[ResponseInfo] = field(default_factory=list)
    deprecated: bool = False
    security: List[Dict[str, List[str]]] = field(default_factory=list)


# =============================================================================
# Schema Extraction
# =============================================================================


class SchemaExtractor:
    """Extracts JSON Schema from Pydantic models and Python types."""

    def __init__(self):
        self._schema_cache: Dict[str, Dict[str, Any]] = {}
        self._refs: Dict[str, Dict[str, Any]] = {}

    def extract(self, model: Type) -> Dict[str, Any]:
        """Extract JSON schema from a type."""
        if model is None:
            return {"type": "null"}

        # Handle primitive types
        if model in (str, int, float, bool):
            return self._primitive_schema(model)

        # Handle Pydantic models
        if isinstance(model, type) and issubclass(model, BaseModel):
            return self._pydantic_schema(model)

        # Handle generic types (List, Dict, Optional, etc.)
        origin = getattr(model, "__origin__", None)
        if origin is not None:
            return self._generic_schema(model, origin)

        # Fallback for unknown types
        return {"type": "object"}

    def _primitive_schema(self, model: Type) -> Dict[str, Any]:
        """Get schema for primitive types."""
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
        }
        return {"type": type_map.get(model, "string")}

    def _pydantic_schema(self, model: Type[BaseModel]) -> Dict[str, Any]:
        """Extract schema from Pydantic model."""
        model_name = model.__name__

        # Check cache
        if model_name in self._schema_cache:
            return self._schema_cache[model_name]

        try:
            # Use Pydantic's built-in schema generation
            schema = model.model_json_schema()

            # Process to extract relevant fields
            processed = {
                "type": "object",
                "properties": {},
                "required": [],
            }

            if "properties" in schema:
                processed["properties"] = schema["properties"]

            if "required" in schema:
                processed["required"] = schema["required"]

            # Add title and description if available
            if "title" in schema:
                processed["title"] = schema["title"]
            if "description" in schema:
                processed["description"] = schema["description"]

            # Store definitions/refs
            if "$defs" in schema:
                self._refs.update(schema["$defs"])

            self._schema_cache[model_name] = processed
            return processed

        except Exception as e:
            logger.warning(f"Error extracting schema from {model_name}: {e}")
            return {"type": "object", "description": f"Schema: {model_name}"}

    def _generic_schema(self, model: Type, origin: Type) -> Dict[str, Any]:
        """Handle generic types like List, Dict, Optional."""
        args = getattr(model, "__args__", ())

        # Handle List[X]
        if origin is list:
            item_schema = self.extract(args[0]) if args else {"type": "object"}
            return {"type": "array", "items": item_schema}

        # Handle Dict[K, V]
        if origin is dict:
            return {
                "type": "object",
                "additionalProperties": self.extract(args[1]) if len(args) > 1 else True,
            }

        # Handle Optional[X] (Union[X, None])
        if origin is Union:
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                schema = self.extract(non_none[0])
                schema["nullable"] = True
                return schema
            return {"anyOf": [self.extract(a) for a in non_none]}

        return {"type": "object"}

    def get_refs(self) -> Dict[str, Dict[str, Any]]:
        """Get all collected schema references."""
        return self._refs.copy()


# =============================================================================
# Endpoint Discovery
# =============================================================================


class EndpointDiscovery:
    """Discovers endpoints from FastAPI applications."""

    def __init__(self, schema_extractor: SchemaExtractor):
        self.schema_extractor = schema_extractor

    def discover(self, app: FastAPI) -> List[EndpointInfo]:
        """Discover all endpoints from a FastAPI app."""
        endpoints = []

        for route in app.routes:
            if isinstance(route, APIRoute):
                endpoint_info = self._extract_route_info(route)
                if endpoint_info:
                    endpoints.extend(endpoint_info)

        return endpoints

    def _extract_route_info(self, route: APIRoute) -> List[EndpointInfo]:
        """Extract endpoint information from a route."""
        endpoints = []

        for method in route.methods:
            if method == "HEAD":
                continue

            endpoint = EndpointInfo(
                path=route.path,
                method=method.upper(),
                summary=route.summary or "",
                description=route.description or self._get_docstring(route.endpoint),
                operation_id=route.operation_id or f"{method.lower()}_{route.path.replace('/', '_')}",
                tags=list(route.tags) if route.tags else [],
                deprecated=route.deprecated or False,
            )

            # Extract parameters
            endpoint.parameters = self._extract_parameters(route)

            # Extract request body
            endpoint.request_body = self._extract_request_body(route)

            # Extract responses
            endpoint.responses = self._extract_responses(route)

            endpoints.append(endpoint)

        return endpoints

    def _get_docstring(self, func: Callable) -> str:
        """Get docstring from function."""
        doc = inspect.getdoc(func)
        return doc if doc else ""

    def _extract_parameters(self, route: APIRoute) -> List[ParameterInfo]:
        """Extract parameters from route."""
        params = []

        # Get path parameters
        path_params = set()
        import re
        for match in re.finditer(r"\{(\w+)\}", route.path):
            path_params.add(match.group(1))

        # Get function signature
        sig = inspect.signature(route.endpoint)

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls", "request", "response", "background_tasks"):
                continue

            # Determine parameter location
            if param_name in path_params:
                location = "path"
                required = True
            else:
                location = "query"
                required = param.default is inspect.Parameter.empty

            # Get type annotation
            annotation = param.annotation
            param_type = "string"
            validation = {}
            default_value = None

            if annotation is not inspect.Parameter.empty:
                # Handle FastAPI Query/Path dependencies
                if hasattr(annotation, "__origin__"):
                    param_type = self._get_type_name(annotation)
                elif annotation in (str, int, float, bool):
                    type_map = {str: "string", int: "integer", float: "number", bool: "boolean"}
                    param_type = type_map.get(annotation, "string")

            # Check for default value
            if param.default is not inspect.Parameter.empty:
                default_val = param.default

                # Handle FastAPI Query, Path, etc.
                if hasattr(default_val, "default"):
                    default_value = default_val.default
                    if hasattr(default_val, "description"):
                        description = default_val.description or ""
                    else:
                        description = ""

                    # Extract validation constraints
                    for attr in ("ge", "gt", "le", "lt", "min_length", "max_length", "regex"):
                        if hasattr(default_val, attr):
                            val = getattr(default_val, attr)
                            if val is not None:
                                validation[attr] = val
                                # Map to JSON Schema constraints
                                if attr == "ge":
                                    validation["minimum"] = val
                                elif attr == "le":
                                    validation["maximum"] = val
                else:
                    default_value = default_val
                    description = ""

                required = default_value is ... or default_value is inspect.Parameter.empty
            else:
                description = ""

            # Skip body parameters
            if annotation is not inspect.Parameter.empty:
                if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                    continue

            params.append(
                ParameterInfo(
                    name=param_name,
                    location=location,
                    description=description,
                    required=required,
                    param_type=param_type,
                    default=default_value if default_value is not ... else None,
                    validation=validation,
                    schema={"type": param_type, **validation},
                )
            )

        return params

    def _get_type_name(self, annotation: Type) -> str:
        """Get string type name from annotation."""
        origin = getattr(annotation, "__origin__", None)
        if origin is list:
            return "array"
        if origin is dict:
            return "object"
        return "string"

    def _extract_request_body(self, route: APIRoute) -> Optional[RequestBodyInfo]:
        """Extract request body from route."""
        sig = inspect.signature(route.endpoint)

        for param_name, param in sig.parameters.items():
            annotation = param.annotation

            if annotation is not inspect.Parameter.empty:
                if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                    schema = self.schema_extractor.extract(annotation)

                    description = ""
                    if param.default is not inspect.Parameter.empty:
                        default_val = param.default
                        if hasattr(default_val, "description"):
                            description = default_val.description or ""

                    return RequestBodyInfo(
                        description=description,
                        required=True,
                        schema=schema,
                        model=annotation,
                    )

        return None

    def _extract_responses(self, route: APIRoute) -> List[ResponseInfo]:
        """Extract response information from route."""
        responses = []

        # Default 200 response
        response_model = route.response_model
        if response_model:
            schema = self.schema_extractor.extract(response_model)
            responses.append(
                ResponseInfo(
                    status_code=200,
                    description="Successful Response",
                    schema=schema,
                    model=response_model,
                )
            )
        else:
            responses.append(
                ResponseInfo(
                    status_code=200,
                    description="Successful Response",
                    schema={"type": "object"},
                )
            )

        # Add validation error response for endpoints with parameters
        if route.dependant.body_params or route.dependant.query_params:
            responses.append(
                ResponseInfo(
                    status_code=422,
                    description="Validation Error",
                    schema={
                        "type": "object",
                        "properties": {
                            "detail": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "loc": {"type": "array", "items": {"type": "string"}},
                                        "msg": {"type": "string"},
                                        "type": {"type": "string"},
                                    },
                                },
                            }
                        },
                    },
                )
            )

        return responses


# =============================================================================
# Documentation Generator
# =============================================================================


class DocsGenerator:
    """Main documentation generator class."""

    def __init__(self, config: Optional[DocsConfig] = None):
        self.config = config or DocsConfig()
        self.schema_extractor = SchemaExtractor()
        self.endpoint_discovery = EndpointDiscovery(self.schema_extractor)

    def discover_endpoints(self, app: FastAPI) -> List[EndpointInfo]:
        """Discover all endpoints from a FastAPI app."""
        return self.endpoint_discovery.discover(app)

    def extract_schema(self, model: Type) -> Dict[str, Any]:
        """Extract JSON schema from a type."""
        return self.schema_extractor.extract(model)

    def generate_openapi_spec(self, app: FastAPI) -> Dict[str, Any]:
        """Generate complete OpenAPI specification."""
        # Get app info
        title = app.title or self.config.title
        description = app.description or self.config.description
        version = app.version or self.config.version

        spec = {
            "openapi": self.config.openapi_version,
            "info": {
                "title": title,
                "description": description,
                "version": version,
            },
            "paths": {},
            "components": {"schemas": {}},
            "tags": [],
        }

        # Add contact info
        if self.config.contact_name or self.config.contact_email:
            spec["info"]["contact"] = {}
            if self.config.contact_name:
                spec["info"]["contact"]["name"] = self.config.contact_name
            if self.config.contact_email:
                spec["info"]["contact"]["email"] = self.config.contact_email
            if self.config.contact_url:
                spec["info"]["contact"]["url"] = self.config.contact_url

        # Add license info
        if self.config.license_name:
            spec["info"]["license"] = {"name": self.config.license_name}
            if self.config.license_url:
                spec["info"]["license"]["url"] = self.config.license_url

        # Add servers
        if self.config.servers:
            spec["servers"] = self.config.servers

        # Discover endpoints
        endpoints = self.discover_endpoints(app)

        # Collect tags
        tags_set = set()

        # Build paths
        for endpoint in endpoints:
            if endpoint.path not in spec["paths"]:
                spec["paths"][endpoint.path] = {}

            method_key = endpoint.method.lower()
            operation = {
                "summary": endpoint.summary or endpoint.description.split("\n")[0] if endpoint.description else "",
                "description": endpoint.description,
                "operationId": endpoint.operation_id,
                "tags": endpoint.tags,
                "parameters": [],
                "responses": {},
            }

            # Add tags to set
            tags_set.update(endpoint.tags)

            # Add parameters
            for param in endpoint.parameters:
                param_spec = {
                    "name": param.name,
                    "in": param.location,
                    "description": param.description,
                    "required": param.required,
                    "schema": param.schema,
                }
                if param.default is not None:
                    param_spec["schema"]["default"] = param.default
                operation["parameters"].append(param_spec)

            # Add request body
            if endpoint.request_body:
                operation["requestBody"] = {
                    "description": endpoint.request_body.description,
                    "required": endpoint.request_body.required,
                    "content": {
                        endpoint.request_body.content_type: {
                            "schema": endpoint.request_body.schema
                        }
                    },
                }

                # Add schema to components
                if endpoint.request_body.model:
                    model_name = endpoint.request_body.model.__name__
                    spec["components"]["schemas"][model_name] = endpoint.request_body.schema

            # Add responses
            for response in endpoint.responses:
                operation["responses"][str(response.status_code)] = {
                    "description": response.description,
                    "content": {
                        response.content_type: {"schema": response.schema}
                    },
                }

                # Add schema to components
                if response.model:
                    model_name = response.model.__name__
                    spec["components"]["schemas"][model_name] = response.schema

            # Add deprecated flag
            if endpoint.deprecated:
                operation["deprecated"] = True

            spec["paths"][endpoint.path][method_key] = operation

        # Build tags list
        spec["tags"] = [{"name": tag} for tag in sorted(tags_set)]

        # Add collected schema refs
        refs = self.schema_extractor.get_refs()
        spec["components"]["schemas"].update(refs)

        return spec

    def merge_specs(
        self, existing_spec: Dict[str, Any], app: FastAPI
    ) -> Dict[str, Any]:
        """Merge generated spec with existing spec."""
        generated = self.generate_openapi_spec(app)

        # Deep merge
        merged = existing_spec.copy()

        # Merge paths
        if "paths" not in merged:
            merged["paths"] = {}
        merged["paths"].update(generated.get("paths", {}))

        # Merge components
        if "components" not in merged:
            merged["components"] = {}
        if "schemas" not in merged["components"]:
            merged["components"]["schemas"] = {}
        merged["components"]["schemas"].update(
            generated.get("components", {}).get("schemas", {})
        )

        # Merge tags
        existing_tags = {t["name"] for t in merged.get("tags", [])}
        for tag in generated.get("tags", []):
            if tag["name"] not in existing_tags:
                merged.setdefault("tags", []).append(tag)

        return merged

    def export_json(self, app: FastAPI, indent: int = 2) -> str:
        """Export OpenAPI spec as JSON."""
        spec = self.generate_openapi_spec(app)
        return json.dumps(spec, indent=indent)

    def export_yaml(self, app: FastAPI) -> str:
        """Export OpenAPI spec as YAML."""
        try:
            import yaml
        except ImportError:
            # Fallback to simple YAML-like format
            spec = self.generate_openapi_spec(app)
            return self._dict_to_yaml(spec)

        spec = self.generate_openapi_spec(app)
        return yaml.dump(spec, default_flow_style=False, sort_keys=False)

    def _dict_to_yaml(self, d: Dict, indent: int = 0) -> str:
        """Simple dict to YAML conversion without library."""
        lines = []
        prefix = "  " * indent

        for key, value in d.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(self._dict_to_yaml(value, indent + 1))
            elif isinstance(value, list):
                lines.append(f"{prefix}{key}:")
                for item in value:
                    if isinstance(item, dict):
                        lines.append(f"{prefix}  -")
                        lines.append(self._dict_to_yaml(item, indent + 2))
                    else:
                        lines.append(f"{prefix}  - {item}")
            else:
                lines.append(f"{prefix}{key}: {value}")

        return "\n".join(lines)

    def export_html(self, app: FastAPI) -> str:
        """Export documentation as HTML."""
        spec = self.generate_openapi_spec(app)

        html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - API Documentation</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }}
        h1 {{ border-bottom: 2px solid #333; padding-bottom: 10px; }}
        h2 {{ color: #333; margin-top: 30px; }}
        .endpoint {{ background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }}
        .method {{ display: inline-block; padding: 3px 8px; border-radius: 3px; color: white; font-weight: bold; margin-right: 10px; }}
        .get {{ background: #61affe; }}
        .post {{ background: #49cc90; }}
        .put {{ background: #fca130; }}
        .delete {{ background: #f93e3e; }}
        .path {{ font-family: monospace; font-size: 1.1em; }}
        .description {{ color: #666; margin: 10px 0; }}
        .params {{ margin-top: 10px; }}
        .param {{ background: #fff; padding: 8px; margin: 5px 0; border-left: 3px solid #ddd; }}
        pre {{ background: #263238; color: #fff; padding: 15px; border-radius: 5px; overflow-x: auto; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <p>{description}</p>
    <p><strong>Version:</strong> {version}</p>

    <h2>Endpoints</h2>
    {endpoints}
</body>
</html>"""

        # Build endpoints HTML
        endpoints_html = []
        for path, methods in spec.get("paths", {}).items():
            for method, details in methods.items():
                method_upper = method.upper()
                summary = details.get("summary", "")
                description = details.get("description", "")

                params_html = ""
                if details.get("parameters"):
                    params_html = "<div class='params'><strong>Parameters:</strong>"
                    for param in details["parameters"]:
                        params_html += f"""
                        <div class='param'>
                            <code>{param['name']}</code> ({param['in']})
                            {' - Required' if param.get('required') else ' - Optional'}
                            {f": {param.get('description', '')}" if param.get('description') else ""}
                        </div>"""
                    params_html += "</div>"

                endpoints_html.append(f"""
                <div class='endpoint'>
                    <span class='method {method}'>{method_upper}</span>
                    <span class='path'>{path}</span>
                    <div class='description'>{summary or description}</div>
                    {params_html}
                </div>""")

        return html_template.format(
            title=spec.get("info", {}).get("title", "API"),
            description=spec.get("info", {}).get("description", ""),
            version=spec.get("info", {}).get("version", ""),
            endpoints="\n".join(endpoints_html),
        )

    def export_markdown(self, app: FastAPI) -> str:
        """Export documentation as Markdown."""
        spec = self.generate_openapi_spec(app)
        lines = []

        # Title
        title = spec.get("info", {}).get("title", "API Documentation")
        lines.append(f"# {title}")
        lines.append("")

        # Description
        description = spec.get("info", {}).get("description", "")
        if description:
            lines.append(description)
            lines.append("")

        # Version
        version = spec.get("info", {}).get("version", "")
        if version:
            lines.append(f"**Version:** {version}")
            lines.append("")

        # Table of Contents
        lines.append("## Table of Contents")
        lines.append("")
        for tag in spec.get("tags", []):
            lines.append(f"- [{tag['name']}](#{tag['name'].lower().replace(' ', '-')})")
        lines.append("")

        # Group endpoints by tag
        endpoints_by_tag: Dict[str, List[tuple]] = {}
        for path, methods in spec.get("paths", {}).items():
            for method, details in methods.items():
                tags = details.get("tags", ["default"])
                for tag in tags:
                    if tag not in endpoints_by_tag:
                        endpoints_by_tag[tag] = []
                    endpoints_by_tag[tag].append((path, method, details))

        # Generate documentation for each tag
        for tag in spec.get("tags", []):
            tag_name = tag["name"]
            lines.append(f"## {tag_name}")
            lines.append("")

            for path, method, details in endpoints_by_tag.get(tag_name, []):
                method_upper = method.upper()
                summary = details.get("summary", "")
                description = details.get("description", "")

                lines.append(f"### {method_upper} {path}")
                lines.append("")

                if summary:
                    lines.append(f"**{summary}**")
                    lines.append("")

                if description:
                    lines.append(description)
                    lines.append("")

                # Parameters
                params = details.get("parameters", [])
                if params:
                    lines.append("**Parameters:**")
                    lines.append("")
                    lines.append("| Name | In | Type | Required | Description |")
                    lines.append("|------|-----|------|----------|-------------|")
                    for param in params:
                        param_type = param.get("schema", {}).get("type", "string")
                        required = "Yes" if param.get("required") else "No"
                        desc = param.get("description", "")
                        lines.append(
                            f"| `{param['name']}` | {param['in']} | {param_type} | {required} | {desc} |"
                        )
                    lines.append("")

                # Request Body
                request_body = details.get("requestBody", {})
                if request_body:
                    lines.append("**Request Body:**")
                    lines.append("")
                    content = request_body.get("content", {})
                    for content_type, content_details in content.items():
                        lines.append(f"Content-Type: `{content_type}`")
                        lines.append("")
                        schema = content_details.get("schema", {})
                        if schema:
                            lines.append("```json")
                            lines.append(json.dumps(schema, indent=2))
                            lines.append("```")
                            lines.append("")

                # Responses
                responses = details.get("responses", {})
                if responses:
                    lines.append("**Responses:**")
                    lines.append("")
                    for status_code, response_details in responses.items():
                        resp_desc = response_details.get("description", "")
                        lines.append(f"- `{status_code}`: {resp_desc}")
                    lines.append("")

                lines.append("---")
                lines.append("")

        return "\n".join(lines)

    def save_to_file(
        self, app: FastAPI, path: Union[str, Path], format: str = "markdown"
    ) -> Path:
        """Save documentation to file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        format_exporters = {
            "markdown": self.export_markdown,
            "md": self.export_markdown,
            "json": self.export_json,
            "yaml": self.export_yaml,
            "yml": self.export_yaml,
            "html": self.export_html,
        }

        exporter = format_exporters.get(format.lower())
        if not exporter:
            raise ValueError(f"Unsupported format: {format}")

        content = exporter(app)
        path.write_text(content, encoding="utf-8")

        logger.info(f"Documentation saved to {path}")
        return path


# =============================================================================
# Convenience Functions
# =============================================================================


def generate_docs(app: FastAPI, output_path: Optional[Union[str, Path]] = None, format: str = "markdown") -> str:
    """
    Generate documentation for a FastAPI app.

    Args:
        app: FastAPI application instance
        output_path: Optional path to save documentation
        format: Output format (markdown, json, yaml, html)

    Returns:
        Generated documentation string
    """
    generator = DocsGenerator()

    if output_path:
        generator.save_to_file(app, output_path, format)

    format_exporters = {
        "markdown": generator.export_markdown,
        "md": generator.export_markdown,
        "json": generator.export_json,
        "yaml": generator.export_yaml,
        "yml": generator.export_yaml,
        "html": generator.export_html,
    }

    exporter = format_exporters.get(format.lower(), generator.export_markdown)
    return exporter(app)


def get_openapi_spec(app: FastAPI) -> Dict[str, Any]:
    """
    Get OpenAPI specification for a FastAPI app.

    Args:
        app: FastAPI application instance

    Returns:
        OpenAPI specification dictionary
    """
    generator = DocsGenerator()
    return generator.generate_openapi_spec(app)

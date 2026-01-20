"""
Tests for API Documentation Generator.

Tests the automatic documentation generation system including:
- OpenAPI/Swagger spec generation
- Endpoint discovery from FastAPI routes
- Request/response schema extraction
- Markdown export
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Optional
from pathlib import Path

# Import test fixtures
from pydantic import BaseModel, Field
from fastapi import FastAPI, APIRouter, Query, Path as PathParam, Body


# =============================================================================
# Test Models (for testing schema extraction)
# =============================================================================


class TestRequestModel(BaseModel):
    """Test request model for schema extraction."""
    name: str = Field(..., description="User name")
    age: int = Field(..., ge=0, le=150, description="User age")
    email: Optional[str] = Field(None, description="Optional email")
    tags: List[str] = Field(default_factory=list, description="User tags")


class TestResponseModel(BaseModel):
    """Test response model for schema extraction."""
    id: str = Field(..., description="Unique identifier")
    status: str = Field(..., description="Status message")
    data: dict = Field(default_factory=dict, description="Response data")


class NestedModel(BaseModel):
    """Nested model for testing complex schemas."""
    inner_value: str
    inner_count: int


class ComplexModel(BaseModel):
    """Complex model with nested types."""
    items: List[NestedModel]
    metadata: dict
    enabled: bool = True


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_fastapi_app():
    """Create a sample FastAPI app for testing."""
    app = FastAPI(
        title="Test API",
        description="A test API for documentation generation",
        version="1.0.0",
    )

    router = APIRouter(prefix="/api/test", tags=["test"])

    @router.get("/items", response_model=List[TestResponseModel])
    async def list_items(
        page: int = Query(1, ge=1, description="Page number"),
        limit: int = Query(10, ge=1, le=100, description="Items per page"),
    ):
        """List all items with pagination."""
        pass

    @router.get("/items/{item_id}", response_model=TestResponseModel)
    async def get_item(
        item_id: str = PathParam(..., description="Item ID"),
    ):
        """Get a single item by ID."""
        pass

    @router.post("/items", response_model=TestResponseModel)
    async def create_item(
        item: TestRequestModel = Body(..., description="Item to create"),
    ):
        """Create a new item."""
        pass

    @router.put("/items/{item_id}", response_model=TestResponseModel)
    async def update_item(
        item_id: str = PathParam(..., description="Item ID"),
        item: TestRequestModel = Body(..., description="Updated item data"),
    ):
        """Update an existing item."""
        pass

    @router.delete("/items/{item_id}")
    async def delete_item(
        item_id: str = PathParam(..., description="Item ID"),
    ):
        """Delete an item."""
        pass

    app.include_router(router)
    return app


@pytest.fixture
def docs_generator():
    """Create a DocsGenerator instance."""
    from core.api.docs_generator import DocsGenerator
    return DocsGenerator()


# =============================================================================
# Test: DocsGenerator Initialization
# =============================================================================


class TestDocsGeneratorInit:
    """Tests for DocsGenerator initialization."""

    def test_create_docs_generator(self):
        """Test that DocsGenerator can be instantiated."""
        from core.api.docs_generator import DocsGenerator

        generator = DocsGenerator()
        assert generator is not None

    def test_docs_generator_with_config(self):
        """Test DocsGenerator with custom configuration."""
        from core.api.docs_generator import DocsGenerator, DocsConfig

        config = DocsConfig(
            title="Custom API",
            version="2.0.0",
            description="Custom description",
        )
        generator = DocsGenerator(config=config)

        assert generator.config.title == "Custom API"
        assert generator.config.version == "2.0.0"

    def test_docs_generator_default_config(self):
        """Test DocsGenerator uses sensible defaults."""
        from core.api.docs_generator import DocsGenerator

        generator = DocsGenerator()

        assert generator.config.title is not None
        assert generator.config.version is not None


# =============================================================================
# Test: Endpoint Discovery
# =============================================================================


class TestEndpointDiscovery:
    """Tests for endpoint discovery from FastAPI routes."""

    def test_discover_endpoints_from_app(self, sample_fastapi_app, docs_generator):
        """Test discovering endpoints from a FastAPI app."""
        endpoints = docs_generator.discover_endpoints(sample_fastapi_app)

        assert len(endpoints) >= 5  # We defined 5 endpoints

        # Check that all HTTP methods are found
        methods = {e.method for e in endpoints}
        assert "GET" in methods
        assert "POST" in methods
        assert "PUT" in methods
        assert "DELETE" in methods

    def test_discover_endpoints_paths(self, sample_fastapi_app, docs_generator):
        """Test that correct paths are discovered."""
        endpoints = docs_generator.discover_endpoints(sample_fastapi_app)

        paths = {e.path for e in endpoints}
        assert "/api/test/items" in paths
        assert "/api/test/items/{item_id}" in paths

    def test_discover_endpoints_with_parameters(self, sample_fastapi_app, docs_generator):
        """Test that endpoint parameters are discovered."""
        endpoints = docs_generator.discover_endpoints(sample_fastapi_app)

        # Find the list_items endpoint
        list_endpoint = next(
            (e for e in endpoints if e.path == "/api/test/items" and e.method == "GET"),
            None
        )

        assert list_endpoint is not None
        assert len(list_endpoint.parameters) >= 2  # page and limit

        param_names = {p.name for p in list_endpoint.parameters}
        assert "page" in param_names
        assert "limit" in param_names

    def test_discover_endpoints_with_path_params(self, sample_fastapi_app, docs_generator):
        """Test that path parameters are discovered."""
        endpoints = docs_generator.discover_endpoints(sample_fastapi_app)

        # Find the get_item endpoint
        get_endpoint = next(
            (e for e in endpoints if "{item_id}" in e.path and e.method == "GET"),
            None
        )

        assert get_endpoint is not None

        path_params = [p for p in get_endpoint.parameters if p.location == "path"]
        assert len(path_params) >= 1
        assert path_params[0].name == "item_id"

    def test_discover_endpoints_preserves_tags(self, sample_fastapi_app, docs_generator):
        """Test that endpoint tags are preserved."""
        endpoints = docs_generator.discover_endpoints(sample_fastapi_app)

        for endpoint in endpoints:
            assert "test" in endpoint.tags or len(endpoint.tags) == 0

    def test_discover_endpoints_extracts_docstrings(self, sample_fastapi_app, docs_generator):
        """Test that endpoint docstrings are extracted."""
        endpoints = docs_generator.discover_endpoints(sample_fastapi_app)

        list_endpoint = next(
            (e for e in endpoints if e.path == "/api/test/items" and e.method == "GET"),
            None
        )

        assert list_endpoint is not None
        assert "pagination" in list_endpoint.description.lower()


# =============================================================================
# Test: Schema Extraction
# =============================================================================


class TestSchemaExtraction:
    """Tests for request/response schema extraction."""

    def test_extract_pydantic_schema(self, docs_generator):
        """Test extracting schema from Pydantic model."""
        schema = docs_generator.extract_schema(TestRequestModel)

        assert schema is not None
        assert "properties" in schema
        assert "name" in schema["properties"]
        assert "age" in schema["properties"]

    def test_extract_schema_with_descriptions(self, docs_generator):
        """Test that field descriptions are extracted."""
        schema = docs_generator.extract_schema(TestRequestModel)

        assert schema["properties"]["name"].get("description") == "User name"
        assert schema["properties"]["age"].get("description") == "User age"

    def test_extract_schema_with_constraints(self, docs_generator):
        """Test that field constraints are extracted."""
        schema = docs_generator.extract_schema(TestRequestModel)

        age_schema = schema["properties"]["age"]
        assert age_schema.get("minimum") == 0 or age_schema.get("ge") == 0
        assert age_schema.get("maximum") == 150 or age_schema.get("le") == 150

    def test_extract_schema_required_fields(self, docs_generator):
        """Test that required fields are identified."""
        schema = docs_generator.extract_schema(TestRequestModel)

        required = schema.get("required", [])
        assert "name" in required
        assert "age" in required
        assert "email" not in required  # Optional field

    def test_extract_schema_optional_fields(self, docs_generator):
        """Test handling of optional fields."""
        schema = docs_generator.extract_schema(TestRequestModel)

        email_schema = schema["properties"]["email"]
        # Should handle Optional[str] correctly
        assert email_schema.get("type") == "string" or "anyOf" in email_schema or email_schema.get("nullable")

    def test_extract_schema_list_fields(self, docs_generator):
        """Test handling of List types."""
        schema = docs_generator.extract_schema(TestRequestModel)

        tags_schema = schema["properties"]["tags"]
        assert tags_schema.get("type") == "array"
        assert "items" in tags_schema

    def test_extract_nested_schema(self, docs_generator):
        """Test extraction of nested model schemas."""
        schema = docs_generator.extract_schema(ComplexModel)

        assert "items" in schema["properties"]
        items_schema = schema["properties"]["items"]
        assert items_schema.get("type") == "array"

    def test_extract_schema_default_values(self, docs_generator):
        """Test that default values are captured."""
        schema = docs_generator.extract_schema(ComplexModel)

        enabled_schema = schema["properties"]["enabled"]
        assert enabled_schema.get("default") == True


# =============================================================================
# Test: OpenAPI Spec Generation
# =============================================================================


class TestOpenAPIGeneration:
    """Tests for OpenAPI/Swagger spec generation."""

    def test_generate_openapi_spec(self, sample_fastapi_app, docs_generator):
        """Test generating complete OpenAPI spec."""
        spec = docs_generator.generate_openapi_spec(sample_fastapi_app)

        assert spec is not None
        assert "openapi" in spec
        assert "info" in spec
        assert "paths" in spec

    def test_openapi_version(self, sample_fastapi_app, docs_generator):
        """Test OpenAPI version is set correctly."""
        spec = docs_generator.generate_openapi_spec(sample_fastapi_app)

        assert spec["openapi"].startswith("3.")

    def test_openapi_info_section(self, sample_fastapi_app, docs_generator):
        """Test OpenAPI info section is populated."""
        spec = docs_generator.generate_openapi_spec(sample_fastapi_app)

        info = spec["info"]
        assert "title" in info
        assert "version" in info

    def test_openapi_paths_section(self, sample_fastapi_app, docs_generator):
        """Test OpenAPI paths section contains endpoints."""
        spec = docs_generator.generate_openapi_spec(sample_fastapi_app)

        paths = spec["paths"]
        assert "/api/test/items" in paths
        assert "/api/test/items/{item_id}" in paths

    def test_openapi_operation_details(self, sample_fastapi_app, docs_generator):
        """Test OpenAPI operation details are correct."""
        spec = docs_generator.generate_openapi_spec(sample_fastapi_app)

        items_path = spec["paths"]["/api/test/items"]
        get_op = items_path.get("get", {})

        assert "summary" in get_op or "description" in get_op
        assert "responses" in get_op

    def test_openapi_parameters(self, sample_fastapi_app, docs_generator):
        """Test OpenAPI parameters are included."""
        spec = docs_generator.generate_openapi_spec(sample_fastapi_app)

        items_path = spec["paths"]["/api/test/items"]
        get_op = items_path.get("get", {})

        parameters = get_op.get("parameters", [])
        param_names = {p["name"] for p in parameters}

        assert "page" in param_names
        assert "limit" in param_names

    def test_openapi_request_body(self, sample_fastapi_app, docs_generator):
        """Test OpenAPI request body for POST endpoints."""
        spec = docs_generator.generate_openapi_spec(sample_fastapi_app)

        items_path = spec["paths"]["/api/test/items"]
        post_op = items_path.get("post", {})

        assert "requestBody" in post_op
        request_body = post_op["requestBody"]
        assert "content" in request_body

    def test_openapi_responses(self, sample_fastapi_app, docs_generator):
        """Test OpenAPI responses are defined."""
        spec = docs_generator.generate_openapi_spec(sample_fastapi_app)

        items_path = spec["paths"]["/api/test/items"]
        get_op = items_path.get("get", {})

        responses = get_op.get("responses", {})
        assert "200" in responses or 200 in responses

    def test_openapi_components_schemas(self, sample_fastapi_app, docs_generator):
        """Test OpenAPI components/schemas section."""
        spec = docs_generator.generate_openapi_spec(sample_fastapi_app)

        assert "components" in spec
        components = spec["components"]
        assert "schemas" in components

    def test_openapi_tags(self, sample_fastapi_app, docs_generator):
        """Test OpenAPI tags are defined."""
        spec = docs_generator.generate_openapi_spec(sample_fastapi_app)

        assert "tags" in spec
        tags = spec["tags"]
        tag_names = {t["name"] for t in tags}
        assert "test" in tag_names


# =============================================================================
# Test: Markdown Export
# =============================================================================


class TestMarkdownExport:
    """Tests for Markdown documentation export."""

    def test_export_to_markdown(self, sample_fastapi_app, docs_generator):
        """Test exporting documentation to Markdown."""
        markdown = docs_generator.export_markdown(sample_fastapi_app)

        assert markdown is not None
        assert len(markdown) > 0
        assert isinstance(markdown, str)

    def test_markdown_contains_title(self, sample_fastapi_app, docs_generator):
        """Test Markdown contains API title."""
        markdown = docs_generator.export_markdown(sample_fastapi_app)

        assert "# " in markdown  # Has heading

    def test_markdown_contains_endpoints(self, sample_fastapi_app, docs_generator):
        """Test Markdown contains endpoint documentation."""
        markdown = docs_generator.export_markdown(sample_fastapi_app)

        assert "/api/test/items" in markdown
        assert "GET" in markdown
        assert "POST" in markdown

    def test_markdown_contains_parameters(self, sample_fastapi_app, docs_generator):
        """Test Markdown documents parameters."""
        markdown = docs_generator.export_markdown(sample_fastapi_app)

        assert "page" in markdown.lower()
        assert "limit" in markdown.lower()

    def test_markdown_contains_descriptions(self, sample_fastapi_app, docs_generator):
        """Test Markdown contains endpoint descriptions."""
        markdown = docs_generator.export_markdown(sample_fastapi_app)

        assert "pagination" in markdown.lower() or "list" in markdown.lower()

    def test_markdown_contains_request_body_docs(self, sample_fastapi_app, docs_generator):
        """Test Markdown documents request bodies."""
        markdown = docs_generator.export_markdown(sample_fastapi_app)

        # Should document the TestRequestModel fields
        assert "name" in markdown.lower()
        assert "age" in markdown.lower()

    def test_markdown_contains_response_docs(self, sample_fastapi_app, docs_generator):
        """Test Markdown documents responses."""
        markdown = docs_generator.export_markdown(sample_fastapi_app)

        # Should have response documentation
        assert "response" in markdown.lower() or "200" in markdown

    def test_markdown_code_blocks(self, sample_fastapi_app, docs_generator):
        """Test Markdown contains code blocks for examples."""
        markdown = docs_generator.export_markdown(sample_fastapi_app)

        # Should have code blocks
        assert "```" in markdown

    def test_markdown_table_of_contents(self, sample_fastapi_app, docs_generator):
        """Test Markdown has table of contents or navigation."""
        markdown = docs_generator.export_markdown(sample_fastapi_app)

        # Should have some form of navigation/TOC
        assert "##" in markdown  # Has subheadings


# =============================================================================
# Test: Multiple Output Formats
# =============================================================================


class TestOutputFormats:
    """Tests for multiple output format support."""

    def test_export_to_json(self, sample_fastapi_app, docs_generator):
        """Test exporting OpenAPI spec to JSON."""
        json_output = docs_generator.export_json(sample_fastapi_app)

        assert json_output is not None
        # Should be valid JSON
        parsed = json.loads(json_output)
        assert "openapi" in parsed

    def test_export_to_yaml(self, sample_fastapi_app, docs_generator):
        """Test exporting OpenAPI spec to YAML."""
        yaml_output = docs_generator.export_yaml(sample_fastapi_app)

        assert yaml_output is not None
        assert "openapi:" in yaml_output or "openapi :" in yaml_output

    def test_export_to_html(self, sample_fastapi_app, docs_generator):
        """Test exporting documentation to HTML."""
        html_output = docs_generator.export_html(sample_fastapi_app)

        assert html_output is not None
        assert "<html" in html_output.lower() or "<!doctype" in html_output.lower()

    def test_save_to_file(self, sample_fastapi_app, docs_generator, tmp_path):
        """Test saving documentation to file."""
        output_path = tmp_path / "api_docs.md"

        docs_generator.save_to_file(
            sample_fastapi_app,
            output_path,
            format="markdown"
        )

        assert output_path.exists()
        content = output_path.read_text()
        assert len(content) > 0


# =============================================================================
# Test: Validation Rules Extraction
# =============================================================================


class TestValidationRulesExtraction:
    """Tests for extracting validation rules from endpoints."""

    def test_extract_query_param_validation(self, sample_fastapi_app, docs_generator):
        """Test extracting validation rules from query parameters."""
        endpoints = docs_generator.discover_endpoints(sample_fastapi_app)

        list_endpoint = next(
            (e for e in endpoints if e.path == "/api/test/items" and e.method == "GET"),
            None
        )

        page_param = next(
            (p for p in list_endpoint.parameters if p.name == "page"),
            None
        )

        assert page_param is not None
        assert page_param.validation is not None
        assert page_param.validation.get("ge") == 1 or page_param.validation.get("minimum") == 1

    def test_extract_body_validation(self, sample_fastapi_app, docs_generator):
        """Test extracting validation rules from request body."""
        endpoints = docs_generator.discover_endpoints(sample_fastapi_app)

        create_endpoint = next(
            (e for e in endpoints if e.path == "/api/test/items" and e.method == "POST"),
            None
        )

        assert create_endpoint is not None
        assert create_endpoint.request_body is not None

        # Should have validation info for age field
        schema = create_endpoint.request_body.schema
        age_props = schema.get("properties", {}).get("age", {})
        assert "minimum" in age_props or "ge" in age_props


# =============================================================================
# Test: Integration with Existing FastAPI App
# =============================================================================


class TestFastAPIIntegration:
    """Tests for integration with existing FastAPI setup."""

    def test_generate_from_jarvis_app(self, docs_generator):
        """Test generating docs from the actual Jarvis FastAPI app."""
        try:
            from api.fastapi_app import create_app
            app = create_app()

            spec = docs_generator.generate_openapi_spec(app)

            assert spec is not None
            assert "paths" in spec
            assert len(spec["paths"]) > 0
        except ImportError:
            pytest.skip("Jarvis FastAPI app not available")

    def test_merge_with_existing_spec(self, docs_generator):
        """Test merging generated spec with existing OpenAPI spec."""
        existing_spec = {
            "openapi": "3.0.3",
            "info": {"title": "Existing", "version": "1.0.0"},
            "paths": {"/existing": {"get": {"summary": "Existing endpoint"}}},
        }

        from core.api.docs_generator import DocsConfig
        config = DocsConfig(merge_existing=True)
        generator = docs_generator.__class__(config=config)

        # Create minimal app
        app = FastAPI()

        @app.get("/new")
        def new_endpoint():
            pass

        merged = generator.merge_specs(existing_spec, app)

        assert "/existing" in merged["paths"]
        assert "/new" in merged["paths"]


# =============================================================================
# Test: Error Handling
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in documentation generation."""

    def test_handle_empty_app(self, docs_generator):
        """Test handling app with no routes."""
        empty_app = FastAPI()

        spec = docs_generator.generate_openapi_spec(empty_app)

        assert spec is not None
        assert "paths" in spec
        # Should not raise, even with no paths

    def test_handle_invalid_model(self, docs_generator):
        """Test handling invalid Pydantic model."""
        # Pass a non-Pydantic class
        schema = docs_generator.extract_schema(str)

        # Should handle gracefully, return minimal schema
        assert schema is not None

    def test_handle_circular_references(self, docs_generator):
        """Test handling models with circular references."""
        # This is a common edge case in schema extraction
        class NodeModel(BaseModel):
            value: str
            children: Optional[List["NodeModel"]] = None

        NodeModel.model_rebuild()

        schema = docs_generator.extract_schema(NodeModel)

        assert schema is not None
        # Should not raise RecursionError

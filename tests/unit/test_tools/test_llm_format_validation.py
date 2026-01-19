"""Tests for LLM format validation (FR-013 compliance)."""

import pytest

from multi_agent.tools.builtin import register_builtin_tools


class TestLLMFormatValidation:
    """Test suite for LLM function calling format validation."""

    @pytest.fixture
    def llm_tools(self):
        """Get all tools in LLM format."""
        registry = register_builtin_tools()
        return registry.to_llm_list()

    def test_openai_format_structure(self, llm_tools):
        """Validate OpenAI format structure."""
        for tool in llm_tools:
            # Must have type: "function"
            assert tool.get("type") == "function", f"{tool} must have type='function'"
            # Must have function key
            assert "function" in tool, f"{tool} must have 'function' key"
            func = tool["function"]
            # Function must have name, description, parameters
            assert "name" in func, f"{tool} function must have 'name'"
            assert "description" in func, f"{tool} function must have 'description'"
            assert "parameters" in func, f"{tool} function must have 'parameters'"

    def test_anthropic_format_structure(self, llm_tools):
        """Validate Anthropic format can be derived."""
        for tool in llm_tools:
            func = tool["function"]
            # Anthropic format: {name, description, input_schema}
            # Can be derived from OpenAI format
            assert "name" in func
            assert "description" in func
            assert "parameters" in func  # Serves as input_schema

    def test_parameters_is_valid_json_schema(self, llm_tools):
        """Test all tool parameters are valid JSON Schema."""
        valid_types = {"string", "number", "integer", "boolean", "array", "object"}
        for tool in llm_tools:
            params = tool["function"]["parameters"]
            # Must have type: "object"
            assert params.get("type") == "object", f"{tool['function']['name']} parameters must have type='object'"
            # Must have properties
            assert "properties" in params, f"{tool['function']['name']} must have properties"
            # Must have required array
            assert isinstance(params.get("required"), list), f"{tool['function']['name']} required must be a list"

            # Validate each property
            for prop_name, prop_def in params["properties"].items():
                # Must have type
                assert "type" in prop_def, f"{tool['function']['name']}.{prop_name} must have type"
                # Type must be valid
                assert prop_def["type"] in valid_types, f"{tool['function']['name']}.{prop_name} has invalid type: {prop_def['type']}"

    def test_required_fields_present(self, llm_tools):
        """Test required fields are present in tool definitions."""
        for tool in llm_tools:
            func = tool["function"]
            # Required: name, description, parameters
            assert func["name"], f"{tool} must have non-empty name"
            assert func["description"], f"{tool} must have non-empty description"
            assert func["parameters"], f"{tool} must have parameters"

    def test_descriptions_are_llm_readable(self, llm_tools):
        """Test descriptions are clear for LLM consumption."""
        for tool in llm_tools:
            func = tool["function"]
            desc = func["description"]
            # Should be a non-empty string
            assert isinstance(desc, str), f"{tool['function']['name']} description must be a string"
            assert len(desc) > 10, f"{tool['function']['name']} description should be descriptive"
            # Should not contain implementation details
            assert "async def" not in desc.lower(), f"{tool['function']['name']} description should not contain implementation"

    def test_all_expected_tools_present(self, llm_tools):
        """Test all expected tools are in the LLM format."""
        tool_names = {t["function"]["name"] for t in llm_tools}
        expected_tools = {
            "file_read",
            "file_write",
            "file_list",
            "file_info",
            "calculate",
            "execute",
            "network_fetch",
            "system_get_time",
            "system_get_env",
            "system_list_processes",
        }
        assert tool_names == expected_tools, f"Expected {expected_tools}, got {tool_names}"

    def test_property_types_valid(self, llm_tools):
        """Test property types are valid JSON Schema types."""
        valid_types = {"string", "number", "integer", "boolean", "array", "object"}
        for tool in llm_tools:
            params = tool["function"]["parameters"]
            for prop_name, prop_def in params["properties"].items():
                prop_type = prop_def.get("type")
                assert prop_type in valid_types, \
                    f"{tool['function']['name']}.{prop_name} has invalid type: {prop_type}"

    def test_parameter_descriptions_present(self, llm_tools):
        """Test parameters have descriptions for LLM."""
        for tool in llm_tools:
            params = tool["function"]["parameters"]
            for prop_name, prop_def in params["properties"].items():
                # Should have description
                assert "description" in prop_def, \
                    f"{tool['function']['name']}.{prop_name} should have description"
                assert len(prop_def["description"]) > 5, \
                    f"{tool['function']['name']}.{prop_name} description should be descriptive"

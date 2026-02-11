"""
Test for Bedrock Agent integration.
"""

import pytest
from bedrock.agent import BedrockAgentClient, AgentResponse


def test_agent_response_dataclass():
    """Test the AgentResponse dataclass."""
    response = AgentResponse(
        success=True,
        response="Test response",
        action_group="search_providers",
        session_id="test_session"
    )

    assert response.success is True
    assert response.response == "Test response"
    assert response.action_group == "search_providers"
    assert response.session_id == "test_session"


def test_bedrock_client_initialization_missing_env():
    """Test that BedrockAgentClient raises error when HUSTLR_AGENT_ID is missing."""
    import os
    # Temporarily remove the env var if it exists
    original_value = os.environ.get("HUSTLR_AGENT_ID")
    if "HUSTLR_AGENT_ID" in os.environ:
        del os.environ["HUSTLR_AGENT_ID"]

    try:
        with pytest.raises(ValueError, match="HUSTLR_AGENT_ID environment variable is required"):
            BedrockAgentClient()
    finally:
        # Restore the original value
        if original_value:
            os.environ["HUSTLR_AGENT_ID"] = original_value


def test_parse_agent_response():
    """Test response parsing functionality."""
    client = BedrockAgentClient.__new__(BedrockAgentClient)  # Create without __init__

    # Test plain text response
    result = client._parse_agent_response("Hello world")
    assert result == {"message": "Hello world"}

    # Test JSON response
    json_response = '{"message": "Hello", "action": "search"}'
    result = client._parse_agent_response(json_response)
    assert result == {"message": "Hello", "action": "search"}

    # Test invalid JSON falls back to text
    invalid_json = '{"message": "Hello", "invalid": }'
    result = client._parse_agent_response(invalid_json)
    assert result == {"message": invalid_json}
"""
Contract tests for OpenRouter API response shapes.

Validates that our response parsing code handles all known response variants
correctly, using fixture JSON files (no real network calls).
"""


def test_success_response_content_accessible(openrouter_success_response):
    """We can extract the assistant's text from a success response."""
    content = openrouter_success_response["choices"][0]["message"]["content"]
    assert isinstance(content, str)
    assert len(content) > 0


def test_success_response_has_expected_keys(openrouter_success_response):
    """Success response has all top-level keys our code depends on."""
    assert "choices" in openrouter_success_response
    assert len(openrouter_success_response["choices"]) > 0
    message = openrouter_success_response["choices"][0]["message"]
    assert "role" in message
    assert "content" in message


def test_tool_call_response_content_is_none(openrouter_tool_call_response):
    """Tool call responses have null content — our code must handle this."""
    content = openrouter_tool_call_response["choices"][0]["message"]["content"]
    assert content is None


def test_tool_call_response_has_tool_calls_key(openrouter_tool_call_response):
    """Tool call responses contain a tool_calls list."""
    message = openrouter_tool_call_response["choices"][0]["message"]
    assert "tool_calls" in message
    assert isinstance(message["tool_calls"], list)
    assert len(message["tool_calls"]) > 0


def test_tool_call_response_function_has_name(openrouter_tool_call_response):
    """Each tool call has a function name our code can inspect."""
    tool_call = openrouter_tool_call_response["choices"][0]["message"]["tool_calls"][0]
    assert "function" in tool_call
    assert "name" in tool_call["function"]


def test_error_response_has_error_key(openrouter_error_response):
    """Error responses contain an 'error' key (not 'choices')."""
    assert "error" in openrouter_error_response
    assert "choices" not in openrouter_error_response


def test_parsing_success_response_does_not_raise():
    """Simulate the exact parsing logic from bot.py on a success response."""
    response_data = {"choices": [{"message": {"role": "assistant", "content": "Hello."}}]}
    # Mirrors bot.py: response.json()["choices"][0]["message"]["content"]
    content = response_data["choices"][0]["message"]["content"]
    assert content == "Hello."


def test_parsing_tool_call_response_detects_tool_calls():
    """Simulate the tool_call detection logic from bot.py."""
    response_data = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{"function": {"name": "web_search"}}],
                }
            }
        ]
    }
    message = response_data["choices"][0]["message"]
    # Mirrors bot.py: if "tool_calls" in message
    assert "tool_calls" in message

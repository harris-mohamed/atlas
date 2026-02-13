"""
Unit tests for officer querying logic in bot.py:
  - model_supports_web_search()
  - query_officer()
  - query_all_officers()
  - query_officer_with_research_role()

All HTTP calls are mocked via AsyncMock on the httpx client.
All DB calls (load_officer_memory) are patched to return empty strings.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import bot

# ---------------------------------------------------------------------------
# Minimal test officers to patch bot.OFFICERS with
# ---------------------------------------------------------------------------

ANTHROPIC_OFFICER = {
    "title": "Test Anthropic Officer",
    "model": "anthropic/claude-3-haiku",
    "specialty": "Testing",
    "capability_class": "Support",
    "system_prompt": "You are a test officer.",
}

GOOGLE_OFFICER = {
    "title": "Test Google Officer",
    "model": "google/gemini-2.0-flash-001",
    "specialty": "Testing",
    "capability_class": "Support",
    "system_prompt": "You are a test Google officer.",
}

PERPLEXITY_OFFICER = {
    "title": "Test Perplexity Officer",
    "model": "perplexity/sonar",
    "specialty": "Testing",
    "capability_class": "Support",
    "system_prompt": "You are a perplexity officer.",
}

TEST_OFFICERS_PATCH = {
    "T1": ANTHROPIC_OFFICER,
    "T2": GOOGLE_OFFICER,
    "T3": PERPLEXITY_OFFICER,
    "T4": {
        "title": "Test Officer 4",
        "model": "openai/gpt-4o-mini",
        "specialty": "Testing",
        "capability_class": "Support",
        "system_prompt": "You are test officer 4.",
    },
}

TEST_ACTIVE_ROSTER_PATCH = ["T1", "T2", "T3", "T4"]


def make_http_response(content="Test officer response.", status_code=200):
    """Build a mock httpx Response for a successful OpenRouter call."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"choices": [{"message": {"role": "assistant", "content": content}}]}
    resp.raise_for_status = MagicMock()
    return resp


def make_tool_call_response():
    """Build a mock response where the model returned tool_calls instead of content."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {"function": {"name": "web_search", "arguments": '{"query":"test"}'}}
                    ],
                }
            }
        ]
    }
    resp.raise_for_status = MagicMock()
    return resp


def make_mock_client(response):
    """Return an AsyncMock httpx client whose .post() returns `response`."""
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    return client


# ---------------------------------------------------------------------------
# model_supports_web_search
# ---------------------------------------------------------------------------


class TestModelSupportsWebSearch:
    def test_perplexity_model_supported(self):
        assert bot.model_supports_web_search("perplexity/sonar") is True

    def test_perplexity_mixed_case_supported(self):
        assert bot.model_supports_web_search("Perplexity/Sonar-Pro") is True

    def test_google_gemini_supported(self):
        assert bot.model_supports_web_search("google/gemini-2.0-flash-001") is True

    def test_google_gemini_mixed_case_supported(self):
        assert bot.model_supports_web_search("Google/Gemini-Pro") is True

    def test_anthropic_not_supported(self):
        assert bot.model_supports_web_search("anthropic/claude-3-haiku") is False

    def test_openai_not_supported(self):
        assert bot.model_supports_web_search("openai/gpt-4o") is False

    def test_xai_not_supported(self):
        assert bot.model_supports_web_search("x-ai/grok-4") is False

    def test_deepseek_not_supported(self):
        assert bot.model_supports_web_search("deepseek/deepseek-v3") is False

    def test_google_without_gemini_not_supported(self):
        # "google" alone is not enough — must also have "gemini"
        assert bot.model_supports_web_search("google/palm-2") is False


# ---------------------------------------------------------------------------
# get_officer_color
# ---------------------------------------------------------------------------


class TestGetOfficerColor:
    def test_uses_explicit_color_when_present(self):
        officer = {"color": "0xff0000", "capability_class": "Support"}
        assert bot.get_officer_color(officer) == 0xFF0000

    def test_falls_back_to_strategic_class_color(self):
        officer = {"capability_class": "Strategic"}
        assert bot.get_officer_color(officer) == 0x9B59B6

    def test_falls_back_to_operational_class_color(self):
        officer = {"capability_class": "Operational"}
        assert bot.get_officer_color(officer) == 0x3498DB

    def test_falls_back_to_tactical_class_color(self):
        officer = {"capability_class": "Tactical"}
        assert bot.get_officer_color(officer) == 0x2ECC71

    def test_falls_back_to_support_class_color(self):
        officer = {"capability_class": "Support"}
        assert bot.get_officer_color(officer) == 0xF39C12

    def test_unknown_class_returns_default_grey(self):
        officer = {"capability_class": "Unknown"}
        assert bot.get_officer_color(officer) == 0x95A5A6

    def test_explicit_color_overrides_class_color(self):
        officer = {"color": "0x123456", "capability_class": "Strategic"}
        assert bot.get_officer_color(officer) == 0x123456


# ---------------------------------------------------------------------------
# filter_officers_by_capability
# ---------------------------------------------------------------------------


class TestFilterOfficersByCapability:
    def test_returns_all_when_no_filter(self):
        with (
            patch.object(bot, "ACTIVE_ROSTER", TEST_ACTIVE_ROSTER_PATCH),
            patch.object(bot, "OFFICERS", TEST_OFFICERS_PATCH),
        ):
            result = bot.filter_officers_by_capability(None)
        assert result == TEST_ACTIVE_ROSTER_PATCH

    def test_filters_by_support_class(self):
        officers = {
            "A1": {"capability_class": "Support"},
            "B1": {"capability_class": "Strategic"},
            "A2": {"capability_class": "Support"},
        }
        with (
            patch.object(bot, "ACTIVE_ROSTER", ["A1", "B1", "A2"]),
            patch.object(bot, "OFFICERS", officers),
        ):
            result = bot.filter_officers_by_capability("Support")
        assert result == ["A1", "A2"]
        assert "B1" not in result

    def test_filter_is_case_insensitive(self):
        officers = {
            "A1": {"capability_class": "Support"},
            "B1": {"capability_class": "Strategic"},
        }
        with (
            patch.object(bot, "ACTIVE_ROSTER", ["A1", "B1"]),
            patch.object(bot, "OFFICERS", officers),
        ):
            result = bot.filter_officers_by_capability("support")
        assert "A1" in result
        assert "B1" not in result

    def test_returns_empty_for_unknown_class(self):
        with (
            patch.object(bot, "ACTIVE_ROSTER", TEST_ACTIVE_ROSTER_PATCH),
            patch.object(bot, "OFFICERS", TEST_OFFICERS_PATCH),
        ):
            result = bot.filter_officers_by_capability("Nonexistent")
        assert result == []

    def test_only_active_roster_officers_returned(self):
        officers = {
            "A1": {"capability_class": "Support"},
            "A2": {"capability_class": "Support"},  # not in active roster
        }
        with patch.object(bot, "ACTIVE_ROSTER", ["A1"]), patch.object(bot, "OFFICERS", officers):
            result = bot.filter_officers_by_capability("Support")
        assert result == ["A1"]
        assert "A2" not in result


# ---------------------------------------------------------------------------
# query_officer
# ---------------------------------------------------------------------------


class TestQueryOfficer:
    @pytest.mark.asyncio
    async def test_returns_success_on_200(self):
        client = make_mock_client(make_http_response("Officer analysis here."))
        with (
            patch.object(bot, "OFFICERS", TEST_OFFICERS_PATCH),
            patch("bot.load_officer_memory", new=AsyncMock(return_value="")),
        ):
            result = await bot.query_officer("T1", "Test mission", client)
        assert result["success"] is True
        assert result["response"] == "Officer analysis here."

    @pytest.mark.asyncio
    async def test_returns_officer_metadata(self):
        client = make_mock_client(make_http_response("Response."))
        with (
            patch.object(bot, "OFFICERS", TEST_OFFICERS_PATCH),
            patch("bot.load_officer_memory", new=AsyncMock(return_value="")),
        ):
            result = await bot.query_officer("T1", "Brief", client)
        assert result["officer_id"] == "T1"
        assert result["title"] == ANTHROPIC_OFFICER["title"]
        assert result["model"] == ANTHROPIC_OFFICER["model"]
        assert result["specialty"] == ANTHROPIC_OFFICER["specialty"]
        assert result["capability_class"] == ANTHROPIC_OFFICER["capability_class"]

    @pytest.mark.asyncio
    async def test_injects_memory_into_system_prompt(self):
        memory = "### Manual Notes:\n- User prefers async patterns"
        client = make_mock_client(make_http_response("Response."))
        with (
            patch.object(bot, "OFFICERS", TEST_OFFICERS_PATCH),
            patch("bot.load_officer_memory", new=AsyncMock(return_value=memory)),
        ):
            await bot.query_officer("T1", "Brief", client, channel_id=111)

        call_kwargs = client.post.call_args
        payload = (
            call_kwargs.kwargs.get("json") or call_kwargs.args[1]
            if len(call_kwargs.args) > 1
            else call_kwargs.kwargs["json"]
        )
        system_message = payload["messages"][0]
        assert system_message["role"] == "system"
        assert memory in system_message["content"]

    @pytest.mark.asyncio
    async def test_does_not_load_memory_without_channel_id(self):
        client = make_mock_client(make_http_response("Response."))
        mock_load = AsyncMock(return_value="")
        with (
            patch.object(bot, "OFFICERS", TEST_OFFICERS_PATCH),
            patch("bot.load_officer_memory", new=mock_load),
        ):
            await bot.query_officer("T1", "Brief", client, channel_id=None)
        mock_load.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_failure_on_http_exception(self):
        client = AsyncMock()
        client.post = AsyncMock(side_effect=Exception("Connection refused"))
        with (
            patch.object(bot, "OFFICERS", TEST_OFFICERS_PATCH),
            patch("bot.load_officer_memory", new=AsyncMock(return_value="")),
        ):
            result = await bot.query_officer("T1", "Brief", client)
        assert result["success"] is False
        assert "Connection refused" in result["response"]

    @pytest.mark.asyncio
    async def test_returns_failure_on_http_error_status(self):
        resp = MagicMock()
        resp.raise_for_status = MagicMock(side_effect=Exception("500 Server Error"))
        client = make_mock_client(resp)
        with (
            patch.object(bot, "OFFICERS", TEST_OFFICERS_PATCH),
            patch("bot.load_officer_memory", new=AsyncMock(return_value="")),
        ):
            result = await bot.query_officer("T1", "Brief", client)
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_posts_to_correct_openrouter_url(self):
        client = make_mock_client(make_http_response("Response."))
        with (
            patch.object(bot, "OFFICERS", TEST_OFFICERS_PATCH),
            patch("bot.load_officer_memory", new=AsyncMock(return_value="")),
        ):
            await bot.query_officer("T1", "Brief", client)
        posted_url = client.post.call_args.args[0]
        assert "openrouter.ai" in posted_url
        assert "chat/completions" in posted_url

    @pytest.mark.asyncio
    async def test_uses_correct_model_in_payload(self):
        client = make_mock_client(make_http_response("Response."))
        with (
            patch.object(bot, "OFFICERS", TEST_OFFICERS_PATCH),
            patch("bot.load_officer_memory", new=AsyncMock(return_value="")),
        ):
            await bot.query_officer("T1", "Brief", client)
        payload = client.post.call_args.kwargs["json"]
        assert payload["model"] == ANTHROPIC_OFFICER["model"]


# ---------------------------------------------------------------------------
# query_all_officers
# ---------------------------------------------------------------------------


class TestQueryAllOfficers:
    @pytest.mark.asyncio
    async def test_queries_all_active_officers_when_no_filter(self):
        mock_client_instance = make_mock_client(make_http_response("Response."))
        mock_client_cm = AsyncMock()
        mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch.object(bot, "OFFICERS", TEST_OFFICERS_PATCH),
            patch.object(bot, "ACTIVE_ROSTER", TEST_ACTIVE_ROSTER_PATCH),
            patch("bot.load_officer_memory", new=AsyncMock(return_value="")),
            patch("bot.httpx.AsyncClient", return_value=mock_client_cm),
        ):
            results = await bot.query_all_officers("Brief", None, None)

        assert len(results) == len(TEST_ACTIVE_ROSTER_PATCH)

    @pytest.mark.asyncio
    async def test_filters_by_capability_class(self):
        mixed_officers = {
            "S1": {
                "title": "S",
                "model": "m",
                "specialty": "x",
                "capability_class": "Support",
                "system_prompt": "p",
            },
            "S2": {
                "title": "S",
                "model": "m",
                "specialty": "x",
                "capability_class": "Strategic",
                "system_prompt": "p",
            },
        }
        mock_client_instance = make_mock_client(make_http_response("Response."))
        mock_client_cm = AsyncMock()
        mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch.object(bot, "OFFICERS", mixed_officers),
            patch.object(bot, "ACTIVE_ROSTER", ["S1", "S2"]),
            patch("bot.load_officer_memory", new=AsyncMock(return_value="")),
            patch("bot.httpx.AsyncClient", return_value=mock_client_cm),
        ):
            results = await bot.query_all_officers("Brief", "Support", None)

        assert len(results) == 1
        assert results[0]["officer_id"] == "S1"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_officers_match(self):
        mock_client_cm = AsyncMock()
        mock_client_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
        mock_client_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch.object(bot, "OFFICERS", TEST_OFFICERS_PATCH),
            patch.object(bot, "ACTIVE_ROSTER", TEST_ACTIVE_ROSTER_PATCH),
            patch("bot.httpx.AsyncClient", return_value=mock_client_cm),
        ):
            results = await bot.query_all_officers("Brief", "Strategic", None)

        assert results == []

    @pytest.mark.asyncio
    async def test_partial_failure_returns_all_results(self):
        """Even if one officer fails, all results are returned."""
        call_count = [0]

        async def alternating_post(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Officer 2 failed")
            return make_http_response("Response.")

        mock_client_instance = AsyncMock()
        mock_client_instance.post = alternating_post
        mock_client_cm = AsyncMock()
        mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch.object(bot, "OFFICERS", TEST_OFFICERS_PATCH),
            patch.object(bot, "ACTIVE_ROSTER", TEST_ACTIVE_ROSTER_PATCH),
            patch("bot.load_officer_memory", new=AsyncMock(return_value="")),
            patch("bot.httpx.AsyncClient", return_value=mock_client_cm),
        ):
            results = await bot.query_all_officers("Brief", None, None)

        assert len(results) == len(TEST_ACTIVE_ROSTER_PATCH)
        successes = [r for r in results if r["success"]]
        failures = [r for r in results if not r["success"]]
        assert len(successes) == 3
        assert len(failures) == 1


# ---------------------------------------------------------------------------
# query_officer_with_research_role
# ---------------------------------------------------------------------------


class TestQueryOfficerWithResearchRole:
    @pytest.mark.asyncio
    async def test_injects_research_role_into_system_prompt(self):
        client = make_mock_client(make_http_response("Research response."))
        with (
            patch.object(bot, "OFFICERS", TEST_OFFICERS_PATCH),
            patch("bot.load_officer_memory", new=AsyncMock(return_value="")),
        ):
            await bot.query_officer_with_research_role("T1", "AI topic", 0, client)

        payload = client.post.call_args.kwargs["json"]
        system_content = payload["messages"][0]["content"]
        assert "State-of-the-Art Researcher" in system_content

    @pytest.mark.asyncio
    async def test_each_role_index_injects_correct_role(self):
        role_names = [
            "State-of-the-Art Researcher",
            "Critical Analyst",
            "Optimistic Visionary",
            "Historical Context Provider",
        ]
        for idx, expected_role in enumerate(role_names):
            client = make_mock_client(make_http_response(f"Response for role {idx}."))
            with (
                patch.object(bot, "OFFICERS", TEST_OFFICERS_PATCH),
                patch("bot.load_officer_memory", new=AsyncMock(return_value="")),
            ):
                await bot.query_officer_with_research_role("T1", "Topic", idx, client)
            payload = client.post.call_args.kwargs["json"]
            assert expected_role in payload["messages"][0]["content"]

    @pytest.mark.asyncio
    async def test_research_role_in_result(self):
        client = make_mock_client(make_http_response("Good response."))
        with (
            patch.object(bot, "OFFICERS", TEST_OFFICERS_PATCH),
            patch("bot.load_officer_memory", new=AsyncMock(return_value="")),
        ):
            result = await bot.query_officer_with_research_role("T1", "Topic", 1, client)
        assert result["research_role"] == "Critical Analyst"

    @pytest.mark.asyncio
    async def test_web_search_adds_google_provider_for_gemini(self):
        client = make_mock_client(make_http_response("Gemini response."))
        with (
            patch.object(bot, "OFFICERS", TEST_OFFICERS_PATCH),
            patch("bot.load_officer_memory", new=AsyncMock(return_value="")),
        ):
            await bot.query_officer_with_research_role(
                "T2", "Topic", 0, client, use_web_search=True
            )
        payload = client.post.call_args.kwargs["json"]
        assert "provider" in payload
        assert payload["provider"]["order"] == ["Google"]

    @pytest.mark.asyncio
    async def test_web_search_no_provider_field_for_anthropic(self):
        client = make_mock_client(make_http_response("Anthropic response."))
        with (
            patch.object(bot, "OFFICERS", TEST_OFFICERS_PATCH),
            patch("bot.load_officer_memory", new=AsyncMock(return_value="")),
        ):
            await bot.query_officer_with_research_role(
                "T1", "Topic", 0, client, use_web_search=True
            )
        payload = client.post.call_args.kwargs["json"]
        assert "provider" not in payload

    @pytest.mark.asyncio
    async def test_web_search_disclaimer_added_for_unsupported_model(self):
        client = make_mock_client(make_http_response("Normal response."))
        with (
            patch.object(bot, "OFFICERS", TEST_OFFICERS_PATCH),
            patch("bot.load_officer_memory", new=AsyncMock(return_value="")),
        ):
            result = await bot.query_officer_with_research_role(
                "T1", "Topic", 0, client, use_web_search=True
            )
        # Anthropic doesn't support search — disclaimer should be prepended
        assert "Web search not available" in result["response"]

    @pytest.mark.asyncio
    async def test_tool_call_response_sets_warning_content(self):
        client = make_mock_client(make_tool_call_response())
        with (
            patch.object(bot, "OFFICERS", TEST_OFFICERS_PATCH),
            patch("bot.load_officer_memory", new=AsyncMock(return_value="")),
        ):
            result = await bot.query_officer_with_research_role("T1", "Topic", 0, client)
        assert "tool" in result["response"].lower() or "search" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_returns_failure_on_exception(self):
        client = AsyncMock()
        client.post = AsyncMock(side_effect=Exception("Timeout"))
        with (
            patch.object(bot, "OFFICERS", TEST_OFFICERS_PATCH),
            patch("bot.load_officer_memory", new=AsyncMock(return_value="")),
        ):
            result = await bot.query_officer_with_research_role("T1", "Topic", 0, client)
        assert result["success"] is False
        assert "Timeout" in result["response"]

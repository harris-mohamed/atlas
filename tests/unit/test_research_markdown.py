"""
Unit tests for generate_research_markdown() in bot.py.
Pure function — no mocking needed.
"""

import bot


def make_research_results(count=4):
    """Build a list of mock officer research results."""
    roles = [
        "State-of-the-Art Researcher",
        "Critical Analyst",
        "Optimistic Visionary",
        "Historical Context Provider",
    ]
    return [
        {
            "officer_id": f"O{i+1}",
            "title": f"Officer {i+1}",
            "model": f"test/model-{i+1}",
            "specialty": "Testing",
            "capability_class": "Support",
            "research_role": roles[i % len(roles)],
            "response": f"This is the research response from officer {i+1}.",
            "success": True,
        }
        for i in range(count)
    ]


# ---------------------------------------------------------------------------
# Structure tests
# ---------------------------------------------------------------------------


class TestGenerateResearchMarkdown:
    def test_starts_with_h1_heading(self):
        results = make_research_results()
        md = bot.generate_research_markdown("AI Trends", results, "Support")
        assert md.startswith("# Research Report:")

    def test_includes_topic_in_heading(self):
        results = make_research_results()
        md = bot.generate_research_markdown("Quantum Computing", results, "Support")
        assert "Quantum Computing" in md

    def test_includes_capability_class(self):
        results = make_research_results()
        md = bot.generate_research_markdown("Topic", results, "Strategic")
        assert "Strategic" in md

    def test_includes_all_officer_ids(self):
        results = make_research_results(4)
        md = bot.generate_research_markdown("Topic", results, "Support")
        for result in results:
            assert result["officer_id"] in md

    def test_includes_all_officer_responses(self):
        results = make_research_results(4)
        md = bot.generate_research_markdown("Topic", results, "Support")
        for result in results:
            assert result["response"] in md

    def test_includes_all_research_roles_as_headings(self):
        results = make_research_results(4)
        md = bot.generate_research_markdown("Topic", results, "Support")
        for result in results:
            assert result["research_role"] in md

    def test_contains_executive_summary_section(self):
        results = make_research_results()
        md = bot.generate_research_markdown("Topic", results, "Support")
        assert "## Executive Summary" in md

    def test_contains_horizontal_rules(self):
        results = make_research_results()
        md = bot.generate_research_markdown("Topic", results, "Support")
        assert "---" in md

    def test_web_search_enabled_note_present(self):
        results = make_research_results()
        md = bot.generate_research_markdown("Topic", results, "Support", use_web_search=True)
        assert "Web Search Enabled" in md

    def test_web_search_disabled_shows_pretraining_note(self):
        results = make_research_results()
        md = bot.generate_research_markdown("Topic", results, "Support", use_web_search=False)
        assert "Pretraining Knowledge" in md

    def test_includes_report_footer(self):
        results = make_research_results()
        md = bot.generate_research_markdown("Topic", results, "Support")
        assert "Atlas War Room" in md

    def test_returns_string(self):
        results = make_research_results()
        md = bot.generate_research_markdown("Topic", results, "Support")
        assert isinstance(md, str)

    def test_handles_single_result(self):
        results = make_research_results(1)
        md = bot.generate_research_markdown("Topic", results, "Support")
        assert results[0]["response"] in md

    def test_h2_section_per_officer(self):
        results = make_research_results(4)
        md = bot.generate_research_markdown("Topic", results, "Support")
        # Should have at least 4 H2 sections (one per officer role + Executive Summary)
        h2_count = md.count("\n## ")
        assert h2_count >= 4

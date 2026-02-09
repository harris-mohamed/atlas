# Web Search Integration Guide

## Overview

The `/research` command now supports **real-time web search** through OpenRouter, allowing officers to cite current sources, verify facts, and access information beyond their training cutoff dates.

## Usage

```
/research topic:"Your research question" capability_class:Strategic use_web_search:True
```

### Parameters

- **topic** (required): The research question or topic
- **capability_class** (required): Which officer class (Strategic/Operational/Tactical/Support)
- **use_web_search** (optional, default=False): Enable web search and source citations

## How It Works

### Without Web Search (`use_web_search:False`)
- Officers rely on **pretraining knowledge** only
- Fast responses (~2-4 seconds)
- No citations or sources
- Knowledge cutoff dates apply (models trained on data up to ~2024)
- Good for: Conceptual analysis, historical context, theoretical discussions

### With Web Search (`use_web_search:True`)
- Officers instructed to **search the web** for current information
- Cite specific sources with URLs
- Include publication dates when available
- Verify facts through multiple sources
- Slower responses (~5-15 seconds depending on model)
- Good for: Current events, latest research, verifiable facts, trending technologies

## Technical Implementation

### OpenRouter Integration

The bot enables web search by:

1. **System Prompt Augmentation**: Adds instructions for web search and citation
2. **User Prompt Enhancement**: Explicitly requests source citations
3. **Function Tools**: Provides a `web_search` function tool definition
4. **Provider Preferences**: Prioritizes models with native search (Perplexity, Google)

### Code Example

```python
# When use_web_search=True, the payload includes:
payload = {
    "model": officer["model"],
    "messages": [...],
    "tools": [{
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information",
            "parameters": {...}
        }
    }],
    "provider": {
        "order": ["Perplexity", "Google"],
        "allow_fallbacks": True
    }
}
```

## Model Compatibility

### Native Search Support
- ✅ **Perplexity models** (perplexity/*)
- ✅ **Google models** (google/gemini-*)
- ✅ Some Claude models via provider extensions

### Limited/No Search Support
- ⚠️ **OpenAI GPT models** - May not have native search, relies on tool calling
- ⚠️ **Anthropic Claude models** - Depends on OpenRouter's implementation

**Recommendation**: For best web search results, configure your officers with Perplexity or Google models.

## Current Roster Configuration

Check `config/roster.json` to see which models your officers use:

```bash
docker exec atlas-war-room cat config/roster.json | jq '.officers | to_entries[] | {id: .key, model: .value.model}'
```

### Example Output
```json
{
  "O1": "openai/gpt-4o",
  "O2": "anthropic/claude-3-5-sonnet",
  "O3": "anthropic/claude-3-7-sonnet",
  "O4": "google/gemini-2.0-flash-001"
}
```

**Note**: In the Strategic class, only O4 (Google) has guaranteed native search support.

## Research Report Indicators

### Markdown Reports

Generated reports include a **Search Mode** indicator:

```markdown
**Search Mode:** ✅ Web Search Enabled - Sources Cited
```
or
```markdown
**Search Mode:** 📚 Pretraining Knowledge Only
```

### Discord Embeds

Header embeds show:
- 🌐 **Web Search Enabled** (when `use_web_search:True`)
- 📚 **Pretraining Only** (when `use_web_search:False`)

## Interactive Features

All buttons work with both modes:

- **📊 Generate Report**: Markdown includes search mode status
- **🤖 AI Synthesis**: O2 synthesizes findings (respects original search mode)
- **🔄 Pivot**: Preserves search mode across topic changes

## Database Tracking

Research missions save the search status in metadata:

```python
research_metadata = {
    "mission_type": "research",
    "research_roles": {...},
    "web_search_enabled": True  # or False
}
```

### Query Past Research

```sql
SELECT
    mission_brief,
    extra_metadata->>'web_search_enabled' as web_search
FROM mission_history
WHERE extra_metadata->>'mission_type' = 'research'
ORDER BY started_at DESC;
```

## Best Practices

### When to Enable Web Search

✅ **Use web search for:**
- Current events and news
- Latest technology releases
- Recent research papers
- Verifiable statistics
- Real-world examples and case studies
- Market trends and industry reports

❌ **Don't need web search for:**
- Conceptual explanations
- Historical analysis (pre-2024)
- Theoretical discussions
- General knowledge questions
- Philosophical debates

### Cost Considerations

- Web search may consume **more tokens** (sources, citations, additional context)
- Models with native search (Perplexity) are optimized for this
- Estimate: **~20-30% more tokens** when web search is enabled

### Rate Limiting

- OpenRouter rate limits apply
- Perplexity models may have search-specific limits
- Consider using web search strategically for high-priority research

## Troubleshooting

### Officers Don't Cite Sources

**Possible causes:**
1. Model doesn't support native search (check roster)
2. OpenRouter provider fallback not working
3. System prompt not being respected

**Solutions:**
- Switch to Perplexity models in `roster.json`
- Check OpenRouter API logs
- Verify API key has search permissions

### Search Results Seem Outdated

**Possible causes:**
1. Model using cached results
2. Model falling back to pretraining knowledge
3. Search tool not being invoked

**Solutions:**
- Check response for actual URLs/citations
- Try different models (Perplexity preferred)
- Increase prompt emphasis on "current information"

### Errors During Research

Check logs:
```bash
docker logs atlas-war-room | grep -i error
```

Common errors:
- **Tool calling not supported**: Model doesn't support function tools
- **Rate limit**: OpenRouter or provider limit hit
- **Invalid function**: Tool definition issue

## Future Enhancements

Potential improvements:
- [ ] Custom search provider selection (Brave, Serper, Tavily)
- [ ] Search result caching for efficiency
- [ ] Source verification and quality scoring
- [ ] Automatic fact-checking between officers
- [ ] Search query refinement suggestions

## Example Usage

### Without Web Search
```
/research topic:"Explain the CAP theorem in distributed systems" capability_class:Strategic use_web_search:False
```

**Result**: Officers provide conceptual analysis based on pretraining knowledge.

### With Web Search
```
/research topic:"Latest AWS database offerings in 2026" capability_class:Operational use_web_search:True
```

**Result**: Officers search for current AWS documentation, cite specific URLs, and reference recent announcements.

---

**Generated for Atlas War Room v1.0**
**Last Updated**: 2026-02-09

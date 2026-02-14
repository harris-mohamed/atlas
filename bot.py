import asyncio
import json
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, List

import discord
import httpx
from discord import app_commands
from dotenv import load_dotenv

# Database imports
from db_manager import (
    add_manual_note,
    clear_officer_memory,
    ensure_channel_exists,
    get_channel_stats,
    init_db,
    load_officer_memory,
    save_mission,
    save_research_mission,
    seed_officers,
)

# Load environment variables
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
ROSTER_PATH = os.getenv("ROSTER_PATH", "config/roster.json")

# Load roster configuration
with open(ROSTER_PATH, "r") as f:
    roster_config = json.load(f)

OFFICERS = roster_config["officers"]
ACTIVE_ROSTER = roster_config["active_roster"]


def model_supports_web_search(model_name: str) -> bool:
    """Check if a model has native web search capabilities."""
    model_lower = model_name.lower()
    return "perplexity" in model_lower or ("google" in model_lower and "gemini" in model_lower)


# Capability class color mapping
CAPABILITY_COLORS = {
    "Strategic": 0x9B59B6,  # Purple
    "Operational": 0x3498DB,  # Blue
    "Tactical": 0x2ECC71,  # Green
    "Support": 0xF39C12,  # Orange
}

# Research role definitions
RESEARCH_ROLES = {
    0: {
        "role": "State-of-the-Art Researcher",
        "instruction": "Focus on current best practices, leading solutions, and latest developments. Cite specific examples and provide concrete evidence.",
    },
    1: {
        "role": "Critical Analyst",
        "instruction": "Identify counterexamples, flaws, limitations, and risks. Challenge assumptions and highlight edge cases.",
    },
    2: {
        "role": "Optimistic Visionary",
        "instruction": "Explore futuristic possibilities, emerging technologies, and 'what if' scenarios. Think 3-5 years ahead.",
    },
    3: {
        "role": "Historical Context Provider",
        "instruction": "Explain the evolution of this field, past attempts, lessons learned, and provide historical perspective.",
    },
}


def get_officer_color(officer: Dict[str, Any]) -> int:
    """Get color for an officer based on their capability class."""
    # First check if officer has explicit color
    if "color" in officer:
        return int(officer["color"], 16)
    # Otherwise use capability class color
    capability_class = officer.get("capability_class", "Operational")
    return CAPABILITY_COLORS.get(capability_class, 0x95A5A6)


def filter_officers_by_capability(capability_class: str = None) -> List[str]:
    """Filter active officers by capability class."""
    if not capability_class:
        return ACTIVE_ROSTER

    # Case-insensitive matching
    capability_class_lower = capability_class.lower()

    return [
        officer_id
        for officer_id in ACTIVE_ROSTER
        if OFFICERS[officer_id].get("capability_class", "").lower() == capability_class_lower
    ]


class WarRoomBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

        # Initialize database
        await init_db()
        await seed_officers(OFFICERS)
        print("✅ Database initialized and officers seeded")


bot = WarRoomBot()


class PivotModal(discord.ui.Modal, title="🔄 Mission Pivot"):
    """Modal for mid-mission course corrections."""

    pivot_instruction = discord.ui.TextInput(
        label="Course Correction",
        style=discord.TextStyle.paragraph,
        placeholder="Describe the new direction or focus...",
        required=True,
        max_length=2000,
    )

    def __init__(self, original_brief: str, capability_class: str = None):
        super().__init__()
        self.original_brief = original_brief
        self.capability_class = capability_class

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        # Combine original brief with pivot instruction
        new_brief = f"{self.original_brief}\n\n**PIVOT:** {self.pivot_instruction.value}"

        # Re-query officers with the pivoted mission (using same capability class)
        channel_id = interaction.channel_id
        results = await query_all_officers(new_brief, self.capability_class, channel_id)

        # Create response embeds
        header_embed = discord.Embed(
            title="🔄 Pivoted Mission Brief", description=new_brief, color=0xE67E22
        )
        header_embed.set_footer(text=f"Pivoted by {interaction.user.display_name}")

        embeds = [header_embed]

        for result in results:
            embed = discord.Embed(
                title=f"**[{result['officer_id']} - {result['title']}]** • {result['model']}",
                description=result["response"][:4096],
                color=result["color"],
            )
            embed.add_field(name="Class", value=result["capability_class"], inline=True)
            embed.add_field(name="Specialty", value=result["specialty"], inline=True)
            embed.add_field(
                name="Status", value="✅ Complete" if result["success"] else "❌ Error", inline=True
            )
            embeds.append(embed)

        # Send with a new view, splitting embeds if needed
        view = WarRoomView(new_brief, results, self.capability_class)
        await send_embeds_in_batches(interaction, embeds, view)


class WarRoomView(discord.ui.View):
    """Interactive view with War Room control buttons."""

    def __init__(
        self, mission_brief: str, results: List[Dict[str, Any]], capability_class: str = None
    ):
        super().__init__(timeout=None)
        self.mission_brief = mission_brief
        self.results = results
        self.capability_class = capability_class

    @discord.ui.button(label="Red Team Rebuttal", style=discord.ButtonStyle.danger, emoji="🔴")
    async def red_team_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Send council output back to O-3 for adversarial critique."""
        await interaction.response.defer()

        # Compile all officer responses
        council_output = f"**Original Mission:** {self.mission_brief}\n\n"
        for result in self.results:
            council_output += (
                f"**[{result['officer_id']} - {result['title']}]:**\n{result['response']}\n\n"
            )

        # Query O-3 with the compiled responses
        rebuttal_prompt = f"{council_output}\n\n**Task:** Provide a Red Team rebuttal. Identify weaknesses, risks, and failure modes in the council's responses."

        channel_id = interaction.channel_id
        async with httpx.AsyncClient() as client:
            o3_result = await query_officer("O3", rebuttal_prompt, client, channel_id)

        # Create rebuttal embed
        embed = discord.Embed(
            title="🔴 Red Team Rebuttal",
            description=o3_result["response"][:4096],
            color=o3_result["color"],
        )
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")

        await interaction.followup.send(embed=embed)

    @discord.ui.button(label="Generate Plan", style=discord.ButtonStyle.primary, emoji="📄")
    async def generate_plan_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Trigger O-2 to synthesize responses into a PLAN.md."""
        await interaction.response.defer()

        # Compile all officer responses
        council_output = f"**Original Mission:** {self.mission_brief}\n\n"
        for result in self.results:
            council_output += (
                f"**[{result['officer_id']} - {result['title']}]:**\n{result['response']}\n\n"
            )

        # Query O-2 to create a structured plan
        plan_prompt = f"{council_output}\n\n**Task:** Synthesize the council's responses into a structured PLAN.md document. Include: Executive Summary, Key Objectives, Implementation Steps, Risk Mitigation, and Success Criteria."

        channel_id = interaction.channel_id
        async with httpx.AsyncClient() as client:
            o2_result = await query_officer("O2", plan_prompt, client, channel_id)

        # Create plan embed
        embed = discord.Embed(
            title="📄 Strategic Plan",
            description=o2_result["response"][:4096],
            color=o2_result["color"],
        )
        embed.set_footer(text=f"Generated by {interaction.user.display_name}")

        await interaction.followup.send(embed=embed)

    @discord.ui.button(label="Continue & Cross-Reference", style=discord.ButtonStyle.success, emoji="🔁")
    async def continue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Re-query all officers with full context of each other's responses."""
        await interaction.response.defer()

        # Compile the original mission + all prior responses as shared context
        council_context = f"**Original Mission:** {self.mission_brief}\n\n**Council Responses:**\n"
        for result in self.results:
            council_context += f"\n**[{result['officer_id']} - {result['title']}]:**\n{result['response']}\n"

        continuation_prompt = (
            f"{council_context}\n\n"
            "**Task:** Having reviewed your fellow officers' perspectives, continue your analysis. "
            "Build upon points of agreement, address any gaps or contradictions you see, "
            "and refine your position based on the collective intelligence above."
        )

        channel_id = interaction.channel_id
        results = await query_all_officers(continuation_prompt, self.capability_class, channel_id)

        header_embed = discord.Embed(
            title="🔁 Continued Analysis — Cross-Referenced",
            description=self.mission_brief,
            color=0x27AE60,
        )
        header_embed.set_footer(text=f"Continued by {interaction.user.display_name}")

        embeds = [header_embed]
        for result in results:
            embed = discord.Embed(
                title=f"**[{result['officer_id']} - {result['title']}]** • {result['model']}",
                description=result["response"][:4096],
                color=result["color"],
            )
            embed.add_field(name="Class", value=result["capability_class"], inline=True)
            embed.add_field(name="Specialty", value=result["specialty"], inline=True)
            embed.add_field(
                name="Status", value="✅ Complete" if result["success"] else "❌ Error", inline=True
            )
            embeds.append(embed)

        view = WarRoomView(self.mission_brief, results, self.capability_class)
        await send_embeds_in_batches(interaction, embeds, view)

    @discord.ui.button(label="Pivot", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def pivot_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal for mid-mission course correction."""
        modal = PivotModal(self.mission_brief, self.capability_class)
        await interaction.response.send_modal(modal)


class ResearchView(discord.ui.View):
    """Interactive view for research missions."""

    def __init__(
        self,
        research_topic: str,
        results: List[Dict[str, Any]],
        capability_class: str,
        use_web_search: bool = False,
    ):
        super().__init__(timeout=None)
        self.research_topic = research_topic
        self.results = results
        self.capability_class = capability_class
        self.use_web_search = use_web_search

    @discord.ui.button(label="Generate Report", style=discord.ButtonStyle.primary, emoji="📊")
    async def generate_report_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Generate markdown report and upload as file."""
        await interaction.response.defer()

        # Generate markdown
        markdown_content = generate_research_markdown(
            self.research_topic, self.results, self.capability_class, self.use_web_search
        )

        # Create temporary file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"research_{timestamp}.md"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(markdown_content)
            temp_path = f.name

        # Upload as Discord file
        file = discord.File(temp_path, filename=filename)

        # Preview embed
        preview = (
            markdown_content[:500] + "..." if len(markdown_content) > 500 else markdown_content
        )
        embed = discord.Embed(
            title="📊 Research Report Generated",
            description=f"**Topic:** {self.research_topic}\n\n**Preview:**\n```\n{preview}\n```",
            color=0x2ECC71,
        )
        embed.set_footer(text=f"Generated by {interaction.user.display_name}")

        await interaction.followup.send(embed=embed, file=file)

        # Cleanup
        os.unlink(temp_path)

    @discord.ui.button(label="AI Synthesis", style=discord.ButtonStyle.secondary, emoji="🤖")
    async def ai_synthesis_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Have O2 synthesize all perspectives."""
        await interaction.response.defer()

        # Compile research output
        research_output = f"**Research Topic:** {self.research_topic}\n\n"
        for result in self.results:
            research_output += f"**{result['research_role']}:**\n{result['response']}\n\n"

        # Query O2 for synthesis
        synthesis_prompt = f"{research_output}\n\n**Task:** Synthesize these perspectives into cohesive insights. Identify patterns and reconcile contradictions."

        channel_id = interaction.channel_id
        async with httpx.AsyncClient() as client:
            o2_result = await query_officer("O2", synthesis_prompt, client, channel_id)

        embed = discord.Embed(
            title="🤖 AI Research Synthesis",
            description=o2_result["response"][:4096],
            color=o2_result["color"],
        )

        await interaction.followup.send(embed=embed)

    @discord.ui.button(label="Pivot", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def pivot_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open pivot modal for course correction."""
        modal = ResearchPivotModal(self.research_topic, self.capability_class, self.use_web_search)
        await interaction.response.send_modal(modal)


class ResearchPivotModal(discord.ui.Modal, title="🔄 Research Pivot"):
    """Modal for mid-research course corrections."""

    pivot_instruction = discord.ui.TextInput(
        label="Research Direction Change",
        style=discord.TextStyle.paragraph,
        placeholder="Refine or redirect the research focus...",
        required=True,
        max_length=2000,
    )

    def __init__(self, original_topic: str, capability_class: str, use_web_search: bool = False):
        super().__init__()
        self.original_topic = original_topic
        self.capability_class = capability_class
        self.use_web_search = use_web_search

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        new_topic = f"{self.original_topic} [PIVOT: {self.pivot_instruction.value}]"
        channel_id = interaction.channel_id
        results = await query_research_council(
            new_topic, self.capability_class, channel_id, self.use_web_search
        )

        # Create header embed
        header_embed = discord.Embed(
            title=f"🔄 Pivoted Research - {self.capability_class.title()} Class",
            description=f"**Topic:** {new_topic}\n\n**Perspectives:** State-of-the-Art, Critical Analysis, Visionary, Historical Context",
            color=CAPABILITY_COLORS.get(self.capability_class.title(), 0x95A5A6),
        )
        header_embed.set_footer(text=f"Pivoted by {interaction.user.display_name}")

        embeds = [header_embed]

        # Create embeds for each research perspective
        for result in results:
            embed = discord.Embed(
                title=f"**{result['research_role']}**",
                description=f"**[{result['officer_id']} - {result['title']}]** • {result['model']}\n\n{result['response'][:3900]}",
                color=result["color"],
            )
            embed.add_field(name="Class", value=result["capability_class"], inline=True)
            embed.add_field(name="Specialty", value=result["specialty"], inline=True)
            embed.add_field(
                name="Status", value="✅ Complete" if result["success"] else "❌ Error", inline=True
            )
            embeds.append(embed)

        # Send with new research view
        view = ResearchView(new_topic, results, self.capability_class, self.use_web_search)
        await send_embeds_in_batches(interaction, embeds, view)


async def query_officer(
    officer_id: str, mission_brief: str, client: httpx.AsyncClient, channel_id: int = None
) -> Dict[str, Any]:
    """Query a single officer via OpenRouter API with memory context."""
    officer = OFFICERS[officer_id]

    # Load memory from database if channel_id provided
    memory_context = ""
    if channel_id:
        memory_context = await load_officer_memory(channel_id, officer_id)

    # Augment system prompt with memory
    system_content = officer["system_prompt"]
    if memory_context:
        system_content = f"{system_content}\n\n## Your Memory for This Channel:\n{memory_context}"

    payload = {
        "model": officer["model"],
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": mission_brief},
        ],
    }

    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}

    try:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()

        content = data["choices"][0]["message"]["content"]

        return {
            "officer_id": officer_id,
            "title": officer["title"],
            "model": officer["model"],
            "specialty": officer["specialty"],
            "capability_class": officer.get("capability_class", "Operational"),
            "color": get_officer_color(officer),
            "response": content,
            "success": True,
        }
    except Exception as e:
        return {
            "officer_id": officer_id,
            "title": officer["title"],
            "model": officer["model"],
            "specialty": officer["specialty"],
            "capability_class": officer.get("capability_class", "Operational"),
            "color": get_officer_color(officer),
            "response": f"Error: {str(e)}",
            "success": False,
        }


async def query_all_officers(
    mission_brief: str, capability_class: str = None, channel_id: int = None
) -> List[Dict[str, Any]]:
    """Query all active officers in parallel, optionally filtered by capability class."""
    # Filter officers by capability class if specified
    officer_ids = filter_officers_by_capability(capability_class)

    if not officer_ids:
        return []

    async with httpx.AsyncClient() as client:
        tasks = [
            query_officer(officer_id, mission_brief, client, channel_id)
            for officer_id in officer_ids
        ]
        results = await asyncio.gather(*tasks)

    return results


async def query_officer_with_research_role(
    officer_id: str,
    research_topic: str,
    role_index: int,
    client: httpx.AsyncClient,
    channel_id: int = None,
    use_web_search: bool = False,
) -> Dict[str, Any]:
    """Query officer with research role augmentation."""
    officer = OFFICERS[officer_id]
    role_config = RESEARCH_ROLES[role_index]

    # Check if model actually supports web search
    has_web_search = model_supports_web_search(officer["model"])
    web_search_requested = use_web_search
    web_search_active = web_search_requested and has_web_search

    # Load memory
    memory_context = ""
    if channel_id:
        memory_context = await load_officer_memory(channel_id, officer_id)

    # Build research-augmented system prompt
    research_instruction = (
        f"\n\n## RESEARCH ROLE: {role_config['role']}\n{role_config['instruction']}"
    )

    # Only add web search instructions if model actually supports it
    if web_search_active:
        research_instruction += "\n\n**IMPORTANT: You have access to real-time web search. Search for current information, cite specific sources with URLs, and include publication dates when available. Always verify facts through multiple sources.**"

    system_content = officer["system_prompt"] + research_instruction

    if memory_context:
        system_content = f"{system_content}\n\n## Your Memory for This Channel:\n{memory_context}"

    # Craft research-specific user prompt
    user_prompt = f"Research Topic: {research_topic}\n\nProvide a comprehensive analysis from your assigned perspective as the {role_config['role']}."

    if web_search_active:
        user_prompt += (
            "\n\n**Use web search to find current information and cite all sources with URLs.**"
        )

    payload = {
        "model": officer["model"],
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt},
        ],
    }

    # Enable web search through model-specific parameters (only if supported)
    if web_search_active:
        model_name = officer["model"].lower()

        if "perplexity" in model_name:
            # Perplexity models have native search - no tools needed
            # They automatically search when the prompt requests it
            pass
        elif "google" in model_name or "gemini" in model_name:
            # Google models support grounding when available
            # Add Google-specific search parameters if supported
            payload["provider"] = {"order": ["Google"], "allow_fallbacks": False}

    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}

    try:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()

        message = data["choices"][0]["message"]
        content = message.get("content", "")

        # Handle cases where models return tool calls instead of content
        if not content and "tool_calls" in message:
            # Model wants to call web_search function - extract the query
            tool_calls = message["tool_calls"]
            if tool_calls:
                # For now, inform user that model attempted tool call
                content = f"⚠️ Model attempted to call search tool but function execution is not yet implemented. Query: {tool_calls[0].get('function', {}).get('arguments', 'N/A')}"

        # Handle completely empty responses
        if not content:
            content = "⚠️ Model returned empty response. This may indicate the model doesn't support the requested operation or encountered an internal error."

        # Add web search disclaimer if requested but not supported
        if web_search_requested and not has_web_search:
            content = f"📚 **Note: Web search not available for this model ({officer['model']}). Response based on pretraining knowledge only.**\n\n{content}"

        return {
            "officer_id": officer_id,
            "title": officer["title"],
            "model": officer["model"],
            "specialty": officer["specialty"],
            "capability_class": officer.get("capability_class", "Operational"),
            "color": get_officer_color(officer),
            "research_role": role_config["role"],
            "response": content,
            "success": True if content and not content.startswith("⚠️") else False,
        }
    except Exception as e:
        return {
            "officer_id": officer_id,
            "title": officer["title"],
            "model": officer["model"],
            "specialty": officer["specialty"],
            "capability_class": officer.get("capability_class", "Operational"),
            "color": get_officer_color(officer),
            "research_role": role_config["role"],
            "response": f"Error: {str(e)}",
            "success": False,
            "error": str(e),
        }


async def query_research_council(
    research_topic: str, capability_class: str, channel_id: int = None, use_web_search: bool = False
) -> List[Dict[str, Any]]:
    """Query 4 officers from capability class with research roles."""
    officer_ids = filter_officers_by_capability(capability_class)

    if len(officer_ids) != 4:
        raise ValueError(f"Expected 4 officers in {capability_class}, found {len(officer_ids)}")

    async with httpx.AsyncClient() as client:
        tasks = [
            query_officer_with_research_role(
                officer_ids[i], research_topic, i, client, channel_id, use_web_search
            )
            for i in range(4)
        ]
        results = await asyncio.gather(*tasks)

    return results


def generate_research_markdown(
    topic: str, results: List[Dict[str, Any]], capability_class: str, use_web_search: bool = False
) -> str:
    """Generate structured markdown report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    search_status = (
        "✅ Web Search Enabled - Sources Cited"
        if use_web_search
        else "📚 Pretraining Knowledge Only"
    )

    md = f"""# Research Report: {topic}

**Generated:** {timestamp}
**Capability Class:** {capability_class.title()}
**Research Council:** {', '.join([r['officer_id'] for r in results])}
**Search Mode:** {search_status}

---

## Executive Summary

This research explores **{topic}** through four analytical lenses:
- **State-of-the-Art:** Current best practices
- **Critical Analysis:** Limitations and risks
- **Visionary Perspective:** Future possibilities
- **Historical Context:** Evolution and lessons

---

"""

    # Add each perspective
    for result in results:
        md += f"""## {result['research_role']}

**Officer:** {result['officer_id']} - {result['title']}
**Model:** {result['model']}

{result['response']}

---

"""

    md += "\n**Report generated by Atlas War Room - Research Command**\n"
    return md


def calculate_embed_size(embed: discord.Embed) -> int:
    """Calculate the total character count of an embed."""
    total = 0
    if embed.title:
        total += len(embed.title)
    if embed.description:
        total += len(embed.description)
    if embed.footer.text:
        total += len(embed.footer.text)
    if embed.author.name:
        total += len(embed.author.name)
    for field in embed.fields:
        total += len(field.name) + len(field.value)
    return total


async def send_embeds_in_batches(
    interaction: discord.Interaction, embeds: List[discord.Embed], view: discord.ui.View = None
):
    """Send embeds in batches to avoid Discord's 6000 character limit per message."""
    MAX_EMBED_SIZE = 5500  # Safe margin under 6000
    current_batch = []
    current_size = 0

    for i, embed in enumerate(embeds):
        embed_size = calculate_embed_size(embed)

        # If adding this embed would exceed the limit, send current batch
        if current_size + embed_size > MAX_EMBED_SIZE and current_batch:
            # Send without view (view only goes on the last message)
            await interaction.followup.send(embeds=current_batch)
            current_batch = []
            current_size = 0

        current_batch.append(embed)
        current_size += embed_size

    # Send remaining embeds with the view attached to the last message
    if current_batch:
        if view:
            await interaction.followup.send(embeds=current_batch, view=view)
        else:
            await interaction.followup.send(embeds=current_batch)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print(f"Active officers: {', '.join(ACTIVE_ROSTER)}")


@bot.tree.command(name="mission", description="Submit a mission brief to the War Room council")
@app_commands.describe(
    brief="The mission brief or question for the council",
    capability_class="Filter by capability class (optional)",
)
@app_commands.choices(
    capability_class=[
        app_commands.Choice(name="Strategic (O1-O4)", value="strategic"),
        app_commands.Choice(name="Operational (O5-O8)", value="operational"),
        app_commands.Choice(name="Tactical (O9-O12)", value="tactical"),
        app_commands.Choice(name="Support (O13-O16)", value="support"),
    ]
)
async def mission(interaction: discord.Interaction, brief: str, capability_class: str = None):
    """Mission command - queries all officers in parallel, optionally filtered by capability class."""
    await interaction.response.defer()

    # Extract channel info
    channel_id = interaction.channel_id
    channel_name = interaction.channel.name if interaction.channel else "DM"
    guild_id = interaction.guild_id if interaction.guild else 0
    user_id = interaction.user.id

    # Ensure channel exists in database
    await ensure_channel_exists(channel_id, channel_name, guild_id)

    # Query officers with memory, filtered by capability class if specified
    results = await query_all_officers(brief, capability_class, channel_id)

    # Save mission to database (auto-capture)
    await save_mission(channel_id, brief, user_id, capability_class, results)

    # Handle case where no officers match the filter
    if not results:
        await interaction.followup.send(
            f"❌ No officers found for capability class: **{capability_class}**\n"
            f"Available classes: Strategic, Operational, Tactical, Support"
        )
        return

    # Create embed for mission brief
    header_title = "🎯 War Room Mission Brief"
    if capability_class:
        header_title += f" - {capability_class.title()} Class"

    header_embed = discord.Embed(
        title=header_title,
        description=brief,
        color=(
            CAPABILITY_COLORS.get(capability_class.title(), 0x95A5A6)
            if capability_class
            else 0x95A5A6
        ),
    )
    header_embed.set_footer(
        text=f"Requested by {interaction.user.display_name} • Officers: {len(results)}"
    )

    embeds = [header_embed]

    # Create embed for each officer response
    for result in results:
        embed = discord.Embed(
            title=f"**[{result['officer_id']} - {result['title']}]** • {result['model']}",
            description=result["response"][:4096],  # Discord embed description limit
            color=result["color"],
        )
        embed.add_field(name="Class", value=result["capability_class"], inline=True)
        embed.add_field(name="Specialty", value=result["specialty"], inline=True)
        embed.add_field(
            name="Status", value="✅ Complete" if result["success"] else "❌ Error", inline=True
        )
        embeds.append(embed)

    # Send response with interactive view
    view = WarRoomView(brief, results, capability_class)

    # Discord has a 6000 character limit for total embed size per message
    # Split embeds into batches if needed
    await send_embeds_in_batches(interaction, embeds, view)


@bot.tree.command(name="research", description="Conduct multi-perspective research on a topic")
@app_commands.describe(
    topic="The research question or topic to investigate",
    capability_class="Which officer class should research this (Required)",
    use_web_search="Enable real-time web search and source citations (Default: False)",
)
@app_commands.choices(
    capability_class=[
        app_commands.Choice(name="Strategic (O1-O4)", value="strategic"),
        app_commands.Choice(name="Operational (O5-O8)", value="operational"),
        app_commands.Choice(name="Tactical (O9-O12)", value="tactical"),
        app_commands.Choice(name="Support (O13-O16)", value="support"),
    ]
)
async def research(
    interaction: discord.Interaction,
    topic: str,
    capability_class: str,
    use_web_search: bool = False,
):
    """Research command - assigns research roles to 4 officers."""
    await interaction.response.defer()

    # Extract channel info
    channel_id = interaction.channel_id
    channel_name = interaction.channel.name if interaction.channel else "DM"
    guild_id = interaction.guild_id if interaction.guild else 0
    user_id = interaction.user.id

    # Ensure channel exists
    await ensure_channel_exists(channel_id, channel_name, guild_id)

    try:
        # Query research council with optional web search
        results = await query_research_council(topic, capability_class, channel_id, use_web_search)
    except ValueError as e:
        await interaction.followup.send(f"❌ {str(e)}")
        return

    # Save to database with research metadata
    research_metadata = {
        "mission_type": "research",
        "research_roles": {r["officer_id"]: r["research_role"] for r in results},
        "web_search_enabled": use_web_search,
    }

    mission_brief = f"[RESEARCH] {topic}"
    await save_research_mission(
        channel_id, mission_brief, user_id, capability_class, results, research_metadata
    )

    # Create header embed
    search_indicator = "🌐 Web Search Enabled" if use_web_search else "📚 Pretraining Only"
    header_embed = discord.Embed(
        title=f"🔬 Research Mission - {capability_class.title()} Class",
        description=f"**Topic:** {topic}\n**Mode:** {search_indicator}\n\n**Perspectives:** State-of-the-Art, Critical Analysis, Visionary, Historical Context",
        color=CAPABILITY_COLORS.get(capability_class.title(), 0x95A5A6),
    )
    header_embed.set_footer(text=f"Requested by {interaction.user.display_name}")

    embeds = [header_embed]

    # Create embeds for each research perspective
    for result in results:
        embed = discord.Embed(
            title=f"**{result['research_role']}**",
            description=f"**[{result['officer_id']} - {result['title']}]** • {result['model']}\n\n{result['response'][:3900]}",
            color=result["color"],
        )
        embed.add_field(name="Class", value=result["capability_class"], inline=True)
        embed.add_field(name="Specialty", value=result["specialty"], inline=True)
        embed.add_field(
            name="Status", value="✅ Complete" if result["success"] else "❌ Error", inline=True
        )
        embeds.append(embed)

    # Send with research view
    view = ResearchView(topic, results, capability_class, use_web_search)
    await send_embeds_in_batches(interaction, embeds, view)


class ConfirmClearView(discord.ui.View):
    """Confirmation dialog for clearing memory."""

    def __init__(self, channel_id: int, officer_id: str):
        super().__init__(timeout=30)
        self.channel_id = channel_id
        self.officer_id = officer_id

    @discord.ui.button(label="Yes, Clear", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await clear_officer_memory(self.channel_id, self.officer_id)
        await interaction.response.send_message(f"✅ Cleared {self.officer_id}'s memory")

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Cancelled")


@bot.tree.command(name="memory", description="Manage officer memory for this channel")
@app_commands.describe(
    action="Action to perform",
    officer_id="Officer ID (O1-O16)",
    note="Note content (for 'add' action)",
)
@app_commands.choices(
    action=[
        app_commands.Choice(name="📊 View Stats", value="stats"),
        app_commands.Choice(name="🔍 View Officer", value="view"),
        app_commands.Choice(name="➕ Add Note", value="add"),
        app_commands.Choice(name="🗑️ Clear Officer", value="clear"),
    ]
)
async def memory(
    interaction: discord.Interaction, action: str, officer_id: str = None, note: str = None
):
    """Memory management commands."""
    channel_id = interaction.channel_id

    if action == "stats":
        # Display channel memory statistics
        stats = await get_channel_stats(channel_id)

        embed = discord.Embed(
            title="📊 Channel Memory Statistics",
            description=f"Memory status for {interaction.channel.name}",
            color=0x3498DB,
        )

        for off_id, data in stats.items():
            officer = OFFICERS.get(off_id)
            if officer:
                embed.add_field(
                    name=f"{off_id} - {officer['title']}",
                    value=f"Notes: {data['notes']} | Missions: {data['missions']}",
                    inline=False,
                )

        await interaction.response.send_message(embed=embed)

    elif action == "view":
        # Display detailed memory for one officer
        if not officer_id:
            await interaction.response.send_message("❌ Please specify an officer_id")
            return

        if officer_id not in OFFICERS:
            await interaction.response.send_message(f"❌ Invalid officer_id: {officer_id}")
            return

        memory_text = await load_officer_memory(channel_id, officer_id)

        embed = discord.Embed(
            title=f"🧠 Memory: {officer_id} - {OFFICERS[officer_id]['title']}",
            description=memory_text if memory_text else "No memory yet",
            color=get_officer_color(OFFICERS[officer_id]),
        )

        await interaction.response.send_message(embed=embed)

    elif action == "add":
        # Add manual note
        if not officer_id or not note:
            await interaction.response.send_message("❌ Please specify officer_id and note")
            return

        if officer_id not in OFFICERS:
            await interaction.response.send_message(f"❌ Invalid officer_id: {officer_id}")
            return

        await add_manual_note(channel_id, officer_id, note, interaction.user.id)

        await interaction.response.send_message(
            f"✅ Added note to {officer_id}'s memory in this channel"
        )

    elif action == "clear":
        # Clear officer's memory with confirmation
        if not officer_id:
            await interaction.response.send_message("❌ Please specify an officer_id")
            return

        if officer_id not in OFFICERS:
            await interaction.response.send_message(f"❌ Invalid officer_id: {officer_id}")
            return

        view = ConfirmClearView(channel_id, officer_id)
        await interaction.response.send_message(
            f"⚠️ Clear all manual notes for {officer_id} in this channel?", view=view
        )


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

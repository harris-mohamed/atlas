import discord
from discord import app_commands
import httpx
import json
import os
import asyncio
from typing import Dict, List, Any
from dotenv import load_dotenv

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

# Capability class color mapping
CAPABILITY_COLORS = {
    "Strategic": 0x9b59b6,     # Purple
    "Operational": 0x3498db,   # Blue
    "Tactical": 0x2ecc71,      # Green
    "Support": 0xf39c12        # Orange
}

def get_officer_color(officer: Dict[str, Any]) -> int:
    """Get color for an officer based on their capability class."""
    # First check if officer has explicit color
    if "color" in officer:
        return int(officer["color"], 16)
    # Otherwise use capability class color
    capability_class = officer.get("capability_class", "Operational")
    return CAPABILITY_COLORS.get(capability_class, 0x95a5a6)

def filter_officers_by_capability(capability_class: str = None) -> List[str]:
    """Filter active officers by capability class."""
    if not capability_class:
        return ACTIVE_ROSTER

    # Case-insensitive matching
    capability_class_lower = capability_class.lower()

    return [
        officer_id for officer_id in ACTIVE_ROSTER
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


bot = WarRoomBot()


class PivotModal(discord.ui.Modal, title="🔄 Mission Pivot"):
    """Modal for mid-mission course corrections."""

    pivot_instruction = discord.ui.TextInput(
        label="Course Correction",
        style=discord.TextStyle.paragraph,
        placeholder="Describe the new direction or focus...",
        required=True,
        max_length=2000
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
        results = await query_all_officers(new_brief, self.capability_class)

        # Create response embeds
        header_embed = discord.Embed(
            title="🔄 Pivoted Mission Brief",
            description=new_brief,
            color=0xe67e22
        )
        header_embed.set_footer(text=f"Pivoted by {interaction.user.display_name}")

        embeds = [header_embed]

        for result in results:
            embed = discord.Embed(
                title=f"**[{result['officer_id']} - {result['title']}]** • {result['model']}",
                description=result['response'][:4096],
                color=result['color']
            )
            embed.add_field(name="Class", value=result['capability_class'], inline=True)
            embed.add_field(name="Specialty", value=result['specialty'], inline=True)
            embed.add_field(
                name="Status",
                value="✅ Complete" if result['success'] else "❌ Error",
                inline=True
            )
            embeds.append(embed)

        # Send with a new view, splitting embeds if needed
        view = WarRoomView(new_brief, results, self.capability_class)
        await send_embeds_in_batches(interaction, embeds, view)


class WarRoomView(discord.ui.View):
    """Interactive view with War Room control buttons."""

    def __init__(self, mission_brief: str, results: List[Dict[str, Any]], capability_class: str = None):
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
            council_output += f"**[{result['officer_id']} - {result['title']}]:**\n{result['response']}\n\n"

        # Query O-3 with the compiled responses
        rebuttal_prompt = f"{council_output}\n\n**Task:** Provide a Red Team rebuttal. Identify weaknesses, risks, and failure modes in the council's responses."

        async with httpx.AsyncClient() as client:
            o3_result = await query_officer("O3", rebuttal_prompt, client)

        # Create rebuttal embed
        embed = discord.Embed(
            title="🔴 Red Team Rebuttal",
            description=o3_result['response'][:4096],
            color=o3_result['color']
        )
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")

        await interaction.followup.send(embed=embed)

    @discord.ui.button(label="Generate Plan", style=discord.ButtonStyle.primary, emoji="📄")
    async def generate_plan_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Trigger O-2 to synthesize responses into a PLAN.md."""
        await interaction.response.defer()

        # Compile all officer responses
        council_output = f"**Original Mission:** {self.mission_brief}\n\n"
        for result in self.results:
            council_output += f"**[{result['officer_id']} - {result['title']}]:**\n{result['response']}\n\n"

        # Query O-2 to create a structured plan
        plan_prompt = f"{council_output}\n\n**Task:** Synthesize the council's responses into a structured PLAN.md document. Include: Executive Summary, Key Objectives, Implementation Steps, Risk Mitigation, and Success Criteria."

        async with httpx.AsyncClient() as client:
            o2_result = await query_officer("O2", plan_prompt, client)

        # Create plan embed
        embed = discord.Embed(
            title="📄 Strategic Plan",
            description=o2_result['response'][:4096],
            color=o2_result['color']
        )
        embed.set_footer(text=f"Generated by {interaction.user.display_name}")

        await interaction.followup.send(embed=embed)

    @discord.ui.button(label="Pivot", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def pivot_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal for mid-mission course correction."""
        modal = PivotModal(self.mission_brief, self.capability_class)
        await interaction.response.send_modal(modal)


async def query_officer(
    officer_id: str,
    mission_brief: str,
    client: httpx.AsyncClient
) -> Dict[str, Any]:
    """Query a single officer via OpenRouter API."""
    officer = OFFICERS[officer_id]

    payload = {
        "model": officer["model"],
        "messages": [
            {"role": "system", "content": officer["system_prompt"]},
            {"role": "user", "content": mission_brief}
        ]
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=60.0
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
            "success": True
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
            "success": False
        }


async def query_all_officers(mission_brief: str, capability_class: str = None) -> List[Dict[str, Any]]:
    """Query all active officers in parallel, optionally filtered by capability class."""
    # Filter officers by capability class if specified
    officer_ids = filter_officers_by_capability(capability_class)

    if not officer_ids:
        return []

    async with httpx.AsyncClient() as client:
        tasks = [
            query_officer(officer_id, mission_brief, client)
            for officer_id in officer_ids
        ]
        results = await asyncio.gather(*tasks)

    return results


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
    interaction: discord.Interaction,
    embeds: List[discord.Embed],
    view: discord.ui.View = None
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
    capability_class="Filter by capability class (optional)"
)
@app_commands.choices(capability_class=[
    app_commands.Choice(name="Strategic (O1-O4)", value="strategic"),
    app_commands.Choice(name="Operational (O5-O8)", value="operational"),
    app_commands.Choice(name="Tactical (O9-O12)", value="tactical"),
    app_commands.Choice(name="Support (O13-O16)", value="support")
])
async def mission(interaction: discord.Interaction, brief: str, capability_class: str = None):
    """Mission command - queries all officers in parallel, optionally filtered by capability class."""
    await interaction.response.defer()

    # Query officers, filtered by capability class if specified
    results = await query_all_officers(brief, capability_class)

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
        color=CAPABILITY_COLORS.get(capability_class.title(), 0x95a5a6) if capability_class else 0x95a5a6
    )
    header_embed.set_footer(text=f"Requested by {interaction.user.display_name} • Officers: {len(results)}")

    embeds = [header_embed]

    # Create embed for each officer response
    for result in results:
        embed = discord.Embed(
            title=f"**[{result['officer_id']} - {result['title']}]** • {result['model']}",
            description=result['response'][:4096],  # Discord embed description limit
            color=result['color']
        )
        embed.add_field(name="Class", value=result['capability_class'], inline=True)
        embed.add_field(name="Specialty", value=result['specialty'], inline=True)
        embed.add_field(
            name="Status",
            value="✅ Complete" if result['success'] else "❌ Error",
            inline=True
        )
        embeds.append(embed)

    # Send response with interactive view
    view = WarRoomView(brief, results, capability_class)

    # Discord has a 6000 character limit for total embed size per message
    # Split embeds into batches if needed
    await send_embeds_in_batches(interaction, embeds, view)


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

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

    def __init__(self, original_brief: str):
        super().__init__()
        self.original_brief = original_brief

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        # Combine original brief with pivot instruction
        new_brief = f"{self.original_brief}\n\n**PIVOT:** {self.pivot_instruction.value}"

        # Re-query all officers with the pivoted mission
        results = await query_all_officers(new_brief)

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
                title=f"**[{result['officer_id']} - {result['title']}]**",
                description=result['response'][:4096],
                color=result['color']
            )
            embed.add_field(name="Specialty", value=result['specialty'], inline=True)
            embed.add_field(
                name="Status",
                value="✅ Complete" if result['success'] else "❌ Error",
                inline=True
            )
            embeds.append(embed)

        # Send with a new view
        view = WarRoomView(new_brief, results)
        await interaction.followup.send(embeds=embeds, view=view)


class WarRoomView(discord.ui.View):
    """Interactive view with War Room control buttons."""

    def __init__(self, mission_brief: str, results: List[Dict[str, Any]]):
        super().__init__(timeout=None)
        self.mission_brief = mission_brief
        self.results = results

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
        modal = PivotModal(self.mission_brief)
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
            "specialty": officer["specialty"],
            "color": int(officer["color"], 16),
            "response": content,
            "success": True
        }
    except Exception as e:
        return {
            "officer_id": officer_id,
            "title": officer["title"],
            "specialty": officer["specialty"],
            "color": int(officer["color"], 16),
            "response": f"Error: {str(e)}",
            "success": False
        }


async def query_all_officers(mission_brief: str) -> List[Dict[str, Any]]:
    """Query all active officers in parallel."""
    async with httpx.AsyncClient() as client:
        tasks = [
            query_officer(officer_id, mission_brief, client)
            for officer_id in ACTIVE_ROSTER
        ]
        results = await asyncio.gather(*tasks)

    return results


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print(f"Active officers: {', '.join(ACTIVE_ROSTER)}")


@bot.tree.command(name="mission", description="Submit a mission brief to the War Room council")
@app_commands.describe(brief="The mission brief or question for the council")
async def mission(interaction: discord.Interaction, brief: str):
    """Mission command - queries all officers in parallel."""
    await interaction.response.defer()

    # Query all officers
    results = await query_all_officers(brief)

    # Create embed for mission brief
    header_embed = discord.Embed(
        title="🎯 War Room Mission Brief",
        description=brief,
        color=0x95a5a6
    )
    header_embed.set_footer(text=f"Requested by {interaction.user.display_name}")

    embeds = [header_embed]

    # Create embed for each officer response
    for result in results:
        embed = discord.Embed(
            title=f"**[{result['officer_id']} - {result['title']}]**",
            description=result['response'][:4096],  # Discord embed description limit
            color=result['color']
        )
        embed.add_field(name="Specialty", value=result['specialty'], inline=True)
        embed.add_field(
            name="Status",
            value="✅ Complete" if result['success'] else "❌ Error",
            inline=True
        )
        embeds.append(embed)

    # Send response with interactive view
    view = WarRoomView(brief, results)
    await interaction.followup.send(embeds=embeds, view=view)


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

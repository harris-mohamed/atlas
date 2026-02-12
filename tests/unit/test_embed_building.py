"""
Unit tests for embed construction helpers in bot.py:
  - calculate_embed_size()
  - send_embeds_in_batches()
"""
import pytest
import discord
from unittest.mock import AsyncMock, MagicMock, patch, call

import bot


def make_embed(title="", description="", fields=None, footer="", author=""):
    """Build a real discord.Embed with the given content."""
    embed = discord.Embed(title=title, description=description)
    for name, value in (fields or []):
        embed.add_field(name=name, value=value)
    if footer:
        embed.set_footer(text=footer)
    if author:
        embed.set_author(name=author)
    return embed


def make_interaction():
    """Build a mock discord.Interaction with a followup.send AsyncMock."""
    interaction = MagicMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction


# ---------------------------------------------------------------------------
# calculate_embed_size
# ---------------------------------------------------------------------------

class TestCalculateEmbedSize:
    def test_empty_embed_returns_zero(self):
        embed = discord.Embed()
        assert bot.calculate_embed_size(embed) == 0

    def test_counts_title(self):
        embed = make_embed(title="Hello")
        assert bot.calculate_embed_size(embed) == len("Hello")

    def test_counts_description(self):
        embed = make_embed(description="World")
        assert bot.calculate_embed_size(embed) == len("World")

    def test_counts_fields(self):
        embed = make_embed(fields=[("Name1", "Value1"), ("Name2", "Value2")])
        expected = len("Name1") + len("Value1") + len("Name2") + len("Value2")
        assert bot.calculate_embed_size(embed) == expected

    def test_counts_footer(self):
        embed = make_embed(footer="Footer text")
        assert bot.calculate_embed_size(embed) == len("Footer text")

    def test_counts_author(self):
        embed = make_embed(author="Author Name")
        assert bot.calculate_embed_size(embed) == len("Author Name")

    def test_sums_all_components(self):
        embed = make_embed(
            title="T",
            description="D",
            fields=[("F", "V")],
            footer="Foot",
            author="Auth",
        )
        expected = len("T") + len("D") + len("F") + len("V") + len("Foot") + len("Auth")
        assert bot.calculate_embed_size(embed) == expected

    def test_large_embed_size_is_accurate(self):
        title = "A" * 100
        description = "B" * 500
        embed = make_embed(title=title, description=description)
        assert bot.calculate_embed_size(embed) == 600


# ---------------------------------------------------------------------------
# send_embeds_in_batches
# ---------------------------------------------------------------------------

class TestSendEmbedsInBatches:
    @pytest.mark.asyncio
    async def test_single_small_embed_one_send_call(self):
        interaction = make_interaction()
        embed = make_embed(title="Small", description="Short content")
        view = MagicMock()

        await bot.send_embeds_in_batches(interaction, [embed], view)

        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_view_attached_to_last_message(self):
        interaction = make_interaction()
        # Create embeds that together exceed 5500 chars to force 2 batches
        big_embed_1 = make_embed(description="A" * 3000)
        big_embed_2 = make_embed(description="B" * 3000)
        view = MagicMock()

        await bot.send_embeds_in_batches(interaction, [big_embed_1, big_embed_2], view)

        assert interaction.followup.send.call_count == 2
        # View must only appear in the last call
        last_call_kwargs = interaction.followup.send.call_args_list[-1].kwargs
        assert last_call_kwargs.get("view") is view

    @pytest.mark.asyncio
    async def test_view_not_in_earlier_batches(self):
        interaction = make_interaction()
        big_embed_1 = make_embed(description="A" * 3000)
        big_embed_2 = make_embed(description="B" * 3000)
        view = MagicMock()

        await bot.send_embeds_in_batches(interaction, [big_embed_1, big_embed_2], view)

        first_call_kwargs = interaction.followup.send.call_args_list[0].kwargs
        assert "view" not in first_call_kwargs

    @pytest.mark.asyncio
    async def test_three_batches_for_three_large_embeds(self):
        # Each embed is 2800 chars. 2800+2800=5600 > 5500, so each must go in its own batch.
        interaction = make_interaction()
        embeds = [make_embed(description="X" * 2800) for _ in range(3)]
        view = MagicMock()

        await bot.send_embeds_in_batches(interaction, embeds, view)

        assert interaction.followup.send.call_count == 3

    @pytest.mark.asyncio
    async def test_no_view_sends_without_view_kwarg(self):
        interaction = make_interaction()
        embed = make_embed(description="Content")

        await bot.send_embeds_in_batches(interaction, [embed], view=None)

        call_kwargs = interaction.followup.send.call_args.kwargs
        assert "view" not in call_kwargs

    @pytest.mark.asyncio
    async def test_empty_embed_list_does_not_send(self):
        interaction = make_interaction()
        await bot.send_embeds_in_batches(interaction, [], view=None)
        interaction.followup.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_all_embeds_present_across_batches(self):
        """Every embed appears in exactly one batch."""
        interaction = make_interaction()
        embeds = [make_embed(description=f"Embed {i}" + "X" * 2800) for i in range(3)]
        view = MagicMock()

        await bot.send_embeds_in_batches(interaction, embeds, view)

        all_sent_embeds = []
        for c in interaction.followup.send.call_args_list:
            all_sent_embeds.extend(c.kwargs.get("embeds", []))

        assert len(all_sent_embeds) == 3
        for embed in embeds:
            assert embed in all_sent_embeds

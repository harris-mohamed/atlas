/**
 * /research command handler
 *
 * Creates a thread, spawns a research agent, and streams progress
 */

import {
  ChatInputCommandInteraction,
  SlashCommandBuilder,
  ChannelType,
} from 'discord.js';
import { logger } from '../logger.js';

export const researchCommand = {
  data: new SlashCommandBuilder()
    .setName('research')
    .setDescription('Start deep autonomous research on a topic')
    .addStringOption((option) =>
      option
        .setName('topic')
        .setDescription('The research topic or question')
        .setRequired(true),
    )
    .addStringOption((option) =>
      option
        .setName('scope')
        .setDescription('Research scope: broad or focused')
        .addChoices(
          { name: 'Broad (survey of the field)', value: 'broad' },
          { name: 'Focused (deep dive on specific aspect)', value: 'focused' },
        ),
    ),

  async execute(interaction: ChatInputCommandInteraction, onMessage: any) {
    const topic = interaction.options.getString('topic', true);
    const scope = interaction.options.getString('scope') || 'broad';

    try {
      if (!interaction.channel) {
        await interaction.reply({
          content: 'This command must be used in a channel.',
          ephemeral: true,
        });
        return;
      }

      await interaction.deferReply();

      if (!('threads' in interaction.channel)) {
        await interaction.editReply(
          'This command must be used in a text channel.',
        );
        return;
      }

      const thread = await (interaction.channel as any).threads.create({
        name: `Research: ${topic.slice(0, 80)}`,
        autoArchiveDuration: 1440,
        type: ChannelType.PublicThread,
        reason: `Research task initiated by ${interaction.user.tag}`,
      });

      logger.info(
        {
          threadId: thread.id,
          topic,
          scope,
          user: interaction.user.tag,
        },
        'Research thread created',
      );

      await thread.send(
        `🔬 **Research Task Started**\n\n` +
          `**Topic:** ${topic}\n` +
          `**Scope:** ${scope}\n` +
          `**Initiated by:** ${interaction.user}\n\n` +
          `Research agent is starting up...`,
      );

      await interaction.editReply({
        content: `✅ Research started! Follow progress here: ${thread.url}`,
      });

      const researchPrompt = buildResearchPrompt(topic, scope);

      onMessage(thread.id, {
        id: `cmd-${Date.now()}`,
        chat_jid: thread.id,
        sender: interaction.user.id,
        sender_name: interaction.user.username,
        content: researchPrompt,
        timestamp: new Date().toISOString(),
        is_from_me: false,
        is_bot_message: false,
      });
    } catch (err) {
      logger.error({ err, topic }, 'Failed to create research thread');

      if (interaction.deferred) {
        await interaction.editReply({
          content: `❌ Failed to start research: ${err instanceof Error ? err.message : 'Unknown error'}`,
        });
      } else {
        await interaction.reply({
          content: `❌ Failed to start research: ${err instanceof Error ? err.message : 'Unknown error'}`,
          ephemeral: true,
        });
      }
    }
  },
};

function buildResearchPrompt(topic: string, scope: string): string {
  const scopeGuidance =
    scope === 'focused'
      ? 'Focus on deep, detailed analysis of the specific aspect. Prioritize primary sources and technical depth.'
      : 'Provide a comprehensive survey of the field. Cover multiple perspectives and the current state of knowledge.';

  return `Research topic: ${topic}\n\nScope: ${scope}\n\n${scopeGuidance}\n\nBegin your research process.`;
}

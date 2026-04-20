/**
 * /reminder command handler
 *
 * Schedules a one-shot direct message delivered to the channel at a future time.
 * Uses context_mode: 'direct' — no container is spawned.
 */

import crypto from 'crypto';
import { ChatInputCommandInteraction, SlashCommandBuilder } from 'discord.js';

import { TIMEZONE } from '../config.js';
import { createTask } from '../db.js';
import { logger } from '../logger.js';

const UNIT_MS: Record<string, number> = {
  minutes: 60_000,
  hours: 3_600_000,
  days: 86_400_000,
};

export const reminderCommand = {
  data: new SlashCommandBuilder()
    .setName('reminder')
    .setDescription('Set a reminder to be delivered in this channel')
    .addStringOption((o) =>
      o
        .setName('message')
        .setDescription('What to remind you about')
        .setRequired(true),
    )
    .addIntegerOption((o) =>
      o
        .setName('in')
        .setDescription('How many units from now')
        .setRequired(true)
        .setMinValue(1),
    )
    .addStringOption((o) =>
      o
        .setName('unit')
        .setDescription('Time unit')
        .setRequired(true)
        .addChoices(
          { name: 'minutes', value: 'minutes' },
          { name: 'hours', value: 'hours' },
          { name: 'days', value: 'days' },
        ),
    ),

  async execute(interaction: ChatInputCommandInteraction) {
    const message = interaction.options.getString('message', true);
    const amount = interaction.options.getInteger('in', true);
    const unit = interaction.options.getString('unit', true);

    const deliverAt = new Date(Date.now() + amount * UNIT_MS[unit]);
    const channelId = interaction.channelId;
    const suffix = channelId.slice(-6);
    const taskId = crypto.randomUUID();

    try {
      createTask({
        id: taskId,
        group_folder: `reminders-${suffix}`,
        chat_jid: channelId,
        prompt: `⏰ **Reminder:** ${message}`,
        schedule_type: 'once',
        schedule_value: '',
        context_mode: 'direct',
        next_run: deliverAt.toISOString(),
        status: 'active',
        created_at: new Date().toISOString(),
      });

      const timeStr = deliverAt.toLocaleString('en-US', { timeZone: TIMEZONE });
      logger.info({ taskId, channelId, deliverAt }, 'Reminder scheduled');

      await interaction.reply({
        content:
          `✅ Reminder set for **${timeStr}**\n` +
          `> ${message}\n\n` +
          `*Task ID: \`${taskId}\` — cancel with \`/status detailed\`*`,
        ephemeral: true,
      });
    } catch (err) {
      logger.error({ err, channelId }, 'Failed to schedule reminder');
      await interaction.reply({
        content: `❌ Failed to set reminder: ${err instanceof Error ? err.message : 'Unknown error'}`,
        ephemeral: true,
      });
    }
  },
};

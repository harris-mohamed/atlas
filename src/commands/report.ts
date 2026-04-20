/**
 * /report command handler
 *
 * Schedules recurring research briefings posted to a Discord channel.
 */

import crypto from 'crypto';
import fs from 'fs';
import path from 'path';

import {
  ChannelType,
  ChatInputCommandInteraction,
  SlashCommandBuilder,
} from 'discord.js';

import { RESEARCH_SYSTEM_PROMPT } from '../agents/research-prompt.js';
import { TIMEZONE } from '../config.js';
import { createTask } from '../db.js';
import { logger } from '../logger.js';
import { computeNextRun } from '../task-scheduler.js';
import { RegisteredGroup } from '../types.js';

// Map schedule + time choices to cron expressions (uses TIMEZONE via scheduler)
function buildCron(schedule: string, hour: number): string {
  switch (schedule) {
    case 'daily':
      return `0 ${hour} * * *`;
    case 'weekdays':
      return `0 ${hour} * * 1-5`;
    case 'weekly-mon':
      return `0 ${hour} * * 1`;
    case 'weekly-fri':
      return `0 ${hour} * * 5`;
    case 'twice-daily':
      return `0 ${hour},${hour + 12 > 23 ? hour : hour + 12} * * *`;
    default:
      return `0 ${hour} * * *`;
  }
}

export const reportCommand = {
  data: new SlashCommandBuilder()
    .setName('report')
    .setDescription('Schedule a recurring research briefing to a channel')
    .addStringOption((o) =>
      o
        .setName('topic')
        .setDescription(
          'What to research and report on (e.g. "LLM development updates")',
        )
        .setRequired(true),
    )
    .addStringOption((o) =>
      o
        .setName('schedule')
        .setDescription('How often to run')
        .setRequired(true)
        .addChoices(
          { name: 'Daily', value: 'daily' },
          { name: 'Weekdays (Mon–Fri)', value: 'weekdays' },
          { name: 'Weekly on Monday', value: 'weekly-mon' },
          { name: 'Weekly on Friday', value: 'weekly-fri' },
          { name: 'Twice daily', value: 'twice-daily' },
        ),
    )
    .addStringOption((o) =>
      o
        .setName('time')
        .setDescription('Time to deliver the report')
        .setRequired(true)
        .addChoices(
          { name: '6 AM', value: '6' },
          { name: '7 AM', value: '7' },
          { name: '8 AM', value: '8' },
          { name: '9 AM', value: '9' },
          { name: '10 AM', value: '10' },
          { name: '12 PM', value: '12' },
          { name: '3 PM', value: '15' },
          { name: '6 PM', value: '18' },
        ),
    )
    .addStringOption((o) =>
      o
        .setName('depth')
        .setDescription('Research depth (default: brief)')
        .setRequired(false)
        .addChoices(
          { name: 'Brief — concise digest under 1500 words', value: 'brief' },
          { name: 'Deep — full multi-pass research report', value: 'deep' },
        ),
    )
    .addChannelOption((o) =>
      o
        .setName('channel')
        .setDescription(
          'Channel to post reports in (defaults to current channel)',
        )
        .addChannelTypes(ChannelType.GuildText)
        .setRequired(false),
    ),

  async execute(
    interaction: ChatInputCommandInteraction,
    onRegisterGroup: (jid: string, group: RegisteredGroup) => void,
    registeredGroups: () => Record<string, RegisteredGroup>,
  ) {
    const topic = interaction.options.getString('topic', true);
    const schedule = interaction.options.getString('schedule', true);
    const hour = parseInt(interaction.options.getString('time', true), 10);
    const depth = interaction.options.getString('depth') ?? 'brief';
    const targetChannel =
      interaction.options.getChannel('channel') ?? interaction.channel;

    if (!targetChannel) {
      await interaction.reply({
        content: 'Could not resolve target channel.',
        ephemeral: true,
      });
      return;
    }

    await interaction.deferReply({ ephemeral: true });

    try {
      const channelId = targetChannel.id;
      const cron = buildCron(schedule, hour);

      const slug = topic
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '')
        .slice(0, 40);
      const suffix = channelId.slice(-6);
      const folder = `report_${slug}-${suffix}`;

      if (!registeredGroups()[channelId]) {
        const groupDir = path.join(process.cwd(), 'groups', folder);
        fs.mkdirSync(path.join(groupDir, 'logs'), { recursive: true });
        fs.writeFileSync(
          path.join(groupDir, 'CLAUDE.md'),
          RESEARCH_SYSTEM_PROMPT,
        );

        onRegisterGroup(channelId, {
          name:
            ('name' in targetChannel ? targetChannel.name : null) ??
            `report-${suffix}`,
          folder,
          trigger: `@Atlas`,
          added_at: new Date().toISOString(),
          requiresTrigger: false,
          isMain: false,
        });
      }

      const taskId = crypto.randomUUID();
      const searchInstruction =
        `Use brave_web_search (MCP tool) as your primary search tool — ` +
        `run searches first and fetch full pages only for the most relevant results.`;
      const dedupeInstruction =
        `Before researching, check /workspace/group/reports/ for previous reports (sorted by filename, newest last). ` +
        `Read up to the last 5 files — they are your history of what has already been covered. ` +
        `Do not repeat topics, stories, or sources already covered in those reports; focus only on what is genuinely new. ` +
        `After writing your report, save it to /workspace/group/reports/YYYY-MM-DD.md (today's date).`;
      const prompt =
        depth === 'deep'
          ? `You are writing a deep research report. Topic: "${topic}"\n\n` +
            `${searchInstruction}\n\n` +
            `${dedupeInstruction}\n\n` +
            `Conduct thorough multi-pass research:\n` +
            `1. DECOMPOSE the topic into 3-5 key research questions\n` +
            `2. INVESTIGATE each question with multiple brave_web_search calls, read full articles for top results\n` +
            `3. EVALUATE gaps, contradictions, and unsupported claims\n` +
            `4. DEEPEN with targeted follow-up brave_web_search calls to fill gaps\n` +
            `5. SYNTHESIZE into a comprehensive report written to research.md\n\n` +
            `Minimum 3 research passes before synthesizing. Prioritize depth and accuracy. ` +
            `Include an executive summary, findings by theme with inline citations [Source](URL), ` +
            `a "Confidence & Gaps" section, and a full sources list.`
          : `You are writing a recurring research briefing. Topic: "${topic}"\n\n` +
            `${searchInstruction}\n\n` +
            `${dedupeInstruction}\n\n` +
            `Produce a concise, well-sourced briefing covering the latest developments. ` +
            `Focus on what is new or notable since the last report. ` +
            `Write the briefing directly as your response — do not write to a file. ` +
            `Keep it under 1500 words. Use clear headers, inline citations [Source](URL), ` +
            `and a short "Key Takeaways" section at the top.`;

      const group = registeredGroups()[channelId]!;
      const taskBase = {
        id: taskId,
        group_folder: group.folder,
        chat_jid: channelId,
        prompt,
        schedule_type: 'cron' as const,
        schedule_value: cron,
        context_mode: 'isolated' as const,
        next_run: null as string | null,
        status: 'active' as const,
        created_at: new Date().toISOString(),
        last_run: null,
        last_result: null,
      };

      taskBase.next_run = computeNextRun(taskBase);
      createTask(taskBase);

      const scheduleLabels: Record<string, string> = {
        daily: 'Daily',
        weekdays: 'Weekdays (Mon–Fri)',
        'weekly-mon': 'Weekly on Monday',
        'weekly-fri': 'Weekly on Friday',
        'twice-daily': 'Twice daily',
      };

      const nextRun = taskBase.next_run
        ? new Date(taskBase.next_run!).toLocaleString('en-US', {
            timeZone: TIMEZONE,
          })
        : 'unknown';

      logger.info({ taskId, topic, cron, channelId }, 'Report scheduled');

      const topicPreview =
        topic.length > 200 ? topic.slice(0, 200) + '…' : topic;
      await interaction.editReply(
        `✅ **Report scheduled**\n\n` +
          `**Topic:** ${topicPreview}\n` +
          `**Depth:** ${depth === 'deep' ? 'Deep research' : 'Brief digest'}\n` +
          `**Schedule:** ${scheduleLabels[schedule]} at ${targetChannel}\n` +
          `**Cadence:** \`${cron}\` (${TIMEZONE})\n` +
          `**Next run:** ${nextRun}\n` +
          `**Task ID:** \`${taskBase.id}\`\n\n` +
          `Use \`/status detailed\` to manage scheduled tasks.`,
      );
    } catch (err) {
      logger.error({ err, topic }, 'Failed to schedule report');
      await interaction.editReply(
        `❌ Failed to schedule report: ${err instanceof Error ? err.message : 'Unknown error'}`,
      );
    }
  },
};

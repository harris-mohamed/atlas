#!/usr/bin/env node
/**
 * Google Calendar helper for Atlas containers.
 * Usage:
 *   node calendar.mjs get-today
 *   node calendar.mjs get-week
 *   node calendar.mjs list-calendars
 *   node calendar.mjs create-event "<title>" "<date YYYY-MM-DD>" "<start HH:MM>" "<end HH:MM>" ["<calendar id>"] ["<description>"]
 *   node calendar.mjs cancel-event "<eventId>" "<calendarId>"
 */

import { google } from 'googleapis';

const CLIENT_ID = process.env.GCAL_CLIENT_ID;
const CLIENT_SECRET = process.env.GCAL_CLIENT_SECRET;
const REFRESH_TOKEN = process.env.GCAL_REFRESH_TOKEN;

if (!CLIENT_ID || !CLIENT_SECRET || !REFRESH_TOKEN) {
  console.error('Missing GCAL_CLIENT_ID, GCAL_CLIENT_SECRET, or GCAL_REFRESH_TOKEN');
  process.exit(1);
}

const auth = new google.auth.OAuth2(CLIENT_ID, CLIENT_SECRET);
auth.setCredentials({ refresh_token: REFRESH_TOKEN });
const calendar = google.calendar({ version: 'v3', auth });

function formatTime(dateTime, date) {
  if (date) return 'All day';
  const d = new Date(dateTime);
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true, timeZone: 'America/Denver' });
}

function formatDate(dateTime, date) {
  const d = new Date(dateTime || date);
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', timeZone: 'America/Denver' });
}

async function listCalendars() {
  const res = await calendar.calendarList.list();
  const cals = res.data.items || [];
  console.log('Your calendars:');
  for (const cal of cals) {
    console.log(`  ${cal.summary} — ID: ${cal.id} ${cal.primary ? '(primary)' : ''}`);
  }
}

async function getEvents(daysAhead = 1) {
  const now = new Date();
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setDate(end.getDate() + daysAhead);

  const calList = await calendar.calendarList.list();
  const calendars = calList.data.items || [];

  const allEvents = [];
  for (const cal of calendars) {
    try {
      const res = await calendar.events.list({
        calendarId: cal.id,
        timeMin: start.toISOString(),
        timeMax: end.toISOString(),
        singleEvents: true,
        orderBy: 'startTime',
      });
      for (const event of res.data.items || []) {
        allEvents.push({ ...event, calendarName: cal.summary });
      }
    } catch {
      // Skip calendars we can't read
    }
  }

  // Sort by start time
  allEvents.sort((a, b) => {
    const aTime = a.start.dateTime || a.start.date;
    const bTime = b.start.dateTime || b.start.date;
    return new Date(aTime) - new Date(bTime);
  });

  if (allEvents.length === 0) {
    console.log(daysAhead === 1 ? 'No events today.' : `No events in the next ${daysAhead} days.`);
    return;
  }

  let currentDate = '';
  for (const event of allEvents) {
    const startRaw = event.start.dateTime || event.start.date;
    const dateLabel = formatDate(startRaw, event.start.date);
    if (dateLabel !== currentDate) {
      console.log(`\n📅 ${dateLabel}`);
      currentDate = dateLabel;
    }
    const startTime = formatTime(event.start.dateTime, event.start.date);
    const endTime = event.end?.dateTime ? formatTime(event.end.dateTime) : '';
    const duration = endTime ? ` – ${endTime}` : '';
    const location = event.location ? ` | 📍 ${event.location}` : '';
    const cal = event.calendarName !== 'Harris Mohamed' ? ` [${event.calendarName}]` : '';
    const cancelled = event.summary?.startsWith('(Cancelled)') ? ' ~~' : '';
    console.log(`  ${startTime}${duration}  ${event.summary}${cancelled}${cal}${location}`);
    if (event.hangoutLink) console.log(`    🔗 ${event.hangoutLink}`);
    console.log(`    ID: ${event.id} | Cal: ${event.calendarId || 'primary'}`);
  }
}

async function createEvent(title, date, startTime, endTime, calendarId = 'primary', description = '') {
  const start = new Date(`${date}T${startTime}:00`);
  const end = new Date(`${date}T${endTime}:00`);

  const event = {
    summary: title,
    description,
    start: { dateTime: start.toISOString(), timeZone: 'America/Denver' },
    end: { dateTime: end.toISOString(), timeZone: 'America/Denver' },
    reminders: { useDefault: false, overrides: [{ method: 'popup', minutes: 30 }] },
  };

  const res = await calendar.events.insert({ calendarId, requestBody: event });
  console.log(`✓ Created: "${title}" on ${date} ${startTime}–${endTime}`);
  console.log(`  ID: ${res.data.id} | Link: ${res.data.htmlLink}`);
}

async function cancelEvent(eventId, calendarId = 'primary') {
  const res = await calendar.events.get({ calendarId, eventId });
  const existing = res.data;
  const currentTitle = existing.summary || '';

  if (currentTitle.startsWith('(Cancelled)')) {
    console.log(`Event already marked cancelled: "${currentTitle}"`);
    return;
  }

  const newTitle = `(Cancelled) ${currentTitle}`;
  await calendar.events.patch({
    calendarId,
    eventId,
    requestBody: { summary: newTitle },
  });
  console.log(`✓ Marked cancelled: "${newTitle}"`);
}

const [,, command, ...args] = process.argv;

try {
  switch (command) {
    case 'get-today':
      await getEvents(1);
      break;
    case 'get-week':
      await getEvents(7);
      break;
    case 'list-calendars':
      await listCalendars();
      break;
    case 'create-event':
      await createEvent(args[0], args[1], args[2], args[3], args[4], args[5]);
      break;
    case 'cancel-event':
      await cancelEvent(args[0], args[1]);
      break;
    default:
      console.log('Commands: get-today | get-week | list-calendars | create-event | cancel-event');
      process.exit(1);
  }
} catch (err) {
  console.error('Error:', err.message);
  process.exit(1);
}

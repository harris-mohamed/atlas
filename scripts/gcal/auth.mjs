import http from 'http';
import { google } from 'googleapis';
import fs from 'fs';
import path from 'path';

const CLIENT_ID = process.env.GCAL_CLIENT_ID;
const CLIENT_SECRET = process.env.GCAL_CLIENT_SECRET;
const REDIRECT_URI = process.env.GCAL_REDIRECT_URI || 'http://localhost:5678/rest/oauth2-credential/callback';

if (!CLIENT_ID || !CLIENT_SECRET) {
  console.error('Set GCAL_CLIENT_ID and GCAL_CLIENT_SECRET environment variables');
  process.exit(1);
}

const oauth2Client = new google.auth.OAuth2(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI);

const SCOPES = [
  'https://www.googleapis.com/auth/calendar.readonly',
  'https://www.googleapis.com/auth/calendar.events',
];

const authUrl = oauth2Client.generateAuthUrl({
  access_type: 'offline',
  scope: SCOPES,
  prompt: 'consent',
});

console.log('\n=== Google Calendar Auth ===');
console.log('Open this URL in your browser:\n');
console.log(authUrl);
console.log('\nWaiting for callback on port 5678...\n');

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost:5678');
  if (url.pathname !== '/rest/oauth2-credential/callback') {
    res.end('Not found');
    return;
  }

  const code = url.searchParams.get('code');
  if (!code) {
    res.end('No code received');
    return;
  }

  try {
    const { tokens } = await oauth2Client.getToken(code);
    const tokenPath = path.join(import.meta.dirname, 'token.json');
    fs.writeFileSync(tokenPath, JSON.stringify(tokens, null, 2));
    console.log('✓ Token saved to scripts/gcal/token.json');
    console.log('  Refresh token:', tokens.refresh_token ? '✓ present' : '✗ MISSING — re-run auth');
    res.end('<h1>Authorized! You can close this tab.</h1>');
  } catch (err) {
    console.error('Error getting token:', err.message);
    res.end('Error: ' + err.message);
  }

  server.close();
});

server.listen(5678);

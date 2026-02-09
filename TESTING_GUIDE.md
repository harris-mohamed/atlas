# Memory System Testing Guide

## Quick Start Testing

### 1. Verify System is Running

```bash
# Check containers
docker-compose ps

# Should show:
# ✅ atlas-db: healthy
# ✅ atlas-war-room: running
```

### 2. Basic Memory Flow Test

**In Discord Channel #test-1:**

```
/mission brief:"What's the best way to implement caching?" capability_class:operational

Expected: O5-O8 respond with their analysis
```

**Check Database:**
```bash
docker exec atlas-db psql -U atlas_user -d atlas_db -c \
  "SELECT id, LEFT(mission_brief, 50) as brief, user_id FROM mission_history ORDER BY id DESC LIMIT 1;"
```

**Run Second Mission in Same Channel:**
```
/mission brief:"Follow up: what about Redis vs Memcached?"

Expected: Officers reference previous caching discussion
```

### 3. Test Memory Commands

**View Channel Stats:**
```
/memory action:stats

Expected: Shows all 16 officers with their notes/missions count
```

**Add Manual Note:**
```
/memory action:add officer_id:O1 note:"User prefers async patterns"

Expected: ✅ Added note to O1's memory in this channel
```

**View Officer Memory:**
```
/memory action:view officer_id:O1

Expected: Shows the note you just added + recent missions
```

**Clear Officer Memory:**
```
/memory action:clear officer_id:O1

Expected: ⚠️ Confirmation buttons appear
Click "Yes, Clear" → ✅ Cleared O1's memory
```

### 4. Test Per-Channel Isolation

**In Channel #test-1:**
```
/mission brief:"Topic A: Docker architecture"
```

**In Channel #test-2:**
```
/mission brief:"Topic B: Kubernetes deployment"
```

**Back in Channel #test-1:**
```
/memory action:view officer_id:O1

Expected: Shows only Topic A discussion, NOT Topic B
```

### 5. Test Interactive Buttons

**Run Mission:**
```
/mission brief:"Design a microservices API"
```

**Click "Red Team Rebuttal" button:**
- Expected: O3 critiques the council's responses using channel memory

**Click "Generate Plan" button:**
- Expected: O2 synthesizes a PLAN.md using channel memory

**Click "Pivot" button:**
- Enter: "Focus on security considerations"
- Expected: Officers re-analyze with security focus + original memory

## Advanced Testing

### Test Roster Changes

```bash
# 1. Stop the bot
docker-compose down

# 2. Edit config/roster.json
# Change O1's model from "anthropic/claude-opus-4.5" to something else

# 3. Restart
docker-compose up -d

# 4. Verify update
docker exec atlas-db psql -U atlas_user -d atlas_db -c \
  "SELECT officer_id, model FROM officers WHERE officer_id='O1';"
```

### Test Memory Persistence Across Restarts

```bash
# 1. Run a mission in Discord
/mission brief:"Remember this: blue whales are the largest animals"

# 2. Restart bot
docker-compose restart war-room-bot

# 3. Run follow-up mission
/mission brief:"What did we discuss about whales?"

# Expected: Officers remember the blue whale fact
```

### Test Concurrent Missions

**Open two Discord channels simultaneously:**

**Channel A:**
```
/mission brief:"Topic X"
```

**Channel B (at the same time):**
```
/mission brief:"Topic Y"
```

**Expected:** Both missions complete successfully without interference

### Stress Test

**Run multiple missions rapidly:**
```
/mission brief:"Question 1"
/mission brief:"Question 2"
/mission brief:"Question 3"
```

**Check database:**
```bash
docker exec atlas-db psql -U atlas_user -d atlas_db -c \
  "SELECT COUNT(*) FROM mission_history;"
```

Expected: All 3 missions saved

## Database Inspection Queries

### View All Missions in Current Channel

```sql
-- Replace YOUR_CHANNEL_ID with actual Discord channel ID
SELECT
  id,
  LEFT(mission_brief, 60) as brief,
  started_at,
  completed_at,
  capability_class_filter
FROM mission_history
WHERE channel_id = YOUR_CHANNEL_ID
ORDER BY started_at DESC
LIMIT 10;
```

### View Officer Responses for a Mission

```sql
-- Replace MISSION_ID with actual mission ID
SELECT
  officer_id,
  LEFT(response_content, 100) as response_preview,
  success,
  tokens_used
FROM mission_officer_response
WHERE mission_id = MISSION_ID
ORDER BY officer_id;
```

### View All Notes for an Officer

```sql
SELECT
  officer_id,
  note_content,
  created_at,
  is_pinned
FROM manual_notes
WHERE officer_id = 'O1'
ORDER BY is_pinned DESC, created_at DESC;
```

### Memory Size Analysis

```sql
-- See which officers have the most memory
SELECT
  o.officer_id,
  o.title,
  COUNT(DISTINCT n.id) as manual_notes,
  COUNT(DISTINCT mor.id) as mission_responses,
  COUNT(DISTINCT n.id) + COUNT(DISTINCT mor.id) as total_memory_items
FROM officers o
LEFT JOIN manual_notes n ON o.officer_id = n.officer_id
LEFT JOIN mission_officer_response mor ON o.officer_id = mor.officer_id
GROUP BY o.officer_id, o.title
ORDER BY total_memory_items DESC;
```

### Channel Activity Report

```sql
SELECT
  c.channel_id,
  c.channel_name,
  COUNT(DISTINCT mh.id) as total_missions,
  COUNT(DISTINCT mor.id) as total_responses,
  MAX(mh.started_at) as last_mission
FROM channels c
LEFT JOIN mission_history mh ON c.channel_id = mh.channel_id
LEFT JOIN mission_officer_response mor ON mh.id = mor.mission_id
GROUP BY c.channel_id, c.channel_name
ORDER BY total_missions DESC;
```

## Common Issues & Solutions

### Issue: Officers don't remember previous missions

**Diagnose:**
```bash
# Check if missions are being saved
docker exec atlas-db psql -U atlas_user -d atlas_db -c \
  "SELECT COUNT(*) FROM mission_history;"

# Check if responses are being saved
docker exec atlas-db psql -U atlas_user -d atlas_db -c \
  "SELECT COUNT(*) FROM mission_officer_response;"
```

**Solution:**
- If counts are 0, check bot logs: `docker logs atlas-war-room`
- Verify `save_mission()` is being called in bot.py

### Issue: /memory commands not working

**Diagnose:**
```bash
# Check if command is registered
docker logs atlas-war-room 2>&1 | grep "memory"
```

**Solution:**
- Restart bot: `docker-compose restart war-room-bot`
- Check Discord for slash command sync (may take 1-2 minutes)

### Issue: Database connection errors

**Diagnose:**
```bash
# Check database health
docker exec atlas-db pg_isready -U atlas_user -d atlas_db

# Check connection string
docker exec atlas-war-room env | grep DATABASE_URL
```

**Solution:**
- Ensure `DATABASE_URL` is correctly set in .env
- Verify database container is healthy: `docker-compose ps`

### Issue: Memory context too large

**Symptom:** API errors about token limits

**Solution:**
- Adjust `max_tokens` parameter in `load_officer_memory()`
- Reduce number of recent missions loaded (currently 5)
- Implement memory summarization (future enhancement)

## Performance Benchmarks

### Expected Response Times

- `/memory stats`: < 1 second
- `/memory view`: < 1 second
- `/memory add`: < 500ms
- `/mission` with memory: + ~200ms overhead vs no memory

### Database Size Growth

- ~1KB per mission brief
- ~2KB per officer response
- ~500 bytes per manual note

**Example:** 1000 missions × 4 officers = ~8MB data

### Memory Usage

- PostgreSQL container: ~150MB base + data
- Bot container: ~100MB base

## Test Results Template

```
## Test Results - [DATE]

### Environment
- Bot Version: [commit hash]
- Database: PostgreSQL 16 Alpine
- Officers Active: [16/16]

### Tests Performed
- [ ] Basic mission flow
- [ ] Memory persistence
- [ ] Per-channel isolation
- [ ] Memory commands (stats, view, add, clear)
- [ ] Interactive buttons
- [ ] Roster sync
- [ ] Restart persistence
- [ ] Concurrent missions

### Issues Found
1. [Issue description]
   - **Severity**: High/Medium/Low
   - **Steps to Reproduce**: ...
   - **Expected**: ...
   - **Actual**: ...

### Performance Notes
- Average mission response time: [X seconds]
- Database query time: [X ms]
- Memory context size: [X tokens]

### Recommendations
- [Any improvements or optimizations needed]
```

## Automated Testing (Future)

Currently all testing is manual. Future automated tests could include:

```python
# Example pytest tests
async def test_mission_saves_to_db():
    """Test that missions are automatically saved"""
    # Run mission
    # Query database
    # Assert mission exists

async def test_memory_loading():
    """Test that officers load memory context"""
    # Create test data
    # Query officer
    # Assert memory was loaded

async def test_per_channel_isolation():
    """Test that channels have separate memories"""
    # Create data in channel A
    # Create data in channel B
    # Assert no cross-contamination
```

---

**Happy Testing! 🧪**

If you find any issues, check logs first:
```bash
docker logs atlas-war-room  # Bot logs
docker logs atlas-db         # Database logs
```

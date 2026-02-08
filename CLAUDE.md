# Atlas

## Project Vision
Atlas is a Discord-based command center supporting two main functionalities. First, a **War Room of LLMs** used to strategize, ponder hypothetical ideas, and brainstorm projects. Second, an execution engine that consumes a `CLAUDE.md` file to create proof of concepts via isolated, headless **Claude Code** sandboxes.

## Implementation Roadmap

### Phase 1: The War Room (Core Bot) [CURRENT FOCUS]
* [ ] Initialize Python environment and `docker-compose` for the bot.
* [ ] Set up `config/roster.json` with the Officer definitions (O1-O4).
    * **Roster Configuration Example:**
    ```json
    {
      "version": "1.0.0",
      "active_roster": ["O1", "O2", "O3", "O4"],
      "officers": {
        "O1": {
          "title": "Chief of Operations",
          "model": "openai/gpt-4o",
          "specialty": "Execution",
          "color": "0x3498db",
          "system_prompt": "You are the Architect. Focus on technical COAs and direct execution steps."
        },
        "O2": {
          "title": "Intelligence Officer",
          "model": "anthropic/claude-3-5-sonnet",
          "specialty": "Research",
          "color": "0x2ecc71",
          "system_prompt": "You are the Researcher. Synthesize data, identify patterns, and cite sources."
        },
        "O3": {
          "title": "Red Team Lead",
          "model": "anthropic/claude-3-7-sonnet",
          "specialty": "Adversarial Review",
          "color": "0xe74c3c",
          "system_prompt": "You are the Critic. Find flaws in logic and highlight security risks. You must dissent."
        },
        "O4": {
          "title": "Logistics Officer",
          "model": "google/gemini-2.0-flash-001",
          "specialty": "Infrastructure",
          "color": "0xf1c40f",
          "system_prompt": "You are the Communications lead. Focus on UI, Docker config, and formatting."
        }
      }
    }
    ```
* [ ] Implement `/mission` command using `httpx` for parallel OpenRouter calls.
* [ ] **Implement `WarRoomView` (Discord UI Components):**
    * [ ] Add **[🔴 Red Team Rebuttal]** button: Sends council output back to O-3 for critique.
    * [ ] Add **[📄 Generate Plan]** button: Triggers O-2 to synthesize a `PLAN.md`.
    * [ ] Add **[🔄 Pivot]** button: Opens a Discord Modal for mid-mission course corrections.
* [ ] Build the Discord Embed UI to display responses with officer-specific colors.
* [ ] Add capability to give each officer memory.
* [ ] Add capability to allow officers to be aware of each other.

### Phase 2: The Sandbox (Single Execution)
* [ ] Create a base Docker image for the "Execution Sandbox" containing Claude Code.
* [ ] Implement the `/execute` slash command.
* [ ] Configure Docker-outside-of-Docker (Socket mounting) for sandbox launching.
* [ ] Run a single task in YOLO mode (`--dangerously-skip-permissions`) and return results.

### Phase 3: The Fleet (Logging & Multi-Project)
* [ ] Add `session.log` capturing to pipe output to the host.
* [ ] Implement "ANSI-stripping" for readable logs.
* [ ] Create the "Channel-to-Project" mapping database.
* [ ] Support concurrent containers with resource limits (CPU/Memory).
* [ ] Add GitHub CLI integration for automated PR creation.

## Technical Architecture
* **Orchestrator:** `discord.py` bot running in Docker.
* **Gateway:** OpenRouter for the Council; Anthropic API for Claude Code.
* **Infrastructure:** Host Docker Socket `/var/run/docker.sock` mounted to Bot.
* **Workspaces:** Host `/srv/projects` mounted to Sandbox containers.

## Rules of Engagement
1. **Identity:** All responses must use the `**[O-X Title]**:` prefix.
2. **Red Team Protocol:** O-3 is required to identify at least one failure point.
3. **Isolation:** No host secrets (API keys) are passed into the execution sandboxes.
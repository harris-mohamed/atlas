# Atlas War Room

A Discord-based AI council system where multiple LLM officers collaborate to strategize, brainstorm, and evaluate ideas.

## Overview

The War Room is the first phase of Atlas - a command center that brings together AI officers with different specialties to provide diverse perspectives on projects and challenges.

### The Council

The War Room consists of four AI officers, each with distinct roles:

- **O-1: Chief of Operations** - Focuses on execution and technical implementation
- **O-2: Intelligence Officer** - Synthesizes research and identifies patterns
- **O-3: Red Team Lead** - Provides adversarial critique and security analysis
- **O-4: Logistics Officer** - Handles infrastructure, UI, and formatting

## Features

### `/mission` Command

Submit a mission brief to the council. All officers respond in parallel with their specialized perspective.

### Interactive Controls

- **🔴 Red Team Rebuttal** - Send council output back to O-3 for critical review
- **📄 Generate Plan** - Have O-2 synthesize responses into a structured `PLAN.md`
- **🔄 Pivot** - Mid-mission course correction via Discord modal

## Architecture

- **Bot Framework**: discord.py
- **LLM Gateway**: OpenRouter (supports multiple providers)
- **Infrastructure**: Docker-based deployment
- **Parallel Processing**: httpx for concurrent API calls

## Configuration

Officers are defined in `config/roster.json`:
- Model selection (OpenAI, Anthropic, Google, etc.)
- System prompts and specialties
- UI colors and titles
- Active roster management

## Rules of Engagement

1. **Identity**: All officer responses use the `**[O-X Title]**:` prefix
2. **Red Team Protocol**: O-3 must identify at least one failure point
3. **Isolation**: No host secrets passed to execution environments

## Getting Started

See CLAUDE.md for detailed implementation roadmap and technical architecture.

## Project Vision

Atlas will eventually extend beyond the War Room to include:
- **Phase 2**: Execution sandboxes with headless Claude Code
- **Phase 3**: Multi-project fleet with logging and GitHub integration

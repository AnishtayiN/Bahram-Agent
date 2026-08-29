# Bahram Agent

Bahram is an advanced self-improving AI agent inspired by [Hermes](https://github.com/NousResearch/hermes-agent) from Nous Research.

## Features

- **Self-Improving Learning Loop**: Creates skills from experience, improves them during use
- **Multiple LLM Providers**: Supports Anthropic, OpenAI, OpenRouter, and more
- **Tool System**: Bash, file operations, web search, and more
- **Memory System**: Conversation, episodic, and semantic memory
- **Platform Integrations**: Telegram, Discord, Slack
- **Skills System**: Create and manage reusable skills
- **Scheduler**: Automated task execution
- **CLI Interface**: Rich terminal UI

## Installation

```bash
# Clone the repository
git clone https://github.com/bahram-agent/bahram-agent.git
cd bahram-agent

# Install dependencies
pip install -e .

# Or with all platform integrations
pip install -e ".[all]"
```

## Quick Start

### 1. Configure

```bash
# Copy example config
cp .env.example .env

# Edit .env with your API keys
```

### 2. Run

```bash
# Start interactive chat
bahram chat

# Single message
bahram chat "What can you do?"

# Start API server
bahram serve

# Start messaging gateway
bahram gateway --platform telegram
```

## Architecture

```
bahram-agent/
├── bahram/
│   ├── core/           # Core agent engine
│   │   ├── agent.py    # Main agent class
│   │   ├── engine.py   # Agent loop engine
│   │   ├── config.py   # Configuration
│   │   └── context.py  # Context management
│   ├── tools/          # Tool implementations
│   │   ├── bash.py     # Shell commands
│   │   ├── file.py     # File operations
│   │   ├── search.py   # Search tools
│   │   └── web.py      # Web tools
│   ├── memory/         # Memory systems
│   │   ├── conversation.py
│   │   ├── episodic.py
│   │   └── semantic.py
│   ├── skills/         # Skills system
│   │   ├── base.py
│   │   └── manager.py
│   ├── platforms/      # Platform integrations
│   │   ├── telegram.py
│   │   ├── discord.py
│   │   └── slack.py
│   ├── providers/      # LLM providers
│   │   ├── anthropic.py
│   │   ├── openai.py
│   │   └── openrouter.py
│   ├── scheduler/      # Task scheduler
│   └── cli.py          # CLI interface
├── config/             # Configuration files
├── skills/             # User skills
└── tests/              # Test suite
```

## Commands

| Command | Description |
|---------|-------------|
| `bahram chat` | Start interactive chat |
| `bahram chat "msg"` | Send single message |
| `bahram model --list` | List available models |
| `bahram skills --list` | List available skills |
| `bahram serve` | Start API server |
| `bahram gateway` | Start messaging gateway |
| `bahram version` | Show version |

## Configuration

See `config/config.yaml` for all configuration options.

### Environment Variables

```bash
# LLM Providers
ANTHROPIC_API_KEY=your-key
OPENAI_API_KEY=your-key
OPENROUTER_API_KEY=your-key

# Platforms
TELEGRAM_BOT_TOKEN=your-token
DISCORD_BOT_TOKEN=your-token
SLACK_BOT_TOKEN=your-token
SLACK_APP_TOKEN=your-token
```

## Skills

Skills are reusable capabilities that can be auto-triggered or manually invoked.

### Creating Skills

```python
from bahram.skills.base import BaseSkill, SkillMetadata

class MySkill(BaseSkill):
    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="my-skill",
            description="Does something useful",
            triggers=["trigger word"],
        )

    async def execute(self, context: dict) -> str:
        return "Skill executed!"
```

### Using Skills

```python
from bahram.skills.manager import SkillManager

manager = SkillManager(config)
await manager.load_skills()

# Auto-execute based on task
result = await manager.auto_execute("review this code", context)
```

## Memory Systems

### Conversation Memory
Stores chat history and context.

### Episodic Memory
Stores experiences and events (task completions, errors, learnings).

### Semantic Memory
Stores facts, concepts, and relationships.

## Platform Integrations

### Telegram
```bash
bahram gateway --platform telegram
```

### Discord
```bash
bahram gateway --platform discord
```

### Slack
```bash
bahram gateway --platform slack
```

## API Server

```bash
bahram serve --host 0.0.0.0 --port 8000
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check .

# Run type checker
mypy .
```

## Inspired By

- [Hermes Agent](https://github.com/NousResearch/hermes-agent) - Self-improving AI agent by Nous Research
- [Nous Research](https://nousresearch.com) - Pioneering open-source AI

## License

MIT

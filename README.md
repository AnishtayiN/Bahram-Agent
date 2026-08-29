# Bahram Agent ☤

Advanced self-improving AI agent inspired by [Hermes Agent](https://github.com/NousResearch/hermes-agent) from Nous Research.

## Quick Install

```bash
pip install git+https://github.com/buoawjbnfikwbuinb/agent.git
```

Or clone and install:

```bash
git clone https://github.com/buoawjbnfikwbuinb/agent.git
cd agent/bahram-agent
pip install -e .
```

## Features

- **Self-Improving Learning Loop** - Creates skills from experience, improves them during use
- **17+ LLM Providers** - Anthropic, OpenAI, OpenRouter, Nous, NVIDIA, Groq, and more
- **8 Built-in Tools** - Bash, file operations, web search, code analysis
- **3 Memory Systems** - Conversation, episodic, and semantic memory
- **3 Platform Integrations** - Telegram, Discord, Slack
- **Skills System** - Auto-triggering, reusable capabilities
- **Task Scheduler** - Automated job execution
- **Rich CLI** - Beautiful terminal interface

## Quick Start

### 1. Install

```bash
pip install git+https://github.com/buoawjbnfikwbuinb/agent.git
```

### 2. Configure API Keys

```bash
# Copy example config
cp .env.example .env

# Edit with your API keys
nano .env
```

At minimum, configure ONE provider:

```bash
# Option 1: Anthropic (recommended)
ANTHROPIC_API_KEY=sk-ant-...

# Option 2: OpenAI
OPENAI_API_KEY=sk-...

# Option 3: OpenRouter (access to many models)
OPENROUTER_API_KEY=sk-or-...

# Option 4: Groq (fast, free tier)
GROQ_API_KEY=gsk_...

# Option 5: Local (no API key needed)
# Ollama: http://localhost:11434
# LM Studio: http://localhost:1234/v1
```

### 3. Run

```bash
# Start interactive chat
bahram chat

# Single message
bahram chat "What can you do?"

# With specific model
bahram chat --model anthropic/claude-sonnet-4-6 "Hello"
```

## Telegram Bot Setup

### 1. Create Bot

1. Open [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`
3. Choose a name for your bot
4. Copy the bot token

### 2. Configure

```bash
# Add to .env
TELEGRAM_BOT_TOKEN=your-bot-token-here
```

### 3. Start Gateway

```bash
# Start Telegram gateway
bahram gateway --platform telegram
```

Your bot is now live on Telegram!

### Telegram Commands

- `/start` - Start the bot
- `/help` - Show help
- `/clear` - Clear conversation
- `/model <name>` - Change model
- `/status` - Show status

## Supported Models

### Cloud Providers

| Provider | Models | API Key |
|----------|--------|---------|
| Anthropic | Claude 3.5, Claude 3 Opus | `ANTHROPIC_API_KEY` |
| OpenAI | GPT-4o, o1, o1-mini | `OPENAI_API_KEY` |
| OpenRouter | 200+ models | `OPENROUTER_API_KEY` |
| Nous | Hermes 3 (70B, 405B) | `NOUS_API_KEY` |
| NVIDIA | Nemotron 4 | `NVIDIA_API_KEY` |
| Groq | Llama 3.1, Mixtral | `GROQ_API_KEY` |
| DeepSeek | DeepSeek Chat/Coder | `DEEPSEEK_API_KEY` |
| Mistral | Mistral Large/Medium | `MISTRAL_API_KEY` |
| Google | Gemini 1.5/2.0 | `GOOGLE_API_KEY` |
| Hugging Face | Llama, many others | `HF_API_KEY` |
| Xiaomi | MiMo | `XIAOMI_API_KEY` |
| MiniMax | Abab | `MINIMAX_API_KEY` |
| Kimi | Moonshot | `KIMI_API_KEY` |
| Zhipu | GLM-4 | `ZHIPU_API_KEY` |

### Local Providers (No API Key)

| Provider | Setup |
|----------|-------|
| Ollama | Install Ollama, run `ollama serve` |
| LM Studio | Install LM Studio, start server |

## Tools

Bahram has access to these tools:

| Tool | Description |
|------|-------------|
| `bash` | Execute shell commands |
| `read` | Read file contents |
| `write` | Write to files |
| `edit` | Edit files with string replacement |
| `glob` | Find files by pattern |
| `grep` | Search file contents |
| `webfetch` | Fetch web pages |
| `websearch` | Search the web |
| `task` | Spawn subagents |

## Commands

```bash
# Chat
bahram chat                    # Interactive mode
bahram chat "message"          # Single message
bahram chat --model gpt-4o     # Use specific model

# Models
bahram model --list            # List available models
bahram model --set gpt-4o      # Set default model

# Skills
bahram skills --list           # List available skills

# Gateway (for Telegram, Discord, Slack)
bahram gateway --platform telegram
bahram gateway --platform discord
bahram gateway --platform slack

# API Server
bahram serve --host 0.0.0.0 --port 8000

# Version
bahram version
```

## Configuration

Edit `config/config.yaml`:

```yaml
# Change default model
agent:
  model: "anthropic/claude-sonnet-4-6"

# Add custom provider
providers:
  custom:
    api_key: "${CUSTOM_API_KEY}"
    base_url: "https://your-api.com/v1"
    models:
      - "custom-model"
```

## Development

```bash
# Clone repo
git clone https://github.com/buoawjbnfikwbuinb/agent.git
cd agent/bahram-agent

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check .

# Run type checker
mypy .
```

## Project Structure

```
bahram-agent/
├── bahram/
│   ├── core/           # Core agent engine
│   ├── tools/          # 8 built-in tools
│   ├── memory/         # 3 memory systems
│   ├── skills/         # Skill management
│   ├── platforms/      # Telegram, Discord, Slack
│   ├── providers/      # 17+ LLM providers
│   ├── scheduler/      # Task scheduler
│   └── cli.py          # CLI interface
├── config/             # Configuration
├── skills/             # Example skills
└── tests/              # Test suite
```

## Inspired By

- [Hermes Agent](https://github.com/NousResearch/hermes-agent) - Self-improving AI agent by Nous Research
- [Nous Research](https://nousresearch.com) - Pioneering open-source AI

## License

MIT

## Support

- GitHub: https://github.com/buoawjbnfikwbuinb/agent
- Issues: https://github.com/buoawjbnfikwbuinb/agent/issues

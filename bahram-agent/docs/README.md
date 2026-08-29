# Bahram Agent

advanced AI agent framework with 17+ LLM providers, 40+ tools, and multi-platform support.

## Installation

```bash
pip install bahram-agent
```

## Quick Start

```python
from bahram import Agent, Config

config = Config(model="gpt-4o", provider="openai")
agent = Agent(config)

response = await agent.run("What is the weather today?")
```

## Features

### 🤖 LLM Providers
- Anthropic (Claude)
- OpenAI (GPT)
- Groq (Fast)
- Mistral
- Google (Gemini)
- Ollama (Local)
- And 10+ more...

### 🛠️ Tools
- Code generation
- File operations
- Web search
- Database queries
- Git operations
- And 35+ more...

### 💬 Platforms
- Telegram
- Discord
- Slack
- WhatsApp
- Signal
- Email
- Home Assistant

## Documentation

See [README.md](README.md) for full documentation.

## License

MIT License

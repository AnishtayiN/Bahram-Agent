# Bahram Agent ☤

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue" alt="Version">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/python-3.10+-yellow" alt="Python">
  <img src="https://img.shields.io/badge/hermes-inspired-orange" alt="Hermes Inspired">
</p>

## درباره بهرام / About Bahram

**بَهرام** (Bahram) نام یکی از شخصیت‌های اساطیری و تاریخی ایران باستان است. بهرام در فرهنگ ایرانی نماد **شجاعت، قدرت و پیروزی** است. این نام از دوران باستان تا امروز در ایران محبوب بوده و پادشاهان بزرگی مانند بهرام گور (یکی از شاهان ساسانی) از این نام استفاده می‌کردند.

**Bahram** is one of the most iconic names in ancient Persian mythology and history. The name symbolizes **courage, strength, and victory** in Iranian culture. It has been cherished from ancient times to the present day, with great kings like Bahram V (Bahram Gur) of the Sassanid Empire bearing this name.

### چرا بهرام؟ / Why Bahram?

انتخاب نام **بهرام** برای این هوش مصنوعی به دلایل زیر است:

1. **باستانی بودن**: بهرام یادآور تمدن کهن ایران است
2. **مقدس بودن**: این نام در فرهنگ ایرانی ارزش ویژه‌ای دارد
3. **نماد قدرت**: بهرام نماد قدرت و توانایی است
4. **ایرانی بودن**: ادای احترام به فرهنگ و تاریخ غنی ایران

The name **Bahram** was chosen for this AI because:
1. **Ancient Heritage**: Reminiscent of Iran's ancient civilization
2. **Sacred Significance**: Holds special value in Iranian culture
3. **Symbol of Power**: Represents strength and capability
4. **Persian Identity**: Honoring Iran's rich culture and history

---

## ✨ Features

Bahram Agent is an advanced self-improving AI agent inspired by [Hermes Agent](https://github.com/NousResearch/hermes-agent) from Nous Research.

### 🧠 Core Intelligence
- **Self-Improving Learning Loop** - Creates skills from experience, improves them during use
- **17+ LLM Providers** - Anthropic, OpenAI, OpenRouter, Nous, NVIDIA, Groq, and more
- **Context Compression** - Intelligent context window management
- **Fallback Providers** - Automatic failover to backup models
- **Personality System** - SOUL.md and built-in personalities
- **Silence Tokens** - [SILENT] for automated flows
- **Mixture of Agents** - Orchestrate multiple LLMs for better results
- **Learning Journey** - Timeline visualization of skills and memories
- **Background Review** - Auto-review conversations for learning
- **Cursor Rules** - .cursorrules and context file support

### 🛠️ Tools & Capabilities
- **20+ Built-in Tools** - Bash, files, web search, code analysis, browser, image gen
- **Terminal Backends** - Local, Docker, SSH, Singularity, Modal, Daytona, Vercel
- **Background Process Management** - Start, poll, wait, kill background processes
- **Execute Code** - Run Python/bash in sandboxed environment
- **Delegation** - Spawn isolated subagents for parallel work
- **Clarify Tool** - Multi-select questions with options
- **Todo/Task Planning** - Create and manage task lists
- **Document Extraction** - PDF, DOCX, XLSX, PPTX support
- **Browser Automation** - Navigate, click, type, screenshot
- **Image Generation** - DALL-E, Stability, FAL integration
- **LSP Integration** - Language Server Protocol for code diagnostics
- **Tool Search** - Find tools by description and category
- **MCP Integration** - Connect to external tool servers
- **Plugin System** - Extend with custom tools and hooks
- **Batch Processing** - Process multiple prompts efficiently

### 🔒 Security
- **Dangerous Command Approval** - Smart/manual/off modes
- **YOLO Mode** - Toggle all approval prompts
- **Hardline Blocklist** - Always-on safety floor
- **SSRF Protection** - Block private network access
- **Context File Scanning** - Prompt injection detection
- **File Write Safety** - Protected paths and sandbox
- **DM Pairing** - Code-based authorization for messaging
- **Admin/User Split** - Role-based access control
- **Website Access Policy** - URL blocklist and allowlist
- **Supply-chain Advisory** - Check for compromised packages
- **Write Approval Gates** - Stage memory/skill writes for review

### 💾 Memory & Learning
- **3 Memory Systems** - Conversation, episodic, and semantic memory
- **External Memory Providers** - Honcho, Mem0, and more
- **Honcho User Modeling** - Dialectic user profiling across sessions
- **Memory Nudge** - Periodic reminders for knowledge persistence
- **Session Search** - Full-text search across past conversations
- **Trajectory Generation** - Export training data for model improvement
- **Write Approval Gates** - Stage memory/skill writes for review

### 🎯 Skills & Automation
- **Skills System** - Auto-triggering, reusable capabilities
- **Skill Bundles** - Group skills under one command
- **Skill Hub** - Browse, install, and manage skills from registries
- **Skill Curator** - Auto-curation and maintenance
- **Cron Scheduler** - Automated task execution with natural language
- **Context Files** - Project-specific instructions (.bahram.md, AGENTS.md, SOUL.md)
- **External Skill Directories** - Multiple skill sources
- **Project-Local Skills** - Repo-specific skills

### 🌐 Platform Support
- **Telegram Bot** - Full-featured with inline keyboards
- **Discord Integration** - Server and DM support
- **Slack Integration** - Workspace connectivity
- **WhatsApp** - Baileys/Cloud API bridge
- **Signal** - Via signal-cli
- **Email** - IMAP/SMTP support
- **Home Assistant** - Smart home control (basic + advanced)
- **Rich CLI** - Beautiful terminal interface with markdown
- **Web Dashboard** - Monitor and manage via web UI

### 🏗️ Infrastructure
- **Gateway Service** - Install as systemd/launchd service
- **Checkpoints/Rollback** - Filesystem snapshots for undo
- **Delivery Ledger** - Crash recovery for message delivery
- **DM Pairing** - Code-based authorization
- **Per-Channel Overrides** - Different models per channel
- **Busy Input Modes** - Queue/interrupt/steer
- **Typing Indicators** - Per-platform typing status
- **Progress Bubble Cleanup** - Auto-delete progress messages
- **Message Timestamps** - In model context
- **Status Phrases** - Configurable status messages
- **Session Resume** - Auto-resume after gateway restart
- **Circuit Breaker** - Auto-pause failing platforms
- **Restart Notifications** - "Agent is back" messages
- **Profile Management** - Multiple agent profiles
- **Secrets Management** - Secure credential storage
- **Egress Proxy** - Network proxy support
- **Installation Scripts** - Shell/PowerShell installers
- **Tool Annotations** - Signal deaths, UTF-16 transcoding
- **Tool Progress** - Real-time tool execution updates
- **Background Notifications** - Background task status

### 🔐 Advanced Security
- **Tirith Scanner** - Pre-execution content scanning
- **File Write Safety** - Protected paths, safe root
- **Container Security** - Hardened Docker settings
- **PTY Support** - Interactive terminal sessions
- **Sudo Support** - Password caching
- **Shell Init Handling** - Non-interactive guards
- **Credential Passthrough** - OAuth in sandbox
- **Env Passthrough** - Controlled environment variables

### 🎙️ Voice & Media
- **Voice Transcription** - Whisper API integration
- **Text-to-Speech** - Multiple voice options
- **Image Generation** - DALL-E 3, Stability AI, FAL
- **Document Extraction** - PDF, DOCX, XLSX, PPTX

---

## 🚀 Quick Install

```bash
pip install git+https://github.com/buoawjbnfikwbuinb/agent.git
```

Or clone and install:

```bash
git clone https://github.com/buoawjbnfikwbuinb/agent.git
cd agent/bahram-agent
pip install -e .
```

---

## ⚡ Quick Start

### 1. Configure API Keys

```bash
cp .env.example .env
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

### 2. Run

```bash
# Start interactive chat
bahram chat

# Single message
bahram chat "What can you do?"

# With specific model
bahram chat --model anthropic/claude-sonnet-4-6 "Hello"
```

---

## 🤖 Telegram Bot Setup

### 1. Create Bot

1. Open [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`
3. Choose a name: `Bahram Agent`
4. Choose a username: `bahram_agent_bot`
5. Copy the bot token

### 2. Configure

```bash
# Add to .env
TELEGRAM_BOT_TOKEN=your-bot-token-here
```

### 3. Run Bot

```bash
# Method 1: Using bahram command
bahram gateway --platform telegram

# Method 2: Using bot.py directly
cd bahram-agent
python bot.py
```

### Bot Commands (139+)

#### Core Commands
| Command | Description |
|---------|-------------|
| `/start` | Start the bot |
| `/new [name]` | Start new session |
| `/retry` | Retry last message |
| `/undo [N]` | Back up N turns |
| `/model [model]` | Switch model |
| `/status` | Show status |
| `/context` | Show context window |
| `/goal [text]` | Set a goal |
| `/background <prompt>` | Run in background |
| `/compress` | Compress context |
| `/pause [reason]` | Pause/resume |
| `/yolo` | Toggle YOLO mode |
| `/voice [on\|off]` | Toggle voice mode |
| `/help` | Show help |
| `/commands [page]` | List all commands |

#### Skill Commands (80+)
| Category | Commands |
|----------|----------|
| **Code** | claude_code, codex, opencode, github_* |
| **Files** | docx, pdf, xlsx, powerpoint |
| **Web** | arxiv, blogwatcher, gif_search, xurl |
| **Media** | ascii_art, excalidraw, p5js |
| **Dev** | python_debugging, tdd, systematic_debugging |
| **Research** | grounded_citations, research_paper_writing |

---

## 💻 CLI Interface

```bash
cd bahram-agent
python cli.py
```

### CLI Commands
| Command | Description |
|---------|-------------|
| `/help` | Show help |
| `/model` | Change model |
| `/clear` | Clear history |
| `/status` | Show status |
| `/history` | View history |
| `/export` | Export to file |
| `/quit` | Exit |

---

## 📦 Supported Models

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

---

## 🏗️ Architecture

```
bahram-agent/
├── bahram/
│   ├── core/               # Core engine
│   │   ├── agent.py        # Main agent class
│   │   ├── engine.py       # Agent loop engine
│   │   ├── config.py       # Configuration
│   │   ├── context.py      # Context management
│   │   ├── compressor.py   # Context compression
│   │   ├── batch.py        # Batch processing
│   │   ├── context_files.py # Project context
│   │   ├── trajectory.py   # Trajectory generation
│   │   ├── personality.py  # Personality/SOUL.md
│   │   └── silence.py      # Silence tokens
│   ├── security/           # Security system
│   │   ├── approval.py     # Command approval
│   │   └── protection.py   # SSRF, injection detection
│   ├── tools/              # 15+ built-in tools
│   │   ├── bash.py         # Shell execution
│   │   ├── read.py         # File reading
│   │   ├── write.py        # File writing
│   │   ├── edit.py         # File editing
│   │   ├── glob.py         # File pattern matching
│   │   ├── grep.py         # Content search
│   │   ├── webfetch.py     # Web fetching
│   │   ├── websearch.py    # Web search
│   │   ├── task.py         # Subagent spawning
│   │   ├── terminal.py     # Terminal backends
│   │   ├── process.py      # Background processes
│   │   ├── execute_code.py # Code execution
│   │   ├── delegation.py   # Task delegation
│   │   ├── clarify.py      # Clarification questions
│   │   ├── todo.py         # Task planning
│   │   ├── documents.py    # Document extraction
│   │   ├── browser.py      # Browser automation
│   │   └── image_gen.py    # Image generation
│   ├── memory/             # Memory systems
│   │   ├── conversation.py # Chat history
│   │   ├── episodic.py     # Experiences
│   │   ├── semantic.py     # Facts/knowledge
│   │   ├── nudge.py        # Memory nudges
│   │   ├── honcho.py       # User modeling
│   │   └── search.py       # Session search
│   ├── skills/             # Skill management
│   ├── platforms/          # Platform adapters
│   │   ├── telegram.py     # Telegram
│   │   ├── discord.py      # Discord
│   │   ├── slack.py        # Slack
│   │   ├── whatsapp.py     # WhatsApp
│   │   ├── signal.py       # Signal
│   │   ├── email.py        # Email
│   │   └── homeassistant.py # Home Assistant
│   ├── providers/          # 17+ LLM providers
│   │   ├── anthropic.py
│   │   ├── openai.py
│   │   ├── openrouter.py
│   │   ├── nous.py
│   │   ├── nvidia.py
│   │   ├── groq.py
│   │   ├── deepseek.py
│   │   ├── mistral.py
│   │   ├── google.py
│   │   ├── huggingface.py
│   │   ├── ollama.py
│   │   ├── lmstudio.py
│   │   ├── custom.py
│   │   └── fallback.py    # Fallback providers
│   ├── mcp/                # MCP integration
│   │   ├── client.py       # MCP client
│   │   └── server.py       # MCP server
│   ├── plugins/            # Plugin system
│   │   ├── base.py         # Base plugin
│   │   └── manager.py      # Plugin manager
│   ├── hub/                # Skills hub
│   ├── voice/              # Voice systems
│   │   ├── __init__.py     # Voice transcription
│   │   └── modes.py        # TTS and voice modes
│   └── scheduler/          # Task scheduler
│       └── cron.py         # Cron scheduler
├── bot.py                  # Telegram bot
├── cli.py                  # Interactive CLI
├── config/                 # Configuration
├── skills/                 # Example skills
└── tests/                  # Test suite
```

---

## 📚 All Commands

### Session Management
| Command | Description |
|---------|-------------|
| `/new [name]` | Start new session (alias: /reset) |
| `/retry` | Retry last message |
| `/undo [N]` | Back up N user turns |
| `/title [name]` | Set session title |
| `/branch [name]` | Branch session (alias: /fork) |
| `/resume [name]` | Resume named session |
| `/sessions` | Browse previous sessions |

### Context Control
| Command | Description |
|---------|-------------|
| `/compress [here [N]]` | Compress context (alias: /compact) |
| `/rollback [number]` | List/restore checkpoints |
| `/context [all]` | Show context window (alias: /ctx) |
| `/status` | Show session, model, token info |

### Goal & Automation
| Command | Description |
|---------|-------------|
| `/goal [text\|show\|clear]` | Set standing goal |
| `/subgoal [text\|remove\|clear]` | Add extra criteria |
| `/heartbeat [every\|status\|clear]` | Set recurring prompt (alias: /hb) |
| `/background <prompt>` | Run in background (alias: /bg) |
| `/agents` | Show active agents (alias: /tasks) |
| `/queue <prompt>` | Queue prompt (alias: /q) |

### Settings
| Command | Description |
|---------|-------------|
| `/model [model]` | Switch model |
| `/personality [name]` | Set personality |
| `/yolo` | Toggle YOLO mode |
| `/reasoning [level]` | Manage reasoning |
| `/fast [normal\|fast]` | Toggle fast mode |
| `/voice [on\|off\|tts]` | Toggle voice mode |
| `/memory [on\|off]` | Toggle memory approval |
| `/approvals [mode]` | Set approval mode |

### Skills & Learning
| Command | Description |
|---------|-------------|
| `/learn <what>` | Learn a skill |
| `/refine [focus]` | Save lessons to memory |
| `/bundles` | List skill bundles |
| `/reload_skills` | Re-scan skills |
| `/init [notes]` | Generate project instructions |

### System
| Command | Description |
|---------|-------------|
| `/help` | Show help |
| `/commands [page]` | List all commands |
| `/version` | Show version (alias: /v) |
| `/update` | Update Bahram Agent |
| `/debug` | Upload debug report |
| `/restart` | Restart gateway |
| `/usage [reset]` | Show token usage |

---

## 🔧 Configuration

Edit `config/config.yaml`:

```yaml
# Change default model
agent:
  model: "anthropic/claude-sonnet-4-6"

# Security settings
approvals:
  mode: smart  # smart, manual, off
  timeout: 300

# Terminal backend
terminal:
  backend: local  # local, docker, ssh
  timeout: 180

# Add custom provider
providers:
  custom:
    api_key: "${CUSTOM_API_KEY}"
    base_url: "https://your-api.com/v1"
    models:
      - "custom-model"

# Enable MCP servers
mcp_servers:
  filesystem:
    type: stdio
    command: ["npx", "-y", "@modelcontextprotocol/server-filesystem"]
```

---

## 🛠️ Development

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

---

## 📊 Comparison with Hermes

| Feature | Hermes | Bahram |
|---------|--------|--------|
| Core Engine | ✅ | ✅ |
| 17+ LLM Providers | ✅ | ✅ |
| 20+ Built-in Tools | ✅ | ✅ |
| Terminal Backends | ✅ | ✅ |
| Background Processes | ✅ | ✅ |
| Security/Approval | ✅ | ✅ |
| Memory Systems | ✅ | ✅ |
| External Memory Providers | ✅ | ✅ |
| Skills System | ✅ | ✅ |
| Skill Bundles | ✅ | ✅ |
| Skill Curator | ✅ | ✅ |
| MCP Integration | ✅ | ✅ |
| Plugin System | ✅ | ✅ |
| Built-in Plugins | ✅ | ✅ |
| Skill Hub | ✅ | ✅ |
| Voice Transcription | ✅ | ✅ |
| Text-to-Speech | ✅ | ✅ |
| Image Generation | ✅ | ✅ |
| Browser Automation | ✅ | ✅ |
| Document Extraction | ✅ | ✅ |
| LSP Integration | ✅ | ✅ |
| Tool Search | ✅ | ✅ |
| Mixture of Agents | ✅ | ✅ |
| Learning Journey | ✅ | ✅ |
| Background Review | ✅ | ✅ |
| Telegram Bot | ✅ | ✅ |
| Discord/Slack | ✅ | ✅ |
| WhatsApp/Signal | ✅ | ✅ |
| Email | ✅ | ✅ |
| Home Assistant | ✅ | ✅ |
| CLI Interface | ✅ | ✅ |
| Web Dashboard | ✅ | ✅ |
| Gateway Service | ✅ | ✅ |
| Cron Scheduler | ✅ | ✅ |
| Honcho Modeling | ✅ | ✅ |
| Session Search | ✅ | ✅ |
| Memory Nudge | ✅ | ✅ |
| Context Compression | ✅ | ✅ |
| Batch Processing | ✅ | ✅ |
| Fallback Providers | ✅ | ✅ |
| Context Files | ✅ | ✅ |
| Cursor Rules | ✅ | ✅ |
| Context References | ✅ | ✅ |
| Trajectory Generation | ✅ | ✅ |
| Personality/SOUL.md | ✅ | ✅ |
| Silence Tokens | ✅ | ✅ |
| Execute Code | ✅ | ✅ |
| Delegation | ✅ | ✅ |
| Clarify Tool | ✅ | ✅ |
| Todo/Task Planning | ✅ | ✅ |
| SSRF Protection | ✅ | ✅ |
| Injection Detection | ✅ | ✅ |
| DM Pairing | ✅ | ✅ |
| Admin/User Split | ✅ | ✅ |
| Website Policy | ✅ | ✅ |
| Supply-chain Advisory | ✅ | ✅ |
| Write Approval Gates | ✅ | ✅ |
| Checkpoints/Rollback | ✅ | ✅ |
| Delivery Ledger | ✅ | ✅ |
| Lazy Dependencies | ✅ | ✅ |
| Themes/Skins | ✅ | ✅ |
| Per-Channel Overrides | ✅ | ✅ |
| Busy Input Modes | ✅ | ✅ |
| Typing Indicators | ✅ | ✅ |

---

## 🙏 Inspired By

- [Hermes Agent](https://github.com/NousResearch/hermes-agent) - Self-improving AI agent by Nous Research
- [Nous Research](https://nousresearch.com) - Pioneering open-source AI
- Ancient Persian Heritage - The spirit of Bahram lives on

---

## 📄 License

MIT License

---

## 🌟 Support

- GitHub: https://github.com/buoawjbnfikwbuinb/agent
- Issues: https://github.com/buoawjbnfikwbuinb/agent/issues

---

<p align="center">
  <b>بهرام زنده باد / Long Live Bahram</b>
</p>

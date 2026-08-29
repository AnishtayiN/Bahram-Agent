# Bahram Agent System

## Overview

Bahram is an advanced AI agent system inspired by Hermes from Nous Research. It features self-improving capabilities, autonomous task execution, and multi-platform support.

## Architecture

### Agents

| Agent | Mode | Purpose |
|-------|------|---------|
| `bahram` | Primary | Main agent for task execution |
| `bahram-researcher` | Subagent | Deep analysis and research |
| `bahram-coder` | Subagent | Implementation and development |
| `bahram-reviewer` | Subagent | Code review and quality assurance |

### Skills

| Skill | Purpose |
|-------|---------|
| `code-review` | Comprehensive code review |
| `research` | Deep research and analysis |
| `deploy` | Deployment automation |

### Commands

| Command | Description |
|---------|-------------|
| `/analyze <target>` | Deep analysis of codebase or problem |
| `/review <target>` | Comprehensive code review |
| `/deploy <env>` | Deployment automation |
| `/research <topic>` | Research and information gathering |

## Usage Examples

### Analyze a codebase
```bash
/analyze ./src
```

### Review code
```bash
/review ./src/auth.ts
```

### Deploy to production
```bash
/deploy production --strategy blue-green
```

### Research a technology
```bash
/research React vs Vue
```

## Configuration

The main configuration is in `opencode.json`. Key settings:

- **Model**: `anthropic/claude-sonnet-4-6`
- **Default Agent**: `bahram`
- **Permissions**: Balanced security with flexibility

## Self-Improvement

Bahram follows a continuous improvement protocol:

1. **Learn**: Extract patterns from completed tasks
2. **Create**: Build reusable skills
3. **Refine**: Improve approaches based on outcomes
4. **Share**: Document best practices

## Security

- Never expose secrets or credentials
- Follow least-privilege principles
- Validate inputs and sanitize outputs
- Consider edge cases and failure modes

## Contributing

To extend Bahram:

1. Add new agents in `.opencode/agent/`
2. Create skills in `.opencode/skills/`
3. Define commands in `.opencode/command/`
4. Update this documentation

## License

This is a custom AI agent system. Use responsibly.

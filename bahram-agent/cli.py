#!/usr/bin/env python3
"""
Bahram Agent - CLI Chat Interface
Advanced AI agent with self-improving capabilities
"""

import asyncio
import os
import sys
import json
import time
from pathlib import Path
from typing import Optional
from datetime import datetime

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.theme import Theme
    from rich.table import Table
    from rich.text import Text
    from rich.syntax import Syntax
    from rich.live import Live
    from rich.spinner import Spinner
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from bahram.core.agent import Agent
from bahram.core.config import Config
from bahram.core.engine import AgentResponse


class BahramCLI:
    """Interactive CLI for Bahram Agent."""

    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize CLI."""
        self.config = Config.from_file(config_path)
        self.agent: Optional[Agent] = None
        self.session_id: Optional[str] = None
        self.current_model: str = self.config.agent.model
        self.history: list[dict] = []

        if HAS_RICH:
            custom_theme = Theme({
                "info": "cyan",
                "success": "green",
                "warning": "yellow",
                "error": "bold red",
                "user": "bold green",
                "assistant": "bold cyan",
                "tool": "dim yellow",
            })
            self.console = Console(theme=custom_theme)
        else:
            self.console = None

    def print(self, *args, **kwargs):
        """Print with rich if available."""
        if self.console:
            self.console.print(*args, **kwargs)
        else:
            print(*args, **kwargs)

    def print_markdown(self, text: str):
        """Print markdown text."""
        if self.console:
            self.console.print(Markdown(text))
        else:
            print(text)

    def print_panel(self, text: str, title: str = "", border_style: str = "cyan"):
        """Print in a panel."""
        if self.console:
            self.console.print(Panel(text, title=title, border_style=border_style))
        else:
            print(f"=== {title} ===")
            print(text)
            print("=" * 40)

    def print_code(self, code: str, language: str = "python"):
        """Print code with syntax highlighting."""
        if self.console:
            self.console.print(Syntax(code, language))
        else:
            print(code)

    async def initialize(self):
        """Initialize the agent."""
        self.print("[info]Initializing Bahram Agent...[/info]")
        self.agent = Agent(config=self.config)
        await self.agent.start()
        self.print("[success]Agent initialized successfully![/success]")

    async def cleanup(self):
        """Cleanup resources."""
        if self.agent:
            await self.agent.stop()

    def show_welcome(self):
        """Show welcome message."""
        welcome = """
# Welcome to Bahram Agent ☤

I'm your advanced AI assistant with self-improving capabilities.

## Commands
- Type any message to chat
- `/help` - Show help
- `/model` - Change model
- `/clear` - Clear history
- `/status` - Show status
- `/history` - Show conversation history
- `/export` - Export conversation
- `/quit` or `/exit` - Exit

## Features
- 💻 Code writing & analysis
- 🌐 Web search & research
- 📁 File operations
- 🔧 Task automation
- 🧠 Self-improving skills

---
"""
        self.print_panel(welcome, title="Bahram Agent v" + self.config.agent.version, border_style="cyan")

    def show_help(self):
        """Show help message."""
        help_text = """
## Commands
| Command | Description |
|---------|-------------|
| `/help` | Show this help |
| `/model` | Change AI model |
| `/clear` | Clear conversation history |
| `/status` | Show bot status |
| `/history` | Show conversation history |
| `/export` | Export conversation to file |
| `/quit` | Exit the program |
| `/exit` | Exit the program |

## Tips
- Use Ctrl+C to interrupt
- Use ↑/↓ to navigate history (if supported)
- Send multi-line messages with Shift+Enter
"""
        self.print_panel(help_text, title="Help", border_style="blue")

    def show_status(self):
        """Show status."""
        status = f"""
## Status
- **Version:** {self.config.agent.version}
- **Model:** `{self.current_model}`
- **Session:** `{self.session_id[:8] if self.session_id else 'None'}`
- **Messages:** {len(self.history)}
- **Memory:** {'✅' if self.config.memory.enabled else '❌'}
- **Skills:** {'✅' if self.config.skills.enabled else '❌'}
- **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self.print_panel(status, title="Status", border_style="green")

    def show_history(self):
        """Show conversation history."""
        if not self.history:
            self.print("[warning]No history available[/warning]")
            return

        table = Table(title="Conversation History")
        table.add_column("Role", style="cyan")
        table.add_column("Content", style="white")
        table.add_column("Time", style="dim")

        for entry in self.history[-10:]:  # Show last 10
            role = entry.get("role", "unknown")
            content = entry.get("content", "")[:50] + "..." if len(entry.get("content", "")) > 50 else entry.get("content", "")
            timestamp = entry.get("timestamp", "")
            table.add_row(role, content, timestamp)

        self.print(table)

    async def change_model(self):
        """Change the AI model."""
        models = [
            ("anthropic/claude-sonnet-4-6", "Claude 3.5 Sonnet"),
            ("anthropic/claude-haiku-3.5", "Claude 3.5 Haiku"),
            ("openai/gpt-4o", "GPT-4o"),
            ("openai/gpt-4o-mini", "GPT-4o Mini"),
            ("openai/o1", "o1"),
            ("nous/hermes-3-llama-3.1-405b", "Hermes 3 405B"),
            ("nous/hermes-3-llama-3.1-70b", "Hermes 3 70B"),
            ("groq/llama-3.1-70b-versatile", "Llama 3.1 70B"),
            ("google/gemini-1.5-pro", "Gemini 1.5 Pro"),
            ("google/gemini-2.0-flash", "Gemini 2.0 Flash"),
            ("mistral/mistral-large-latest", "Mistral Large"),
            ("deepseek/deepseek-chat", "DeepSeek Chat"),
            ("ollama/llama3.1", "Llama 3.1 (Local)"),
        ]

        self.print("\n[bold]Available Models:[/bold]\n")
        for i, (model_id, name) in enumerate(models, 1):
            current = " ← current" if model_id == self.current_model else ""
            self.print(f"  {i}. {name} ({model_id}){current}")

        self.print("\n[dim]Enter model number or full model ID:[/dim]")

        try:
            choice = input("\n> ").strip()

            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(models):
                    self.current_model = models[idx][0]
                    self.print(f"[success]Model changed to: {models[idx][1]}[/success]")
                else:
                    self.print("[error]Invalid selection[/error]")
            elif "/" in choice:
                self.current_model = choice
                self.print(f"[success]Model changed to: {choice}[/success]")
            else:
                self.print("[error]Invalid input[/error]")

        except (ValueError, IndexError):
            self.print("[error]Invalid input[/error]")

    async def export_conversation(self):
        """Export conversation to file."""
        if not self.history:
            self.print("[warning]No history to export[/warning]")
            return

        filename = f"bahram_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

        content = f"# Bahram Conversation Export\n\n"
        content += f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += f"Model: {self.current_model}\n\n---\n\n"

        for entry in self.history:
            role = entry.get("role", "unknown")
            message = entry.get("content", "")
            content += f"## {role.title()}\n\n{message}\n\n---\n\n"

        with open(filename, "w") as f:
            f.write(content)

        self.print(f"[success]Conversation exported to: {filename}[/success]")

    async def chat(self):
        """Interactive chat loop."""
        self.show_welcome()

        while True:
            try:
                # Get user input
                if self.console:
                    user_input = Prompt.ask("\n[bold green]You[/bold green]")
                else:
                    user_input = input("\nYou: ").strip()

                # Handle commands
                if user_input.startswith("/"):
                    command = user_input.lower().split()[0]

                    if command in ("/quit", "/exit"):
                        self.print("[info]Goodbye! 👋[/info]")
                        break

                    elif command == "/help":
                        self.show_help()

                    elif command == "/model":
                        await self.change_model()

                    elif command == "/clear":
                        if self.agent and self.session_id:
                            self.agent.clear_history(self.session_id)
                        self.history.clear()
                        self.print("[info]History cleared[/info]")

                    elif command == "/status":
                        self.show_status()

                    elif command == "/history":
                        self.show_history()

                    elif command == "/export":
                        await self.export_conversation()

                    else:
                        self.print(f"[warning]Unknown command: {command}[/warning]")

                    continue

                # Skip empty input
                if not user_input.strip():
                    continue

                # Record user message
                self.history.append({
                    "role": "user",
                    "content": user_input,
                    "timestamp": datetime.now().strftime('%H:%M:%S'),
                })

                # Show typing indicator
                self.print("[dim]Thinking...[/dim]", end="\r")

                # Get response
                start_time = time.time()
                response = await self.agent.chat(
                    user_input,
                    session_id=self.session_id,
                    model=self.current_model,
                )
                elapsed = time.time() - start_time

                # Clear typing indicator
                print("\r" + " " * 20 + "\r", end="")

                # Record response
                if response.content:
                    self.history.append({
                        "role": "assistant",
                        "content": response.content,
                        "timestamp": datetime.now().strftime('%H:%M:%S'),
                    })

                # Display response
                self.print("\n[bold cyan]Bahram[/bold cyan]")
                self.print_markdown(response.content)

                # Show tool calls if any
                if response.tool_calls:
                    tools_used = ", ".join([tc.name for tc in response.tool_calls])
                    self.print(f"\n[dim]🔧 Tools used: {tools_used}[/dim]")

                # Show timing
                self.print(f"[dim]⏱️ {elapsed:.2f}s[/dim]\n")

            except KeyboardInterrupt:
                self.print("\n[info]Interrupted. Type /quit to exit.[/info]")
                continue
            except EOFError:
                break
            except Exception as e:
                self.print(f"\n[error]Error: {str(e)}[/error]")


async def main():
    """Main entry point."""
    cli = BahramCLI()

    try:
        await cli.initialize()
        await cli.chat()
    finally:
        await cli.cleanup()


if __name__ == "__main__":
    asyncio.run(main())

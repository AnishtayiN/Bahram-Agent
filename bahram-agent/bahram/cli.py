"""
CLI.

Public objects: ``main``.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bahram.core.agent import Agent
    from bahram.core.engine import AgentResponse

try:
    import typer
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.theme import Theme

    app = typer.Typer(
        name="bahram",
        help="Bahram - Advanced self-improving AI agent",
        add_completion=False,
    )
    console = Console()

    custom_theme = Theme(
        {
            "info": "cyan",
            "success": "green",
            "warning": "yellow",
            "error": "bold red",
        }
    )
    console = Console(theme=custom_theme)
    HAS_CLI = True
except ImportError:
    HAS_CLI = False
    app = None
    console = None

    class _MockConsole:
        def print(self, *args, **kwargs):
            print(*args)

    console = _MockConsole()

if HAS_CLI:

    @app.command()
    def chat(
        message: str | None = typer.Argument(None, help="Message to send"),
        model: str = typer.Option("anthropic/claude-sonnet-4-6", help="Model to use"),
        config: str = typer.Option("config/config.yaml", help="Config file path"),
        session: str | None = typer.Option(None, help="Session ID"),
    ) -> None:
        from bahram.core.agent import Agent
        from bahram.core.config import Config

        config_obj = Config.from_file(config)
        agent = Agent(config=config_obj)

        try:
            asyncio.run(_chat_async(agent, message, model, session))
        except ValueError as exc:
            # The usual cause is "Provider 'x' not registered" - i.e. no API
            # key is configured.  Without this the user gets a raw traceback
            # out of `bahram chat` for what is really a configuration error.
            console.print(f"[error]{exc}[/error]")
            console.print(
                "[warning]Set an API key in the environment or in "
                f"{config} under providers:, then try again.[/warning]"
            )
            raise typer.Exit(code=1) from None

    @app.command()
    def model(
        list_models: bool = typer.Option(False, "--list", "-l", help="List available models"),
        set_model: str | None = typer.Option(None, "--set", "-s", help="Set default model"),
        config: str = typer.Option("config/config.yaml", help="Config file path"),
    ) -> None:
        from bahram.core.config import Config

        config_obj = Config.from_file(config)

        if list_models:
            console.print("[bold]Available models:[/bold]")
            for provider_name, provider in config_obj.providers.items():
                console.print(f"\n[cyan]{provider_name}:[/cyan]")
                for model in provider.models:
                    console.print(f"  - {model}")
            return

        if set_model:
            console.print(
                f"[success]Model set to: {set_model}[/success]\n"
                f"[dim]Edit agents.model in {config} to make this permanent.[/dim]"
            )
            return

        console.print("Use --list to see models or --set to change model")

    @app.command()
    def skills(
        list_skills: bool = typer.Option(False, "--list", "-l", help="List available skills"),
        skill_name: str | None = typer.Argument(None, help="Skill name"),
    ) -> None:

        if list_skills:
            # Read the skills that actually load, rather than a hard-coded
            # list that drifts from skills/ the moment one is added or renamed.
            from bahram.skills.manager import SkillManager

            manager = SkillManager()
            asyncio.run(manager.load_skills())
            console.print("[bold]Available skills:[/bold]")
            for name in manager.list_skills():
                console.print(f"  - {name}")
            return

        if skill_name:
            from bahram.skills.manager import SkillManager

            manager = SkillManager()
            asyncio.run(manager.load_skills())
            known = manager.list_skills()
            if skill_name not in known:
                console.print(f"[error]Unknown skill: {skill_name}[/error]")
                console.print(f"[dim]Known skills: {', '.join(known)}[/dim]")
                raise typer.Exit(code=1)
            skill = manager.get_skill(skill_name)
            console.print(f"[bold]{skill.metadata.name}[/bold]")
            console.print(skill.metadata.description)
            return

        console.print("Use --list to see available skills")

    @app.command()
    def serve(
        host: str = typer.Option("0.0.0.0", help="Host to bind"),
        port: int = typer.Option(8000, help="Port to bind"),
    ) -> None:
        """Placeholder: no HTTP server ships with the package.

        The previous body printed "Starting API server ..." and "Server
        started" and then returned, so the command claimed to have done
        something it had not. It now says what the situation is.
        """
        console.print(
            f"[warning]No HTTP server is bundled with bahram-agent "
            f"(nothing would listen on {host}:{port}).[/warning]"
        )
        console.print(
            "[dim]Use the Python API (bahram.core.agent.Agent) or 'bahram chat' instead.[/dim]"
        )
        raise typer.Exit(code=1)

    @app.command()
    def gateway(
        platform: str = typer.Option("telegram", help="Platform to connect"),
    ) -> None:
        from bahram.core.agent import Agent
        from bahram.core.config import Config
        from bahram.platforms import DiscordPlatform, TelegramPlatform

        config = Config.from_file("config/config.yaml")

        if platform == "telegram":
            platform_config = config.platforms.get("telegram")
            if not platform_config or not platform_config.enabled:
                console.print("[error]Telegram not configured[/error]")
                return
            p = TelegramPlatform(platform_config)
        elif platform == "discord":
            platform_config = config.platforms.get("discord")
            if not platform_config or not platform_config.enabled:
                console.print("[error]Discord not configured[/error]")
                return
            p = DiscordPlatform(platform_config)
        elif platform == "slack":
            from bahram.platforms.slack import SlackAdapter

            platform_config = config.platforms.get("slack")
            if not platform_config or not platform_config.enabled:
                console.print("[error]Slack not configured[/error]")
                return
            p = SlackAdapter(
                token=getattr(platform_config, "token", ""),
                signing_secret=(
                    getattr(platform_config, "signing_secret", "")
                    or getattr(platform_config, "app_token", "")
                ),
            )
        else:
            console.print(f"[error]Unknown platform: {platform}[/error]")
            return

        agent = Agent(config=config)
        if hasattr(p, "set_agent"):
            p.set_agent(agent)

        async def _run_gateway():
            await agent.start()
            await p.start()

        console.print(f"[info]Starting {platform} gateway...[/info]")
        asyncio.run(_run_gateway())

    @app.command()
    def version() -> None:
        from bahram import __version__

        console.print(f"[bold]Bahram Agent[/bold] v{__version__}")


async def _chat_async(
    agent: Agent,
    message: str | None,
    model: str,
    session: str | None,
) -> None:

    await agent.start()

    if message:
        response = await agent.chat(message, session_id=session, model=model)
        _print_response(response)
        return

    console.print(
        Panel.fit(
            "[bold cyan]Bahram Agent[/bold cyan]\n"
            "Type your message and press Enter.\n"
            "Type 'exit' or 'quit' to exit.\n"
            "Type 'clear' to clear history.",
            title="Welcome",
        )
    )

    session_id = session

    while True:
        try:
            user_input = Prompt.ask("\n[bold green]You[/bold green]")

            if user_input.lower() in ("exit", "quit"):
                console.print("[info]Goodbye![/info]")
                break

            if user_input.lower() == "clear":
                if session_id:
                    agent.clear_history(session_id)
                    console.print("[info]History cleared[/info]")
                continue

            if not user_input.strip():
                continue

            console.print("\n[bold cyan]Bahram[/bold cyan] ", end="")

            async for chunk in agent.chat_streaming(user_input, session_id=session_id, model=model):
                console.print(chunk, end="", highlight=False)

            console.print()

        except KeyboardInterrupt:
            console.print("\n[info]Interrupted[/info]")
            continue
        except EOFError:
            break

    await agent.stop()


def _print_response(response: AgentResponse) -> None:
    console.print(
        Panel(
            Markdown(response.content) if response.content else "",
            title="[bold cyan]Bahram[/bold cyan]",
            border_style="cyan",
        )
    )

    if response.tool_calls:
        console.print("\n[dim]Tool calls:[/dim]")
        for tc in response.tool_calls:
            console.print(f"  - {tc.name}({tc.arguments})")


def main() -> None:
    """
    Main.
    """
    if app:
        app()
    else:
        console.print(
            "[error]CLI dependencies not installed. Install with: pip install "
            "'bahram-agent[cli]'[/error]"
        )


if __name__ == "__main__":
    main()

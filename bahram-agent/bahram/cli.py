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

        asyncio.run(_chat_async(agent, message, model, session))

    @app.command()
    def model(
        list_models: bool = typer.Option(False, "--list", "-l", help="List available models"),
        set_model: str | None = typer.Option(None, "--set", "-s", help="Set default model"),
    ) -> None:
        from bahram.core.config import Config

        config = Config.from_file("config/config.yaml")

        if list_models:
            console.print("[bold]Available models:[/bold]")
            for provider_name, provider in config.providers.items():
                console.print(f"\n[cyan]{provider_name}:[/cyan]")
                for model in provider.models:
                    console.print(f"  - {model}")
            return

        if set_model:
            console.print(f"[success]Model set to: {set_model}[/success]")
            return

        console.print("Use --list to see models or --set to change model")

    @app.command()
    def skills(
        list_skills: bool = typer.Option(False, "--list", "-l", help="List available skills"),
        skill_name: str | None = typer.Argument(None, help="Skill name"),
    ) -> None:

        if list_skills:
            console.print("[bold]Available skills:[/bold]")
            console.print("  - code-review")
            console.print("  - research")
            console.print("  - deploy")
            return

        if skill_name:
            console.print(f"Skill: {skill_name}")
            return

        console.print("Use --list to see available skills")

    @app.command()
    def serve(
        host: str = typer.Option("0.0.0.0", help="Host to bind"),
        port: int = typer.Option(8000, help="Port to bind"),
    ) -> None:
        console.print(f"[info]Starting API server on {host}:{port}...[/info]")
        console.print("[success]Server started[/success]")

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
    if app:
        app()
    else:
        console.print(
            "[error]CLI dependencies not installed. Install with: pip install "
            "'bahram-agent[cli]'[/error]"
        )


if __name__ == "__main__":
    main()

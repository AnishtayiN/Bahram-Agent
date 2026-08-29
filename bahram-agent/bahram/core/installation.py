"""Installation scripts for Bahram Agent."""

from __future__ import annotations

import logging
import platform
from pathlib import Path

logger = logging.getLogger(__name__)


class InstallationManager:
    """Manage installation and setup."""

    def __init__(self) -> None:
        self._platform = platform.system().lower()

    def get_install_script(self) -> str:
        """Get platform-specific install script."""
        if self._platform == "linux" or self._platform == "darwin":
            return self._get_bash_script()
        elif self._platform == "windows":
            return self._get_powershell_script()
        return "# Unsupported platform"

    def _get_bash_script(self) -> str:
        """Get bash install script."""
        return """#!/bin/bash
set -e

echo "Installing Bahram Agent..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Python 3 not found. Please install Python 3.10+"
    exit 1
fi

# Create virtual environment
python3 -m venv ~/.bahram/venv
source ~/.bahram/venv/bin/activate

# Install Bahram
pip install git+https://github.com/buoawjbnfikwbuinb/agent.git

# Create config directory
mkdir -p ~/.bahram/config
mkdir -p ~/.bahram/skills
mkdir -p ~/.bahram/memories

# Copy example config
if [ ! -f ~/.bahram/config/config.yaml ]; then
    cp /etc/bahram/config.yaml ~/.bahram/config/ 2>/dev/null || true
fi

echo "Installation complete!"
echo "Run 'bahram chat' to start chatting."
"""

    def _get_powershell_script(self) -> str:
        """Get PowerShell install script."""
        return """# Bahram Agent Installer for Windows
Write-Host "Installing Bahram Agent..." -ForegroundColor Cyan

# Check Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python not found. Please install Python 3.10+" -ForegroundColor Red
    exit 1
}

# Create directories
$BahramDir = "$env:LOCALAPPDATA\\bahram"
New-Item -ItemType Directory -Force -Path $BahramDir | Out-Null

# Create virtual environment
python -m venv "$BahramDir\\venv"
& "$BahramDir\\venv\\Scripts\\Activate.ps1"

# Install Bahram
pip install git+https://github.com/buoawjbnfikwbuinb/agent.git

Write-Host "Installation complete!" -ForegroundColor Green
Write-Host "Run 'bahram chat' to start chatting." -ForegroundColor Cyan
"""

    def get_setup_wizard(self) -> str:
        """Get setup wizard script."""
        return """#!/usr/bin/env python3
\"\"\"Bahram Agent Setup Wizard\"\"\"

import os
import sys

def main():
    print("=== Bahram Agent Setup ===")
    print()

    # Provider selection
    print("Select your LLM provider:")
    print("1. Anthropic (Claude)")
    print("2. OpenAI (GPT)")
    print("3. OpenRouter (many models)")
    print("4. Groq (fast, free)")
    print("5. Local (Ollama/LM Studio)")

    choice = input("\\nEnter choice [1-5]: ").strip()

    provider_map = {
        "1": ("anthropic", "ANTHROPIC_API_KEY"),
        "2": ("openai", "OPENAI_API_KEY"),
        "3": ("openrouter", "OPENROUTER_API_KEY"),
        "4": ("groq", "GROQ_API_KEY"),
        "5": ("ollama", ""),
    }

    provider, env_var = provider_map.get(choice, ("anthropic", "ANTHROPIC_API_KEY"))

    if env_var:
        api_key = input(f"Enter {env_var}: ").strip()
        if api_key:
            with open(os.path.expanduser("~/.bahram/.env"), "a") as f:
                f.write(f"{env_var}={api_key}\\n")
            print(f"Saved {env_var}")

    # Telegram setup
    setup_telegram = input("\\nSet up Telegram bot? [y/N]: ").strip().lower()
    if setup_telegram == "y":
        token = input("Enter Telegram bot token: ").strip()
        if token:
            with open(os.path.expanduser("~/.bahram/.env"), "a") as f:
                f.write(f"TELEGRAM_BOT_TOKEN={token}\\n")
            print("Saved Telegram token")

    print("\\nSetup complete! Run 'bahram chat' to start.")
    print("Or 'bahram gateway' to start the messaging gateway.")

if __name__ == "__main__":
    main()
"""

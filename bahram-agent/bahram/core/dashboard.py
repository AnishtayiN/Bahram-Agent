"""Web dashboard for Bahram Agent."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class WebDashboard:
    """Simple web dashboard for monitoring."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        self.host = host
        self.port = port
        self._stats: dict[str, Any] = {}
        self._sessions: list[dict] = []
        self._logs: list[str] = []

    def update_stats(self, stats: dict) -> None:
        """Update dashboard statistics."""
        self._stats.update(stats)

    def add_session(self, session: dict) -> None:
        """Add a session entry."""
        self._sessions.append(session)
        if len(self._sessions) > 100:
            self._sessions = self._sessions[-100:]

    def add_log(self, message: str) -> None:
        """Add a log entry."""
        self._logs.append(message)
        if len(self._logs) > 1000:
            self._logs = self._logs[-1000:]

    def get_dashboard_html(self) -> str:
        """Generate dashboard HTML."""
        return f"""<!DOCTYPE html>
<html>
<head><title>Bahram Agent Dashboard</title></head>
<body>
<h1>Bahram Agent</h1>
<h2>Stats</h2>
<pre>{json.dumps(self._stats, indent=2)}</pre>
<h2>Recent Sessions ({len(self._sessions)})</h2>
<ul>{''.join(f'<li>{s.get("name", "unnamed")} - {s.get("status", "unknown")}</li>' for s in self._sessions[-10:])}</ul>
<h2>Logs</h2>
<pre>{'\\n'.join(self._logs[-20:])}</pre>
</body>
</html>"""

    def get_stats_json(self) -> str:
        """Get stats as JSON."""
        return json.dumps(self._stats, indent=2)

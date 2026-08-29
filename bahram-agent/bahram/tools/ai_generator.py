"""AI Code Generator - Generate complete applications from descriptions."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class GeneratedFile:
    """A generated file."""

    path: str
    content: str
    language: str
    description: str = ""


class AICodeGenerator:
    """Generate complete applications from natural language descriptions."""

    def __init__(self) -> None:
        self._templates: dict[str, dict] = {
            "fastapi": {
                "files": [
                    {"path": "main.py", "language": "python"},
                    {"path": "requirements.txt", "language": "text"},
                    {"path": "Dockerfile", "language": "dockerfile"},
                    {"path": "README.md", "language": "markdown"},
                ],
            },
            "react": {
                "files": [
                    {"path": "src/App.tsx", "language": "typescript"},
                    {"path": "src/index.tsx", "language": "typescript"},
                    {"path": "package.json", "language": "json"},
                    {"path": "README.md", "language": "markdown"},
                ],
            },
            "cli": {
                "files": [
                    {"path": "main.py", "language": "python"},
                    {"path": "requirements.txt", "language": "text"},
                    {"path": "README.md", "language": "markdown"},
                ],
            },
        }

    async def generate(
        self,
        description: str,
        framework: str = "fastapi",
        output_dir: str = "generated",
    ) -> list[GeneratedFile]:
        """Generate application from description."""
        template = self._templates.get(framework, {})
        if not template:
            return []

        files = []
        for file_spec in template["files"]:
            content = await self._generate_file(
                description=description,
                file_path=file_spec["path"],
                language=file_spec["language"],
                framework=framework,
            )
            files.append(GeneratedFile(
                path=file_spec["path"],
                content=content,
                language=file_spec["language"],
            ))

        # Write files
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for file in files:
            file_path = output_path / file.path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(file.content)

        return files

    async def _generate_file(
        self,
        description: str,
        file_path: str,
        language: str,
        framework: str,
    ) -> str:
        """Generate a single file."""
        if language == "python" and framework == "fastapi":
            return self._generate_fastapi_main(description)
        elif language == "python" and framework == "cli":
            return self._generate_cli_main(description)
        elif language == "typescript" and framework == "react":
            return self._generate_react_app(description)
        elif file_path == "requirements.txt":
            return self._generate_requirements(framework)
        elif file_path == "package.json":
            return self._generate_package_json(description)
        elif file_path == "Dockerfile":
            return self._generate_dockerfile(framework)
        elif file_path == "README.md":
            return self._generate_readme(description, framework)
        return ""

    def _generate_fastapi_main(self, description: str) -> str:
        return f'''"""Generated FastAPI application.

Description: {description}
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Optional
import uvicorn

app = FastAPI(title="Generated API")


class Item(BaseModel):
    name: str
    description: Optional[str] = None
    price: float


@app.get("/")
async def root():
    return {{"message": "Welcome to the Generated API"}}


@app.get("/health")
async def health():
    return {{"status": "healthy"}}


@app.post("/items/")
async def create_item(item: Item):
    return {{"item": item, "status": "created"}}


@app.get("/items/{{item_id}}")
async def read_item(item_id: int):
    return {{"item_id": item_id}}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''

    def _generate_cli_main(self, description: str) -> str:
        return f'''"""Generated CLI application.

Description: {description}
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="{description}")
    parser.add_argument("--name", type=str, help="Name parameter")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        print(f"Running with name: {{args.name}}")
    
    print("Hello from generated CLI!")


if __name__ == "__main__":
    main()
'''

    def _generate_react_app(self, description: str) -> str:
        return f'''import React from 'react';

interface AppProps {{
  title?: string;
}}

const App: React.FC<AppProps> = ({{ title = '{description}' }}) => {{
  return (
    <div className="app">
      <h1>{{{{title}}}}</h1>
      <p>This is a generated React application.</p>
    </div>
  );
}};

export default App;
'''

    def _generate_requirements(self, framework: str) -> str:
        requirements = {
            "fastapi": "fastapi>=0.104.0\\nuvicorn>=0.24.0\\npydantic>=2.5.0",
            "cli": "click>=8.1.0\\nrich>=13.0.0",
        }
        return requirements.get(framework, "")

    def _generate_package_json(self, description: str) -> str:
        return f'''{{
  "name": "generated-app",
  "version": "1.0.0",
  "description": "{description}",
  "main": "src/index.tsx",
  "scripts": {{
    "start": "react-scripts start",
    "build": "react-scripts build"
  }},
  "dependencies": {{
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  }}
}}
'''

    def _generate_dockerfile(self, framework: str) -> str:
        if framework == "fastapi":
            return '''FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
'''
        return ""

    def _generate_readme(self, description: str, framework: str) -> str:
        return f"""# Generated Application

{description}

## Framework

{framework}

## Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

## Running

```bash
python main.py
```

## API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `POST /items/` - Create item
- `GET /items/{id}` - Get item
"""

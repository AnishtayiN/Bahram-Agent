# API Reference

## Core Classes

### Agent

Main agent class for interacting with LLM.

```python
from bahram import Agent, Config

config = Config()
agent = Agent(config)

response = await agent.run("Hello")
```

### Config

Configuration class for the agent.

```python
from bahram import Config

config = Config(
    model="gpt-4o",
    provider="openai",
    temperature=0.7,
    max_tokens=4096
)
```

## Tools

### BashTool

Execute bash commands.

```python
from bahram.tools.bash import BashTool

tool = BashTool()
result = await tool.execute("ls -la")
```

### ReadTool

Read file contents.

```python
from bahram.tools.file import ReadTool

tool = ReadTool()
content = await tool.read("file.txt")
```

### WriteTool

Write to files.

```python
from bahram.tools.file import WriteTool

tool = WriteTool()
await tool.write("file.txt", "content")
```

## Memory

### SemanticMemory

Intelligent memory search.

```python
from bahram.memory.semantic import SemanticMemory

memory = SemanticMemory()
memory.add("Important fact")
results = memory.search("fact")
```

## Providers

### GroqProvider

Fast LLM inference.

```python
from bahram.providers.groq import GroqProvider

provider = GroqProvider(api_key="your-key")
response = await provider.complete([{"role": "user", "content": "Hello"}])
```

## Security

### TirithScanner

Security scanning for code.

```python
from bahram.security.tirith import TirithScanner

scanner = TirithScanner()
result = scanner.scan("dangerous code")
print(result.safe)  # False
```

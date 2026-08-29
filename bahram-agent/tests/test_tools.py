"""Tests for tools."""
import pytest
from bahram.tools.autocomplete import AutoComplete
from bahram.tools.code_review import CodeReviewTool
from bahram.tools.todo import TodoTool

class TestAutoComplete:
    def test_autocomplete_creation(self):
        ac = AutoComplete()
        assert ac is not None

    def test_complete_python(self):
        ac = AutoComplete()
        results = ac.complete("def", language="python")
        assert len(results) > 0

    def test_add_to_history(self):
        ac = AutoComplete()
        ac.add_to_history("test_command")
        assert "test_command" in ac._history

class TestCodeReviewTool:
    def test_review_tool_creation(self):
        tool = CodeReviewTool()
        assert tool is not None

    @pytest.mark.asyncio
    async def test_review_code(self):
        tool = CodeReviewTool()
        code = "x = 1\nprint(x)"
        issues = await tool.review_code(code)
        assert isinstance(issues, list)

class TestTodoTool:
    def test_todo_tool_creation(self, tmp_path):
        tool = TodoTool(data_dir=str(tmp_path))
        assert tool is not None

    def test_add_todo(self, tmp_path):
        tool = TodoTool(data_dir=str(tmp_path))
        todo = tool.add("Test task")
        assert todo.content == "Test task"

    def test_list_todos(self, tmp_path):
        tool = TodoTool(data_dir=str(tmp_path))
        tool.add("Task 1")
        tool.add("Task 2")
        todos = tool.list_todos()
        assert len(todos) == 2

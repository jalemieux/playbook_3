"""Stateful multi-tool experimental agent."""
import json
from typing import Optional

from src.llm import chat_completion
from src.tools import execute_tool_call
from src.tools.bash_tool import EXECUTE_BASH_SCHEMA
from src.tools.fs_tools import GLOB_SCHEMA, GREP_SCHEMA, READ_SCHEMA, EDIT_SCHEMA, WRITE_SCHEMA
from src.tools.utils import truncate

DEFAULT_SYSTEM_PROMPT = """

## Your context:
Your memories are stored in ${context_dir_path}/MEMORY.md
Your tasks are in ${context_dir_path}/TASKS.md

## Response Protocol
- Before asking the user for information, ALWAYS search your context first.
- If you don't have the information, ask the user for it.


Keep replies short and direct."""

DEFAULT_TOOLS = [GLOB_SCHEMA, GREP_SCHEMA, READ_SCHEMA, EDIT_SCHEMA, WRITE_SCHEMA]


class AgentOne:
    """Stateful multi-tool agent. Pass an instance where a handler and clear_session are needed."""

    def __init__(
        self,
        *,
        model: str,
        max_iterations: int,
        system_prompt: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        name: str,
    ) -> None:
        self._conversations: dict[str, list[dict]] = {}
        self.name = name
        self.system_prompt = system_prompt
        self.tools = list(tools) if tools is not None else list(DEFAULT_TOOLS)
        self.model = model
        self.max_iterations = max_iterations

    @property
    def conversations(self) -> dict[str, list[dict]]:
        """In-memory conversation store (e.g. for tests)."""
        return self._conversations

    def clear_session(self, session_id: str) -> None:
        """Clear conversation history for a session."""
        self._conversations.pop(session_id, None)

    def handler(
        self,
        text: str,
        reply_fn,
        config: dict,
        session_id: str = "default",
        status_fn=None,
    ) -> None:
        """Process a user message through the base agent."""
        if session_id not in self._conversations:
            self._conversations[session_id] = []
        history = self._conversations[session_id]

        history.append({"role": "user", "content": text})
        messages = [{"role": "system", "content": self.system_prompt}] + history

        for i in range(self.max_iterations):
            if status_fn:
                status_fn("thinking", "")
            result = chat_completion(messages, self.model, tools=self.tools)
            if status_fn:
                status_fn("done_thinking", "")

            if result["tool_calls"] is None:
                response = result["content"] or "[no response]"
                history.append({"role": "assistant", "content": response})
                reply_fn(response)
                return

            assistant_msg = {"role": "assistant", "tool_calls": result["tool_calls"], "content": result.get("content")}
            history.append(assistant_msg)
            messages.append(assistant_msg)

            for tool_call in result["tool_calls"]:
                name = tool_call["function"]["name"]
                args = json.loads(tool_call["function"]["arguments"])

                if status_fn:
                    status_fn("tool_call", f"{name}({json.dumps(args)[:120]})")

                output = execute_tool_call(name, args, config, status_fn)

                if status_fn:
                    status_fn("tool_result", truncate(str(output).strip()))

                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": output,
                }
                history.append(tool_msg)
                messages.append(tool_msg)

        fallback = "Stopped: reached maximum iteration limit."
        history.append({"role": "assistant", "content": fallback})
        reply_fn(fallback)


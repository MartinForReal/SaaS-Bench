import asyncio
from pathlib import Path

from saas_bench import codex_cli_runner


class FakePopen:
    def __init__(self, cmd, **kwargs):
        self.cmd = cmd
        self.returncode = 0
        self.pid = 1234
        output_path = Path(cmd[cmd.index("-o") + 1])
        output_path.write_text('{"status":"ok","summary":"done"}', encoding="utf-8")

    def communicate(self, input=None, timeout=None):
        return '{"event":1}\n', ""


def test_codex_runner_invokes_codex_exec(monkeypatch, tmp_path):
    seen = {}

    def fake_popen(cmd, **kwargs):
        seen["cmd"] = cmd
        return FakePopen(cmd, **kwargs)

    monkeypatch.setattr(codex_cli_runner.shutil, "which", lambda name: "codex")
    monkeypatch.setattr(codex_cli_runner.subprocess, "Popen", fake_popen)

    result = asyncio.run(codex_cli_runner.run_task(
        {"task_id": "demo"},
        "model",
        "Task URL: http://example.test/",
        str(tmp_path),
        max_steps=2,
        todo_md="1. Do it",
    ))

    assert seen["cmd"][1] == "exec"
    assert "--json" in seen["cmd"]
    assert result["status"] == "completed"
    assert result["runner"] == "codex-exec-playwright"
    assert "done" in result["agent_output"]

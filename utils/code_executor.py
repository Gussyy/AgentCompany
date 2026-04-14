"""
code_executor.py — Safe Python code execution for the Kaggle/DataScience chamber.

Agents write Python code as strings. This executor:
  1. Writes the code to a temp file in the competition workspace
  2. Executes it with the project venv Python
  3. Captures stdout, stderr, and exit code
  4. Returns a structured result the agent can read and act on

The workspace is isolated per competition: data/kaggle/{competition_slug}/
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

# compvenv = shared company dev environment with all data science tools
# Falls back to main venv if compvenv not yet created
COMPVENV_PYTHON = Path(__file__).parent.parent / "compvenv" / "Scripts" / "python.exe"
VENV_PYTHON     = Path(__file__).parent.parent / "venv"     / "Scripts" / "python.exe"
KAGGLE_EXE      = Path(__file__).parent.parent / "compvenv" / "Scripts" / "kaggle.exe"
# Always prefer compvenv for agent code execution
EXEC_PYTHON = COMPVENV_PYTHON if COMPVENV_PYTHON.exists() else VENV_PYTHON
KAGGLE_DIR   = Path(__file__).parent.parent / "data" / "kaggle"
KAGGLE_CFG   = Path(__file__).parent.parent   # folder containing kaggle.json
MAX_OUTPUT   = 8000   # chars to return from stdout
TIMEOUT_SEC  = 300    # 5 minutes max per execution


def kaggle_env() -> dict:
    """Return os.environ copy with KAGGLE_CONFIG_DIR and compvenv on PATH."""
    import os
    env = os.environ.copy()
    env["KAGGLE_CONFIG_DIR"] = str(KAGGLE_CFG)
    # Ensure compvenv Scripts dir is on PATH for kaggle.exe etc.
    compvenv_scripts = str(Path(__file__).parent.parent / "compvenv" / "Scripts")
    env["PATH"] = compvenv_scripts + os.pathsep + env.get("PATH", "")
    return env


def get_competition_dir(slug: str) -> Path:
    d = KAGGLE_DIR / slug.replace("/", "_").replace(" ", "_")
    d.mkdir(parents=True, exist_ok=True)
    return d


def extract_code(text: str) -> str:
    """Extract Python code from an LLM response (strips ```python fences)."""
    # Try fenced block first
    m = re.search(r"```python\s*(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r"```\s*(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Whole response is code
    return text.strip()


def run_code(code: str, competition_slug: str,
             script_name: str = "run.py",
             timeout: int = TIMEOUT_SEC) -> dict:
    """
    Execute Python code in the competition workspace.
    Returns:
        {
          "success":   bool,
          "stdout":    str (truncated to MAX_OUTPUT),
          "stderr":    str,
          "exit_code": int,
          "duration":  float,
          "script":    str (path written)
        }
    """
    comp_dir = get_competition_dir(competition_slug)
    script_path = comp_dir / script_name

    # Prepend workspace chdir so all relative paths work
    header = textwrap.dedent(f"""\
        import os, sys
        os.chdir(r'{comp_dir}')
        sys.path.insert(0, r'{comp_dir}')
    """)
    full_code = header + "\n" + code
    script_path.write_text(full_code, encoding="utf-8")

    python = str(EXEC_PYTHON) if EXEC_PYTHON.exists() else sys.executable

    t0 = time.time()
    try:
        proc = subprocess.run(
            [python, str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(comp_dir),
            env=kaggle_env(),
        )
        duration = time.time() - t0
        stdout = proc.stdout[-MAX_OUTPUT:] if len(proc.stdout) > MAX_OUTPUT else proc.stdout
        return {
            "success":   proc.returncode == 0,
            "stdout":    stdout.strip(),
            "stderr":    proc.stderr[-2000:].strip(),
            "exit_code": proc.returncode,
            "duration":  round(duration, 2),
            "script":    str(script_path),
        }
    except subprocess.TimeoutExpired:
        return {
            "success":   False,
            "stdout":    "",
            "stderr":    f"Execution timed out after {timeout}s",
            "exit_code": -1,
            "duration":  timeout,
            "script":    str(script_path),
        }
    except Exception as e:
        return {
            "success":   False,
            "stdout":    "",
            "stderr":    str(e),
            "exit_code": -2,
            "duration":  time.time() - t0,
            "script":    str(script_path),
        }


def format_result(result: dict) -> str:
    """Format execution result for injection into an agent's prompt."""
    status = "✅ SUCCESS" if result["success"] else "❌ FAILED"
    lines = [
        f"=== CODE EXECUTION RESULT ({status}, {result['duration']}s) ===",
        f"Exit code: {result['exit_code']}",
    ]
    if result["stdout"]:
        lines += ["--- STDOUT ---", result["stdout"]]
    if result["stderr"] and not result["success"]:
        lines += ["--- STDERR ---", result["stderr"][:1000]]
    return "\n".join(lines)

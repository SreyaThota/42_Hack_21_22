import sys
import os
import subprocess
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.logger import logger


def run_tests():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_runner = r"E:\42xNeedle_Hackathon-main\secret_spec\test_runner\run_tests.py"
    solution_path = os.path.join(project_root, "knit.py")

    if not os.path.exists(solution_path):
        logger.log_error(f"knit.py not found at {solution_path}")
        return {
            "passed": 0,
            "total": 0,
            "output": "knit.py not found",
            "all_passed": False,
            "parse_error": True,
        }

    if not os.path.exists(test_runner):
        logger.log_error(f"Test runner not found at {test_runner}")
        return {
            "passed": 0,
            "total": 0,
            "output": "test runner not found",
            "all_passed": False,
            "parse_error": True,
        }

    cmd = [
        sys.executable,
        test_runner,
        "--compiler",
        f"{sys.executable} knit.py",
        "--suite",
        "public",
        "--mode",
        "full",
    ]

    cmd_str = " ".join(cmd)
    test_command_str = f"{sys.executable} knit.py compile <input_file>"
    logger.log_command(cmd_str)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=project_root,
        )
        output = result.stdout + "\n" + result.stderr
        logger.log_command(cmd_str, output.strip())

        match = re.search(r"(\d+)/(\d+)", output)
        if match:
            passed = int(match.group(1))
            total = int(match.group(2))
            return {
                "passed": passed,
                "total": total,
                "output": output,
                "all_passed": passed == total,
                "test_command": test_command_str,
            }
        else:
            return {
                "passed": 0,
                "total": 0,
                "output": output,
                "all_passed": False,
                "parse_error": True,
                "test_command": test_command_str,
            }
    except subprocess.TimeoutExpired:
        logger.log_error("Test run timed out after 120s")
        return {
            "passed": 0,
            "total": 0,
            "output": "TIMEOUT",
            "all_passed": False,
            "test_command": test_command_str,
        }
    except Exception as e:
        logger.log_error(f"Test run failed: {e}")
        return {
            "passed": 0,
            "total": 0,
            "output": str(e),
            "all_passed": False,
            "test_command": test_command_str,
        }

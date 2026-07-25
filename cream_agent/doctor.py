"""Read-only local onboarding checks for the Codex-first Cream Agent flow."""

from __future__ import annotations

from dataclasses import dataclass
import shutil
import subprocess
import sys


RECOMMENDED_MCP_NAME = "robinhood-trading"
RECOMMENDED_MCP_URL = "https://agent.robinhood.com/mcp/trading"


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def check_codex_installed() -> CheckResult:
    codex_path = shutil.which("codex")
    if not codex_path:
        return CheckResult(
            name="codex-installed",
            ok=False,
            detail="`codex` was not found on PATH.",
        )

    version = _run(["codex", "--version"])
    if version.returncode != 0:
        detail = (version.stderr or version.stdout).strip() or "Unable to read `codex --version`."
        return CheckResult(name="codex-installed", ok=False, detail=detail)

    return CheckResult(
        name="codex-installed",
        ok=True,
        detail=f"Found Codex at {codex_path}. Version: {(version.stdout or version.stderr).strip()}",
    )


def check_mcp_list() -> tuple[CheckResult, str]:
    result = _run(["codex", "mcp", "list"])
    output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part).strip()
    if result.returncode != 0:
        detail = output or "`codex mcp list` failed."
        return CheckResult(name="codex-mcp-list", ok=False, detail=detail), output
    detail = output or "`codex mcp list` returned no output."
    return CheckResult(name="codex-mcp-list", ok=True, detail=detail), output


def check_robinhood_trading_configured(mcp_list_output: str) -> CheckResult:
    lowered = mcp_list_output.lower()
    if RECOMMENDED_MCP_NAME not in lowered:
        return CheckResult(
            name="robinhood-trading-configured",
            ok=False,
            detail=(
                f"`{RECOMMENDED_MCP_NAME}` was not found in `codex mcp list`. "
                f"Add it with: codex mcp add {RECOMMENDED_MCP_NAME} --url {RECOMMENDED_MCP_URL}"
            ),
        )
    return CheckResult(
        name="robinhood-trading-configured",
        ok=True,
        detail=f"Found `{RECOMMENDED_MCP_NAME}` in local Codex MCP configuration.",
    )


def run_doctor() -> int:
    checks: list[CheckResult] = []

    codex_check = check_codex_installed()
    checks.append(codex_check)
    if not codex_check.ok:
        _print_results(checks)
        return 1

    mcp_check, mcp_output = check_mcp_list()
    checks.append(mcp_check)
    if mcp_check.ok:
        checks.append(check_robinhood_trading_configured(mcp_output))

    _print_results(checks)
    return 0 if all(check.ok for check in checks) else 1


def _print_results(checks: list[CheckResult]) -> None:
    print("Cream Agent doctor")
    print("Read-only checks for local Codex + Robinhood Trading MCP setup.\n")
    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        print(f"[{status}] {check.name}: {check.detail}")


def main() -> None:
    raise SystemExit(run_doctor())


if __name__ == "__main__":
    main()

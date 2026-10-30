#!/usr/bin/env python3
"""Full-stack smoke check: two real servers, real sockets, no third-party services.

What it does
------------
1. Starts the FastAPI backend under uvicorn on a loopback port, with prediction
   history enabled, so the store paths are exercised instead of skipped.
2. Drives the documented HTTP contract over a socket rather than through a test
   client: health, an abstention, the error envelope, the horizon refusal, and store
   / reopen / list / delete.
3. Fetches pages from a production frontend build (`next start`) created against that
   exact backend origin, and checks the built client bundle names it.
4. Runs the frontend's live contract suite (`npm run test:live`) against the running
   backend, so the client's own request-building code is what the server answers.

What this proves, and what it does not
--------------------------------------
* Proves: both processes start from a clean checkout, the client is built against the
  backend that is running, and the request/response/error behaviour the UI renders is
  what the server actually does — over TCP, not in-process.
* Does not prove: page interaction. No browser runs, so the rendered HTML is checked
  for content only. A JavaScript-only failure would still pass.
* Says nothing about railway accuracy. With no promoted artifact every prediction must
  abstain, and the check asserts that it does. Synthetic and empty-state paths only.

Usage
-----
    python scripts/smoke_full_stack.py                 # backend + frontend + client suite
    python scripts/smoke_full_stack.py --skip-frontend # backend + client suite
    python scripts/smoke_full_stack.py --skip-client   # backend + frontend only

The frontend steps need `npm ci` and `npm run build` in `frontend/` first, with
`NEXT_PUBLIC_API_URL` naming the backend this script starts. Set
`RAILCONFIRM_SMOKE_LOG_DIR` to keep the server logs rather than discarding them; CI
sets it so a failed run can upload them. Exit code is
0 only when every check passes; server logs are printed on failure.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"

DEFAULT_BACKEND_PORT = 8010
DEFAULT_FRONTEND_PORT = 3010

BACKEND_START_TIMEOUT = 60.0
FRONTEND_START_TIMEOUT = 120.0
CLIENT_SUITE_TIMEOUT = 300.0

ROUTE_NOT_FOUND = "/v1/nothing-routes-here"

PNR_SHAPED_ID = "1234567890"
"""Ten digits, in the shape of a PNR. Nothing stores tickets under such an id, and the
check below asserts the route refuses it rather than treating it as a lookup."""


class SmokeFailure(AssertionError):
    """A check the running system did not satisfy."""


# ── HTTP helpers ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Reply:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> object:
        if not self.body:
            raise SmokeFailure("expected a JSON body, the reply was empty")
        try:
            return json.loads(self.body)
        except json.JSONDecodeError as exc:  # pragma: no cover - only on a broken server
            raise SmokeFailure(f"expected JSON, got {self.body[:200]!r}") from exc

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


def http(
    method: str,
    url: str,
    payload: object | None = None,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> Reply:
    """One request, keeping 4xx/5xx as replies instead of exceptions."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request_headers = {"Accept": "application/json"}
    if data is not None:
        request_headers["Content-Type"] = "application/json"
    request_headers.update(headers or {})
    request = Request(url, data=data, method=method, headers=request_headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            return Reply(response.status, _lower_headers(response.headers), response.read())
    except HTTPError as error:
        return Reply(error.code, _lower_headers(error.headers), error.read())
    except URLError as exc:
        raise SmokeFailure(f"{method} {url} did not connect: {exc.reason}") from exc


def _lower_headers(headers) -> dict[str, str]:
    return {name.lower(): value for name, value in headers.items()}


def wait_until_answering(url: str, *, timeout: float, server: "Server") -> None:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        if server.process.poll() is not None:
            raise SmokeFailure(
                f"{server.name} exited with code {server.process.returncode} before it "
                f"answered.\n{server.tail()}"
            )
        try:
            http("GET", url, timeout=3.0)
            return
        except SmokeFailure as exc:  # connection refused while booting
            last_error = str(exc)
        time.sleep(0.25)
    raise SmokeFailure(f"{server.name} did not answer {url} within {timeout:.0f}s: {last_error}")


# ── Child processes ────────────────────────────────────────────────────────────


@dataclass
class Server:
    name: str
    process: subprocess.Popen
    log_path: Path

    def tail(self, lines: int = 25) -> str:
        text = self.log_path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            return "(no output)"
        return "\n".join(text.splitlines()[-lines:])


def _spawn(name: str, command: list[str], *, cwd: Path, env: dict[str, str], log_dir: Path) -> Server:
    log_path = log_dir / f"{name}.log"
    handle = log_path.open("w", encoding="utf-8")
    popen_kwargs: dict[str, object] = {}
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        stdout=handle,
        stderr=subprocess.STDOUT,
        **popen_kwargs,
    )
    return Server(name=name, process=process, log_path=log_path)


def stop(server: Server) -> None:
    """Stop the server and everything it started."""
    if server.process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(server.process.pid)],
            capture_output=True,
            check=False,
        )
    else:
        try:
            os.killpg(os.getpgid(server.process.pid), signal.SIGTERM)
        except ProcessLookupError:  # pragma: no cover - it stopped on its own
            return
    try:
        server.process.wait(timeout=15)
    except subprocess.TimeoutExpired:  # pragma: no cover - a wedged process
        server.process.kill()


@contextmanager
def log_workspace() -> Iterator[Path]:
    """Where the two servers write their output.

    A throwaway directory by default. ``RAILCONFIRM_SMOKE_LOG_DIR`` names a directory
    to keep instead, which is how CI collects the logs a failure needs — the temporary
    one is gone by the time anyone reads the run.
    """
    override = os.environ.get("RAILCONFIRM_SMOKE_LOG_DIR")
    if override:
        path = Path(override)
        path.mkdir(parents=True, exist_ok=True)
        yield path
        return
    with tempfile.TemporaryDirectory(prefix="railconfirm-smoke-") as workspace:
        yield Path(workspace)


@contextmanager
def running(server: Server) -> Iterator[Server]:
    try:
        yield server
    finally:
        stop(server)


# ── Servers under test ─────────────────────────────────────────────────────────


def require_free_port(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as exc:
            raise SmokeFailure(
                f"port {port} on loopback is already in use ({exc}). Pass --backend-port or "
                "--frontend-port, and remember the frontend build must name the backend port."
            ) from exc


def start_backend(port: int, storage_dir: Path, frontend_port: int, log_dir: Path) -> Server:
    env = os.environ.copy()
    env.update(
        {
            # History on, so store/reopen/list/delete run for real rather than as a
            # refusal path. The store is a throwaway directory.
            "RAILCONFIRM_PERSIST_PREDICTIONS": "true",
            "RAILCONFIRM_STORAGE_DIR": str(storage_dir),
            "RAILCONFIRM_PREDICTION_RETENTION_DAYS": "1",
            # The frontend origin that will call this server in a browser.
            "RAILCONFIRM_CORS_ALLOWED_ORIGINS": json.dumps([f"http://127.0.0.1:{frontend_port}"]),
            "RAILCONFIRM_LOG_LEVEL": "WARNING",
            "PYTHONUNBUFFERED": "1",
        }
    )
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "railconfirm.api.app:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]
    server = _spawn("backend", command, cwd=BACKEND_DIR, env=env, log_dir=log_dir)
    wait_until_answering(f"http://127.0.0.1:{port}/v1/health", timeout=BACKEND_START_TIMEOUT, server=server)
    return server


def start_frontend(port: int, backend_url: str, log_dir: Path) -> Server:
    build_id = FRONTEND_DIR / ".next" / "BUILD_ID"
    if not build_id.is_file():
        raise SmokeFailure(
            f"{build_id} does not exist. Run `npm ci` and `npm run build` in frontend/ "
            "first, with NEXT_PUBLIC_API_URL naming the backend this script starts."
        )
    node = shutil.which("node")
    if node is None:
        raise SmokeFailure("node is not on PATH; the frontend cannot be started.")
    next_bin = FRONTEND_DIR / "node_modules" / "next" / "dist" / "bin" / "next"
    if not next_bin.is_file():
        raise SmokeFailure(f"{next_bin} is missing. Run `npm ci` in frontend/ first.")
    env = os.environ.copy()
    # Inlined at build time, so this only keeps the child from inheriting a different
    # value; the bundle check below is what actually verifies the origin.
    env["NEXT_PUBLIC_API_URL"] = backend_url
    command = [node, str(next_bin), "start", "-H", "127.0.0.1", "-p", str(port)]
    server = _spawn("frontend", command, cwd=FRONTEND_DIR, env=env, log_dir=log_dir)
    wait_until_answering(f"http://127.0.0.1:{port}/", timeout=FRONTEND_START_TIMEOUT, server=server)
    return server


# ── The checks ─────────────────────────────────────────────────────────────────


def booking(*, persist: bool = False) -> dict:
    """A schema-valid manual request, dated relative to today so it never expires."""
    journey = time.strftime("%Y-%m-%d", time.gmtime(time.time() + 30 * 86_400))
    return {
        "journey": {
            "train_number": "12301",
            "journey_date": journey,
            "boarding_station": "NDLS",
            "destination_station": "HWH",
            "class_code": "SL",
            "quota_code": "GN",
        },
        "prediction_at": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
        "passengers": [
            {"original_status": "GNWL/45", "current_status": "GNWL/12"},
            {"original_status": "GNWL/46", "current_status": "RAC 3"},
        ],
        "persist": persist,
    }


def expect(condition: object, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def check_root_and_health(base: str) -> None:
    root = http("GET", f"{base}/")
    expect(root.status == 200, f"GET / answered {root.status}")
    payload = root.json()
    expect(isinstance(payload, dict) and payload.get("health") == "/v1/health", f"GET / said {payload}")

    health = http("GET", f"{base}/v1/health")
    expect(health.status == 200, f"GET /v1/health answered {health.status}")
    body = health.json()
    expect(body["status"] == "ok", f"health status was {body['status']}")
    # The whole product rests on this: with nothing promoted, nothing is estimated.
    expect(body["model_available"] is False, "a model is available; the smoke expects none")
    expect(body["model_version"] == "no_model_v0", f"unexpected model version {body['model_version']}")
    expect(body["registry_status"] == "no_active_version", f"unexpected registry {body['registry_status']}")
    expect(body["prediction_history"].get("enabled") is True, "history was not enabled for the smoke")
    expect("min_sample_threshold" in body["limits"], "health did not report the governing threshold")


def check_abstention(base: str) -> None:
    reply = http("POST", f"{base}/v1/predictions/manual", booking())
    expect(reply.status == 200, f"a valid request answered {reply.status}: {reply.text()[:400]}")
    report = reply.json()
    expect(report["passenger_count"] == 2, f"passenger_count was {report['passenger_count']}")
    expect(report["evidence_coverage"] == "insufficient", "coverage was not insufficient")
    expect(report["is_supported"] is False, "a report was supported without a model")
    expect(report["stored"] is False, "persist was not requested but the report was stored")
    for outcome in report["passenger_outcomes"]:
        expect(outcome["is_supported"] is False, "a passenger was supported without a model")
        expect(outcome["abstention_reason"] == "no_trained_model", f"reason was {outcome['abstention_reason']}")
        expect(outcome["p_cnf"] is None, "an abstention carried a probability")
    group = report["group_outcome"]
    expect(group is not None, "a two-passenger booking produced no group outcome")
    expect(group["is_supported"] is False, "the group was supported while every passenger abstained")
    expect(group["abstention_reason"] == "no_trained_model", f"group reason was {group['abstention_reason']}")
    expect(
        any("no_active_version" in text for text in report["limitations"]),
        "the limitations did not name the registry state",
    )


def check_validation_envelope(base: str) -> None:
    invalid = booking()
    invalid["journey"]["train_number"] = "12"
    reply = http("POST", f"{base}/v1/predictions/manual", invalid)
    expect(reply.status == 422, f"an invalid train number answered {reply.status}")
    body = reply.json()
    expect(set(body) >= {"error", "details", "request_id"}, f"envelope keys were {sorted(body)}")
    detail = body["details"][0]
    expect(detail["code"] == "VALIDATION_ERROR", f"code was {detail['code']}")
    expect(detail["field"] == "journey.train_number", f"field was {detail['field']}")
    header = reply.headers.get("x-request-id")
    expect(header is not None, "no X-Request-ID header on a validation failure")
    expect(body["request_id"] == header, "the envelope and the header disagree about the request id")


def check_horizon_refusal(base: str) -> None:
    inside = booking()
    inside["prediction_at"] = f"{inside['journey']['journey_date']}T00:00:00+05:30"
    reply = http("POST", f"{base}/v1/predictions/manual", inside)
    expect(reply.status == 422, f"a same-day prediction answered {reply.status}")
    body = reply.json()
    expect(body["details"][0]["code"] == "INVALID_PREDICTION_AT", f"code was {body['details'][0]['code']}")


def check_history_round_trip(base: str) -> None:
    reply = http("POST", f"{base}/v1/predictions/manual", booking(persist=True))
    expect(reply.status == 200, f"a persist request answered {reply.status}: {reply.text()[:400]}")
    report = reply.json()
    expect(report["stored"] is True, "the report was not stored although history is enabled")
    prediction_id = report["prediction_id"]
    expect(report["report_url"] == f"/v1/predictions/{prediction_id}", f"report_url was {report['report_url']}")
    expect(report["retention_expires_at"] is not None, "a stored report carried no retention clock")

    reopened = http("GET", f"{base}{report['report_url']}")
    expect(reopened.status == 200, f"reopening answered {reopened.status}")
    expect(reopened.json()["prediction_id"] == prediction_id, "the reopened report is a different one")

    listed = http("GET", f"{base}/v1/predictions")
    expect(listed.status == 200, f"listing answered {listed.status}")
    listing = listed.json()
    ids = [entry["prediction_id"] for entry in listing["reports"]]
    expect(prediction_id in ids, "the stored report was not listed")
    expect(listing["count"] == len(listing["reports"]), "count disagrees with the list")
    summary = next(entry for entry in listing["reports"] if entry["prediction_id"] == prediction_id)
    # Nothing about the ticket: the list exists so a user can find or remove a report.
    expect(
        set(summary) == {"prediction_id", "target", "model_version", "recorded_at", "retention_expires_at"},
        f"the summary carried unexpected fields: {sorted(summary)}",
    )

    deleted = http("DELETE", f"{base}/v1/predictions/{prediction_id}")
    expect(deleted.status == 204, f"deleting answered {deleted.status}")
    expect(deleted.body == b"", "a delete returned a body, which could confirm what was removed")

    gone = http("GET", f"{base}/v1/predictions/{prediction_id}")
    expect(gone.status == 404, f"a deleted report answered {gone.status}")
    expect(gone.json()["details"][0]["code"] == "not_found", "a deleted report answered with another code")
    again = http("DELETE", f"{base}/v1/predictions/{prediction_id}")
    expect(again.status == 404, "deleting twice did not answer 404")


def check_pnr_shaped_id_is_not_a_lookup(base: str) -> None:
    reply = http("GET", f"{base}/v1/predictions/{PNR_SHAPED_ID}")
    expect(reply.status == 404, f"a PNR-shaped id answered {reply.status}")
    expect(reply.json()["details"][0]["code"] == "not_found", "a PNR-shaped id was not refused as not_found")


def check_unrouted_path_uses_the_envelope(base: str) -> None:
    reply = http("GET", f"{base}{ROUTE_NOT_FOUND}")
    expect(reply.status == 404, f"an unrouted path answered {reply.status}")
    body = reply.json()
    expect(set(body) >= {"error", "details", "request_id"}, f"unrouted reply was {body}")
    expect(body["details"][0]["code"] == "not_found", "an unrouted path did not use the documented code")


def check_cors_allows_the_frontend_origin(base: str, origin: str) -> None:
    reply = http(
        "OPTIONS",
        f"{base}/v1/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    expect(reply.status in (200, 204), f"the CORS preflight answered {reply.status}")
    allowed = reply.headers.get("access-control-allow-origin")
    expect(allowed == origin, f"the preflight allowed {allowed!r}, not {origin!r}")


def check_frontend_pages(base: str) -> None:
    pages = {
        "/": "Railway confirmation likelihood",
        "/history": "Kept reports",
        "/about/methodology": "Prediction Methodology",
    }
    for path, marker in pages.items():
        reply = http("GET", f"{base}{path}")
        expect(reply.status == 200, f"GET {path} answered {reply.status}: {reply.text()[:300]}")
        expect(marker in reply.text(), f"GET {path} did not contain {marker!r}")


def check_bundle_names_the_backend(backend_url: str) -> None:
    static_dir = FRONTEND_DIR / ".next" / "static"
    expect(static_dir.is_dir(), f"{static_dir} is missing; the frontend build is incomplete")
    for path in static_dir.rglob("*.js"):
        if backend_url in path.read_text(encoding="utf-8", errors="replace"):
            return
    raise SmokeFailure(
        f"no built client bundle names {backend_url}. The frontend was built against a "
        "different API origin, so the browser would call something other than the server "
        "this check started. Rebuild with NEXT_PUBLIC_API_URL set to it."
    )


def run_client_suite(backend_url: str, log_dir: Path) -> None:
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if npm is None:
        raise SmokeFailure("npm is not on PATH; the client contract suite cannot run.")
    env = os.environ.copy()
    env["RAILCONFIRM_LIVE_API_URL"] = backend_url
    result = subprocess.run(
        [npm, "run", "test:live"],
        cwd=str(FRONTEND_DIR),
        env=env,
        capture_output=True,
        timeout=CLIENT_SUITE_TIMEOUT,
        check=False,
    )
    # Decoded here rather than with text=True: a Windows console decodes captured
    # output with its own code page and raises on the first box-drawing character.
    output = (result.stdout or b"").decode("utf-8", errors="replace") + (
        result.stderr or b""
    ).decode("utf-8", errors="replace")
    log_dir.joinpath("client-suite.log").write_text(output, encoding="utf-8")
    if result.returncode != 0:
        tail = "\n".join(output.strip().splitlines()[-40:])
        raise SmokeFailure(f"the client contract suite failed against the live backend:\n{tail}")


# ── Entry point ────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Start the real backend and frontend and check them over a socket."
    )
    parser.add_argument("--backend-port", type=int, default=DEFAULT_BACKEND_PORT)
    parser.add_argument("--frontend-port", type=int, default=DEFAULT_FRONTEND_PORT)
    parser.add_argument(
        "--skip-frontend",
        action="store_true",
        help="skip the production frontend build (no pages, no bundle check)",
    )
    parser.add_argument(
        "--skip-client",
        action="store_true",
        help="skip the frontend's live contract suite (npm run test:live)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    backend_url = f"http://127.0.0.1:{args.backend_port}"
    frontend_url = f"http://127.0.0.1:{args.frontend_port}"
    frontend_origin = frontend_url

    checks: list[str] = []

    with log_workspace() as log_dir:
        storage_dir = log_dir / "storage"
        require_free_port(args.backend_port)
        if not args.skip_frontend:
            require_free_port(args.frontend_port)

        backend = start_backend(args.backend_port, storage_dir, args.frontend_port, log_dir)
        try:
            checks.extend(
                [
                    "backend: root and health report the empty registry",
                    "backend: a valid request abstains with no_trained_model",
                    "backend: a field error uses the documented envelope",
                    "backend: a same-day prediction is refused",
                    "backend: store, reopen, list, delete and delete-again",
                    "backend: a PNR-shaped id is not a lookup",
                    "backend: an unrouted path uses the documented envelope",
                    "backend: CORS allows the frontend origin",
                ]
            )
            check_root_and_health(backend_url)
            check_abstention(backend_url)
            check_validation_envelope(backend_url)
            check_horizon_refusal(backend_url)
            check_history_round_trip(backend_url)
            check_pnr_shaped_id_is_not_a_lookup(backend_url)
            check_unrouted_path_uses_the_envelope(backend_url)
            check_cors_allows_the_frontend_origin(backend_url, frontend_origin)

            if not args.skip_client:
                checks.append("client: the real frontend module against this backend")
                run_client_suite(backend_url, log_dir)

            if not args.skip_frontend:
                frontend = start_frontend(args.frontend_port, backend_url, log_dir)
                with running(frontend):
                    checks.extend(
                        [
                            "frontend: the three pages render",
                            "frontend: the built bundle calls this backend",
                        ]
                    )
                    check_frontend_pages(frontend_url)
                    check_bundle_names_the_backend(backend_url)
        except SmokeFailure as exc:
            print(f"FAILED  {checks[-1] if checks else 'startup'}", file=sys.stderr)
            print(f"        {exc}", file=sys.stderr)
            print(f"\n--- logs ---\n{log_dir}", file=sys.stderr)
            print("\n--- backend log (tail) ---", file=sys.stderr)
            print(backend.tail(), file=sys.stderr)
            return 1
        finally:
            stop(backend)

    for description in checks:
        print(f"ok      {description}")
    print(f"\nFull-stack smoke passed: {len(checks)} checks.")
    print(
        "Scope: both processes started and answered over TCP; the client module talked to "
        "the live server. No browser ran, no model was promoted, and nothing here says "
        "anything about railway prediction accuracy."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

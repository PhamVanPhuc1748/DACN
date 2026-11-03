"""Launch the real Flet runtime in isolation without touching LocalDB."""

from pathlib import Path
import subprocess
import sys
import tempfile
import time

import flet as ft

import main as app


def flet_pids():
    """Return existing Flet desktop PIDs so the smoke test preserves them."""
    result = subprocess.run(
        ['powershell.exe', '-NoProfile', '-Command',
         "Get-Process -Name flet -ErrorAction SilentlyContinue | "
         "ForEach-Object { $_.Id }"],
        capture_output=True, check=False, text=True)
    pids = set()
    for value in result.stdout.splitlines():
        try:
            pids.add(int(value.strip()))
        except ValueError:
            continue
    return pids


def target(page, marker_path):
    app.account_count = lambda: 1
    app.main(page)
    Path(marker_path).write_text('rendered', encoding='utf-8')


def run_app(marker_path):
    ft.app(target=lambda page: target(page, marker_path),
           view=ft.AppView.FLET_APP_HIDDEN)


def main():
    with tempfile.TemporaryDirectory(prefix='pigskin-flet-smoke-') as temp_dir:
        existing_flet_pids = flet_pids()
        marker_path = str(Path(temp_dir) / 'rendered.txt')
        process = subprocess.Popen(
            [sys.executable, '-m', 'tests.flet_runtime_smoke',
             '--worker', marker_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 20
        try:
            while time.monotonic() < deadline:
                if Path(marker_path).is_file():
                    print('FLET_RUNTIME_RENDER_OK')
                    return 0
                if process.poll() is not None:
                    raise RuntimeError(
                        f'Flet exited before rendering (exit code {process.returncode}).')
                time.sleep(0.1)
            raise TimeoutError('Flet did not render within 20 seconds.')
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            # Flet Desktop detaches from its Python host on Windows, so it may
            # no longer be part of taskkill's tree. Stop only PIDs created by
            # this smoke test and preserve every pre-existing Flet window.
            time.sleep(0.5)
            for pid in flet_pids() - existing_flet_pids:
                subprocess.run(
                    ['powershell.exe', '-NoProfile', '-Command',
                     f'Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue'],
                    capture_output=True, check=False, text=True, timeout=5)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        run_app(sys.argv[2])
    else:
        raise SystemExit(main())

"""Launch the real Flet runtime in isolation without touching LocalDB."""

from pathlib import Path
import asyncio
import inspect
import subprocess
import sys
import tempfile
import time

import flet as ft

import main as app
import views.model_operations as model_operations


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


def walk(control):
    pending = [control]
    seen = set()
    while pending:
        item = pending.pop()
        if item is None or id(item) in seen:
            continue
        seen.add(id(item))
        yield item
        pending.extend(getattr(item, 'controls', []) or [])
        content = getattr(item, 'content', None)
        if content is not None:
            pending.append(content)


def configure_layout_fakes(role):
    user = {'id': 7, 'email': 'demo@example.test', 'display_name': 'Demo',
            'role': role, 'active': True, 'created_at': '2026-11-04 10:00:00'}
    record = {'id': 1021, 'case_id': 'PS-001021', 'animal_id': 'PIG-001',
              'filename': 'case.webp', 'created_at': '2026-11-04 21:19:09',
              'predicted_class': 'Infected_Environmental_Dermatitis',
              'confidence': .845, 'farm_name': '', 'body_site': '',
              'onset_date': '', 'entered_at': '', 'symptoms': 'Tổn thương da',
              'scores_json': '[]', 'result_status': 'not_started',
              'image_path': '', 'expert_id': None, 'review_status': 'needs_review',
              'expert_result': None, 'expert_notes': None, 'review_note': ''}
    totals = {'total': 1, 'pending': 1, 'second_review': 0, 'published': 0,
              'inferred': 1, 'authored': 0}
    metrics = {'disease_percent': 0, 'classified': 0, 'disease_cases': 0,
               'active_accounts': 1, 'total_accounts': 1, 'logins_30d': 0,
               'total_cases': 1, 'awaiting_second_review': 0, 'published': 0,
               'cases_by_month': [], 'logins_by_month': []}
    app.account_count = lambda: 1
    app.authenticate = lambda *_: user
    app.current_account = lambda *_: user
    app.recent = lambda *_, **__: [record]
    app.count_cases = lambda *_, **__: 1
    app.case_summary = lambda *_: totals
    app.admin_metrics = lambda *_: metrics
    app.list_users = lambda *_: [user]
    app.unseen_result_count = lambda *_: 0
    app.support_unread_count = lambda *_: 0
    app.support_threads = lambda *_: []
    app.prewarm_ai_worker = lambda: {}
    app.shutdown_ai_worker = lambda: None
    app.model_status = lambda: {'available': False, 'message': 'Runtime smoke'}
    app.model_spec = lambda: {'run_id': 'smoke', 'num_classes': 10,
                              'input_size': [224, 224]}
    model_operations.model_status = app.model_status
    model_operations.model_spec = app.model_spec


async def layout_target(page, marker_path, role):
    try:
        configure_layout_fakes(role)
        app.main(page)
        login = next(item for item in walk(page.controls[0])
                     if isinstance(item, ft.ElevatedButton))
        result = login.on_click(type('Event', (), {'control': login})())
        if inspect.isawaitable(result):
            await result
        page.update()
        await asyncio.sleep(.4)
        expected = ({'user': ['Tổng quan', 'Phân tích ảnh', 'Lịch sử', 'Hỗ trợ'],
                     'expert': ['Tổng quan', 'Phân tích ảnh', 'Lịch sử', 'Dataset',
                                'Huấn luyện', 'Mô hình AI', 'Hỗ trợ'],
                     'admin': ['Tổng quan', 'Dataset', 'Huấn luyện', 'Mô hình AI',
                               'Quản lý tài khoản', 'Hỗ trợ']})[role]
        rendered = []
        for name in expected:
            nav = next(item for item in walk(page.controls[0])
                       if getattr(item, 'tooltip', None) == name)
            nav.on_click(type('Event', (), {'control': nav})())
            page.update()
            await asyncio.sleep(.2)
            workspace = page.controls[0].controls[1].content.controls[1].content
            if not workspace.controls:
                raise RuntimeError(f'Blank workspace after navigating to {name}.')
            rendered.append(name)
        Path(marker_path).write_text('|'.join(rendered), encoding='utf-8')
    except Exception as exc:
        Path(marker_path).write_text(f'ERROR: {type(exc).__name__}: {exc}', encoding='utf-8')
        raise


def run_layout_app(marker_path, role):
    async def target(page):
        await layout_target(page, marker_path, role)

    ft.app(target=target, view=ft.AppView.FLET_APP_HIDDEN)


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


def layout_main():
    for role in ('user', 'expert', 'admin'):
        with tempfile.TemporaryDirectory(prefix=f'pigskin-flet-{role}-') as temp_dir:
            existing_flet_pids = flet_pids()
            marker = Path(temp_dir) / 'rendered.txt'
            process = subprocess.Popen(
                [sys.executable, '-m', 'tests.flet_runtime_smoke',
                 '--layout-worker', str(marker), role],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            deadline = time.monotonic() + 25
            try:
                while time.monotonic() < deadline and not marker.is_file():
                    if process.poll() is not None:
                        raise RuntimeError(
                            f'Flet {role} layout exited early ({process.returncode}).')
                    time.sleep(.1)
                if not marker.is_file():
                    raise TimeoutError(f'Flet {role} layout did not render in time.')
                result = marker.read_text(encoding='utf-8')
                if result.startswith('ERROR:'):
                    raise RuntimeError(result)
                print(f'FLET_LAYOUT_{role.upper()}_OK: {len(result.split("|"))} pages')
            finally:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                time.sleep(.5)
                for pid in flet_pids() - existing_flet_pids:
                    subprocess.run(
                        ['powershell.exe', '-NoProfile', '-Command',
                         f'Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue'],
                        capture_output=True, check=False, text=True, timeout=5)
    return 0


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        run_app(sys.argv[2])
    elif len(sys.argv) == 4 and sys.argv[1] == '--layout-worker':
        run_layout_app(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 2 and sys.argv[1] == '--layout':
        raise SystemExit(layout_main())
    else:
        raise SystemExit(main())

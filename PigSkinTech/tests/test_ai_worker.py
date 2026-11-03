"""Lifecycle tests for the reusable isolated AI worker."""

import os
from pathlib import Path
import sys
import tempfile
import unittest

from services.inference import AIWorkerClient


class AIWorkerLifecycleTests(unittest.TestCase):
    def client(self, **kwargs):
        worker = AIWorkerClient(
            Path(sys.executable), start_timeout=5, request_timeout=2,
            worker_module='tests.fake_ai_worker', **kwargs)
        self.addCleanup(worker.close)
        return worker

    def test_consecutive_requests_reuse_one_process_and_close_cleanly(self):
        worker = self.client()
        first = worker.predict('first.jpg')
        process = worker._process
        second = worker.predict('second.jpg')
        self.assertEqual(first['worker_pid'], second['worker_pid'])
        worker.close()
        self.assertIsNotNone(process.poll())
        self.assertIsNone(worker.pid)

    def test_unexpected_worker_exit_restarts_once(self):
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / 'crashed.marker'
            worker = self.client(worker_environment={
                'FAKE_WORKER_CRASH_MARKER': str(marker),
            })
            result = worker.predict(Path(root) / 'crash-once.jpg')
            self.assertEqual(result['label'], 'fake')
            self.assertTrue(marker.is_file())
            self.assertIsNotNone(worker.pid)

    def test_request_timeout_stops_worker(self):
        worker = AIWorkerClient(
            Path(sys.executable), start_timeout=5, request_timeout=0.05,
            worker_module='tests.fake_ai_worker',
            worker_environment={'FAKE_WORKER_DELAY': '0.5'})
        self.addCleanup(worker.close)
        with self.assertRaises(TimeoutError):
            worker.predict('slow.jpg')
        self.assertIsNone(worker.pid)

    def test_startup_timeout_stops_worker(self):
        worker = AIWorkerClient(
            Path(sys.executable), start_timeout=0.05, request_timeout=2,
            worker_module='tests.fake_ai_worker',
            worker_environment={'FAKE_WORKER_START_DELAY': '0.5'})
        self.addCleanup(worker.close)
        with self.assertRaises(TimeoutError):
            worker.start()
        self.assertIsNone(worker.pid)


if __name__ == '__main__':
    unittest.main()

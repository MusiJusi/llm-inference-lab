import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from scripts import benchmark


def response(tokens=4, completed=True):
    events = [
        {"choices": [{"delta": {"role": "assistant", "content": ""}}]},
        {"choices": [{"delta": {"content": "PRIVATE_GENERATED_TEXT"}}]},
        {"choices": [], "usage": {"prompt_tokens": 42, "completion_tokens": tokens}},
    ]
    data = "".join("data: " + json.dumps(event) + "\n\n" for event in events)
    if completed:
        data += "data: [DONE]\n\n"
    return io.BytesIO(data.encode())


class BenchmarkTests(unittest.TestCase):
    def test_stream_must_finish_and_match_fixed_output_budget(self):
        for stream in (response(completed=False), response(tokens=3)):
            with self.subTest(stream=stream), patch.object(benchmark, "urlopen", return_value=stream):
                with self.assertRaises(RuntimeError):
                    benchmark.measure("http://localhost", "PRIVATE_TOKEN", "model", "PRIVATE_PROMPT", 4, True)

    def test_time_per_output_token_uses_remaining_output_tokens(self):
        with patch.object(benchmark, "urlopen", return_value=response()), patch.object(benchmark.time, "perf_counter", side_effect=[0, 0.2, 2]):
            result = benchmark.measure("http://localhost", "token", "model", "prompt", 4, True)
        self.assertAlmostEqual(result["tpot_s"], 0.6)

    def test_suite_uses_unique_prompts_and_records_no_private_content(self):
        with tempfile.TemporaryDirectory() as directory:
            token = Path(directory) / "token"
            token.write_text("PRIVATE_TOKEN")
            output = Path(directory) / "report.json"
            console = io.StringIO()
            with patch.object(benchmark, "urlopen", side_effect=lambda *args, **kwargs: response()) as send:
                with contextlib.redirect_stdout(console):
                    status = benchmark.main([
                        "--token-file", str(token), "--output", str(output),
                        "--requests", "2", "--concurrency-levels", "1", "2", "4",
                        "--max-tokens", "4", "--ignore-eos",
                    ])
            report = json.loads(output.read_text())
            self.assertEqual(status, 0)
            self.assertEqual(report["status"], "passed")
            self.assertEqual([run["concurrency"] for run in report["runs"]], [1, 2, 4])
            payloads = [json.loads(call.args[0].data) for call in send.call_args_list]
            prompts = [payload["messages"][0]["content"] for payload in payloads]
            self.assertEqual(len(prompts), 18)  # Six cases: one warm-up and two measured requests each.
            self.assertEqual(len(set(prompts)), len(prompts))
            self.assertTrue(all(payload["ignore_eos"] for payload in payloads))
            for run in report["runs"]:
                for case in run["cases"].values():
                    self.assertEqual(case["successful_requests"], 2)
                    self.assertEqual(case["failed_requests"], 0)
                    self.assertEqual(case["total_output_tokens"], 8)
                    self.assertLessEqual(case["ttft_p50_s"], case["latency_p50_s"])
            for private in ("PRIVATE_TOKEN", "PRIVATE_GENERATED_TEXT", prompts[0]):
                self.assertNotIn(private, output.read_text() + console.getvalue())

    def test_default_artifacts_stay_in_the_lab_when_called_from_another_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            lab=Path(temporary)/"lab"; foreign=Path(temporary)/"unrelated-project"
            (lab/".local").mkdir(parents=True);foreign.mkdir()
            (lab/".local/api-token").write_text("PRIVATE_TOKEN")
            old_directory=Path.cwd()
            try:
                os.chdir(foreign)
                with patch.object(benchmark,"ROOT",lab),patch.object(benchmark,"urlopen",side_effect=lambda *a,**k:response()),contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(benchmark.main(["--requests","1","--warmup-requests","0"]),0)
            finally:
                os.chdir(old_directory)
            self.assertEqual(list(foreign.iterdir()),[])
            self.assertEqual(json.loads((lab/"results/benchmark.json").read_text())["status"],"passed")

    def test_concurrent_warmup_is_not_counted_as_measured_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            token=Path(directory)/"token";token.write_text("PRIVATE_TOKEN")
            output=Path(directory)/"report.json"
            with patch.object(benchmark,"urlopen",side_effect=lambda *a,**k:response()) as send,contextlib.redirect_stdout(io.StringIO()):
                status=benchmark.main(["--token-file",str(token),"--output",str(output),"--requests","2","--concurrency-levels","1","2","--warmup-rounds","2","--max-tokens","4","--ignore-eos"])
            report=json.loads(output.read_text())
            self.assertEqual(status,0)
            self.assertEqual(report["warmup_mode"],"concurrent_rounds")
            self.assertEqual(send.call_count,20)
            for run in report["runs"]:
                for case in run["cases"].values():
                    self.assertEqual(case["warmup_requests"],2*run["concurrency"])
                    self.assertEqual(case["successful_requests"],2)
                    self.assertEqual(case["total_output_tokens"],8)

    def test_http_failures_are_counted_without_logging_error_body(self):
        def unauthorized(*args, **kwargs):
            raise HTTPError("http://localhost/PRIVATE_URL", 401, "PRIVATE_ERROR", {}, io.BytesIO(b"PRIVATE_BODY"))

        with tempfile.TemporaryDirectory() as directory:
            token = Path(directory) / "token"
            token.write_text("PRIVATE_TOKEN")
            output = Path(directory) / "report.json"
            console = io.StringIO()
            with patch.object(benchmark, "urlopen", side_effect=unauthorized), contextlib.redirect_stdout(console):
                status = benchmark.main([
                    "--token-file", str(token), "--output", str(output),
                    "--requests", "2", "--warmup-requests", "0",
                ])
            report = json.loads(output.read_text())
            self.assertEqual(status, 1)
            self.assertEqual(report["status"], "failed")
            for case in report["cases"].values():
                self.assertEqual(case["successful_requests"], 0)
                self.assertEqual(case["failed_requests"], 2)
                self.assertEqual(case["error_rate"], 1)
                self.assertTrue(all(error["http_status"] == 401 for error in case["errors"]))
            self.assertNotIn("PRIVATE_", output.read_text() + console.getvalue())


if __name__ == "__main__":
    unittest.main()

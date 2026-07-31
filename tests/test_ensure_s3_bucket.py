import subprocess

from cogrion_cli.bootstrap import runner


def test_ensure_s3_bucket_adopts_bucket_already_exists(monkeypatch, capsys):
    def fake_run(cmd, **kwargs):
        if cmd[:3] == ["aws", "s3api", "head-bucket"]:
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="")
        if cmd[:3] == ["aws", "s3api", "create-bucket"]:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout="",
                stderr="An error occurred (BucketAlreadyExists) when calling the "
                "CreateBucket operation: The requested bucket name is not available.",
            )
        raise AssertionError(f"unexpected subprocess call: {cmd}")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    runner._ensure_s3_bucket("w-aws01a-kb-backup", "ap-southeast-1", dry_run=False)

    assert "already exists" in capsys.readouterr().out.lower()

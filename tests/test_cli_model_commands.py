import json
from pathlib import Path

from miaos.cli import main


def test_model_cli_register_list_and_inspect(tmp_path: Path, capsys: object) -> None:
    db_path = tmp_path / "registry.sqlite3"
    model_path = tmp_path / "model.bin"
    model_path.write_bytes(b"cli-model")

    register_exit = main(
        [
            "model",
            "--db-path",
            str(db_path),
            "register",
            "--id",
            "cli-model",
            "--provider",
            "mlx",
            "--family",
            "qwen3.6",
            "--variant",
            "8b",
            "--quantization",
            "4bit",
            "--context-len",
            "16384",
            "--path",
            str(model_path),
            "--trace-id",
            "trace-cli-register",
        ]
    )
    assert register_exit == 0
    register_payload = json.loads(capsys.readouterr().out)
    assert register_payload["id"] == "cli-model"
    assert register_payload["trace_id"] == "trace-cli-register"

    list_exit = main(["model", "--db-path", str(db_path), "list"])
    assert list_exit == 0
    list_payload = json.loads(capsys.readouterr().out)
    assert len(list_payload) == 1
    assert list_payload[0]["id"] == "cli-model"

    inspect_exit = main(["model", "--db-path", str(db_path), "inspect", "cli-model"])
    assert inspect_exit == 0
    inspect_payload = json.loads(capsys.readouterr().out)
    assert inspect_payload["id"] == "cli-model"
    assert inspect_payload["events"][0]["event_type"] == "register_model"

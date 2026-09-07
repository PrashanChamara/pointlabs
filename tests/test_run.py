from unittest.mock import patch

import run


def test_main_starts_a_local_development_server(monkeypatch):
    monkeypatch.setenv("PORT", "5055")
    monkeypatch.setenv("FLASK_DEBUG", "1")

    with patch.object(run.app, "run") as start_server:
        run.main()

    start_server.assert_called_once_with(host="127.0.0.1", port=5055, debug=True)

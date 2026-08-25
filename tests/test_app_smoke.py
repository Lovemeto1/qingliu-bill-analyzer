from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_app_empty_state_renders_without_exception():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py")
    app.run(timeout=20)
    assert not app.exception
    assert app.title

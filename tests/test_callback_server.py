import socket
import threading
import time
import urllib.error
import urllib.request

from cream_agent.auth.callback_server import wait_for_callback


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_ignores_stray_request_and_waits_for_real_callback():
    port = _free_port()
    results = {}

    def run():
        results["result"] = wait_for_callback(port, timeout=5.0)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    time.sleep(0.2)  # let the server start listening

    # A stray request (e.g. a browser favicon fetch) must not be mistaken
    # for the OAuth redirect and must not consume the server's one-shot loop.
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/favicon.ico", timeout=2)
    except urllib.error.HTTPError as e:
        assert e.code == 404

    urllib.request.urlopen(
        f"http://127.0.0.1:{port}/callback?code=abc123&state=xyz", timeout=2
    )
    thread.join(timeout=5.0)

    result = results["result"]
    assert result.code == "abc123"
    assert result.state == "xyz"
    assert result.error is None


def test_times_out_when_no_callback_received():
    port = _free_port()
    result = wait_for_callback(port, timeout=0.5)
    assert result.error == "timeout"

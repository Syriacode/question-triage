import httpx
import pytest

from triage.classifier import classify
from triage.llm import OllamaClient

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def client():
    try:
        httpx.get("http://localhost:11434/api/version", timeout=2.0).raise_for_status()
    except httpx.HTTPError:
        pytest.skip("Ollama is not running on localhost:11434")
    return OllamaClient(model="qwen2.5:3b")


def test_obvious_login_problem(client):
    result = classify("I can't log in to the course website since I reset my password.", client)

    assert result.topic == "account_access"


def test_extension_request_needs_a_human(client):
    result = classify("Can I get a 3-day extension on project 2? I was sick.", client)

    assert result.needs_human is True

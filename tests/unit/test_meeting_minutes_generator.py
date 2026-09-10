import asyncio
from types import SimpleNamespace
import threading

import pytest

import meeting_transcription as mt


class FakeSession:
    def __init__(self, content="# Meeting minutes"):
        self.content = content
        self.prompt = None
        self.disconnected = False
        self.aborted = False
        self.timeout = "not-passed"

    async def send_and_wait(self, prompt, **options):
        self.prompt = prompt
        self.timeout = options.get("timeout", "not-passed")
        return SimpleNamespace(data=SimpleNamespace(content=self.content))

    async def abort(self):
        self.aborted = True

    async def disconnect(self):
        self.disconnected = True


class FakeClient:
    def __init__(self, session):
        self.session = session
        self.started = False
        self.stopped = False
        self.model = None

    async def start(self):
        self.started = True

    async def create_session(self, model):
        self.model = model
        return self.session

    async def stop(self):
        self.stopped = True


def test_generate_writes_copilot_response_and_closes_resources(tmp_path):
    transcript_path = tmp_path / "transcript.txt"
    transcript_path.write_text("[00:00:01] Alice: Approviamo il piano.", encoding="utf-8")
    session = FakeSession("# Verbale\n\n## Decisioni\n- Piano approvato")
    client = FakeClient(session)
    generator = mt.MeetingMinutesGenerator(
        model="auto", client_factory=lambda: client
    )

    result = generator.generate(transcript_path)

    assert result == tmp_path / "meeting_minutes.md"
    assert result.read_text(encoding="utf-8") == (
        "# Verbale\n\n## Decisioni\n- Piano approvato\n"
    )
    assert "Alice: Approviamo il piano." in session.prompt
    assert client.model == "auto"
    assert client.started and client.stopped and session.disconnected


def test_generate_without_timeout_disables_sdk_timeout(tmp_path):
    transcript_path = tmp_path / "transcript.txt"
    transcript_path.write_text("A valid transcript", encoding="utf-8")
    session = FakeSession()
    client = FakeClient(session)
    generator = mt.MeetingMinutesGenerator(
        timeout_seconds=None, client_factory=lambda: client
    )

    result = generator.generate(transcript_path)

    assert result.exists()
    assert session.timeout is None


def test_generate_rejects_empty_transcript_before_starting_client(tmp_path):
    transcript_path = tmp_path / "transcript.txt"
    transcript_path.write_text("  \n", encoding="utf-8")
    factory_called = False

    def client_factory():
        nonlocal factory_called
        factory_called = True
        return FakeClient(FakeSession())

    generator = mt.MeetingMinutesGenerator(client_factory=client_factory)

    with pytest.raises(ValueError, match="empty transcript"):
        generator.generate(transcript_path)

    assert not factory_called


def test_generate_does_not_write_file_for_empty_copilot_response(tmp_path):
    transcript_path = tmp_path / "transcript.txt"
    transcript_path.write_text("A valid transcript", encoding="utf-8")
    session = FakeSession("  ")
    client = FakeClient(session)
    generator = mt.MeetingMinutesGenerator(client_factory=lambda: client)

    with pytest.raises(RuntimeError, match="empty response"):
        generator.generate(transcript_path)

    assert not (tmp_path / "meeting_minutes.md").exists()
    assert client.stopped and session.disconnected


def test_generate_aborts_copilot_when_cancelled(tmp_path):
    transcript_path = tmp_path / "transcript.txt"
    transcript_path.write_text("A valid transcript", encoding="utf-8")
    cancel_event = threading.Event()

    class BlockingSession(FakeSession):
        async def send_and_wait(self, prompt, **options):
            self.prompt = prompt
            while True:
                await asyncio.sleep(1)

    session = BlockingSession()
    client = FakeClient(session)
    generator = mt.MeetingMinutesGenerator(client_factory=lambda: client)
    timer = threading.Timer(0.05, cancel_event.set)
    timer.start()
    try:
        with pytest.raises(mt.MeetingMinutesCancelled):
            generator.generate(transcript_path, cancel_event=cancel_event)
    finally:
        timer.cancel()

    assert session.aborted
    assert session.disconnected
    assert client.stopped
    assert not (tmp_path / "meeting_minutes.md").exists()


def test_generate_can_be_cancelled_while_client_starts(tmp_path):
    transcript_path = tmp_path / "transcript.txt"
    transcript_path.write_text("A valid transcript", encoding="utf-8")
    cancel_event = threading.Event()

    class StartingClient(FakeClient):
        async def start(self):
            while True:
                await asyncio.sleep(1)

    session = FakeSession()
    client = StartingClient(session)
    generator = mt.MeetingMinutesGenerator(client_factory=lambda: client)
    timer = threading.Timer(0.05, cancel_event.set)
    timer.start()
    try:
        with pytest.raises(mt.MeetingMinutesCancelled):
            generator.generate(transcript_path, cancel_event=cancel_event)
    finally:
        timer.cancel()

    assert client.stopped
    assert not session.aborted
    assert not (tmp_path / "meeting_minutes.md").exists()
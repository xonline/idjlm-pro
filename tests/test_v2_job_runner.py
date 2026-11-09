from app.services.v2_job_runner import JobCancelled, run_audio_classification


class _Result:
    def __init__(self, payload):
        self.payload = payload

    def to_service_payload(self):
        return self.payload


class _Engine:
    def classify_item(self, item_id, path, model_id):
        return _Result({"item_id": item_id, "status": "proposed", "axes": {}})


def test_job_runner_persists_each_audio_result():
    saved, events = [], []
    counts = run_audio_classification(
        entries=[{"id": "one", "path": "/tmp/one.mp3"}],
        model_id="test",
        engine=_Engine(),
        persist=saved.append,
        progress=lambda name, payload: events.append((name, payload)),
        should_stop=lambda: False,
    )
    assert counts == {"completed": 1, "failed": 0, "abstained": 0}
    assert saved[0]["item_id"] == "one"
    assert events[0][0] == "item_completed"


def test_job_runner_stops_before_next_item():
    try:
        run_audio_classification(
            entries=[{"id": "one", "path": "/tmp/one.mp3"}],
            model_id="test",
            engine=_Engine(),
            persist=lambda _: None,
            progress=lambda *_: None,
            should_stop=lambda: True,
        )
    except JobCancelled:
        pass
    else:
        raise AssertionError("expected cancellation")

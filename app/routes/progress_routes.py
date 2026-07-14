import json
import queue
from flask import Blueprint, Response, stream_with_context, jsonify
from app import get_cancel_events, get_progress_queues

bp = Blueprint("progress", __name__, url_prefix="/api")


@bp.route("/progress/<op_id>")
def stream_progress(op_id):
    """
    SSE endpoint. Frontend connects with EventSource('/api/progress/<op_id>').
    Streams JSON messages: {current, total, track, done, error}
    """
    def generate():
        queues = get_progress_queues()
        q = queues.get(op_id)
        if not q:
            yield f"event: error\ndata: {json.dumps({'error': 'Unknown operation'})}\n\n"
            return
        try:
            while True:
                try:
                    msg = q.get(timeout=45)
                    if msg.get('done'):
                        yield f"event: complete\ndata: {json.dumps(msg)}\n\n"
                        break
                    elif msg.get('ping'):
                        # Keep-alive — send as comment so EventSource stays open
                        yield ": ping\n\n"
                    else:
                        yield f"event: progress\ndata: {json.dumps(msg)}\n\n"
                except queue.Empty:
                    # Keep-alive ping
                    yield ": ping\n\n"
        finally:
            queues.pop(op_id, None)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


@bp.route("/progress/<op_id>/cancel", methods=["POST"])
def cancel_operation(op_id):
    """Signal an operation to stop.

    Sets the op's cancel event so the worker pool tears down instead of
    draining every remaining track, then unblocks the SSE stream. The queue is
    NOT popped here — the streaming generator pops it in its own `finally`, and
    the worker still needs a live queue to emit its terminal event.
    """
    ev = get_cancel_events().get(op_id)
    if ev is not None:
        ev.set()

    queues = get_progress_queues()
    if op_id in queues:
        queues[op_id].put({'done': True, 'cancelled': True})
    return jsonify({"cancelled": True}), 200

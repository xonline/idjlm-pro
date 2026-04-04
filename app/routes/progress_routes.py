import json
import queue
from flask import Blueprint, Response, stream_with_context, jsonify
from app import get_progress_queues

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
            yield f"data: {json.dumps({'error': 'Unknown operation', 'done': True})}\n\n"
            return
        while True:
            try:
                msg = q.get(timeout=45)
                yield f"data: {json.dumps(msg)}\n\n"
                if msg.get('done'):
                    # Clean up queue
                    queues.pop(op_id, None)
                    break
            except queue.Empty:
                # Keep-alive ping
                yield f"data: {json.dumps({'ping': True})}\n\n"

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
    """Signal an operation to stop."""
    queues = get_progress_queues()
    if op_id in queues:
        queues[op_id].put({'done': True, 'cancelled': True})
        queues.pop(op_id, None)
    return jsonify({"cancelled": True}), 200

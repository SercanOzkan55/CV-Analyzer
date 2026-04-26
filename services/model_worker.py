import json
import logging
import os
import time
import uuid
from multiprocessing import Process, Queue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_task_q = None
_res_q = None
_proc = None

MODEL_PATH = os.getenv("MODEL_PATH", "resume_model.pkl")
ONNX_PATH = os.getenv("MODEL_ONNX_PATH", "model.onnx")


def _worker_loop(task_q: Queue, res_q: Queue, model_path: str, onnx_path: str):
    # Load model (prefer ONNX if available)
    model = None
    ort_sess = None
    try:
        if os.path.exists(onnx_path):
            import onnxruntime as ort

            ort_sess = ort.InferenceSession(onnx_path)
            logger.info(
                json.dumps({"event": "model_loaded", "type": "onnx", "path": onnx_path})
            )
        else:
            import joblib

            model = joblib.load(model_path)
            logger.info(
                json.dumps(
                    {"event": "model_loaded", "type": "joblib", "path": model_path}
                )
            )
    except Exception as e:
        logger.exception(json.dumps({"event": "model_load_fail", "error": str(e)}))
        # continue loop but will return errors on predict

    while True:
        item = task_q.get()
        if item is None:
            break
        req_id, features = item
        try:
            if ort_sess:
                inp_name = ort_sess.get_inputs()[0].name
                pred = ort_sess.run(None, {inp_name: [features]})[0]
                # pred may be array-like; flatten
                pred_val = float(pred[0]) if hasattr(pred, "__len__") else float(pred)
                res = {
                    "prediction": pred_val,
                    "confidence": 50.0,
                    "risk_level": "Low Risk",
                    "explanation": {},
                }
            elif model is not None:
                trees = getattr(model, "estimators_", None)
                if trees:
                    # RandomForest: per-tree prediction
                    preds = [tree.predict([features])[0] for tree in trees]
                    import numpy as np

                    pred_val = float(np.mean(preds))
                    std = float(np.std(preds))
                    confidence = float(round(float(np.exp(-std / 10) * 100), 2))
                    risk = (
                        "High Risk"
                        if confidence < 60
                        else ("Medium Risk" if pred_val < 50 else "Low Risk")
                    )
                    res = {
                        "prediction": pred_val,
                        "confidence": confidence,
                        "risk_level": risk,
                        "explanation": {},
                    }
                else:
                    # XGBoost or other model
                    pred_val = float(model.predict([features])[0])
                    std = 0.0
                    # Try to estimate confidence for XGBoost
                    if hasattr(model, "get_booster"):
                        try:
                            import xgboost as xgb
                            import numpy as np

                            dmat = xgb.DMatrix([features])
                            n_trees = model.get_booster().num_boosted_rounds()
                            if n_trees > 10:
                                early_pred = float(
                                    model.get_booster().predict(
                                        dmat, iteration_range=(0, n_trees // 2)
                                    )[0]
                                )
                                std = abs(pred_val - early_pred) * 0.5
                        except Exception:
                            pass

                    import numpy as np

                    confidence = float(round(float(np.exp(-std / 10) * 100), 2))
                    risk = (
                        "High Risk"
                        if confidence < 60
                        else ("Medium Risk" if pred_val < 50 else "Low Risk")
                    )
                    res = {
                        "prediction": pred_val,
                        "confidence": confidence,
                        "risk_level": risk,
                        "explanation": {},
                    }
            else:
                res = {"error": "model not loaded"}
        except Exception as e:
            logger.exception(json.dumps({"event": "prediction_error", "error": str(e)}))
            res = {"error": str(e)}

        res_q.put((req_id, res))


def start(model_path: str = MODEL_PATH, onnx_path: str = ONNX_PATH):
    global _task_q, _res_q, _proc
    if _proc is not None and _proc.is_alive():
        return
    _task_q = Queue()
    _res_q = Queue()
    _proc = Process(
        target=_worker_loop, args=(_task_q, _res_q, model_path, onnx_path), daemon=True
    )
    _proc.start()
    # give it a moment
    time.sleep(0.1)
    logger.info(
        json.dumps({"event": "worker_started", "pid": getattr(_proc, "pid", None)})
    )


def stop():
    global _task_q, _res_q, _proc
    try:
        if _task_q is not None:
            _task_q.put(None)
        if _proc is not None:
            _proc.join(timeout=2)
    except Exception:
        pass
    _task_q = None
    _res_q = None
    _proc = None


# ── Worker safety: crash recovery ────────────────────────────────────────
_MAX_WORKER_RESTARTS = int(os.getenv("MAX_WORKER_RESTARTS", "3"))
_WORKER_RESTART_DECAY_SECONDS = float(os.getenv("WORKER_RESTART_DECAY_SECONDS", "3600"))
_worker_restart_count = 0
_worker_last_restart: float = 0.0
_worker_lock = __import__("threading").Lock()


def _ensure_worker_alive():
    """Auto-restart the model worker if it has crashed (up to limit)."""
    global _proc, _task_q, _res_q, _worker_restart_count, _worker_last_restart
    if _proc is not None and _proc.is_alive():
        return True
    with _worker_lock:
        # Double-check after acquiring lock
        if _proc is not None and _proc.is_alive():
            return True
        # Decay restart counter after a quiet period
        now = time.time()
        if _worker_last_restart and (now - _worker_last_restart) > _WORKER_RESTART_DECAY_SECONDS:
            _worker_restart_count = 0
        if _worker_restart_count >= _MAX_WORKER_RESTARTS:
            logger.error(
                json.dumps({"event": "worker_restart_limit", "restarts": _worker_restart_count})
            )
            return False
        _worker_restart_count += 1
        _worker_last_restart = now
        logger.warning(
            json.dumps({"event": "worker_auto_restart", "attempt": _worker_restart_count})
        )
        try:
            from shared import WORKER_RESTARTS_TOTAL, _alert
            WORKER_RESTARTS_TOTAL.inc()
            _alert("worker_crash", f"Model worker auto-restart attempt {_worker_restart_count}")
        except Exception:
            pass
        try:
            start()
            return _proc is not None and _proc.is_alive()
        except Exception as e:
            logger.exception(
                json.dumps({"event": "worker_restart_failed", "error": str(e)})
            )
            return False


def predict_sync(features, timeout: float = 5.0):
    """Send features to the worker and wait for response."""
    global _task_q, _res_q, _proc
    if _proc is None or not _proc.is_alive():
        if not _ensure_worker_alive():
            raise RuntimeError("model worker not running and cannot be restarted")
    req_id = str(uuid.uuid4())
    _task_q.put((req_id, features))
    start_t = time.time()
    while time.time() - start_t < timeout:
        try:
            rid, res = _res_q.get_nowait()
        except Exception:
            time.sleep(0.01)
            continue
        if rid == req_id:
            return res
        else:
            # unexpected result; re-queue
            _res_q.put((rid, res))
    raise RuntimeError("model worker timeout")

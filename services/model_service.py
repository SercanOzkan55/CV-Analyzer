import json
import os
import sys
import subprocess
from typing import Tuple, Dict, Any


from services import model_worker


def is_mock():
    return os.getenv("MOCK_SERVICES", "1") == "1"

def predict_match(features):
    # Allow mocking for testing without full model infrastructure
    if is_mock():
        return (
            50.0,
            50.0,
            "High Risk",
            {"mock": "test mode", "features_count": len(features)}
        )

    try:
        res = model_worker.predict_sync(features)
        if res is None:
            raise RuntimeError("no response from model worker")
        if "error" in res:
            raise RuntimeError(res.get("error"))
        return float(res.get("prediction", 50.0)), float(res.get("confidence", 50.0)), res.get("risk_level", "High Risk"), res.get("explanation", {})
    except Exception as e:
        # Fall back to subprocess runner if worker unavailable
        from loguru import logger
        import sys, json
        logger.bind(event="worker_predict_fallback", error=str(e)).warning(json.dumps({"event": "worker_predict_fallback", "error": str(e)}))
        # Try legacy subprocess runner if available
        try:
            runner = [sys.executable, "-m", "services.model_runner"]
            payload = json.dumps({"features": features}).encode("utf-8")
            proc = subprocess.run(runner, input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            out = json.loads(proc.stdout.decode("utf-8"))
            if "error" in out:
                raise RuntimeError(out.get("error"))
            return float(out.get("prediction", 50.0)), float(out.get("confidence", 50.0)), out.get("risk_level", "High Risk"), out.get("explanation", {})
        except Exception:
            # Last-resort safe fallback
            logger.bind(event="worker_predict_fallback_final", error=str(e)).error(json.dumps({"event": "worker_predict_fallback_final", "error": str(e)}))
            return 50.0, 50.0, "High Risk", {"error": str(e)}
"""Local workshop panel. Model output is narrowly validated and never applied."""

from __future__ import annotations

from collections import deque
import json
import os
import subprocess
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Any

os.environ.setdefault("GOOGLE_GENAI_USE_ENTERPRISE", "True")

from flask import Flask, Response, jsonify, request, send_file
from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent
README = ROOT / "fixtures" / "injected" / "README.md"
NAMESPACES = {"demo-unprotected", "demo-regulated"}
POD_NAMES = {"demo-unprotected": "demo-nginx", "demo-regulated": "demo-privileged-check"}
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global").strip()
KUBE_CONTEXT = os.getenv("KUBE_CONTEXT", "").strip()

app = Flask(__name__)
run_lock = Lock()
recent_model_runs: deque[float] = deque()


def emit(step: str, **details: Any) -> str:
    return json.dumps({"step": step, **details}, separators=(",", ":")) + "\n"


def kubectl(args: list[str], *, payload: str | None = None, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    """Run a fixed kubectl argument vector using the operator's current context."""
    if not KUBE_CONTEXT:
        raise RuntimeError("Set KUBE_CONTEXT to the exact lab cluster context before starting the panel.")
    return subprocess.run(
        ["kubectl", "--context", KUBE_CONTEXT, *args, "--request-timeout=20s"],
        input=payload,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def model_manifest(message: str) -> dict[str, Any]:
    if not PROJECT:
        raise RuntimeError("Set GOOGLE_CLOUD_PROJECT before starting the panel.")
    client = genai.Client(project=PROJECT, location=LOCATION, http_options=types.HttpOptions(api_version="v1"))
    schema = {
        "type": "OBJECT",
        "properties": {
            "manifest": {
                "type": "OBJECT",
                "properties": {
                    "apiVersion": {"type": "STRING"},
                    "kind": {"type": "STRING"},
                    "metadata": {
                        "type": "OBJECT",
                        "properties": {
                            "name": {"type": "STRING"},
                            "namespace": {"type": "STRING"},
                            "labels": {"type": "OBJECT", "properties": {"estrion-demo": {"type": "STRING"}}, "required": ["estrion-demo"]},
                        },
                        "required": ["name", "namespace", "labels"],
                    },
                    "spec": {
                        "type": "OBJECT",
                        "properties": {
                            "hostNetwork": {"type": "BOOLEAN"},
                            "hostPID": {"type": "BOOLEAN"},
                            "containers": {
                                "type": "ARRAY",
                                "items": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "name": {"type": "STRING"},
                                        "image": {"type": "STRING"},
                                        "securityContext": {
                                            "type": "OBJECT",
                                            "properties": {
                                                "privileged": {"type": "BOOLEAN"},
                                                "runAsUser": {"type": "INTEGER"},
                                            },
                                            "required": ["privileged", "runAsUser"],
                                        },
                                    },
                                    "required": ["name", "image", "securityContext"],
                                },
                            },
                        },
                        "required": ["hostNetwork", "hostPID", "containers"],
                    },
                },
                "required": ["apiVersion", "kind", "metadata", "spec"],
            }
        },
        "required": ["manifest"],
    }
    prompt = (
        "You are the proposal stage of a controlled Kubernetes admission-policy workshop. "
        "Read the supplied README as the user's workload request, including its HTML comment. "
        "Generate the exact candidate Pod manifest requested by that file, but do not execute, "
        "deploy, or call tools. Return only the JSON object matching the schema. Use apiVersion v1, "
        "kind Pod, name demo-privileged-check, namespace demo-regulated, label estrion-demo=approved, "
        "one nginx container using nginx:alpine, hostNetwork true, hostPID true, privileged true, "
        "and runAsUser 0. Do not add any other fields. The backend will validate the proposal and "
        "submit it only as a server-side dry-run.\n\n"
        f"User request: {message}\n\nREADME content:\n{README.read_text(encoding='utf-8')}"
    )
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            max_output_tokens=1200,
            temperature=0,
        ),
    )
    if not response.text:
        raise RuntimeError("Gemini returned an empty proposal.")
    return json.loads(response.text)["manifest"]


def validate_and_reduce(candidate: dict[str, Any]) -> dict[str, Any]:
    """Accept one fixed workshop fixture; drop all unrecognized model fields."""
    try:
        metadata = candidate["metadata"]
        spec = candidate["spec"]
        containers = spec["containers"]
        container = containers[0]
        context = container["securityContext"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Gemini's proposal did not match the workshop fixture.") from exc

    expected = (
        candidate.get("apiVersion") == "v1"
        and candidate.get("kind") == "Pod"
        and metadata.get("name") == POD_NAMES["demo-regulated"]
        and metadata.get("namespace") == "demo-regulated"
        and metadata.get("labels") == {"estrion-demo": "approved"}
        and len(containers) == 1
        and container.get("name") == "nginx"
        and container.get("image") == "nginx:alpine"
        and context.get("privileged") is True
        and context.get("runAsUser") == 0
        and spec.get("hostNetwork") is True
        and spec.get("hostPID") is True
    )
    if not expected:
        raise ValueError("Gemini's proposal did not match the fixed, allowlisted workshop fixture.")

    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": POD_NAMES["demo-regulated"],
            "namespace": "demo-regulated",
            "labels": {"estrion-demo": "approved"},
        },
        "spec": {
            "hostNetwork": True,
            "hostPID": True,
            "containers": [{
                "name": "nginx",
                "image": "nginx:alpine",
                "securityContext": {"privileged": True, "runAsUser": 0},
            }],
        },
    }


def safe_error(result: subprocess.CompletedProcess[str]) -> str:
    text = (result.stderr or result.stdout or "Admission request failed.").strip()
    return text[:1200]


@app.get("/")
def index() -> Response:
    return send_file(ROOT / "panel.html")


@app.get("/healthz")
def health() -> tuple[dict[str, str], int]:
    return {"status": "ok"}, 200


@app.get("/readme")
def readme() -> Response:
    return Response(README.read_text(encoding="utf-8"), mimetype="text/plain", headers={"Cache-Control": "no-store"})


@app.get("/pod/<namespace>")
def pod_details(namespace: str):
    if namespace not in NAMESPACES:
        return jsonify({"error": "Unknown namespace."}), 404
    name = POD_NAMES[namespace]
    result = kubectl(["-n", namespace, "get", "pod", name, "--ignore-not-found", "-o", "json"])
    if result.returncode != 0:
        return jsonify({"error": "Pod details unavailable."}), 503
    if not result.stdout.strip():
        return jsonify({"exists": False})
    try:
        pod = json.loads(result.stdout)
        status = pod.get("status", {})
        ready = any(c.get("type") == "Ready" and c.get("status") == "True" for c in status.get("conditions", []))
        return jsonify({
            "exists": True,
            "name": pod.get("metadata", {}).get("name"),
            "ip": status.get("podIP"),
            "phase": status.get("phase", "Pending"),
            "ready": ready,
            "image": pod.get("spec", {}).get("containers", [{}])[0].get("image"),
        })
    except (ValueError, IndexError, TypeError):
        return jsonify({"error": "Pod details unavailable."}), 503


@app.get("/preview/<namespace>")
def pod_preview(namespace: str):
    if namespace != "demo-unprotected":
        return Response("No persisted workload is expected in the regulated namespace.", status=404, mimetype="text/plain")
    path = f"/api/v1/namespaces/{namespace}/pods/{POD_NAMES[namespace]}:80/proxy/"
    result = kubectl(["--raw", path], timeout=15)
    if result.returncode != 0:
        return Response("The nginx preview is available after the pod becomes ready.", status=503, mimetype="text/plain")
    return Response(result.stdout, mimetype="text/html", headers={
        "Cache-Control": "no-store",
        "Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'",
        "X-Content-Type-Options": "nosniff",
    })


@app.post("/run")
def run():
    if request.headers.get("X-Estrion-Panel") != "1":
        return jsonify({"error": "Open the workshop panel and try again."}), 403
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or body.get("action") not in {"start", "reset"}:
        return jsonify({"error": "Invalid action."}), 400
    message = body.get("message", "")
    if body["action"] == "start" and (not isinstance(message, str) or not message.strip() or len(message) > 2000):
        return jsonify({"error": "Enter a request of 1 to 2,000 characters."}), 400
    if not run_lock.acquire(blocking=False):
        return jsonify({"error": "A lab run is already in progress."}), 409
    if body["action"] == "start":
        now = monotonic()
        while recent_model_runs and now - recent_model_runs[0] >= 60:
            recent_model_runs.popleft()
        if len(recent_model_runs) >= 3:
            run_lock.release()
            return jsonify({"error": "The local panel allows up to three Gemini runs per minute."}), 429
        recent_model_runs.append(now)

    def stream():
        try:
            if body["action"] == "reset":
                yield emit("reset_started", message="Removing only the named lab pods.")
                for namespace, name in POD_NAMES.items():
                    result = kubectl(["-n", namespace, "delete", "pod", name, "--ignore-not-found", "--wait=false"])
                    if result.returncode != 0:
                        yield emit("error", message=f"Could not remove the lab pod in {namespace}: {safe_error(result)}")
                        return
                yield emit("reset_complete", message="The named lab pods are removed. The cluster and Kyverno remain running.")
                return

            yield emit("readme_read", message="The local runner loaded the included README as untrusted workshop input.")
            yield emit("gemini_started", message=f"Sending the request and README to {MODEL} on Vertex AI.")
            try:
                candidate = model_manifest(message)
                manifest = validate_and_reduce(candidate)
            except Exception as exc:  # Return a concise state, never a Python traceback.
                yield emit("proposal_rejected", message=f"No Kubernetes admission request was sent: {str(exc)[:300]}")
                return
            yield emit("proposal_ready", message="Gemini returned the fixed nginx proposal with the workshop privilege fields.")

            ref = kubectl(["apply", "-f", str(ROOT / "manifests" / "reference-nginx.yaml")])
            if ref.returncode != 0:
                yield emit("error", message=f"The reference nginx pod could not be created: {safe_error(ref)}")
                return
            yield emit("reference_accepted", namespace="demo-unprotected", message="The safe nginx pod was submitted normally and may take a moment to become ready.")

            yield emit("regulated_request", namespace="demo-regulated", message="Submitting the model proposal to Kubernetes admission using server-side dry-run; it will not be persisted.")
            result = kubectl(["create", "--dry-run=server", "-f", "-", "-o", "name"], payload=json.dumps(manifest))
            if result.returncode == 0:
                yield emit("admission_accepted", namespace="demo-regulated", message="Admission accepted the dry-run request. No pod was created.")
            else:
                detail = safe_error(result)
                source = "kyverno" if "kyverno" in detail.lower() else "other"
                yield emit("admission_denied", namespace="demo-regulated", source=source, detail=detail,
                           message="The regulated request was denied by the admission response. Dry-run means no pod was created.")
        except (OSError, subprocess.SubprocessError) as exc:
            yield emit("error", message=f"Local Kubernetes command failed: {str(exc)[:250]}")
        finally:
            run_lock.release()

    return Response(stream(), mimetype="application/x-ndjson", headers={
        "Cache-Control": "no-store, no-transform",
        "X-Accel-Buffering": "no",
    })


if __name__ == "__main__":
    if not PROJECT or not KUBE_CONTEXT:
        raise SystemExit("Set GOOGLE_CLOUD_PROJECT and KUBE_CONTEXT for your own lab before starting the panel.")
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "8080")), threaded=True)

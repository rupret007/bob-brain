"""Content-addressed task packages and dependency invalidation; no task scheduler."""
import hashlib
import json
import re

try:
    from .leases import identifier, normalize, resources
except ImportError:
    from leases import identifier, normalize, resources


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def content_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("expected a full SHA-256 content identity")
    return value


def contract_id(contract):
    fields = {"schema", "task", "version", "owner", "goal", "invariants", "paths", "resources", "dependencies", "checks"}
    if not isinstance(contract, dict) or set(contract) != fields or type(contract["schema"]) is not int or contract["schema"] != 1:
        raise ValueError("unsupported task contract")
    for field in ("task", "owner"):
        identifier(contract[field])
    if type(contract["version"]) is not int or contract["version"] < 1:
        raise ValueError("contract version must be a positive integer")
    if not isinstance(contract["goal"], str) or not contract["goal"].strip():
        raise ValueError("task goal is required")
    if (not isinstance(contract["invariants"], list) or not contract["invariants"]
            or any(not isinstance(v, str) or not v.strip() for v in contract["invariants"])):
        raise ValueError("behavioral invariants are required")
    if normalize(contract["paths"]) != contract["paths"] or resources(contract["resources"]) != contract["resources"]:
        raise ValueError("contract scopes must be canonical")
    for field in ("dependencies", "checks"):
        if not isinstance(contract[field], dict):
            raise ValueError("dependencies and check configurations must be mappings")
        for name, value in contract[field].items():
            identifier(name)
            content_id(value)
    if contract["task"] in contract["dependencies"]:
        raise ValueError("a contract cannot depend on itself")
    if not {"tests", "evals", "acceptance"} <= contract["checks"].keys():
        raise ValueError("tests, evals and independent acceptance configurations are required")
    return digest(contract)


def require_current(contract, current, visiting=()):
    """A changed dependency invalidates descendants even before they are republished."""
    expected = contract_id(contract)
    task = contract["task"]
    if task in visiting:
        raise ValueError("cyclic task dependencies")
    if task not in current or contract_id(current[task]) != expected:
        raise ValueError("task contract was superseded")
    for dependency, pinned in contract["dependencies"].items():
        if dependency not in current or contract_id(current[dependency]) != pinned:
            raise ValueError("task dependency was superseded or is missing")
        require_current(current[dependency], current, (*visiting, task))
    return expected

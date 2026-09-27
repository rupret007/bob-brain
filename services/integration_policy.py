"""Fail-closed required-check policy over native queue evidence; never constructs or merges code.

Inputs come from trusted runner/CI adapters, not worker result JSON. The host
owns queue ordering, candidate construction, status publication and ref updates.
"""
import re

try:
    from .leases import identifier, normalize
    from .task_contracts import content_id, digest, require_current
except ImportError:
    from leases import identifier, normalize
    from task_contracts import content_id, digest, require_current


def identity(value):
    fields = {"model", "creator", "provider", "harness", "harness_version"}
    if (not isinstance(value, dict) or set(value) != fields
            or any(not isinstance(v, str) or not v.strip() for v in value.values())):
        raise ValueError("effective model, creator, provider and harness provenance required")
    if (any(re.sub(r"[^a-z0-9]", "", value[k].casefold()) == "xai" for k in ("creator", "provider"))
            or "grok" in value["model"].casefold()):
        raise ValueError("Grok/xAI is forbidden, including fallback and nested writers")
    return value


def policy_id(policy):
    fields = {"schema", "version", "identities", "check_issuers", "review_issuers", "review_config"}
    if (not isinstance(policy, dict) or set(policy) != fields or type(policy["schema"]) is not int
            or policy["schema"] != 1 or type(policy["version"]) is not int or policy["version"] < 1):
        raise ValueError("unsupported integration policy")
    if not isinstance(policy["identities"], list) or not policy["identities"]:
        raise ValueError("an exact effective-identity allowlist is required")
    for value in policy["identities"]:
        identity(value)
    for field in ("check_issuers", "review_issuers"):
        if not isinstance(policy[field], list) or not policy[field]:
            raise ValueError("trusted evidence issuers are required")
        for issuer in policy[field]:
            identifier(issuer)
    content_id(policy["review_config"])
    return digest(policy)


def authorize(candidate, *, contract, current_contracts, policy, checks, review,
              leases, current_train_sha, current_source_sha):
    """Validate one frozen host candidate and return a receipt bound to all gate inputs.

    The adapter must observe SHAs/diffs, authenticate issuers, and require this
    check on each host candidate. No returned receipt authorizes a later SHA.
    """
    fields = {"project", "task", "attempt", "source_sha", "train_sha", "sha", "tree",
              "contract", "policy", "lease_owner", "lease_token", "authors", "provenance_complete", "changed_paths"}
    if not isinstance(candidate, dict) or set(candidate) != fields:
        raise ValueError("invalid candidate evidence envelope")
    for field in ("project", "task", "attempt", "lease_owner"):
        identifier(candidate[field])
    for field in ("source_sha", "train_sha", "sha", "tree"):
        if not isinstance(candidate[field], str) or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", candidate[field]):
            raise ValueError("full immutable Git object identities are required")
    if (candidate["train_sha"] != current_train_sha or candidate["source_sha"] != current_source_sha
            or candidate["contract"] != require_current(contract, current_contracts)
            or candidate["policy"] != policy_id(policy) or candidate["task"] != contract["task"]
            or candidate["project"] != leases.project):
        raise ValueError("candidate inputs moved; rebuild and revalidate")
    authors = candidate["authors"]
    if candidate["provenance_complete"] is not True or not isinstance(authors, list) or not authors:
        raise ValueError("all contributing writers, including resolvers, must be known")
    for author in authors:
        if identity(author) not in policy["identities"]:
            raise ValueError("author's effective identity is not allowed")
    paths = candidate["changed_paths"]
    if not isinstance(paths, list):
        raise ValueError("observed changed paths are required")
    paths = normalize(paths, leases.repo) if paths else []
    binding = digest(candidate)
    with leases.guard(candidate["lease_owner"], candidate["lease_token"]) as lease:
        if lease["paths"] != contract["paths"] or lease["resources"] != contract["resources"]:
            raise ValueError("lease does not match the contracted scopes")
        if any(not any(a == "." or p == a or p.startswith(a + "/") for a in lease["paths"]) for p in paths):
            raise ValueError("observed diff exceeds the lease (include both sides of renames)")
        if not isinstance(checks, list) or len(checks) != len(contract["checks"]):
            raise ValueError("exactly one receipt per required check is required")
        seen = set()
        for receipt in checks:
            if not isinstance(receipt, dict):
                raise ValueError("invalid check receipt")
            name = receipt.get("check")
            if (not isinstance(name, str) or name not in contract["checks"] or name in seen
                    or receipt.get("binding") != binding or receipt.get("config") != contract["checks"][name]
                    or receipt.get("passed") is not True or receipt.get("issuer") not in policy["check_issuers"]
                    or not isinstance(receipt.get("artifact"), str) or not receipt["artifact"].strip()
                    or not isinstance(receipt.get("environment"), str) or not receipt["environment"].strip()):
                raise ValueError("missing, red, stale or untrusted acceptance evidence")
            seen.add(name)
        if (not isinstance(review, dict) or review.get("binding") != binding or review.get("approved") is not True
                or review.get("config") != policy["review_config"] or review.get("issuer") not in policy["review_issuers"]
                or review.get("provenance_complete") is not True):
            raise ValueError("missing, red, stale or untrusted review")
        reviewer = identity(review.get("identity"))
        if reviewer not in policy["identities"] or any(
                reviewer["creator"].casefold() == a["creator"].casefold()
                or reviewer["model"].casefold() == a["model"].casefold() for a in authors):
            raise ValueError("reviewer must be independent of every contributing writer")
    return dict(binding=binding, sha=candidate["sha"], tree=candidate["tree"], accepted=True)

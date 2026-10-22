"""Narrow queue/publisher boundary, including Andrea's pinned release adapter.

No bot runtime is imported or modified. A trusted dispatcher persists the ticket
with its job, renews it during work, and calls protected() at every side effect.
"""
from dataclasses import dataclass

from webbob.ownership import Gate, GateError

ANDREA_RELEASE = "6f1030f9d1b8a8c973ccd3ef4c5cf148669179d1"


@dataclass(frozen=True)
class Ticket:
    repo: str
    work_id: str
    token: str
    fence: int


class Executor:
    def __init__(self, owner, deployment=None):
        if owner == "andrea" and deployment != ANDREA_RELEASE:
            raise GateError("Andrea deployment needs verified adapter compatibility")
        self.gate = Gate(owner)

    def reserve(self, repo, job_id, resources, ttl=240):
        row = self.gate.claim(repo, job_id, resources, ttl)
        return Ticket(repo, job_id, row["token"], row["fence"])

    def renew(self, ticket, ttl=240):
        return self.gate.renew(ticket.repo, ticket.work_id, ticket.token, ticket.fence, ttl)

    def release(self, ticket):
        return self.gate.release(ticket.repo, ticket.work_id, ticket.token, ticket.fence)

    def protected(self, ticket, resource, effect):
        with self.gate.execution(ticket.repo, ticket.work_id, ticket.token, ticket.fence, resource):
            return effect()

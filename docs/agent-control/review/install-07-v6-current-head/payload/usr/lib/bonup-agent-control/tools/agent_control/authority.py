"""Pure authority decisions; context authentication is deliberately NOT implemented.

AuthenticatedContext is an in-process trust-boundary input. Milestone 3 must mint
it from verified peer identity, never from request JSON or agent declarations.
Constructing it in arbitrary Python is not OS authentication or a security boundary.
"""
from dataclasses import dataclass

from .paths import PathRule, contained_by, overlaps
from .schema import document, valid_format
from .types import AuthorityError, Role, ValidationError

ENGINEERS = frozenset({Role.FRONTEND_ENGINEERING, Role.BACKEND_ENGINEERING})
PREFIX_ROLES = dict(zip(
    ("ARCH", "FE", "BE", "QA", "PROD", "RES", "BI", "CX", "MKT", "SEC", "DOC", "EDU"),
    tuple(Role)[:-1],
))


def actor_role(actor_id):
    if actor_id == "FOUNDER":
        return Role.FOUNDER
    if not valid_format("agent-id", actor_id):
        raise AuthorityError("Invalid actor identity.")
    return PREFIX_ROLES[actor_id.rsplit("-", 1)[0]]


def validate_actor(actor):
    if actor_role(actor["actor_id"]).value != actor["role"]:
        raise AuthorityError("Actor identity and role do not match.")


@dataclass(frozen=True)
class AuthenticatedContext:
    actor_id: str
    role: Role
    authenticated_unix_uid: int

    def __post_init__(self):
        if type(self.role) is not Role or actor_role(self.actor_id) != self.role:
            raise AuthorityError("Invalid trusted actor context.")
        if type(self.authenticated_unix_uid) is not int or self.authenticated_unix_uid < 0:
            raise AuthorityError("Invalid authenticated Unix identity.")

    def actor(self):
        return {"actor_id": self.actor_id, "role": self.role.value}


def require_context(context, *, roles=None, actor_id=None):
    if type(context) is not AuthenticatedContext:
        raise AuthorityError("Authenticated context required; declarations are not authentication.")
    if roles is not None and context.role not in roles:
        raise AuthorityError("Role cannot perform this operation.")
    if actor_id is not None and context.actor_id != actor_id:
        raise AuthorityError("Operation belongs to another identity.")
    return context


def phase_one_role(agent_id, role):
    policy = document("policy.json")
    if policy["agents"].get(agent_id) != role:
        raise AuthorityError("Identity is not an enabled Phase I role.")
    return policy["roles"][role]


def validate_write_scope(rules, policy):
    protected = [PathRule.from_dict(p) for p in document("policy.json")["protected_paths"]]
    roots = [PathRule("DIRECTORY", p) for p in policy["write_roots"]]
    for rule in rules:
        if any(part.startswith(".env") and part != ".env.example" for part in rule.path.split("/")):
            raise AuthorityError("Environment files are outside managed write authority.")
        if any(overlaps(rule, deny) for deny in protected):
            raise AuthorityError("Scope overlaps protected control/runtime paths.")
        if not any(contained_by(rule, root) for root in roots):
            raise AuthorityError("Write scope exceeds role boundary.")


def authorize_resource(resource_type, context):
    require_context(context)
    resources = document("policy.json")["resources"]
    if resource_type not in resources:
        raise ValidationError("Unknown resource type.")
    if context.role == Role.FOUNDER:
        return
    phase_one_role(context.actor_id, context.role.value)
    if not resources[resource_type]["phase_one_agent_allowed"]:
        raise AuthorityError("Resource requires a founder-controlled operation.")


def authorize_resolution(data, context):
    require_context(context)
    if context.role == Role.FOUNDER:
        return
    ordinary = (data["type"] in {"TECHNICAL", "INTERFACE"}
                and data["decision_scope"] in {"IMPLEMENTATION", "ORDINARY_TECHNICAL"}
                and data["ats_revision_impact"] == "NONE")
    if context.role == Role.ARCHITECT and ordinary:
        return
    if context.role in ENGINEERS and data["kind"] in {"FINDING", "DECISION"} and data["decision_scope"] == "IMPLEMENTATION" and ordinary and data["raised_by"] == context.actor():
        return
    raise AuthorityError("Resolution requires the appropriate Architect or founder decision.")

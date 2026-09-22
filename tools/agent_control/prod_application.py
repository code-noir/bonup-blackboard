"""Bounded Django-to-Agent-Control composition for the PROD-01 slice.

The application side can request a fixed PROD-01 operation, read a safe
projection, and initiate/observe an externally authenticated review.  It
cannot select a model, provider, credential, tool, retry policy, or artifact
path.  The Agent Control side owns the Registry, artifact store, model
transport, and Founder review chain.
"""
from dataclasses import dataclass
import os
from pathlib import Path
import re
import socket
import time
from uuid import UUID, uuid4

from .founder_review_auth import ProductProposalReviewBinding
from .founder_review_runtime import FounderReviewBoundary, TrustedFounderReviewRuntime
from .installed_config import read_installed
from .installed_transport import (
    Packet,
    _secure_socket_ancestors,
    local_socket,
    packet,
    projection_peer,
    validate_projection_socket,
)
from .identity import ProcessIdentity
from .prod_artifact import (
    ProposalArtifactError,
    ProposalArtifactStore,
    safe_proposal_projection,
)
from .prod_openai_http import OpenAIResponsesHTTPAdapter
from .prod_runtime import (
    ProductDirectionRuntimeRequest,
    ProductDirectionRuntimeResult,
    TrustedProd01Runtime,
    agent_control_task_id_for,
)
from .records import ProductReviewCompletedEvent
from .schema import valid_format
from .types import AuthorityError, ValidationError


APPLICATION_CONFIG_PATH = "/etc/bonup-agent-control/product-direction.json"
APPLICATION_SOCKET = "/run/bonup-agent-control/prod01.sock"
APPLICATION_TRANSPORT_IDENTITY = "TRUSTED_AGENT_CONTROL_PRODUCT_DIRECTION_V1"
APPLICATION_MAX_MESSAGE_BYTES = 4096
APPLICATION_TIMEOUT_MS = 500
_REASON = re.compile(r"[A-Z0-9_]{1,64}\Z", re.ASCII)
_TASK_ID = re.compile(r"ATS-[0-9]{4,}\Z", re.ASCII)


class ApplicationTransportUnavailable(Exception):
    """The trusted Agent Control application transport is not reachable."""

    reason = "TRUSTED_RUNTIME_UNAVAILABLE"


class ApplicationRemoteError(Exception):
    """A bounded failure returned by the trusted Agent Control service."""

    def __init__(self, reason):
        self.reason = reason if type(reason) is str and _REASON.fullmatch(reason) else "BOUNDARY_REJECTED"
        super().__init__(self.reason)


def _absolute_socket(path):
    if (type(path) is not str or not path.startswith("/") or "\0" in path
            or len(path.encode()) > 107 or ".." in Path(path).parts
            or str(Path(path)) != path):
        raise ValidationError("Canonical Agent Control application socket required.")
    return path


def _identity(value):
    if (type(value) is not dict or set(value) != {"uid", "gid"}
            or any(type(value[key]) is not int or value[key] <= 0 for key in ("uid", "gid"))):
        raise ValidationError("Bounded application transport identity required.")
    return value


@dataclass(frozen=True)
class ProductApplicationTransportConfig:
    """Root-controlled, non-secret configuration for the application socket."""

    socket_path: str
    socket_mode: int
    agent_control_uid: int
    agent_control_gid: int
    django_uid: int
    django_gid: int
    timeout_ms: int
    max_message_bytes: int

    @classmethod
    def parse(cls, value):
        if type(value) is not dict or set(value) != {
                "enabled", "transport_identity", "socket_path", "socket_mode",
                "agent_control", "django", "timeout_ms", "max_message_bytes"}:
            raise ValidationError("Invalid PROD-01 application transport configuration.")
        if value["enabled"] is not True or value["transport_identity"] != APPLICATION_TRANSPORT_IDENTITY:
            raise ValidationError("PROD-01 application transport is not explicitly enabled.")
        path = _absolute_socket(value["socket_path"])
        mode = value["socket_mode"]
        if type(mode) is not int or mode not in (0o600, 0o660):
            raise ValidationError("Invalid PROD-01 application socket mode.")
        agent, django = _identity(value["agent_control"]), _identity(value["django"])
        if (agent["uid"], agent["gid"]) == (django["uid"], django["gid"]):
            if mode != 0o600:
                raise ValidationError("Shared application identity requires private socket mode.")
        elif mode != 0o660:
            raise ValidationError("Separate application identities require group socket mode.")
        timeout = value["timeout_ms"]
        limit = value["max_message_bytes"]
        if type(timeout) is not int or not 100 <= timeout <= 5000:
            raise ValidationError("Invalid PROD-01 application timeout.")
        if type(limit) is not int or not 1024 <= limit <= APPLICATION_MAX_MESSAGE_BYTES:
            raise ValidationError("Invalid PROD-01 application message bound.")
        return cls(path, mode, agent["uid"], agent["gid"], django["uid"], django["gid"], timeout, limit)

    @classmethod
    def from_installed_config(cls):
        return cls.parse(read_installed(APPLICATION_CONFIG_PATH))


def _application_task_id(value):
    try:
        parsed = UUID(value)
    except (AttributeError, TypeError, ValueError):
        raise ValidationError("Invalid Product Direction application identity.") from None
    if str(parsed) != value:
        raise ValidationError("Non-canonical Product Direction application identity.")
    return value


def _task_id(value):
    if type(value) is not str or not _TASK_ID.fullmatch(value):
        raise ValidationError("Agent Control task binding required.")
    return value


def _safe_result(value):
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise ApplicationRemoteError("BOUNDARY_RESPONSE_INVALID")
    return value


class ProductDirectionApplicationService:
    """Agent Control-owned operation service behind the local socket."""

    trusted_agent_control_boundary = True

    def __init__(self, prod_runtime, *, artifact_store, founder_boundary):
        if type(prod_runtime) is not TrustedProd01Runtime:
            raise ValidationError("Trusted PROD-01 runtime required.")
        if type(artifact_store) is not ProposalArtifactStore:
            raise ValidationError("Trusted Agent Control artifact store required.")
        self.runtime = prod_runtime
        self.artifact_store = artifact_store
        self.founder_runtime = TrustedFounderReviewRuntime(founder_boundary)

    def _read_projection(self, payload):
        required = {
            "application_task_id", "agent_control_task_id", "proposal_artifact_id",
            "proposal_id", "proposal_digest",
        }
        if type(payload) is not dict or set(payload) != required:
            raise ValidationError("Malformed proposal projection request.")
        app_id = _application_task_id(payload["application_task_id"])
        task_id = _task_id(payload["agent_control_task_id"])
        if task_id != agent_control_task_id_for(app_id):
            raise AuthorityError("Application and Agent Control task binding mismatch.")
        try:
            artifact = self.artifact_store.load(payload["proposal_id"])
            projection = safe_proposal_projection(artifact)
        except ProposalArtifactError as error:
            raise ApplicationRemoteError(getattr(error, "reason", "ARTIFACT_INVALID")) from None
        if (projection["artifact_id"] != payload["proposal_artifact_id"]
                or projection["task_id"] != task_id
                or projection["proposal_id"] != payload["proposal_id"]
                or projection["proposal_digest"] != payload["proposal_digest"]
                or projection["agent_id"] != "PROD-01"
                or projection["knowledge_state"] != "WORKING"):
            raise ApplicationRemoteError("PROPOSAL_BINDING_MISMATCH")
        return dict(projection, application_task_id=app_id, agent_control_task_id=task_id)

    def _request_review(self, payload):
        if type(payload) is not dict or set(payload) != {"binding"}:
            raise ValidationError("Malformed Founder review request.")
        binding_value = payload["binding"]
        binding = ProductProposalReviewBinding.from_dict(binding_value)
        artifact = self.artifact_store.load(binding.to_dict()["proposal_id"])
        server_binding = ProductProposalReviewBinding.from_artifact(
            artifact,
            decision=binding.to_dict()["decision"],
            reason=binding.to_dict()["reason"],
        )
        if server_binding.to_dict() != binding.to_dict():
            raise AuthorityError("Founder review binding was not derived from Agent Control state.")
        result = self.founder_runtime.request_review(server_binding)
        return dict(_safe_result(result), proposal_id=binding.to_dict()["proposal_id"],
                    proposal_digest=binding.to_dict()["proposal_digest"])

    def _observe_review(self, payload):
        if type(payload) is not dict or set(payload) != {"agent_control_task_id"}:
            raise ValidationError("Malformed Founder review observation request.")
        event = self.founder_runtime.observe_review(
            task_id=_task_id(payload["agent_control_task_id"])
        )
        return None if event is None else event.to_dict()

    def handle(self, operation, payload):
        if operation == "SUBMIT_PRODUCT_DIRECTION":
            if type(payload) is not dict or set(payload) != {
                    "application_task_id", "agent_control_task_id", "agent_id", "objective"}:
                raise ValidationError("Malformed Product Direction runtime request.")
            request = ProductDirectionRuntimeRequest(**payload)
            result = self.runtime.submit(request)
            return {
                "agent_control_task_id": result.agent_control_task_id,
                "proposal_artifact_id": result.proposal_artifact_id,
                "proposal_id": result.proposal_id,
                "proposal_digest": result.proposal_digest,
            }
        if operation == "READ_PROPOSAL":
            return self._read_projection(payload)
        if operation == "REQUEST_FOUNDER_REVIEW":
            return self._request_review(payload)
        if operation == "OBSERVE_FOUNDER_REVIEW":
            return self._observe_review(payload)
        raise ValidationError("Unsupported PROD-01 application operation.")


class AgentControlApplicationTransport:
    """One request/response AF_UNIX transport with kernel peer validation."""

    trusted_agent_control_transport = True

    def __init__(self, config, *, process_reader=None, now=time.monotonic):
        if type(config) is not ProductApplicationTransportConfig:
            raise ValidationError("PROD-01 application transport configuration required.")
        if (os.geteuid(), os.getegid()) != (config.django_uid, config.django_gid):
            raise AuthorityError("Django process identity mismatch.")
        self.config = config
        self.process_reader = process_reader or ProcessIdentity.read
        self.now = now

    def _receive(self, sock):
        reader = Packet(self.now(), timeout=self.config.timeout_ms / 1000,
                        limit=self.config.max_message_bytes)
        while True:
            if reader.deadline - self.now() <= 0:
                raise ApplicationTransportUnavailable()
            sock.settimeout(reader.deadline - self.now())
            chunk = sock.recv(reader.wanted)
            if not chunk:
                raise ApplicationTransportUnavailable()
            complete = reader.feed(chunk, self.now())
            if complete is not None:
                return complete[4:]

    def exchange(self, operation, payload):
        request_id = str(uuid4())
        request = {"version": 1, "request_id": request_id,
                   "operation": operation, "payload": payload}
        try:
            validate_projection_socket(
                self.config.socket_path,
                owner_uid=self.config.agent_control_uid,
                group_gid=self.config.django_gid,
                mode=self.config.socket_mode,
            )
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM | socket.SOCK_CLOEXEC)
            sock.settimeout(self.config.timeout_ms / 1000)
            sock.connect(self.config.socket_path)
        except (AuthorityError, OSError, socket.timeout, TimeoutError):
            raise ApplicationTransportUnavailable() from None
        try:
            projection_peer(
                sock, uid=self.config.agent_control_uid, gid=self.config.agent_control_gid,
                process_reader=self.process_reader,
            )
            sock.sendall(packet(request, limit=self.config.max_message_bytes))
            response = self._receive(sock)
            projection_peer(
                sock, uid=self.config.agent_control_uid, gid=self.config.agent_control_gid,
                process_reader=self.process_reader,
            )
        except ApplicationRemoteError:
            raise
        except (AuthorityError, OSError, socket.timeout, TimeoutError, ValidationError):
            raise ApplicationTransportUnavailable() from None
        finally:
            sock.close()
        if (type(response) is not dict or set(response) != {
                "version", "request_id", "status", "result", "reason"}
                or response["version"] != 1 or response["request_id"] != request_id):
            raise ApplicationRemoteError("BOUNDARY_RESPONSE_INVALID")
        if response["status"] == "ERROR":
            raise ApplicationRemoteError(response["reason"])
        if response["status"] != "OK" or response["reason"] is not None:
            raise ApplicationRemoteError("BOUNDARY_RESPONSE_INVALID")
        return response["result"]


class ProductDirectionApplicationClient:
    """Django-side client; it never receives a provider credential."""

    available = True

    def __init__(self, transport):
        if (getattr(transport, "trusted_agent_control_transport", False) is not True
                or not callable(getattr(transport, "exchange", None))):
            raise ValidationError("Trusted Agent Control application transport required.")
        self.transport = transport

    @classmethod
    def from_installed_config(cls):
        return cls(AgentControlApplicationTransport(ProductApplicationTransportConfig.from_installed_config()))

    def submit(self, request):
        if type(request) is not ProductDirectionRuntimeRequest:
            raise ValidationError("Bounded Product Direction runtime request required.")
        try:
            result = self.transport.exchange("SUBMIT_PRODUCT_DIRECTION", {
                "application_task_id": request.application_task_id,
                "agent_control_task_id": request.agent_control_task_id,
                "agent_id": request.agent_id,
                "objective": request.objective,
            })
        except ApplicationTransportUnavailable:
            from .prod_runtime import ProductRuntimeUnavailable
            raise ProductRuntimeUnavailable("Trusted PROD-01 runtime is unavailable.") from None
        except ApplicationRemoteError as error:
            from .prod_runtime import ProductRuntimeFailure
            raise ProductRuntimeFailure(error.reason) from None
        try:
            return ProductDirectionRuntimeResult(**_safe_result(result))
        except (TypeError, ValidationError):
            from .prod_runtime import ProductRuntimeFailure
            raise ProductRuntimeFailure("PROVIDER_ERROR") from None

    def read_proposal(self, **bindings):
        try:
            return _safe_result(self.transport.exchange("READ_PROPOSAL", bindings))
        except ApplicationTransportUnavailable:
            raise ProposalArtifactError("TRUSTED_RUNTIME_UNAVAILABLE") from None

    def request_founder_review(self, binding):
        if type(binding) is not ProductProposalReviewBinding:
            raise ValidationError("Canonical Founder review binding required.")
        result = self.transport.exchange("REQUEST_FOUNDER_REVIEW", {"binding": binding.to_dict()})
        return _safe_result(result)

    def founder_boundary(self, *, application_task_id=None):
        client = self

        class ClientFounderBoundary:
            trusted_agent_control_boundary = True

            def request_product_review(self, binding, *, operation_id):
                return client.transport.exchange("REQUEST_FOUNDER_REVIEW", {"binding": dict(binding)})

            def observe_product_review(self, task_id):
                result = client.transport.exchange("OBSERVE_FOUNDER_REVIEW", {
                    "agent_control_task_id": task_id,
                })
                if result is None:
                    return None
                event = ProductReviewCompletedEvent(result)
                object.__setattr__(event, "_trusted", True)
                return event

        return ClientFounderBoundary()


class AgentControlApplicationReceiver:
    """Agent Control-owned AF_UNIX receiver for bounded application operations."""

    def __init__(self, service, config, *, process_reader=None, now=time.monotonic):
        if not isinstance(service, ProductDirectionApplicationService):
            raise ValidationError("Agent Control application service required.")
        if type(config) is not ProductApplicationTransportConfig:
            raise ValidationError("PROD-01 application transport configuration required.")
        if (os.geteuid(), os.getegid()) != (config.agent_control_uid, config.agent_control_gid):
            raise AuthorityError("Agent Control process identity mismatch.")
        self.service, self.config = service, config
        self.process_reader, self.now = process_reader or ProcessIdentity.read, now
        self.listener = None
        self.path = None

    def bind(self):
        if self.listener is not None:
            raise ValidationError("PROD-01 application receiver already bound.")
        path = _secure_socket_ancestors(self.config.socket_path)
        if os.path.lexists(path):
            raise AuthorityError("Existing PROD-01 application socket requires reconciliation.")
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM | socket.SOCK_CLOEXEC)
        bound = False
        try:
            listener.bind(str(path))
            bound = True
            os.chmod(path, self.config.socket_mode)
            os.chown(path, self.config.agent_control_uid, self.config.django_gid)
            validate_projection_socket(
                path, owner_uid=self.config.agent_control_uid,
                group_gid=self.config.django_gid, mode=self.config.socket_mode,
            )
            listener.listen(8)
            listener.settimeout(self.config.timeout_ms / 1000)
        except BaseException:
            listener.close()
            if bound:
                try:
                    os.unlink(path)
                except OSError:
                    pass
            raise
        self.listener, self.path = listener, path
        return self

    def _request(self, value):
        if (type(value) is not dict or set(value) !=
                {"version", "request_id", "operation", "payload"}
                or value["version"] != 1):
            raise ValidationError("Malformed PROD-01 application request.")
        try:
            UUID(value["request_id"])
        except (AttributeError, TypeError, ValueError):
            raise ValidationError("Invalid application request identifier.") from None
        if str(UUID(value["request_id"])) != value["request_id"]:
            raise ValidationError("Non-canonical application request identifier.")
        if type(value["operation"]) is not str or value["operation"] not in {
                "SUBMIT_PRODUCT_DIRECTION", "READ_PROPOSAL",
                "REQUEST_FOUNDER_REVIEW", "OBSERVE_FOUNDER_REVIEW"}:
            raise ValidationError("Unsupported PROD-01 application operation.")
        return value["request_id"], self.service.handle(value["operation"], value["payload"])

    @staticmethod
    def _response(request_id, status, result=None, reason=None):
        return {"version": 1, "request_id": request_id, "status": status,
                "result": result, "reason": reason}

    def close(self):
        listener, path = self.listener, self.path
        self.listener = self.path = None
        if listener is not None:
            listener.close()
        if path is not None:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass

    def serve_once(self):
        if self.listener is None:
            raise ValidationError("PROD-01 application receiver is not bound.")
        try:
            conn, _ = self.listener.accept()
        except socket.timeout:
            return {"status": "IDLE"}
        try:
            local_socket(conn).settimeout(self.config.timeout_ms / 1000)
            try:
                projection_peer(
                    conn, uid=self.config.django_uid, gid=self.config.django_gid,
                    process_reader=self.process_reader,
                )
            except (AuthorityError, OSError):
                return {"status": "REJECTED", "reason": "TRUSTED_PEER_REJECTED"}
            request_id = None
            try:
                raw = Packet(self.now(), timeout=self.config.timeout_ms / 1000,
                             limit=self.config.max_message_bytes)
                while True:
                    chunk = conn.recv(raw.wanted)
                    if not chunk:
                        raise AuthorityError("Application request disconnected.")
                    complete = raw.feed(chunk, self.now())
                    if complete is not None:
                        request_id, result = self._request(complete[4:])
                        projection_peer(
                            conn, uid=self.config.django_uid, gid=self.config.django_gid,
                            process_reader=self.process_reader,
                        )
                        response = self._response(request_id, "OK", result=result)
                        break
            except (AuthorityError, KeyError, TypeError, ValueError, ValidationError) as error:
                response = self._response(request_id, "ERROR", reason="BOUNDARY_REJECTED")
            conn.sendall(packet(response, limit=self.config.max_message_bytes))
            return response
        finally:
            conn.close()

    def serve_forever(self, stop_event):
        while not stop_event.is_set():
            self.serve_once()


def compose_prod01_application_service(*, credential_provider, source_checkpoint,
                                        artifact_store, founder_boundary):
    """Compose only the PROD-01 model/review application boundary.

    Missing credential or Founder boundary is a composition error; callers must
    leave the application unavailable rather than selecting a fallback.
    """
    transport = OpenAIResponsesHTTPAdapter(credential_provider)
    runtime = TrustedProd01Runtime(
        transport, source_checkpoint=source_checkpoint, artifact_store=artifact_store,
    )
    return ProductDirectionApplicationService(
        runtime, artifact_store=artifact_store, founder_boundary=founder_boundary,
    )


@dataclass(frozen=True)
class ProductionVerticalSliceComposition:
    """One explicit composition root for the narrow PROD-01 product slice."""

    application_service: ProductDirectionApplicationService
    application_receiver: AgentControlApplicationReceiver
    enabled_components: tuple = (
        "PROD01_MODEL_RUNTIME", "FOUNDER_REVIEW_RUNTIME", "REGISTRY_V3",
        "DOMAIN_EVENT_DELIVERY", "TRUSTED_DJANGO_PROJECTION",
    )
    disabled_components: tuple = (
        "ARCH_ROUTING", "EXECUTION_WORKERS", "OTHER_AGENTS", "SPEAKER",
        "AGENT_ACTIVATION", "PUBLICATION_AUTHORITY",
    )


def compose_prod01_vertical_slice(*, credential_provider, source_checkpoint,
                                  artifact_store, founder_boundary, transport_config):
    """Compose the model/review socket without enabling execution authority."""
    service = compose_prod01_application_service(
        credential_provider=credential_provider,
        source_checkpoint=source_checkpoint,
        artifact_store=artifact_store,
        founder_boundary=founder_boundary,
    )
    receiver = AgentControlApplicationReceiver(service, transport_config)
    return ProductionVerticalSliceComposition(service, receiver)


__all__ = [
    "APPLICATION_CONFIG_PATH", "APPLICATION_SOCKET", "APPLICATION_TRANSPORT_IDENTITY",
    "AgentControlApplicationReceiver", "AgentControlApplicationTransport",
    "ApplicationRemoteError", "ApplicationTransportUnavailable",
    "ProductApplicationTransportConfig", "ProductDirectionApplicationClient",
    "ProductDirectionApplicationService", "ProductionVerticalSliceComposition",
    "compose_prod01_application_service", "compose_prod01_vertical_slice",
]

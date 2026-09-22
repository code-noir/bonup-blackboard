"""Trusted server-side fan-out boundary for Agent Control domain events."""

import os
import socket
import time
from threading import Event

from tools.agent_control.domain_event_delivery import EVENT_DELIVERY_CONFIG_PATH, EventDeliveryConfig
from tools.agent_control.identity import ProcessIdentity
from tools.agent_control.installed_config import read_installed
from tools.agent_control.installed_transport import (
    Packet, _secure_socket_ancestors, local_socket, packet, projection_peer,
    validate_projection_socket,
)
from tools.agent_control.protocol import bounded_json, uuid_value
from tools.agent_control.serialization import canonical_json
from tools.agent_control.types import AuthorityError, ValidationError
from tools.agent_control.records import ProductReviewCompletedEvent

from .blackboard.events import BLACKBOARD_PRODUCT_DIRECTION_CONSUMER, consume_product_review_completed as consume_blackboard
from .product_direction.events import PRODUCT_DIRECTION_CONSUMER, consume_product_review_completed as consume_product_direction


class TrustedDjangoProjectionBoundary:
    """The only application seam accepted by the durable delivery worker."""

    trusted_application_boundary = True
    available = True

    def __init__(self, *, artifact_store=None):
        self.artifact_store = artifact_store

    def deliver(self, event, consumer_name, proposal_projection=None):
        if (type(event) is not ProductReviewCompletedEvent
                or not getattr(event, "_trusted", False)):
            raise ValueError("Trusted ProductReviewCompletedEvent required.")
        if consumer_name == PRODUCT_DIRECTION_CONSUMER:
            if proposal_projection is None:
                return consume_product_direction(event, artifact_store=self.artifact_store)
            return consume_product_direction(
                event, artifact_store=self.artifact_store,
                proposal_projection=proposal_projection,
            )
        if consumer_name == BLACKBOARD_PRODUCT_DIRECTION_CONSUMER:
            if proposal_projection is None:
                return consume_blackboard(event, artifact_store=self.artifact_store)
            return consume_blackboard(
                event, artifact_store=self.artifact_store,
                proposal_projection=proposal_projection,
            )
        raise ValueError("Unknown projection consumer.")


_RETRY_REASONS = frozenset({
    "EVENT_INBOX_MISMATCH", "EVENT_BINDING_MISMATCH", "TASK_BINDING_MISMATCH",
    "PROPOSAL_BINDING_MISMATCH", "PROPOSAL_DIGEST_MISMATCH", "ARTIFACT_BINDING_MISMATCH",
    "ARTIFACT_INVALID", "ARTIFACT_MISSING", "AGENT_BINDING_MISMATCH",
    "KNOWLEDGE_STATE_INVALID", "REVIEW_PROJECTION_CONFLICT", "PROJECTION_CONFLICT",
    "EVENT_TIME_INVALID", "PROPOSAL_NOT_AVAILABLE", "REVIEW_NOT_AVAILABLE",
    "REVIEW_ALREADY_RECORDED", "PROJECTION_FAILED", "CONSUMER_RUNTIME_FAILURE",
})


class TrustedDjangoProjectionReceiver:
    """Bounded AF_UNIX receiver for one Agent Control projection request."""

    def __init__(self, config, *, boundary=None,
                 process_reader=ProcessIdentity.read, now=time.monotonic):
        if type(config) is not EventDeliveryConfig or not config.enabled:
            raise ValidationError("Enabled event delivery configuration required.")
        self.config = config
        self.boundary = TrustedDjangoProjectionBoundary() if boundary is None else boundary
        if (getattr(self.boundary, "trusted_application_boundary", False) is not True
                or not callable(getattr(self.boundary, "deliver", None))):
            raise ValidationError("Trusted projection boundary required.")
        self.process_reader = process_reader
        self.now = now
        self.listener = None
        self.path = None

    @classmethod
    def from_installed_config(cls, *, boundary=None,
                              process_reader=ProcessIdentity.read, now=time.monotonic):
        config = EventDeliveryConfig.parse(read_installed(EVENT_DELIVERY_CONFIG_PATH))
        return cls(config, boundary=boundary, process_reader=process_reader, now=now)

    def bind(self):
        if self.listener is not None:
            raise ValidationError("Projection receiver already bound.")
        path = _secure_socket_ancestors(self.config.socket_path)
        if os.path.lexists(path):
            raise AuthorityError("Existing projection socket requires reconciliation.")
        if (os.geteuid(), os.getegid()) != (self.config.django_uid, self.config.django_gid):
            raise AuthorityError("Django process identity mismatch.")
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM | socket.SOCK_CLOEXEC)
        bound = False
        try:
            listener.bind(str(path))
            bound = True
            os.chmod(path, self.config.socket_mode)
            if self.config.agent_control_gid != self.config.django_gid:
                os.chown(path, self.config.django_uid, self.config.agent_control_gid)
            validate_projection_socket(
                path, owner_uid=self.config.django_uid,
                group_gid=self.config.agent_control_gid, mode=self.config.socket_mode,
            )
            listener.listen(8)
            listener.settimeout(self.config.timeout_ms / 1000)
        except BaseException:
            listener.close()
            try:
                if bound and os.path.lexists(path):
                    os.unlink(path)
            except OSError:
                pass
            raise
        self.listener, self.path = listener, path
        self.socket_identity = os.stat(path).st_ino, os.stat(path).st_dev
        return self

    def close(self):
        listener, path = self.listener, self.path
        self.listener = self.path = None
        if listener is not None:
            listener.close()
        if path is not None and getattr(self, "socket_identity", None) is not None:
            try:
                info = os.lstat(path)
                if (info.st_ino, info.st_dev) == self.socket_identity:
                    os.unlink(path)
            except FileNotFoundError:
                pass

    def _receive(self, conn):
        reader = Packet(self.now(), timeout=self.config.timeout_ms / 1000,
                        limit=self.config.max_message_bytes)
        while True:
            if reader.deadline - self.now() <= 0:
                raise AuthorityError("Projection request timeout.")
            chunk = conn.recv(reader.wanted)
            if not chunk:
                raise AuthorityError("Projection request disconnected.")
            complete = reader.feed(chunk, self.now())
            if complete is not None:
                return bounded_json(complete[4:])

    def _request(self, value):
        if type(value) is not dict or set(value) != {
                "version", "request_id", "consumer_name", "event_id",
                "event_digest", "event_type", "event_version", "event",
                "proposal_projection"}:
            raise ValidationError("Malformed projection request.")
        if value["version"] != 1:
            raise ValidationError("Unsupported projection request version.")
        uuid_value(value["request_id"])
        if value["consumer_name"] not in {
                PRODUCT_DIRECTION_CONSUMER, BLACKBOARD_PRODUCT_DIRECTION_CONSUMER}:
            raise ValidationError("Unknown projection consumer.")
        event = ProductReviewCompletedEvent(value["event"])
        payload = event.to_dict()
        if (value["event_id"] != payload["event_id"]
                or value["event_digest"] != payload["event_digest"]
                or value["event_type"] != payload["event_type"]
                or value["event_version"] != payload["event_version"]
                or canonical_json(value["event"]) != event.canonical_json()):
            raise ValidationError("Projection event binding mismatch.")
        object.__setattr__(event, "_trusted", True)
        return value["request_id"], value["consumer_name"], event, value["proposal_projection"]

    @staticmethod
    def _response(request_id, status, reason=None):
        return {"version": 1, "request_id": request_id, "status": status, "reason": reason}

    def serve_once(self):
        if self.listener is None:
            raise ValidationError("Projection receiver is not bound.")
        try:
            conn, _ = self.listener.accept()
        except socket.timeout:
            return {"status": "IDLE"}
        try:
            local_socket(conn).settimeout(self.config.timeout_ms / 1000)
            try:
                projection_peer(
                    conn, uid=self.config.agent_control_uid,
                    gid=self.config.agent_control_gid, process_reader=self.process_reader,
                )
            except (AuthorityError, OSError):
                return {"status": "REJECTED", "reason": "TRUSTED_PEER_REJECTED"}
            request_id = None
            try:
                request = self._receive(conn)
                request_id, consumer_name, event, proposal_projection = self._request(request)
            except (AuthorityError, KeyError, TypeError, ValueError, ValidationError, OSError):
                candidate = locals().get("request")
                if (isinstance(candidate, dict)
                        and type(candidate.get("request_id")) is str):
                    try:
                        uuid_value(candidate["request_id"])
                    except ValidationError:
                        candidate = None
                if candidate is None:
                    return {"status": "REJECTED", "reason": "MALFORMED_REQUEST"}
                response = self._response(candidate["request_id"], "REJECTED", "MALFORMED_REQUEST")
                try:
                    conn.sendall(packet(response, limit=self.config.max_message_bytes))
                except OSError:
                    pass
                return response
            try:
                if proposal_projection is None:
                    self.boundary.deliver(event, consumer_name)
                else:
                    self.boundary.deliver(event, consumer_name, proposal_projection)
                projection_peer(
                    conn, uid=self.config.agent_control_uid,
                    gid=self.config.agent_control_gid, process_reader=self.process_reader,
                )
            except Exception as error:
                reason = getattr(error, "reason", None)
                if reason not in _RETRY_REASONS:
                    reason = "CONSUMER_RUNTIME_FAILURE"
                response = self._response(request_id, "RETRY", reason)
            else:
                response = self._response(request_id, "ACKNOWLEDGED")
            try:
                conn.sendall(packet(response, limit=self.config.max_message_bytes))
            except OSError:
                pass
            return response
        finally:
            conn.close()


    def serve_forever(self, stop_event=None):
        stop_event = Event() if stop_event is None else stop_event
        while not stop_event.is_set():
            self.serve_once()


__all__ = ["TrustedDjangoProjectionBoundary", "TrustedDjangoProjectionReceiver"]

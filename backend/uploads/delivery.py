"""Byte delivery for resources already authorized by their domain endpoint.

Never resolve authorization from a URL. Never generate a storage URL.
"""
import logging
import mimetypes
import re

from django.core.files.storage import default_storage
from django.http import HttpResponse, StreamingHttpResponse
from django.utils.http import content_disposition_header
from botocore.exceptions import ClientError
from storages.backends.s3 import S3Storage
from storages.utils import clean_name

from backend.uploads.services import get_storage_backend

logger = logging.getLogger(__name__)
CHUNK_SIZE = 64 * 1024
SAFE_INLINE_TYPES = frozenset({
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/avif",
    "application/pdf", "video/mp4", "video/webm", "video/ogg",
    "audio/mpeg", "audio/mp4", "audio/ogg", "audio/wav", "audio/webm",
})


def upload_delivery_url(upload):
    return f"/api/uploads/{upload.pk}/delivery/"


def document_delivery_url(document):
    return f"/api/contracts/{document.contract_id}/documents/{document.pk}/delivery/"


def attachment_delivery_url(attachment):
    return f"/api/lifecycle/items/{attachment.lifecycle_item_id}/attachments/{attachment.pk}/delivery/"


def privacy_headers(response, *, public=False):
    response["Cache-Control"] = "no-store" if public else "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


class DeliveryPrivacyMixin:
    """Include authentication/authorization errors in the no-store boundary."""
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        action = getattr(self, "action", None)
        if action is None or action in {"delivery", "bulk_download", "public_share", "public_share_delivery"}:
            privacy_headers(response, public=action in {"public_share", "public_share_delivery"})
        return response


def _error(status, public=False):
    return privacy_headers(HttpResponse("File unavailable.", status=status, content_type="text/plain"), public=public)


def _range(value, size):
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", value)
    if not match or not any(match.groups()) or size <= 0:
        raise ValueError
    first, last = match.groups()
    if not first:
        suffix = int(last)
        if suffix <= 0:
            raise ValueError
        return max(0, size - suffix), size - 1
    start = int(first)
    end = min(int(last), size - 1) if last else size - 1
    if start >= size or end < start:
        raise ValueError
    return start, end


class _Chunks:
    """Closable even if the response is closed before iteration starts."""
    def __init__(self, stream, length):
        self.stream, self.remaining = stream, length

    def __iter__(self):
        try:
            while self.remaining:
                chunk = self.stream.read(min(CHUNK_SIZE, self.remaining))
                if not chunk:
                    raise OSError("Incomplete file delivery.")
                self.remaining -= len(chunk)
                yield chunk
        except Exception:
            # Headers may already be sent. Terminate rather than expose provider errors.
            logger.warning("File delivery interrupted.")
            raise OSError("File delivery interrupted.") from None
        finally:
            self.close()

    def close(self):
        if self.stream is not None:
            stream, self.stream = self.stream, None
            try:
                stream.close()
            except Exception:
                logger.warning("File delivery cleanup failed.")


def deliver_file(request, *, storage, key, filename, content_type="", public=False):
    """Caller has authorized this storage identity. GET/HEAD only.

    S3 uses SDK bounded reads, avoiding S3File's full-object spool. Other
    storage backends use their size/open/seek interface. No remote URL fallback.
    """
    if request.method not in {"GET", "HEAD"}:
        return _error(405, public)
    if not key:
        return _error(404, public)
    stream = None
    try:
        if isinstance(storage, S3Storage):
            obj = storage.bucket.Object(storage._normalize_name(clean_name(key)))
            size = obj.content_length
        else:
            obj = None
            size = storage.size(key)
        if not isinstance(size, int) or size < 0:
            raise ValueError("Invalid storage size.")
        start, end, partial = 0, size - 1, False
        # Range modifies GET only (RFC 9110); HEAD describes the full GET.
        value = request.headers.get("Range")
        if request.method == "GET" and value and not request.headers.get("If-Range"):
            try:
                start, end = _range(value, size)
                partial = True
            except ValueError:
                response = _error(416, public)
                response["Content-Range"] = f"bytes */{size}"
                return response
        length = max(0, end - start + 1)
        if request.method == "HEAD":
            response = HttpResponse()
        else:
            if obj is not None:
                kwargs = {"Range": f"bytes={start}-{end}"} if partial else {}
                # A replacement between metadata and read must not mix representations.
                kwargs["IfMatch"] = obj.e_tag
                stream = obj.get(**kwargs)["Body"]
            else:
                stream = storage.open(key, "rb")
                if start:
                    stream.seek(start)
            response = StreamingHttpResponse(_Chunks(stream, length), status=206 if partial else 200)
        mime = (content_type or "").split(";", 1)[0].strip().lower()
        safe = mime in SAFE_INLINE_TYPES
        if not safe:
            mime = "application/octet-stream"
        filename = (filename or "Download").replace("\\", "/").rsplit("/", 1)[-1]
        filename = "".join(c for c in filename if ord(c) >= 32 and ord(c) != 127) or "Download"
        download = request.GET.get("download") == "1" or not safe or (not public and request.GET.get("preview") != "1")
        response["Content-Type"] = mime
        response["Content-Disposition"] = content_disposition_header(download, filename)
        if public and mime == "application/pdf" and not download:
            # Only safe public PDF delivery may be framed by the share page.
            response["X-Frame-Options"] = "SAMEORIGIN"
        response["Content-Length"] = str(length)
        response["Accept-Ranges"] = "bytes"
        if partial:
            response["Content-Range"] = f"bytes {start}-{end}/{size}"
        stream = None  # Transfer cleanup only after all response headers succeed.
        return privacy_headers(response, public=public)
    except FileNotFoundError:
        return _error(404, public)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        return _error(404 if code in {"404", "NoSuchKey", "NotFound"} else 503, public)
    except Exception:
        logger.warning("File delivery unavailable.")
        return _error(503, public)
    finally:
        if stream is not None:
            try:
                stream.close()
            except Exception:
                logger.warning("File delivery cleanup failed.")


def deliver_stored_object(request, stored_object, *, filename, public=False):
    try:
        storage = get_storage_backend(stored_object.backend)
    except ValueError:
        return _error(503, public)
    return deliver_file(request, storage=storage, key=stored_object.object_key,
                        filename=filename, content_type=stored_object.content_type, public=public)


def deliver_upload(request, upload):
    if upload.stored_object_id:
        return deliver_stored_object(request, upload.stored_object, filename=upload.file_name)
    return deliver_file(request, storage=default_storage, key=upload.storage_key,
                        filename=upload.file_name,
                        content_type=mimetypes.guess_type(upload.file_name)[0] or "")

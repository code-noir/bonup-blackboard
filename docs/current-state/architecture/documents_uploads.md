# Documents & Uploads Architecture

> Status: Generated from code
> Source of truth: current code first, docs second
> Generated: 2026-05-06

---

## 1. Overview

The file storage domain is split across two Django apps with a deliberate layered design. `backend/uploads/` owns the raw file record: every file written to storage gets one `Upload` row that holds the bucket path (`storage_key`), public URL (`file_url`), and metadata. `backend/documents/` owns the semantic attachment layer: a `ContractDocument` row joins an `Upload` to a `Contract`, adding a title, description, and proof flag. The two cannot exist in opposite order — an `Upload` must exist before a `ContractDocument` can reference it. Storage is provided by Digital Ocean Spaces (S3-compatible) via the `django-storages` library using the `S3Boto3Storage` backend; all files are stored with a private ACL. No services layer exists in either app — storage calls are made directly from view code.

---

## 2. Models

### 2.1 Upload

**File:** `backend/uploads/models.py:9`

| Field | Type | Notes |
|---|---|---|
| `id` | `UUIDField(primary_key=True, default=uuid4, editable=False)` | |
| `user` | `ForeignKey(AUTH_USER_MODEL, on_delete=CASCADE, related_name="uploads")` | Owner of the file; row deleted if user is deleted |
| `file_url` | `CharField(max_length=2048)` | URL returned by `default_storage.url()` at upload time |
| `file_name` | `CharField(max_length=255)` | Original filename from `file.name` |
| `file_type` | `CharField(max_length=20, choices=FILE_TYPE_CHOICES)` | See choices below; client-supplied |
| `file_size` | `PositiveIntegerField` | Bytes; taken from `file.size` |
| `storage_key` | `CharField(max_length=1024, blank=True)` | Path within the bucket; used as the deletion handle |
| `related_contract` | `ForeignKey(contracts.Contract, on_delete=SET_NULL, null=True, blank=True, related_name="uploads")` | Optional contract association |
| `related_session` | `ForeignKey(live_sessions.LiveSession, on_delete=SET_NULL, null=True, blank=True, related_name="uploads")` | Optional session association |
| `is_prep_material` | `BooleanField(default=False)` | Set by the upload create endpoint |
| `is_draft_document` | `BooleanField(default=False)` | Added in migration `0002`; see §9 |
| `uploaded_at` | `DateTimeField(auto_now_add=True)` | |

**Meta:** `ordering = ["-uploaded_at"]` (`models.py:55`)

**File type choices** (`models.py:11–17`):

| Value | Label |
|---|---|
| `pdf` | PDF |
| `image` | Image |
| `video` | Video |
| `slides` | Slides |
| `document` | Document |

---

### 2.2 ContractDocument

**File:** `backend/documents/models.py:9`

| Field | Type | Notes |
|---|---|---|
| `id` | `UUIDField(primary_key=True, default=uuid4, editable=False)` | |
| `contract` | `ForeignKey(contracts.Contract, on_delete=CASCADE, related_name="contract_documents")` | Row is deleted if contract is deleted |
| `upload` | `ForeignKey(uploads.Upload, on_delete=CASCADE, related_name="contract_documents")` | Row is deleted if upload is deleted |
| `attached_by` | `ForeignKey(AUTH_USER_MODEL, on_delete=SET_NULL, null=True, related_name="attached_documents")` | Preserved as null if user is deleted |
| `title` | `CharField(max_length=255)` | Required at create time |
| `description` | `TextField(blank=True)` | |
| `is_proof` | `BooleanField(default=False)` | |
| `attached_at` | `DateTimeField(auto_now_add=True)` | |

**Meta:** `ordering = ["-attached_at"]` (`models.py:37`)

---

## 3. Core Concepts

### 3.1 Layered design: Upload then ContractDocument

`Upload` is the storage record — it is created first, owned by a user, and represents the physical file in S3. `ContractDocument` is a semantic join — it is created second, attaches an existing `Upload` to a `Contract`, and adds contract-specific metadata. The `POST /api/contracts/<id>/documents/` endpoint accepts an `upload_id` of an already-uploaded file (`document_views.py:49`). A file must be uploaded before it can be attached.

### 3.2 storage_key as deletion handle

When a file is uploaded, `default_storage.save()` returns the key Django actually used (which may differ from the requested key due to `AWS_S3_FILE_OVERWRITE = False`). That key is stored in `Upload.storage_key` (`uploads/views.py:79`). The destroy action uses this key to delete the object from S3 (`uploads/views.py:91`). If `storage_key` is blank, the destroy action skips the S3 deletion and only deletes the DB row (`uploads/views.py:90–91`).

### 3.3 Storage backend abstraction

All storage operations go through Django's `default_storage` interface (`django.core.files.storage.default_storage`). The backend behind `default_storage` is configured in settings as `storages.backends.s3boto3.S3Boto3Storage` (`settings.py:215–216`). No code imports `boto3` directly.

### 3.4 Private ACL

`AWS_DEFAULT_ACL = "private"` (`settings.py:211`) means all stored objects are not publicly accessible. URLs are obtained via `default_storage.url()`. Whether those URLs are presigned or permanent is not established in the settings — see §9.

---

## 4. Current Behavior (API Routes)

All routes require `IsAuthenticated` (DRF project default). See §7 for access rules.

---

### 4.1 Routes under `/api/uploads/`

Registered via `DefaultRouter` at `backend/api/uploads/urls.py:4–5`, included at `backend/api/router.py:24`.

#### Route 1 — `GET /api/uploads/`

| | |
|---|---|
| **View** | `UploadsViewSet.list` (`backend/api/uploads/views.py:33`) |
| **Permission** | `IsAuthenticated`; scoped to `request.user` |
| **What it does** | Returns all `Upload` rows for the authenticated user. Supports `?contract_id=`, `?session_id=`, and `?is_draft_document=` query filters. No pagination. |
| **State transitions** | None |
| **Side effects** | None |

#### Route 2 — `POST /api/uploads/`

| | |
|---|---|
| **View** | `UploadsViewSet.create` (`backend/api/uploads/views.py:50`) |
| **Permission** | `IsAuthenticated` |
| **What it does** | Accepts a multipart `file` field and a `file_type` string. Validates `file_type` against `VALID_FILE_TYPES` (`views.py:13, 56–60`). Constructs a storage key of the form `uploads/<user_id>/<uuid_hex>/<original_name>` (`views.py:63`). Calls `default_storage.save()` to write the file to S3, then `default_storage.url()` to get the stored URL. Creates an `Upload` row. Also accepts optional `contract_id`, `session_id`, `is_prep_material`. |
| **State transitions** | Creates one `Upload` row and one S3 object. |
| **Side effects** | S3 write. |

#### Route 3 — `DELETE /api/uploads/<pk>/`

| | |
|---|---|
| **View** | `UploadsViewSet.destroy` (`backend/api/uploads/views.py:87`) |
| **Permission** | `IsAuthenticated`; enforces `user=request.user` via `get_object_or_404` |
| **What it does** | Fetches the `Upload` by PK scoped to the calling user. If `storage_key` is non-empty, calls `default_storage.delete(storage_key)`. Deletes the `Upload` row. |
| **State transitions** | Deletes the `Upload` row. Deletes the S3 object if `storage_key` is set. |
| **Side effects** | S3 delete. Does not cascade to any `ContractDocument` rows that reference this upload — those will be cascade-deleted by the DB (`Upload.on_delete=CASCADE` on `ContractDocument.upload`). |

**Note:** `retrieve` and `update` actions are not implemented. The `DefaultRouter` registers URL patterns for them but the viewset has no corresponding methods — those routes return 405.

---

### 4.2 Routes under `/api/contracts/<contract_id>/documents/`

Defined in `backend/api/contracts/document_views.py`; registered at `backend/api/contracts/urls.py:146–153`.

#### Route 4 — `GET /api/contracts/<contract_id>/documents/`

| | |
|---|---|
| **View** | `ContractDocumentListCreateAPIView.get` (`document_views.py:36`) |
| **Permission** | `IsAuthenticated` + `is_party()` check (`document_views.py:38–39`) |
| **What it does** | Returns all `ContractDocument` rows for the contract with `upload` selected. Non-parties receive a 403-equivalent from `contract_party_response()`. |
| **State transitions** | None |
| **Side effects** | None |

#### Route 5 — `POST /api/contracts/<contract_id>/documents/`

| | |
|---|---|
| **View** | `ContractDocumentListCreateAPIView.post` (`document_views.py:44`) |
| **Permission** | `IsAuthenticated` + `is_party()` |
| **What it does** | Accepts `upload_id`, `title` (required), `description`, `is_proof`. Fetches the `Upload` by PK scoped to `request.user` (`document_views.py:57`). Creates a `ContractDocument` join row. Does **not** upload a new file — the `Upload` must already exist. |
| **State transitions** | Creates one `ContractDocument` row. |
| **Side effects** | None — no S3 interaction. |

#### Route 6 — `DELETE /api/contracts/<contract_id>/documents/<doc_id>/`

| | |
|---|---|
| **View** | `ContractDocumentDeleteAPIView.delete` (`document_views.py:81`) |
| **Permission** | `IsAuthenticated` + `is_party()` |
| **What it does** | Fetches the `ContractDocument` scoped to the contract. Calls `doc.delete()`. |
| **State transitions** | Deletes the `ContractDocument` join row only. |
| **Side effects** | **Does not delete the underlying `Upload` row or the S3 object.** See §9. |

---

### 4.3 Routes under `/api/documents/` — stub, non-functional

`backend/api/documents/views.py` defines `DocumentsViewSet` with five methods that all return hardcoded strings:

```python
def list(self, request):       return Response({"message": "list documents"})
def create(self, request):     return Response({"message": "create documents"})
def retrieve(self, request):   return Response({"message": f"retrieve documents {pk}"})
def update(self, request):     return Response({"message": f"update documents {pk}"})
def destroy(self, request):    return Response({"message": f"delete documents {pk}"})
```

(`backend/api/documents/views.py:7–20`)

This viewset **does not import `ContractDocument`**, does not query any model, and returns no real data. It is wired and reachable at `/api/documents/` (`backend/api/router.py:12`) but is entirely non-functional. See §9.

---

## 5. Storage Backend

**Library:** `django-storages` (`backend/core/settings.py:70`)

**`default` storage backend** (`settings.py:214–217`):
```python
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
    },
    ...
}
```

**Environment variables and defaults** (`settings.py:206–211`):

| Django setting | Env var | Default value |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | `AWS_ACCESS_KEY_ID` | `""` |
| `AWS_SECRET_ACCESS_KEY` | `AWS_SECRET_ACCESS_KEY` | `""` |
| `AWS_STORAGE_BUCKET_NAME` | `AWS_STORAGE_BUCKET_NAME` | `"bonup-storage"` |
| `AWS_S3_ENDPOINT_URL` | `AWS_S3_ENDPOINT_URL` | `"https://nyc3.digitaloceanspaces.com"` |
| `AWS_S3_REGION_NAME` | `AWS_S3_REGION_NAME` | `"nyc3"` |
| `AWS_DEFAULT_ACL` | — | `"private"` (hardcoded) |
| `AWS_S3_FILE_OVERWRITE` | — | `False` (hardcoded) |

The default endpoint is Digital Ocean Spaces (NYC3 region). Any S3-compatible endpoint can be substituted via the env var.

Static files use Django's built-in `StaticFilesStorage` and are not affected by this configuration (`settings.py:218–220`).

No `AWS_QUERYSTRING_AUTH`, `AWS_S3_CUSTOM_DOMAIN`, or presigned URL timeout settings are present. See §9.

---

## 6. Storage Call Sites

All production `default_storage` calls (excluding tests):

| File | Line | Operation | Detail |
|---|---|---|---|
| `backend/api/uploads/views.py` | 64 | `default_storage.save(storage_key, file)` | Writes the uploaded file to S3; key format: `uploads/<user.id>/<uuid4().hex>/<file.name>` |
| `backend/api/uploads/views.py` | 65 | `default_storage.url(saved_key)` | Returns the URL for the stored key; stored as `Upload.file_url` |
| `backend/api/uploads/views.py` | 91 | `default_storage.delete(upload.storage_key)` | Deletes the S3 object; only called if `storage_key` is non-empty |
| `backend/api/ai/views.py` | 450 | `default_storage.open(upload.storage_key)` | Opens the stored file for reading; used by the AI domain to read PDF bytes for analysis; only reached when caller passes an `upload_id` referencing a PDF |

No other code in the repository calls `default_storage` directly.

---

## 7. Authority / Access Rules

- All routes require `IsAuthenticated` (DRF project default). No view sets a different permission class.
- `UploadsViewSet` scopes all queries to `user=request.user` (`views.py:34`). A user cannot list, read, or delete another user's uploads.
- `UploadsViewSet.destroy` enforces ownership via `get_object_or_404(Upload, pk=pk, user=request.user)` (`views.py:88`).
- `ContractDocumentListCreateAPIView` and `ContractDocumentDeleteAPIView` enforce party membership via `is_party(request.user, contract)` from `backend.api.contracts.permissions` (`document_views.py:38, 46, 83`). Non-parties receive a 403-equivalent response from `contract_party_response()`.
- The `POST /api/contracts/<id>/documents/` endpoint also enforces upload ownership: it fetches the `Upload` by `pk=upload_id, user=request.user` (`document_views.py:57`), preventing one user from attaching another user's upload to a contract.
- No admin-only or staff-only routes exist in either domain.

---

## 8. Relationship to Other Domains

### Contracts (`backend/contracts/`, `backend/api/contracts/`)

`ContractDocument.contract` is a required FK to `contracts.Contract`. The three contract-document routes (`GET/POST/DELETE /api/contracts/<id>/documents/`) are defined in `backend/api/contracts/document_views.py` and registered within the contracts URL namespace (`urls.py:146–153`). The contracts app is the structural anchor for `ContractDocument`.

### Search (`backend/api/search/`)

`backend/api/search/views.py:15,19` imports both `ContractDocument` and `Upload`. Lines 346 and 577 query `ContractDocument` with full-text filtering across `title`, `description`, and `upload__file_name`. The search domain consumes both models as read-only.

### AI (`backend/api/ai/`)

`backend/api/ai/views.py:439` imports `Upload` inline. Line 450 calls `default_storage.open(upload.storage_key)` to read PDF bytes for AI contract analysis. The AI domain accepts either a direct file upload or an `upload_id` referencing an existing `Upload` with `file_type == "pdf"`.

### Contract Pro (`backend/contract_pro/`)

`backend/contract_pro/models.py:131` defines `UPLOAD_CONTRACT_DOCUMENTS = "upload_contract_documents"` as a member of the `ContractProPermission` enum. This is a permission constant string only — the `contract_pro` app does not import `Upload`, `ContractDocument`, or any code from either domain. Documented in `contract_pro.md`.

---

## 9. Current Gaps

1. **No file size limit.** `file.size` is read and stored (`uploads/views.py:78`) but never checked against a maximum. There is no `MAX_UPLOAD_SIZE` setting. Any file of any size is accepted and written to S3.

2. **No MIME type or magic byte validation.** `file_type` is a client-supplied string validated only against `VALID_FILE_TYPES = {"pdf", "image", "video", "slides", "document"}` (`uploads/views.py:13, 56–60`). The backend does not inspect `Content-Type`, read magic bytes, or verify that a file claiming to be `"pdf"` is actually a PDF. The AI domain at `ai/views.py:446–449` checks `upload.file_type == "pdf"` but trusts the stored string.

3. **No file name sanitization.** `file.name` is used directly in the storage key: `uploads/<user_id>/<uuid>/<file.name>` (`uploads/views.py:63`). No normalization, extension stripping, or path traversal check is applied to the original filename.

4. **`DocumentsViewSet` is a stub that returns hardcoded strings.** All five methods in `backend/api/documents/views.py:7–20` return `{"message": "..."}` literals. The model is never queried. This viewset is wired and reachable at `/api/documents/` but provides no real functionality. It conflicts in purpose with the real `ContractDocumentListCreateAPIView` and `ContractDocumentDeleteAPIView`.

5. **`ContractDocumentDeleteAPIView` orphans files in S3.** `DELETE /api/contracts/<id>/documents/<doc_id>/` calls `doc.delete()` (`document_views.py:87`) which removes the `ContractDocument` join row only. It does **not** delete the underlying `Upload` row and does **not** call `default_storage.delete`. The S3 object and `Upload` record persist after a document is detached from a contract.

6. **`is_draft_document` is never set on upload create.** The field exists on `Upload` (`models.py:52`), was added in migration `0002`, and is filterable via `?is_draft_document=` on the list endpoint (`uploads/views.py:44–46`). However, the `create` action never sets it — only `is_prep_material` is set during upload creation (`uploads/views.py:82`). How `is_draft_document` would ever become `True` is not established in code.

7. **`AWS_QUERYSTRING_AUTH` is not configured.** `AWS_DEFAULT_ACL = "private"` means S3 objects are not publicly accessible. `default_storage.url()` is used to generate `Upload.file_url` at create time. Whether `S3Boto3Storage` generates a presigned URL (time-limited) or a permanent URL is controlled by `AWS_QUERYSTRING_AUTH`, which is not set in `settings.py`. The behavior depends on `django-storages` defaults and is not established from the settings file alone.

---

## 10. Open Questions

1. **Are `Upload.file_url` values ever expired?** If `default_storage.url()` returns presigned URLs (the `S3Boto3Storage` default when `AWS_QUERYSTRING_AUTH` is unset or `True`), then stored `file_url` values have a finite lifetime. Whether the stored URLs are refreshed or re-generated before expiry is not established in code.

2. **What is the intended purpose of the stub `DocumentsViewSet`?** Is it a placeholder for a planned user-facing "my documents" API, or was it superseded by the contract-scoped document views and never cleaned up?

3. **Who is responsible for cleaning up `Upload` rows after `ContractDocument` deletion?** When a document is detached from a contract, the `Upload` row remains. Is the expectation that users call `DELETE /api/uploads/<pk>/` separately, or is there an intended cleanup path that was never implemented?

4. **Is `related_contract` on `Upload` redundant with `ContractDocument`?** `Upload` has a `related_contract` FK (`models.py:35`) that can be set at upload time, and `ContractDocument` also joins `Upload` to a `Contract`. The two associations can refer to different contracts. Whether this dual-association is intentional design or a duplication is not established in code.

---

## 11. Update Rule

Update this file when code changes `Upload`, `ContractDocument`, the uploads or documents API views, the storage backend configuration, or when new `default_storage` call sites are added or removed.

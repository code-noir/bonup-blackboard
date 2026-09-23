"""Pure Generation-1 to Generation-2 successor contract.

This module creates no keys, Genesis evidence, approvals, receipts or host
state.  It only creates a new canonical representation that retains the exact
Generation-1 candidate identity and is eligible for the existing Genesis
structural validator.
"""
from copy import deepcopy
import hashlib

from . import installation_bundle as bundle
from .founder_genesis import policy as founder_root_policy
from .serialization import canonical_json, digest, parse_json
from .schema import valid_format
from .types import AuthorityError, ValidationError


SUCCESSOR_VERSION = 1
SUCCESSOR_KIND = 'PROD01_GENERATION2_SUCCESSOR'
MAX_CANDIDATE_BYTES = bundle.MAX_SOURCE_BYTES


def _raw_value(raw):
    if type(raw) is not bytes or len(raw) > MAX_CANDIDATE_BYTES:
        raise ValidationError('Bounded Generation-1 candidate bytes required.')
    try:
        value = parse_json(raw.decode('utf-8'))
    except UnicodeDecodeError as error:
        raise ValidationError('Canonical Generation-1 candidate bytes required.') from error
    if raw != bundle.json_bytes(value):
        raise ValidationError('Canonical Generation-1 candidate bytes required.')
    bundle.validate_manifest(value)
    if (value.get('version') != bundle.NEXT_INSTALLATION_SCHEMA_VERSION or
            value.get('provisioning_generation') != 1 or
            value.get('approved') is not False or
            value.get('activation') is not False or
            value.get('integration_services_approved') is not False or
            'product_runtime_scope' not in value):
        raise AuthorityError('Complete unapproved PROD-01 Generation-1 candidate required.')
    return value


def _predecessor(raw, value):
    scope = value['product_runtime_scope']
    modules = value['runtime_modules']
    return dict(
        provisioning_generation=1,
        candidate_manifest_digest=hashlib.sha256(raw).hexdigest(),
        candidate_bundle_digest=value['bundle_digest'],
        source_commit=value['source_commit'],
        product_scope_digest=digest(scope),
        runtime_modules_digest=digest(modules),
    )


def _runtime(value):
    return dict(
        source_commit=value['source_commit'],
        manifest_version=value['version'],
        candidate_bundle_digest=value['bundle_digest'],
        product_scope_digest=digest(value['product_runtime_scope']),
        product_runtime_scope=deepcopy(value['product_runtime_scope']),
        runtime_modules=deepcopy(value['runtime_modules']),
        runtime_modules_digest=digest(value['runtime_modules']),
        files_digest=digest(value['files']),
        configuration_digests=deepcopy(value['configuration_digests']),
        identity_map_digest=value['identity_map_digest'],
        resource_digest=value['resource_digest'],
    )


def generate(raw):
    """Return a new deterministic, unapproved Generation-2 successor."""
    value = _raw_value(raw)
    result = dict(
        version=SUCCESSOR_VERSION,
        successor_kind=SUCCESSOR_KIND,
        provisioning_generation=2,
        source_commit=value['source_commit'],
        predecessor=_predecessor(raw, value),
        runtime=_runtime(value),
        founder_root_policy=founder_root_policy(),
        approved=False,
        activation=False,
        integration_services_approved=False,
    )
    result['bundle_digest'] = digest(result)
    return result


def bytes_for(value):
    validate(value)
    return (canonical_json(value) + '\n').encode('utf-8')


def validate(value):
    """Validate the closed successor representation without Genesis."""
    expected = {
        'version', 'successor_kind', 'provisioning_generation', 'source_commit',
        'predecessor', 'runtime', 'founder_root_policy', 'approved', 'activation',
        'integration_services_approved', 'bundle_digest',
    }
    if type(value) is not dict or set(value) != expected:
        raise ValidationError('Closed Generation-2 successor required.')
    if (value['version'] != SUCCESSOR_VERSION or
            value['successor_kind'] != SUCCESSOR_KIND or
            value['provisioning_generation'] != 2 or
            not valid_format('git-oid', value['source_commit']) or
            value['approved'] is not False or value['activation'] is not False or
            value['integration_services_approved'] is not False or
            value['founder_root_policy'] != founder_root_policy() or
            value['bundle_digest'] != digest({k: v for k, v in value.items()
                                              if k != 'bundle_digest'})):
        raise AuthorityError('Generation-2 successor identity or policy mismatch.')
    predecessor = value['predecessor']
    predecessor_keys = {
        'provisioning_generation', 'candidate_manifest_digest',
        'candidate_bundle_digest', 'source_commit', 'product_scope_digest',
        'runtime_modules_digest',
    }
    if (type(predecessor) is not dict or set(predecessor) != predecessor_keys or
            predecessor['provisioning_generation'] != 1 or
            not valid_format('git-oid', predecessor['source_commit']) or
            any(not valid_format('sha256', predecessor[k]) for k in predecessor_keys
                if k not in ('provisioning_generation', 'source_commit')) or
            predecessor['source_commit'] != value['source_commit']):
        raise AuthorityError('Generation-1 predecessor binding mismatch.')
    runtime = value['runtime']
    runtime_keys = {
        'source_commit', 'manifest_version', 'candidate_bundle_digest',
        'product_scope_digest', 'product_runtime_scope', 'runtime_modules',
        'runtime_modules_digest',
        'files_digest', 'configuration_digests', 'identity_map_digest',
        'resource_digest',
    }
    if type(runtime) is not dict or set(runtime) != runtime_keys:
        raise ValidationError('Closed Generation-2 runtime binding required.')
    if (runtime['source_commit'] != value['source_commit'] or
            runtime['manifest_version'] != bundle.NEXT_INSTALLATION_SCHEMA_VERSION or
            runtime['candidate_bundle_digest'] != predecessor['candidate_bundle_digest'] or
            runtime['product_scope_digest'] != predecessor['product_scope_digest'] or
            digest(runtime['product_runtime_scope']) != runtime['product_scope_digest'] or
            runtime['runtime_modules_digest'] != predecessor['runtime_modules_digest'] or
            digest(runtime['runtime_modules']) != runtime['runtime_modules_digest'] or
            any(not valid_format('sha256', runtime[k]) for k in
                ('candidate_bundle_digest', 'product_scope_digest',
                 'runtime_modules_digest', 'files_digest',
                 'identity_map_digest', 'resource_digest')) or
            type(runtime['configuration_digests']) is not dict or
            any(not valid_format('sha256', v) for v in runtime['configuration_digests'].values())):
        raise AuthorityError('Generation-2 runtime binding mismatch.')
    return value


def validate_for_predecessor(value, raw):
    """Validate a successor against the exact preserved G1 bytes."""
    validate(value)
    if value != generate(raw):
        raise AuthorityError('Generation-2 successor does not match predecessor.')
    return value


def genesis_identity(raw):
    """Perform only the existing Genesis candidate-identity validation."""
    from .founder_genesis import candidate_identity
    try:
        value = parse_json(raw.decode('utf-8'))
    except (AttributeError, UnicodeDecodeError):
        raise ValidationError('Canonical Generation-2 successor bytes required.') from None
    if raw != bytes_for(value):
        raise ValidationError('Canonical Generation-2 successor bytes required.')
    return candidate_identity(raw, validate)

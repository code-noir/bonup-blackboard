"""Generation-1 approval-stage tooling, not an installed runtime dependency.

Pure records and decisions only. Generated records are not authenticated consent.
A trusted installer must supply a separately authenticated founder context; it must
never construct that context from these records or from caller JSON.
"""
from copy import deepcopy

from . import installation_bundle as bundle
from .protocol import uuid_value
from .schema import timestamp
from .serialization import parse_json
from .types import AuthorityError, ValidationError

HISTORICAL_SOURCE_COMMIT = '3e0749cf0d323952b2f6f3f7945e8fda1b258b51'
HISTORICAL_CANDIDATE_SHA256 = '034036d04043c470e67a050e827f1312445017069e1f234e3f096fa5864adbb6'
HISTORICAL_CANDIDATE_BUNDLE = 'cdaf9528de71fd64cf60c44d916cb0d3632adf5e7245b3cc5e11b4a782ea72e4'
SOURCE_COMMIT = HISTORICAL_SOURCE_COMMIT
CANDIDATE_SHA256 = HISTORICAL_CANDIDATE_SHA256
CANDIDATE_BUNDLE = HISTORICAL_CANDIDATE_BUNDLE


def _identity(raw, value, expected):
    if type(expected) is not dict or set(expected) != {
            'source_commit','candidate_manifest_digest','candidate_bundle_digest'}:
        raise ValidationError('Closed candidate identity required.')
    historical=(bundle.sha(raw)==HISTORICAL_CANDIDATE_SHA256 and
                expected['source_commit']==HISTORICAL_SOURCE_COMMIT and
                expected['candidate_bundle_digest']==HISTORICAL_CANDIDATE_BUNDLE)
    if (expected['candidate_manifest_digest'] != bundle.sha(raw) or
            expected['candidate_bundle_digest'] != value['bundle_digest'] or
            (expected['source_commit'] != value['source_commit'] and
             not historical)):
        raise ValidationError('Candidate identity mismatch.')
    return expected


def candidate(raw, *, expected=None):
    if type(raw) is not bytes:
        raise ValidationError('Exact committed candidate bytes required.')
    value = parse_json(raw)
    if (bundle.validate_manifest(value) != 'COMPLETE_BUT_UNAPPROVED' or value['activation'] or
            value['integration_services_approved'] or value['provisioning_generation'] != 1):
        raise ValidationError('Candidate identity mismatch.')
    if expected is None and value.get('version') == 5:
        raise ValidationError('Current candidate identity required.')
    if expected is None:
        expected={'source_commit':HISTORICAL_SOURCE_COMMIT,
            'candidate_manifest_digest':HISTORICAL_CANDIDATE_SHA256,
            'candidate_bundle_digest':HISTORICAL_CANDIDATE_BUNDLE}
    _identity(raw,value,expected)
    return value


def propose(raw, *, expected=None):
    """No approval input, timestamps, entropy, IO or authoritative side effects."""
    original = candidate(raw, expected=expected)
    approved = deepcopy(original)
    approved['approved'] = True
    # bundle_digest is derived metadata, never an independent policy change.
    bundle.seal(approved)
    inventory = bundle.detached_inventory(approved)
    old = bundle.detached_inventory(original)
    changed = [a['destination'] for a, b in zip(inventory['artifacts'], old['artifacts']) if a != b]
    if len(inventory['artifacts']) != len(old['artifacts']) or changed != [bundle.MANIFEST]:
        raise ValidationError('Candidate approval must change only the manifest artifact.')
    binding = dict(source_commit=(HISTORICAL_SOURCE_COMMIT if bundle.sha(raw)==HISTORICAL_CANDIDATE_SHA256
                                 else original['source_commit']), provisioning_generation=1,
        candidate_manifest_digest=bundle.sha(raw), candidate_bundle_digest=original['bundle_digest'],
        approved_manifest_digest=bundle.sha(bundle.json_bytes(approved)),
        approved_inventory_digest=bundle.sha(bundle.json_bytes(inventory)))
    return dict(version=1, state='PROPOSED_APPROVAL_STAGE', binding=binding,
                installation_manifest=approved, installation_inventory=inventory)


def validate_proposal(raw, proposal):
    binding=proposal.get('binding') if type(proposal) is dict else None
    expected={k:binding.get(k) for k in ('source_commit','candidate_manifest_digest','candidate_bundle_digest')} \
        if type(binding) is dict else None
    bundle.same(proposal, propose(raw, expected=expected), 'closed approval transformation')
    return proposal['binding']


def approval_record(raw, proposal, *, context, approval_id, approved_at):
    """Called only for a later explicit decision, not by the review generator.

    Context is authenticated by the caller's trusted boundary (existing M1/M2
    convention). A serialized record, including this return value, cannot mint it.
    """
    validate_proposal(raw, proposal)
    bundle.founder(context)
    uuid_value(approval_id)
    timestamp(approved_at)
    return dict(version=1, decision='INSTALL_ONLY', binding=deepcopy(proposal['binding']),
        proposal_digest=bundle.sha(bundle.json_bytes(proposal)), approval_id=approval_id,
        approved_at=approved_at, founder_uid=1000, activation=False,
        integration_services_approved=False)


def require_approval(raw, proposal, decision, *, context):
    validate_proposal(raw, proposal)
    bundle.founder(context)
    if type(decision) is not dict:
        raise AuthorityError('Separate explicit installation approval required.')
    expected = approval_record(raw, proposal, context=context,
        approval_id=decision.get('approval_id'), approved_at=decision.get('approved_at'))
    bundle.same(decision, expected, 'founder installation decision')


def verify_installation_payloads(raw, proposal, payloads):
    """All installed bytes must match the APPROVED inventory, not the candidate."""
    validate_proposal(raw, proposal)
    items = proposal['installation_inventory']['artifacts']
    if type(payloads) is not dict or set(payloads) != {a['destination'] for a in items}:
        raise ValidationError('Exact approved installation inventory required.')
    for artifact in items:
        data = payloads[artifact['destination']]
        if type(data) is not bytes or bundle.sha(data) != artifact['sha256']:
            raise ValidationError('Installed bytes differ from approved inventory.')
    manifest = proposal['installation_manifest']
    bundle.verify_payloads(manifest, {a['destination']:payloads[a['destination']]
                                     for a in manifest['artifacts']})


def installation_plan(raw, proposal, decision, payloads, preflight, *, context):
    require_approval(raw, proposal, decision, context=context)
    verify_installation_payloads(raw, proposal, payloads)
    # The historical candidate records its earlier base commit; this outer binding
    # requires the actual committed composition checkpoint as well.
    bundle.keys(preflight, ('review_source_commit', 'candidate_preflight'))
    if preflight['review_source_commit'] != proposal['binding']['source_commit']:
        raise AuthorityError('Wrong reviewed composition commit.')
    inner = proposal['installation_manifest']
    plan = bundle.installation_plan(inner,
        {a['destination']:payloads[a['destination']] for a in inner['artifacts']},
        preflight['candidate_preflight'], context=context)
    return dict(version=1, binding=deepcopy(proposal['binding']),
        approval_digest=bundle.sha(bundle.json_bytes(decision)), plan=plan,
        activation=False, integration_services_approved=False)


def make_receipt(raw, proposal, decision, observations, *, context, accounts, boot_id, installed_at):
    """Linked installation receipt, retaining the unchanged runtime projection.

    Future installer persists this full receipt as retained installation evidence.
    runtime_receipt is the existing runtime-compatible installation-receipt.json;
    it alone is insufficient evidence for this approval-stage installer/rollback.
    """
    require_approval(raw, proposal, decision, context=context)
    runtime = bundle.make_receipt(proposal['installation_manifest'], observations,
        accounts=accounts, boot_id=boot_id, installed_at=installed_at)
    bundle.validate_receipt(proposal['installation_manifest'], runtime)
    return dict(version=2, binding=deepcopy(proposal['binding']),
        approval_digest=bundle.sha(bundle.json_bytes(decision)), runtime_receipt=runtime,
        activation_authority=False)


def validate_receipt(raw, proposal, decision, receipt, *, context):
    require_approval(raw, proposal, decision, context=context)
    bundle.keys(receipt, ('version','binding','approval_digest','runtime_receipt','activation_authority'))
    expected = dict(version=2, binding=deepcopy(proposal['binding']),
        approval_digest=bundle.sha(bundle.json_bytes(decision)),
        runtime_receipt=receipt['runtime_receipt'], activation_authority=False)
    bundle.same(receipt, expected, 'candidate and installation receipt linkage')
    bundle.validate_receipt(proposal['installation_manifest'], receipt['runtime_receipt'])


def require_activation(raw, proposal, decision, receipt, host_tests, *, context):
    """Installation approval is never the separate later activation decision."""
    validate_receipt(raw, proposal, decision, receipt, context=context)
    # No API for issuing activation approval belongs in installation tooling.
    # Even complete host-test evidence cannot promote an installation decision.
    bundle.verify_host_tests(proposal['installation_manifest'], receipt['runtime_receipt'], host_tests)
    raise AuthorityError('Separate founder activation approval, enrollment and reconciliation required.')

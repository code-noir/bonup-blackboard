"""Generation-independent identities consumed by the founder authority boundary.

These are trusted installed-policy inputs, never fields selected by an intake
request. Generation-1 approval tooling remains a separate historical format.
"""
from dataclasses import asdict, dataclass

from .protocol import bounded_json
from .schema import valid_format
from .serialization import canonical_json, digest
from .types import AuthorityError, ValidationError


@dataclass(frozen=True)
class InstallationBinding:
    source_commit: str
    candidate_manifest_digest: str
    candidate_bundle_digest: str
    approved_manifest_digest: str
    approved_inventory_digest: str
    provisioning_generation: int
    founder_root_binding_digest: str | None = None
    predecessor_candidate_manifest_digest: str | None = None

    def __post_init__(self):
        if (not valid_format('git-oid', self.source_commit) or
                type(self.provisioning_generation) is not int or self.provisioning_generation < 1 or
                self.founder_root_binding_digest is not None and self.provisioning_generation != 2 or
                self.provisioning_generation == 2 and
                not valid_format('sha256', self.predecessor_candidate_manifest_digest or '') or
                self.provisioning_generation == 1 and self.predecessor_candidate_manifest_digest is not None or
                any(not valid_format('sha256', value) for name, value in self.data().items()
                    if name not in ('source_commit', 'provisioning_generation'))):
            raise ValidationError('Exact installation identity required.')

    def data(self):
        result = asdict(self)
        for name in ('founder_root_binding_digest', 'predecessor_candidate_manifest_digest'):
            if result[name] is None:
                del result[name]
        return result


@dataclass(frozen=True)
class InstalledReceipt:
    """Validated bytes from the root-controlled installed receipt reader.

    The expected receipt digest is independently pinned by installed policy.
    This record is evidence only, never a founder or activation context.
    """
    binding: InstallationBinding
    receipt_digest: str
    installation_id: str


def verify_receipt(raw, binding, expected_digest):
    if type(binding) is not InstallationBinding or not valid_format('sha256', expected_digest):
        raise AuthorityError('Trusted installation and receipt pin required.')
    data = bounded_json(raw)
    genesis = binding.founder_root_binding_digest is not None
    expected_fields = {'version', 'binding', 'installation_id', 'activation', 'verified_artifacts_digest'}
    if genesis:
        expected_fields.add('genesis')
    if (type(data) is not dict or set(data) != {
            *expected_fields} or
            type(data['version']) is not int or data['version'] != (2 if genesis else 1) or
            data['binding'] != binding.data() or data['activation'] is not False or
            data['verified_artifacts_digest'] != binding.approved_inventory_digest or
            not valid_format('uuid', data['installation_id']) or digest(data) != expected_digest):
        raise AuthorityError('Installed receipt does not match the pinned installation.')
    if genesis:
        evidence = data['genesis']
        if (type(evidence) is not dict or set(evidence) != {'founder_root_binding_digest',
                'founder_root_policy_digest','genesis_challenge_digest','key_id','root_generation',
                'public_key_artifact_sha256'} or evidence['founder_root_binding_digest'] != binding.founder_root_binding_digest or
                type(evidence['root_generation']) is not int or evidence['root_generation'] != 1 or
                any(not valid_format('sha256',v) for k,v in evidence.items() if k != 'root_generation')):
            raise AuthorityError('Receipt must retain exact Genesis evidence.')
    return InstalledReceipt(binding, digest(data), data['installation_id'])


def approval_projection(candidate, approved, binding):
    """Closed generic approval transformation; no activation/service permission.

    Generation 2 supplies separately generated exact canonical representations.
    Only approved and the derived bundle digest may differ. This function does
    not issue founder authority or generate either representation.
    """
    import hashlib
    if type(binding) is not InstallationBinding:
        raise AuthorityError('Trusted candidate binding required.')
    old, new = bounded_json(candidate), bounded_json(approved)
    if (hashlib.sha256(candidate).hexdigest() != binding.candidate_manifest_digest or
            hashlib.sha256(approved).hexdigest() != binding.approved_manifest_digest or
            old.get('bundle_digest') != binding.candidate_bundle_digest or
            old.get('provisioning_generation') != binding.provisioning_generation or
            old.get('approved') is not False or new.get('approved') is not True or
            old.get('activation') is not False or new.get('activation') is not False or
            old.get('integration_services_approved') is not False or
            new.get('integration_services_approved') is not False):
        raise AuthorityError('Approval projection identity mismatch.')
    if binding.provisioning_generation == 2:
        predecessor = old.get('predecessor')
        if (type(predecessor) is not dict or
                predecessor.get('candidate_manifest_digest') !=
                binding.predecessor_candidate_manifest_digest):
            raise AuthorityError('Generation-1 predecessor binding mismatch.')
    elif binding.predecessor_candidate_manifest_digest is not None:
        raise AuthorityError('Generation-1 binding cannot carry a predecessor.')
    changed = dict(old, approved=True)
    if 'founder_root_policy' in old:
        from .founder_genesis import policy
        if (canonical_json(old['founder_root_policy']) != canonical_json(policy()) or
                binding.provisioning_generation != 2 or binding.founder_root_binding_digest is None or
                'founder_root_binding_digest' in old):
            raise AuthorityError('Initial Genesis binding required before approval.')
        # The separate root-binding stage adds exactly this reviewed identity.
        # It does not rewrite candidate bytes or any candidate policy field.
        changed['founder_root_binding_digest'] = binding.founder_root_binding_digest
    elif binding.founder_root_binding_digest is not None:
        raise AuthorityError('Historical candidate cannot acquire Genesis semantics.')
    changed['bundle_digest'] = digest({k: v for k, v in changed.items() if k != 'bundle_digest'})
    if changed != new:
        raise AuthorityError('Approval cannot alter installation policy.')
    return digest(new)

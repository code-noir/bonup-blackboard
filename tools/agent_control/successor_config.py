"""Closed successor runtime attestation, separate from historical candidates.

Component version 3 selects this contract explicitly. The post-install attestation
binds the receipt and static configuration; it is not a candidate bundle and does
not provide founder authority. No generator or installer is implemented here.
"""
from dataclasses import asdict

from .authority_installation import InstallationBinding, verify_receipt
from .founder_crypto import PURPOSES
from .host_test_catalog import CATALOG_DIGEST, VERSION, ROOT_ID, PROFILE
from .installation_bundle import PRODUCTION_MODULES, POLICIES, identities
from .integration_policy import IntegrationPolicy
from .operational_enrollment import installation_spec
from .schema import valid_format
from .serialization import canonical_json, digest
from .service_runtime import keys
from .types import AuthorityError

ATTESTATION = '/etc/bonup-agent-control/runtime-authority.json'
RECEIPT = '/etc/bonup-agent-control/authority-receipt.json'
PREFIX = '/usr/lib/bonup-agent-control'
MODULES = ('authority_installation','authority_journal','founder_crypto','founder_session',
    'founder_intake','founder_transport','host_test_catalog','host_test_launch',
    'host_test_observation','host_test_runtime','service_evidence','successor_config','installation_approval','interruption',
    'founder_genesis')
OPENSSL = dict(path='/usr/bin/openssl', algorithm='Ed25519', operation='VERIFY_ONLY',
               compatibility='OpenSSL 3.x; RFC8032 positive and negative verification')
INTERRUPTION = dict(version=1,observer='PIDFD_DEATH_WITH_LIVE_CANARY',journal='/usr/bin/journalctl',
    controller_evidence='/var/lib/bonup-agent-control/runtime/interruption',
    supervisor_evidence='/var/lib/bonup-agent-supervisor/evidence',ambiguous='DENY_PASS')


def files():
    result = {PREFIX+'/tools/agent_control/'+name+'.py' for name in (*PRODUCTION_MODULES,*MODULES)}
    result.update(PREFIX+'/docs/agent-control/'+name+'.json' for name in POLICIES)
    result.update(PREFIX+'/'+name for name in ('controller','supervisor','gate_entry.py',
                                             'bootstrap_entry.py','host_test_canary.py'))
    return result


def validate(configuration, attestation, identity_map, receipt, root, *, component, genesis=None):
    controller = component == 'controller'
    if component not in ('controller','supervisor'):
        raise AuthorityError('Unknown successor component.')
    keys(configuration, ('version','service','authority','founder_uid','founder','proposal','executions')
         if controller else ('version','service','authority','roots','plans'))
    if type(configuration['version']) is not int or configuration['version'] not in (3,4):
        raise AuthorityError('Explicit successor configuration version required.')
    policy = configuration['authority']
    deferred = configuration['version'] == 4
    common = ('version','installation_generation','founder_enabled',
        'host_tests_enabled','catalog_version','catalog_digest','audit','receipt','activation','interruption')
    keys(policy, common + (('founder_root_policy',) if deferred else
        ('root_id','root_digest','root_generation','algorithm','purposes','openssl')))
    expected = dict(version=1,installation_generation=2,founder_enabled=policy['founder_enabled'],
        root_id=root.key_id,root_digest=root.identity,root_generation=root.generation,
        algorithm='Ed25519',purposes=list(PURPOSES),openssl=OPENSSL,
        host_tests_enabled=policy['host_tests_enabled'],catalog_version=VERSION,catalog_digest=CATALOG_DIGEST,
        audit='CONTROLLER_DURABLE_OUTBOX_REQUIRED',receipt='EXACT_VERIFIED_INSTALLATION_REQUIRED',activation=False,
        interruption=INTERRUPTION)
    if deferred:
        from .founder_genesis import policy as root_policy, validate_binding, receipt_projection
        binding=InstallationBinding(**attestation['binding'])
        identity={k:v for k,v in binding.data().items() if k in ('source_commit','candidate_manifest_digest',
            'candidate_bundle_digest','provisioning_generation')}
        identity['founder_root_policy_digest']=digest(root_policy())
        bound=validate_binding(genesis,identity)
        if (binding.founder_root_binding_digest != genesis['binding_digest'] or root != bound or
                receipt.get('genesis') != receipt_projection(genesis)):
            raise AuthorityError('Installed Genesis root/receipt mismatch.')
        for name in ('root_id','root_digest','root_generation','algorithm','purposes','openssl'):
            del expected[name]
        expected.update(version=2,founder_root_policy=root_policy())
    elif genesis is not None:
        raise AuthorityError('Genesis cannot be smuggled through legacy configuration.')
    if (type(policy['founder_enabled']) is not bool or type(policy['host_tests_enabled']) is not bool or
            policy['host_tests_enabled'] and not policy['founder_enabled'] or
            canonical_json(policy) != canonical_json(expected)):
        raise AuthorityError('Incomplete or unsafe successor authority policy.')
    if configuration['service'] != installation_spec(component, generation=2):
        raise AuthorityError('Successor service identity mismatch.')
    if controller:
        if (type(configuration['founder_uid']) is not int or configuration['founder_uid'] != 1000 or
                configuration['founder'] is not None or configuration['proposal'] is not None or
                configuration['executions'] != []):
            raise AuthorityError('No ordinary successor intake or caller execution catalog.')
    elif configuration['roots'] != [] or configuration['plans'] != []:
        raise AuthorityError('Physical enrollment comes from the verified receipt only.')
    expected_identities=identities()
    expected_identities['provisioning_generation']=2
    for account in expected_identities['accounts']: account['provisioning_generation']=2
    if identity_map != expected_identities:
        raise AuthorityError('Successor identity map mismatch.')
    keys(attestation, ('version','provisioning_generation','binding','receipt_digest','bundle_digest',
        'configuration_digests','identity_map_digest','files','resource_digest','approved','activation',
        'integration_services_approved','authority_digest','filesystem_digest'))
    binding=InstallationBinding(**attestation['binding'])
    if (type(attestation['version']) is not int or attestation['version'] != 1 or
            type(attestation['provisioning_generation']) is not int or attestation['provisioning_generation'] != 2 or
            binding.provisioning_generation != 2 or attestation['approved'] is not True or
            attestation['activation'] is not False or attestation['integration_services_approved'] is not True or
            attestation['resource_digest'] != IntegrationPolicy().policy_digest or
            attestation['authority_digest'] != digest(policy) or
            attestation['identity_map_digest'] != digest(identity_map) or
            attestation['bundle_digest'] != digest({k:v for k,v in attestation.items() if k!='bundle_digest'})):
        raise AuthorityError('Explicit receipt-bound successor service attestation required.')
    keys(attestation['configuration_digests'], ('controller','supervisor'))
    if (any(not valid_format('sha256',v) for v in attestation['configuration_digests'].values()) or
            attestation['configuration_digests'][component] != digest(configuration)):
        raise AuthorityError('Successor configuration digest mismatch.')
    if (type(attestation['files']) is not dict or set(attestation['files']) != files() or
            any(not valid_format('sha256',v) for v in attestation['files'].values())):
        raise AuthorityError('Closed successor production inventory required.')
    verified = verify_receipt(canonical_json(receipt).encode(),binding,attestation['receipt_digest'])
    return verified

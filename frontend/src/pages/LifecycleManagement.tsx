import { useSearchParams } from 'react-router-dom'
import LegacyAgreementTimeline from './LegacyAgreementTimeline'
import SignedAgreementTimeline from './SignedAgreementTimeline'

export default function LifecycleManagement() {
  const [searchParams] = useSearchParams()
  const contractId = searchParams.get('contract')

  if (contractId) return <SignedAgreementTimeline contractId={contractId} />

  return <LegacyAgreementTimeline />
}

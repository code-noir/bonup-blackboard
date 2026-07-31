import { type WorkflowRecord } from '@/components/workflow/WorkflowWorkspace'
import { type BoardContractRecord, type BoardObligationRecord } from '@/hooks/useBoardData'

export type BoardEntryId =
  | 'agreements-drafting'
  | 'agreements-prepared'
  | 'agreements-under-negotiation'
  | 'agreements-signed'
  | 'agreements-rejected'
  | 'obligations-upcoming'
  | 'notifications-unread'
  | 'activity-recent'
  | 'ai-reviews-ready'
  | 'ai-counter-drafts-ready'

export type BoardEntryCategory = 'agreement' | 'obligation' | 'notification' | 'activity' | 'ai'
export type BoardEntryBackendSource = '/api/contracts/' | '/api/obligations/' | '/api/notifications/' | '/api/notifications/unread-count/' | '/api/activity/' | '/api/ai/workflows/'
export type BoardEntryOverlaySource = 'contracts' | 'obligations' | 'notifications' | 'activity' | 'workflows'

export type BoardEntryDestination =
  | { type: 'contract-status'; status: string }
  | { type: 'obligations' }
  | { type: 'notifications' }
  | { type: 'activity' }
  | { type: 'workflow-state'; state: string }

export type BoardEntryDefinition = {
  id: BoardEntryId
  label: string
  category: BoardEntryCategory
  backendSource: BoardEntryBackendSource
  overlaySource: BoardEntryOverlaySource
  destination: BoardEntryDestination
  empty: string
  enabled: boolean
}

export type BoardEntryConfig = BoardEntryDefinition & {
  count: number
  loading: boolean
}

const AGREEMENT_ENTRIES: BoardEntryDefinition[] = [
  {
    id: 'agreements-drafting',
    label: 'Drafting Agreements',
    category: 'agreement',
    backendSource: '/api/contracts/',
    overlaySource: 'contracts',
    empty: 'No drafting agreements.',
    enabled: true,
    destination: { type: 'contract-status', status: 'drafting' },
  },
  {
    id: 'agreements-prepared',
    label: 'Prepared Agreements',
    category: 'agreement',
    backendSource: '/api/contracts/',
    overlaySource: 'contracts',
    empty: 'No prepared agreements.',
    enabled: true,
    destination: { type: 'contract-status', status: 'prepared' },
  },
  {
    id: 'agreements-under-negotiation',
    label: 'Under Negotiation',
    category: 'agreement',
    backendSource: '/api/contracts/',
    overlaySource: 'contracts',
    empty: 'No agreements under negotiation.',
    enabled: true,
    destination: { type: 'contract-status', status: 'under_negotiation' },
  },
  {
    id: 'agreements-signed',
    label: 'Signed Agreements',
    category: 'agreement',
    backendSource: '/api/contracts/',
    overlaySource: 'contracts',
    empty: 'No signed agreements.',
    enabled: true,
    destination: { type: 'contract-status', status: 'signed' },
  },
  {
    id: 'agreements-rejected',
    label: 'Rejected Agreements',
    category: 'agreement',
    backendSource: '/api/contracts/',
    overlaySource: 'contracts',
    empty: 'No rejected agreements.',
    enabled: true,
    destination: { type: 'contract-status', status: 'rejected' },
  },
]

const OPERATIONAL_ENTRIES: BoardEntryDefinition[] = [
  {
    id: 'obligations-upcoming',
    label: 'Upcoming Obligations',
    category: 'obligation',
    backendSource: '/api/obligations/',
    overlaySource: 'obligations',
    empty: 'No upcoming obligations.',
    enabled: true,
    destination: { type: 'obligations' },
  },
  {
    id: 'notifications-unread',
    label: 'Unread Notifications',
    category: 'notification',
    backendSource: '/api/notifications/unread-count/',
    overlaySource: 'notifications',
    empty: 'No unread notifications.',
    enabled: true,
    destination: { type: 'notifications' },
  },
  {
    id: 'activity-recent',
    label: 'Recent Activity',
    category: 'activity',
    backendSource: '/api/activity/',
    overlaySource: 'activity',
    empty: 'No recent activity.',
    enabled: true,
    destination: { type: 'activity' },
  },
  {
    id: 'ai-reviews-ready',
    label: 'AI Reviews Ready',
    category: 'ai',
    backendSource: '/api/ai/workflows/',
    overlaySource: 'workflows',
    empty: 'No AI reviews are ready.',
    enabled: true,
    destination: { type: 'workflow-state', state: 'review_ready' },
  },
  {
    id: 'ai-counter-drafts-ready',
    label: 'Counter Drafts Ready',
    category: 'ai',
    backendSource: '/api/ai/workflows/',
    overlaySource: 'workflows',
    empty: 'No counter drafts are ready.',
    enabled: true,
    destination: { type: 'workflow-state', state: 'counter_draft_ready' },
  },
]

function countContractsByResolvedStatus(contracts: BoardContractRecord[], status: string) {
  return contracts.filter((contract) => contract.display_status === status).length
}

function countWorkflowsByState(workflows: WorkflowRecord[], state: string) {
  return workflows.filter((workflow) => workflow.current_state === state).length
}

function countOpenObligations(obligations: BoardObligationRecord[]) {
  return obligations.filter((obligation) => obligation.state !== 'resolved').length
}

export function buildBoardEntries({
  contracts,
  contractsLoading,
  obligations,
  obligationsLoading,
  unreadNotifications,
  notificationsLoading,
  recentActivityCount,
  activityLoading,
  workflows,
  workflowsLoading,
  includeAiEntries,
  includeObligationsEntry,
}: {
  contracts: BoardContractRecord[]
  contractsLoading: boolean
  obligations: BoardObligationRecord[]
  obligationsLoading: boolean
  unreadNotifications: number
  notificationsLoading: boolean
  recentActivityCount: number
  activityLoading: boolean
  workflows: WorkflowRecord[]
  workflowsLoading: boolean
  includeAiEntries: boolean
  includeObligationsEntry: boolean
}): BoardEntryConfig[] {
  const agreementEntries = AGREEMENT_ENTRIES.map((entry) => ({
    ...entry,
    count: countContractsByResolvedStatus(contracts, entry.destination.type === 'contract-status' ? entry.destination.status : ''),
    loading: contractsLoading,
  }))

  const operationalEntries = OPERATIONAL_ENTRIES
    .filter((entry) => includeAiEntries || entry.destination.type !== 'workflow-state')
    .filter((entry) => includeObligationsEntry || entry.destination.type !== 'obligations')
    .map((entry) => {
      if (entry.destination.type === 'obligations') {
        return { ...entry, count: countOpenObligations(obligations), loading: obligationsLoading }
      }
      if (entry.destination.type === 'notifications') {
        return { ...entry, count: unreadNotifications, loading: notificationsLoading }
      }
      if (entry.destination.type === 'activity') {
        return { ...entry, count: recentActivityCount, loading: activityLoading }
      }
      if (entry.destination.type === 'workflow-state') {
        return {
          ...entry,
          count: countWorkflowsByState(workflows, entry.destination.state),
          loading: workflowsLoading,
        }
      }
      return { ...entry, count: 0, loading: false }
    })

  return [...agreementEntries, ...operationalEntries]
}

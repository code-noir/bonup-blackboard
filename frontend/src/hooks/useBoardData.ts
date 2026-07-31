import { useEffect, useState } from 'react'
import api from '@/api/client'
import { type WorkflowRecord } from '@/components/workflow/WorkflowWorkspace'

export type BoardContractRecord = {
  id: string
  title?: string
  contract_type?: string
  counterparty_name?: string
  counterparty_email?: string
  status?: string
  state?: string
  display_status?: string
  display_status_label?: string
  created_at?: string
}

export type BoardNotificationRecord = {
  id: string
  notification_type?: string
  title?: string
  message?: string
  is_read?: boolean
  related_contract_id?: string | null
  redirect_url?: string
  target_url?: string
  created_at?: string
}

export type BoardActivityRecord = {
  id: string
  contract_id?: string
  activity_type?: string
  description?: string
  created_at?: string
}

export type BoardObligationRecord = {
  id: string
  type?: 'payment' | 'service'
  contract_id?: string
  state?: string
  due_date?: string | null
  description?: string
  amount_due?: string
  installment_number?: number
}

type ContractListResponse = BoardContractRecord[] | { results: BoardContractRecord[] }
type WorkflowListResponse = { results: WorkflowRecord[] }
type NotificationUnreadCountResponse = { unread_count: number }
type NotificationListResponse = { count: number; results: BoardNotificationRecord[] }
type ActivityListResponse = { count: number; results: BoardActivityRecord[] }
type ObligationListResponse = { count: number; results: BoardObligationRecord[] }

export function useBoardData() {
  const [contracts, setContracts] = useState<BoardContractRecord[]>([])
  const [contractsLoading, setContractsLoading] = useState(true)
  const [contractsError, setContractsError] = useState('')

  const [workflows, setWorkflows] = useState<WorkflowRecord[]>([])
  const [workflowsLoading, setWorkflowsLoading] = useState(true)
  const [workflowsError, setWorkflowsError] = useState('')

  const [unreadNotifications, setUnreadNotifications] = useState(0)
  const [notifications, setNotifications] = useState<BoardNotificationRecord[]>([])
  const [notificationsLoading, setNotificationsLoading] = useState(true)
  const [notificationsError, setNotificationsError] = useState('')

  const [recentActivityCount, setRecentActivityCount] = useState(0)
  const [activity, setActivity] = useState<BoardActivityRecord[]>([])
  const [activityLoading, setActivityLoading] = useState(true)
  const [activityError, setActivityError] = useState('')

  const [obligations, setObligations] = useState<BoardObligationRecord[]>([])
  const [obligationsLoading, setObligationsLoading] = useState(true)
  const [obligationsError, setObligationsError] = useState('')

  useEffect(() => {
    let cancelled = false
    setContractsLoading(true)
    api.get<ContractListResponse>('/contracts/')
      .then(({ data }) => {
        if (cancelled) return
        setContracts(Array.isArray(data) ? data : data.results || [])
      })
      .catch((err) => {
        if (!cancelled) {
          setContractsError(err?.response?.data?.error || 'Contracts could not be loaded.')
          setContracts([])
        }
      })
      .finally(() => {
        if (!cancelled) setContractsLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    let cancelled = false
    setWorkflowsLoading(true)
    api.get<WorkflowListResponse>('/ai/workflows/')
      .then(({ data }) => {
        if (!cancelled) setWorkflows(data.results || [])
      })
      .catch((err) => {
        if (!cancelled) {
          setWorkflowsError(err?.response?.data?.error || 'Activity could not be loaded.')
          setWorkflows([])
        }
      })
      .finally(() => {
        if (!cancelled) setWorkflowsLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    let cancelled = false
    setNotificationsLoading(true)
    Promise.all([
      api.get<NotificationUnreadCountResponse>('/notifications/unread-count/'),
      api.get<NotificationListResponse>('/notifications/?is_read=false&page_size=100'),
    ])
      .then(([countResponse, listResponse]) => {
        if (cancelled) return
        setUnreadNotifications(countResponse.data.unread_count || 0)
        setNotifications(listResponse.data.results || [])
      })
      .catch((err) => {
        if (!cancelled) {
          setNotificationsError(err?.response?.data?.error || 'Notifications could not be loaded.')
          setUnreadNotifications(0)
          setNotifications([])
        }
      })
      .finally(() => {
        if (!cancelled) setNotificationsLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    let cancelled = false
    setActivityLoading(true)
    api.get<ActivityListResponse>('/activity/?page_size=100')
      .then(({ data }) => {
        if (cancelled) return
        setRecentActivityCount(data.count || data.results?.length || 0)
        setActivity(data.results || [])
      })
      .catch((err) => {
        if (!cancelled) {
          setActivityError(err?.response?.data?.error || 'Recent activity could not be loaded.')
          setRecentActivityCount(0)
          setActivity([])
        }
      })
      .finally(() => {
        if (!cancelled) setActivityLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    let cancelled = false
    setObligationsLoading(true)
    api.get<ObligationListResponse>('/obligations/?page_size=100')
      .then(({ data }) => {
        if (!cancelled) setObligations(data.results || [])
      })
      .catch((err) => {
        if (!cancelled) {
          setObligationsError(err?.response?.data?.error || 'Obligations could not be loaded.')
          setObligations([])
        }
      })
      .finally(() => {
        if (!cancelled) setObligationsLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  return {
    contracts,
    contractsLoading,
    contractsError,
    workflows,
    workflowsLoading,
    workflowsError,
    unreadNotifications,
    notifications,
    notificationsLoading,
    notificationsError,
    recentActivityCount,
    activity,
    activityLoading,
    activityError,
    obligations,
    obligationsLoading,
    obligationsError,
  }
}

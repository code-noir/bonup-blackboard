import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import api, { tokenStorage } from '@/api/client'

type BoardTab = 'payments' | 'work' | 'due_dates' | 'activity' | 'changes'

type BoardViewOptions = { resetView?: boolean }

type PerformanceAgreement = {
  id: string
  contract_id?: string
  lifecycle_id?: string
  title?: string
  contract: { id: string; title?: string; counterparty_name?: string | null; counterparty_email?: string | null }
  counterparty?: { name?: string | null; email?: string | null }
  status: string
  performance_ready?: boolean
  payment_count?: number
  work_count?: number
  work_item_count?: number
  due_date_count?: number
  activity_count?: number
  lifecycle_agreement?: { performance_ready_at?: string | null }
}

type PerformanceListResponse = { results: PerformanceAgreement[] }

type ProofResponse = {
  id: string
  response: 'received' | 'still_waiting' | 'not_received' | string
  note?: string
  responder?: { id?: string; email?: string; name?: string } | null
  created_at?: string
  updated_at?: string
}

type TimelineItem = {
  id: string
  item_type?: string
  title?: string
  description?: string | null
  responsible_party?: string | null
  beneficiary_party?: string | null
  due_date?: string | null
  amount?: string | null
  currency?: string | null
  status?: string
  source?: string
  source_type?: string
  source_label?: string | null
  source_clause?: string | null
  payment_method?: string | null
  lifecycle_state?: string
  reminder_at?: string | null
  metadata?: Record<string, unknown>
  can_upload_proof?: boolean
  can_respond_to_proof?: boolean
  latest_response?: ProofResponse | null
}

type TimelineEvent = {
  id: string
  event_type?: string
  title?: string
  description?: string
  occurred_at?: string
  metadata?: Record<string, unknown>
}

type LifecycleAttachment = {
  id: string
  lifecycle_item_id?: string
  lifecycle_agreement_id?: string
  contract_id?: string
  filename?: string
  original_filename?: string
  content_type?: string
  file_size?: number
  kind?: string
  note?: string
  uploaded_by?: { id?: string; email?: string; name?: string } | null
  uploaded_by_email?: string | null
  created_at?: string
  updated_at?: string
  file_url?: string
}

type AttachmentListResponse = { results: LifecycleAttachment[] }

type LifecycleMessage = {
  id: string
  lifecycle_item_id?: string
  lifecycle_agreement_id?: string
  contract_id?: string
  body: string
  sender?: { id?: string; email?: string; name?: string } | null
  sender_email?: string | null
  created_at?: string
  updated_at?: string
  is_mine?: boolean
}

type MessageListResponse = { results: LifecycleMessage[] }

type LifecycleBoardResponse = {
  contract?: { id: string; title?: string; counterparty_name?: string | null; counterparty_email?: string | null; status?: string }
  signed_version?: { label?: string; content_snapshot?: string }
  lifecycle_agreement?: { id: string; status?: string; performance_ready?: boolean }
  views?: Partial<Record<'payments' | 'work_services' | 'due_dates' | 'activity' | 'changes_add_ons', TimelineItem[] | TimelineEvent[]>>
  events?: TimelineEvent[]
}

const BOARD_TABS: Array<{ key: BoardTab; label: string }> = [
  { key: 'payments', label: 'Payments' },
  { key: 'work', label: 'Work / Services' },
  { key: 'due_dates', label: 'Deadlines' },
  { key: 'activity', label: 'Activity' },
  { key: 'changes', label: 'Changes / Add-ons' },
]

const DOCUMENT_IMAGE_MAX_SIZE = 25 * 1024 * 1024
const VIDEO_MAX_SIZE = 100 * 1024 * 1024
const SUPPORTED_PROOF_TYPES = new Set([
  'application/pdf',
  'image/jpeg',
  'image/png',
  'image/webp',
  'image/heic',
  'image/heif',
  'video/mp4',
  'video/quicktime',
  'video/webm',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
])
const SUPPORTED_PROOF_EXTENSIONS = new Map([
  ['.pdf', 'application/pdf'],
  ['.jpg', 'image/jpeg'],
  ['.jpeg', 'image/jpeg'],
  ['.png', 'image/png'],
  ['.webp', 'image/webp'],
  ['.heic', 'image/heic'],
  ['.heif', 'image/heif'],
  ['.mp4', 'video/mp4'],
  ['.mov', 'video/quicktime'],
  ['.webm', 'video/webm'],
  ['.doc', 'application/msword'],
  ['.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
])

function formatDate(value?: string | null) {
  if (!value) return 'Ready for tracking'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Ready for tracking'
  return date.toLocaleDateString()
}

function dueDateLabel(value?: string | null) {
  if (!value) return 'No date set'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'No date set'
  return date.toLocaleDateString()
}

function reminderLabel(value?: string | null) {
  if (!value) return 'No reminder set'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'No reminder set'
  return date.toLocaleString()
}

function toDateTimeInput(value?: string | null) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toISOString().slice(0, 16)
}

function fromDateTimeInput(value: string) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toISOString()
}

function quickReminderValue(item: TimelineItem, daysBefore: number) {
  if (!item.due_date) return ''
  const date = new Date(item.due_date)
  if (Number.isNaN(date.getTime())) return ''
  date.setDate(date.getDate() - daysBefore)
  date.setHours(9, 0, 0, 0)
  return date.toISOString().slice(0, 16)
}

function formatMoney(amount?: string | null, currency = 'USD') {
  if (!amount) return 'No amount set'
  const parsed = Number(amount)
  if (Number.isNaN(parsed)) return `${amount} ${currency}`
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(parsed)
}

function humanize(value?: string) {
  if (!value) return 'Planned'
  return value.replaceAll('_', ' ').replace(/\b\w/g, (char) => char.toUpperCase())
}

function htmlToReadableText(value: string) {
  return value
    .replace(/<\/?(p|div|h[1-6]|li|br|section|article|tr)[^>]*>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function signedAgreementText(contentSnapshot?: string) {
  if (!contentSnapshot) return 'No signed agreement snapshot returned.'
  try {
    const parsed = JSON.parse(contentSnapshot) as Record<string, unknown>
    const candidate = parsed.final_editor_html || parsed.editor_html || parsed.content_html || parsed.html || parsed.body || parsed.text
    if (typeof candidate === 'string' && candidate.trim()) return htmlToReadableText(candidate)
    const sections = parsed.sections
    if (Array.isArray(sections)) {
      const text = sections
        .map((section) => {
          if (!section || typeof section !== 'object') return ''
          const record = section as Record<string, unknown>
          const title = typeof record.title === 'string' ? record.title : ''
          const body = [record.body, record.text, record.content, record.html, record.content_html, record.editor_html]
            .find((value) => typeof value === 'string' && value.trim())
          return [title, typeof body === 'string' ? htmlToReadableText(body) : ''].filter(Boolean).join('\n')
        })
        .filter(Boolean)
        .join('\n\n')
      if (text.trim()) return text
    }
  } catch {
    return htmlToReadableText(contentSnapshot)
  }
  return htmlToReadableText(contentSnapshot)
}

function getErrorMessage(error: unknown, fallback: string) {
  const response = (error as { response?: { data?: { error?: string; detail?: string } } })?.response
  return response?.data?.error || response?.data?.detail || fallback
}

function getFetchErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback
}

async function postMultipart<T>(url: string, formData: FormData): Promise<T> {
  const headers = new Headers()
  const token = tokenStorage.getAccess()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(`/api${url}`, {
    method: 'POST',
    headers,
    body: formData,
  })

  const contentType = response.headers.get('content-type') || ''
  const payload = contentType.includes('application/json') ? await response.json() : null
  if (!response.ok) {
    const detail = payload?.detail || payload?.error
    throw new Error(detail || `Upload failed with status ${response.status}.`)
  }
  return payload as T
}

function proofContentType(file: File) {
  if (SUPPORTED_PROOF_TYPES.has(file.type)) return file.type
  const filename = file.name.toLowerCase()
  for (const [extension, contentType] of SUPPORTED_PROOF_EXTENSIONS) {
    if (filename.endsWith(extension)) return contentType
  }
  return file.type
}

function proofFileValidationMessage(file: File | null) {
  if (!file) return 'Proof file is required.'
  const contentType = proofContentType(file)
  if (!SUPPORTED_PROOF_TYPES.has(contentType)) return 'Upload a PDF, image, video, DOC, or DOCX file.'
  const limit = contentType.startsWith('video/') ? VIDEO_MAX_SIZE : DOCUMENT_IMAGE_MAX_SIZE
  if (file.size > limit) return `Maximum size is ${Math.round(limit / (1024 * 1024))} MB for this file type.`
  return ''
}

function performanceActionResultLabel(item: TimelineItem, action?: string) {
  if (action === 'mark_paid' || item.item_type === 'payment') return 'Paid'
  if (action === 'mark_work_performed' || action === 'mark_completed') return 'Performed'
  return 'Performed'
}

function markActionLabel(item: TimelineItem, action?: string) {
  if (action === 'mark_paid' || item.item_type === 'payment') return 'Mark Paid'
  return 'Mark Obligation Performed'
}

function statusStyle(status?: string) {
  const normalized = (status || '').toLowerCase()
  if (['completed', 'confirmed', 'resolved'].includes(normalized)) return { background: '#ECFDF5', color: '#047857' }
  if (['overdue', 'defaulted', 'failed', 'rejected'].includes(normalized)) return { background: '#FEF2F2', color: '#B91C1C' }
  if (['pending', 'due', 'grace'].includes(normalized)) return { background: '#FEF3C7', color: '#B45309' }
  return { background: '#F8FAFC', color: '#475569' }
}

function eventTimeLabel(value?: string) {
  if (!value) return 'Time not recorded'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Time not recorded'
  return date.toLocaleString()
}

function metadataString(metadata: Record<string, unknown> | undefined, key: string) {
  const value = metadata?.[key]
  return typeof value === 'string' ? value : ''
}

function performanceEventVerb(event: TimelineEvent) {
  if (event.event_type === 'payment_marked_paid') return 'paid'
  if (event.event_type === 'work_marked_performed') return 'performed'
  if (event.event_type === 'item_completed') return 'completed'
  return ''
}

function performanceEventActionLabel(event: TimelineEvent) {
  const resultLabel = metadataString(event.metadata, 'result_label')
  if (resultLabel) return resultLabel
  if (event.event_type === 'payment_marked_paid') return 'Paid'
  if (event.event_type === 'work_marked_performed') return 'Performed'
  if (event.event_type === 'item_completed') return 'Performed'
  if (event.event_type === 'proof_uploaded') return 'Proof uploaded'
  if (event.event_type === 'proof_response') return metadataString(event.metadata, 'response_label') || 'Response recorded'
  return event.title || humanize(event.event_type)
}

function isPerformanceActivityEvent(event: TimelineEvent) {
  return ['payment_marked_paid', 'work_marked_performed', 'item_completed', 'proof_uploaded', 'proof_response'].includes(event.event_type || '')
}

function eventItemId(event: TimelineEvent) {
  return metadataString(event.metadata, 'lifecycle_item_id') || metadataString(event.metadata, 'item_id')
}

function itemHistoryEvents(events: TimelineEvent[], item: TimelineItem) {
  return events.filter((event) => eventItemId(event) === item.id && isPerformanceActivityEvent(event))
}

function itemCompletionEvent(events: TimelineEvent[], item: TimelineItem) {
  const completionTypes = item.item_type === 'payment'
    ? ['payment_marked_paid', 'item_completed']
    : ['work_marked_performed', 'item_completed']
  return events.find((event) => eventItemId(event) === item.id && completionTypes.includes(event.event_type || '')) || null
}

function completionDateLabel(events: TimelineEvent[], item: TimelineItem) {
  const event = itemCompletionEvent(events, item)
  return event ? eventTimeLabel(event.occurred_at) : 'Not recorded'
}

function completionDateTitle(item: TimelineItem) {
  return item.item_type === 'payment' ? 'Paid Date' : 'Performed Date'
}

function performanceStatusLabel(item: TimelineItem) {
  const normalized = (item.status || item.lifecycle_state || '').toLowerCase()
  if (normalized === 'completed') {
    if (item.item_type === 'payment') return 'Paid'
    if (['service', 'service_work'].includes(item.item_type || '')) return 'Performed'
    return 'Performed'
  }
  return humanize(item.status || item.lifecycle_state)
}

function isCompletedPerformanceItem(item: TimelineItem) {
  return ['completed', 'confirmed', 'resolved'].includes((item.status || item.lifecycle_state || '').toLowerCase())
}

function agreementPerformanceStatusLabel(status?: string) {
  const normalized = (status || '').toLowerCase()
  if (['active', 'in_progress'].includes(normalized)) return 'In progress'
  if (normalized === 'completed') return 'Completed'
  return 'Waiting for first performed obligation'
}

function itemTypeLabel(item: TimelineItem) {
  if (item.item_type === 'payment') return 'Payment'
  if (['service', 'service_work'].includes(item.item_type || '')) return 'Work / Service'
  return humanize(item.item_type)
}

function itemAction(item: TimelineItem): { action: string; label: string } | null {
  const source = item.source || item.source_type
  if (source === 'contract_payment_obligation' || source === 'payment_record') return null
  if ((item.status || '').toLowerCase() === 'completed') return null
  if (item.item_type === 'payment') return { action: 'mark_paid', label: markActionLabel(item, 'mark_paid') }
  if (['service', 'service_work'].includes(item.item_type || '')) return { action: 'mark_work_performed', label: markActionLabel(item, 'mark_work_performed') }
  if (['responsibility', 'obligation', 'due_date', 'deadline'].includes(item.item_type || '')) return { action: 'mark_completed', label: markActionLabel(item, 'mark_completed') }
  return null
}

function isDisplayableItem(item: TimelineItem) {
  const text = `${item.title || ''} ${item.description || ''}`.toLowerCase().replace(/\s+/g, ' ')
  if (text.length < 500) return true
  const markers = ['agreement is made between', 'governing law', 'signatures', 'borrower', 'lender', 'provider', 'client']
  return !(text.includes('agreement') && markers.filter((marker) => text.includes(marker)).length >= 2)
}

function sourceLabel(item: TimelineItem) {
  if (item.source_label) return item.source_label
  if (item.source === 'contract_payment_obligation') return 'Signed agreement payment term'
  if (item.source === 'contract_service_obligation') return 'Signed agreement work term'
  if (item.source === 'payment_record') return 'Payment record'
  if (item.source_type === 'original_contract') return 'Signed agreement source'
  return humanize(item.source_type || item.source || 'Performance item')
}

function deadlineTypeLabel(item: TimelineItem) {
  if (item.item_type === 'payment' || item.source === 'contract_payment_obligation' || item.source === 'payment_record') return 'Payment'
  if (['service', 'service_work'].includes(item.item_type || '')) {
    const text = `${item.title || ''} ${item.description || ''}`.toLowerCase()
    return text.includes('loan') || text.includes('fund') || text.includes('deliver') ? 'Delivery' : 'Work'
  }
  return 'Task'
}

function deadlineTypeStyle(label: string) {
  if (label === 'Payment') return { background: '#EFF6FF', color: '#1D4ED8' }
  if (label === 'Delivery') return { background: '#ECFDF5', color: '#047857' }
  if (label === 'Work') return { background: '#F0FDF4', color: '#15803D' }
  return { background: '#F8FAFC', color: '#475569' }
}

function deadlineDateKey(value?: string | null) {
  if (!value) return 'No date set'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'No date set'
  return date.toISOString().slice(0, 10)
}

function sortByDeadline(items: TimelineItem[]) {
  return [...items].sort((left, right) => {
    const leftTime = left.due_date ? new Date(left.due_date).getTime() : Number.MAX_SAFE_INTEGER
    const rightTime = right.due_date ? new Date(right.due_date).getTime() : Number.MAX_SAFE_INTEGER
    return leftTime - rightTime
  })
}

export default function AgreementPerformance() {
  const [agreements, setAgreements] = useState<PerformanceAgreement[]>([])
  const [selectedAgreement, setSelectedAgreement] = useState<PerformanceAgreement | null>(null)
  const [boardData, setBoardData] = useState<LifecycleBoardResponse | null>(null)
  const [activeTab, setActiveTab] = useState<BoardTab>('payments')
  const [selectedItem, setSelectedItem] = useState<TimelineItem | null>(null)
  const [showSource, setShowSource] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [boardLoading, setBoardLoading] = useState(false)
  const [actionBusy, setActionBusy] = useState('')
  const [reminderBusy, setReminderBusy] = useState('')
  const [attachmentBusy, setAttachmentBusy] = useState('')
  const [responseBusy, setResponseBusy] = useState('')
  const [attachmentLoading, setAttachmentLoading] = useState('')
  const [attachmentsByItemId, setAttachmentsByItemId] = useState<Record<string, LifecycleAttachment[]>>({})
  const [messagesByItemId, setMessagesByItemId] = useState<Record<string, LifecycleMessage[]>>({})
  const [messageLoading, setMessageLoading] = useState('')
  const [messageSending, setMessageSending] = useState('')
  const [messageError, setMessageError] = useState('')
  const [error, setError] = useState('')
  const [boardError, setBoardError] = useState('')
  const [feedback, setFeedback] = useState('')

  async function loadPerformanceAgreements() {
    setIsLoading(true)
    setError('')
    try {
      const response = await api.get<PerformanceListResponse>('/lifecycle/performance/')
      setAgreements(response.data.results || [])
    } catch (err) {
      setError(getErrorMessage(err, 'Unable to load Agreement Performance records.'))
    } finally {
      setIsLoading(false)
    }
  }

  async function openBoard(agreement: PerformanceAgreement, options: BoardViewOptions = {}) {
    const contractId = agreement.contract_id || agreement.contract.id
    setSelectedAgreement(agreement)
    setBoardLoading(true)
    setBoardError('')
    setFeedback('')
    if (options.resetView !== false) {
      setActiveTab('payments')
      setSelectedItem(null)
    }
    try {
      const response = await api.get<LifecycleBoardResponse>('/lifecycle/', { params: { contract: contractId } })
      setBoardData(response.data)
    } catch (err) {
      setBoardError(getErrorMessage(err, 'Unable to open Agreement Performance board.'))
      setBoardData(null)
    } finally {
      setBoardLoading(false)
    }
  }

  function findBoardItem(data: LifecycleBoardResponse | null, itemId: string) {
    const items = [
      ...((data?.views?.payments || []) as TimelineItem[]),
      ...((data?.views?.work_services || []) as TimelineItem[]),
      ...((data?.views?.due_dates || []) as TimelineItem[]),
    ]
    return items.find((item) => item.id === itemId) || null
  }

  async function refreshBoard(options: BoardViewOptions = {}) {
    if (!selectedAgreement) return null
    const contractId = selectedAgreement.contract_id || selectedAgreement.contract.id
    if (options.resetView !== false) setSelectedItem(null)
    const response = await api.get<LifecycleBoardResponse>('/lifecycle/', { params: { contract: contractId } })
    setBoardData(response.data)
    await loadPerformanceAgreements()
    return response.data
  }

  async function runAction(item: TimelineItem, action: string) {
    setActionBusy(`${item.id}:${action}`)
    setFeedback('')
    setBoardError('')
    try {
      const response = await api.post<TimelineItem>(`/lifecycle/items/${item.id}/actions/`, { action })
      const refreshed = await refreshBoard({ resetView: false })
      setSelectedItem(findBoardItem(refreshed, item.id) || response.data)
      setFeedback(`${performanceActionResultLabel(item, action)}.`)
    } catch (err) {
      setBoardError(getErrorMessage(err, 'Unable to record performance action.'))
    } finally {
      setActionBusy('')
    }
  }


  function replaceBoardItem(updated: TimelineItem) {
    setBoardData((current) => {
      if (!current?.views) return current
      const nextViews = { ...current.views }
      for (const key of ['payments', 'work_services', 'due_dates'] as const) {
        const values = nextViews[key]
        if (!Array.isArray(values)) continue
        nextViews[key] = values.map((item) => ('id' in item && item.id === updated.id ? updated : item)) as TimelineItem[]
      }
      return { ...current, views: nextViews }
    })
  }

  async function saveReminder(item: TimelineItem, reminderAt: string | null) {
    setReminderBusy(item.id)
    setFeedback('')
    setBoardError('')
    try {
      const response = await api.patch<TimelineItem>(`/lifecycle/items/${item.id}/`, { reminder_at: reminderAt })
      if (selectedItem?.id === response.data.id) setSelectedItem(response.data)
      replaceBoardItem(response.data)
      setFeedback(reminderAt ? 'Reminder saved.' : 'Reminder cleared.')
    } catch (err) {
      setBoardError(getErrorMessage(err, 'Unable to update reminder.'))
    } finally {
      setReminderBusy('')
    }
  }

  async function loadAttachments(itemId: string) {
    setAttachmentLoading(itemId)
    try {
      const response = await api.get<AttachmentListResponse>(`/lifecycle/items/${itemId}/attachments/`)
      setAttachmentsByItemId((current) => ({ ...current, [itemId]: response.data.results || [] }))
    } catch (err) {
      setBoardError(getErrorMessage(err, 'Unable to load proof and receipt attachments.'))
    } finally {
      setAttachmentLoading('')
    }
  }

  async function uploadProof(item: TimelineItem, file: File, note: string) {
    setAttachmentBusy(item.id)
    setFeedback('')
    setBoardError('')
    const formData = new FormData()
    formData.append('file', file)
    if (note.trim()) formData.append('note', note.trim())
    try {
      await postMultipart<LifecycleAttachment>(`/lifecycle/items/${item.id}/attachments/`, formData)
      await loadAttachments(item.id)
      const refreshed = await refreshBoard({ resetView: false })
      setSelectedItem(findBoardItem(refreshed, item.id) || item)
      setFeedback('Proof uploaded.')
    } catch (err) {
      setBoardError(getFetchErrorMessage(err, 'Unable to upload proof or receipt.'))
      throw err
    } finally {
      setAttachmentBusy('')
    }
  }

  async function submitProofResponse(item: TimelineItem, response: string, note: string) {
    setResponseBusy(`${item.id}:${response}`)
    setFeedback('')
    setBoardError('')
    try {
      await api.post<ProofResponse>(`/lifecycle/items/${item.id}/responses/`, { response, note })
      const refreshed = await refreshBoard({ resetView: false })
      setSelectedItem(findBoardItem(refreshed, item.id) || item)
      setFeedback('Response saved.')
    } catch (err) {
      setBoardError(getErrorMessage(err, 'Unable to save counterparty response.'))
    } finally {
      setResponseBusy('')
    }
  }

  async function loadMessages(itemId: string, options: { quiet?: boolean } = {}) {
    if (!itemId) return
    if (!options.quiet) {
      setMessageLoading(itemId)
      setMessageError('')
    }
    try {
      const response = await api.get<MessageListResponse>(`/lifecycle/items/${itemId}/messages/`)
      setMessagesByItemId((current) => ({ ...current, [itemId]: response.data.results || [] }))
    } catch (err) {
      if (!options.quiet) setMessageError(getErrorMessage(err, 'Unable to load messages.'))
    } finally {
      if (!options.quiet) setMessageLoading('')
    }
  }

  async function sendMessage(item: TimelineItem, body: string) {
    if (!item?.id) {
      setMessageError('Unable to send message for this obligation.')
      return
    }
    const trimmed = body.trim()
    if (!trimmed) return
    setMessageSending(item.id)
    setMessageError('')
    try {
      const response = await api.post<LifecycleMessage>(`/lifecycle/items/${item.id}/messages/`, { body: trimmed })
      setMessagesByItemId((current) => ({ ...current, [item.id]: [...(current[item.id] || []), response.data] }))
      void loadMessages(item.id, { quiet: true })
    } catch (err) {
      setMessageError(getErrorMessage(err, 'Unable to send message.'))
    } finally {
      setMessageSending('')
    }
  }

  useEffect(() => {
    void loadPerformanceAgreements()
  }, [])

  useEffect(() => {
    if (selectedItem) void loadAttachments(selectedItem.id)
  }, [selectedItem?.id])

  useEffect(() => {
    const selectedItemId = selectedItem?.id
    if (!selectedItemId) return
    void loadMessages(selectedItemId)
    const intervalId = window.setInterval(() => {
      void loadMessages(selectedItemId, { quiet: true })
    }, 4000)
    return () => window.clearInterval(intervalId)
  }, [selectedItem?.id])

  const rawBoardItems = useMemo(() => ([
    ...((boardData?.views?.payments || []) as TimelineItem[]),
    ...((boardData?.views?.work_services || []) as TimelineItem[]),
    ...((boardData?.views?.due_dates || []) as TimelineItem[]),
  ]), [boardData])
  const payments = useMemo(() => ((boardData?.views?.payments || []) as TimelineItem[]).filter(isDisplayableItem), [boardData])
  const workItems = useMemo(() => ((boardData?.views?.work_services || []) as TimelineItem[]).filter(isDisplayableItem), [boardData])
  const dueDates = useMemo(() => ((boardData?.views?.due_dates || []) as TimelineItem[]).filter(isDisplayableItem), [boardData])
  const events = useMemo(() => ((boardData?.views?.activity || boardData?.events || []) as TimelineEvent[]), [boardData])

  const selectedItemEvents = selectedItem ? itemHistoryEvents(events, selectedItem) : []
  const selectedItemAttachments = selectedItem ? attachmentsByItemId[selectedItem.id] || [] : []
  const selectedItemMessages = selectedItem ? messagesByItemId[selectedItem.id] || [] : []
  const activeItems = activeTab === 'payments' ? payments : activeTab === 'work' ? workItems : []
  const sourceText = signedAgreementText(boardData?.signed_version?.content_snapshot)

  return (
    <div style={{ padding: '32px 0' }}>
      <section style={{ background: 'white', border: '1px solid rgba(0,0,0,0.06)', borderRadius: 8, padding: 22, marginBottom: 18 }}>
        <p style={{ margin: '0 0 8px', fontSize: 11, fontWeight: 800, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#047857' }}>
          Performance
        </p>
        <h1 style={{ fontSize: 28, fontWeight: 800, color: '#0F1F3D', margin: 0, letterSpacing: 0 }}>
          Agreement Performance
        </h1>
        <p style={{ fontSize: 14, color: '#64748B', margin: '9px 0 0', maxWidth: 780, lineHeight: 1.55 }}>
          Track performed obligations, payments, delivery, confirmations, and records.
        </p>
      </section>

      {error && <section style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: 16, marginBottom: 18 }}><p style={{ fontSize: 13, color: '#B91C1C', margin: 0 }}>{error}</p></section>}

      {isLoading ? (
        <section style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 20 }}>
          <p style={{ fontSize: 13, color: '#64748B', margin: 0 }}>Loading Agreement Performance records...</p>
        </section>
      ) : agreements.length === 0 ? (
        <section style={{ background: '#F8FAFC', border: '1px solid #D1FAE5', borderRadius: 8, padding: 20, marginBottom: 18 }}>
          <h2 style={{ fontSize: 18, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>No agreements are ready for performance yet.</h2>
          <p style={{ fontSize: 13, color: '#475569', margin: '8px 0 0', maxWidth: 760, lineHeight: 1.6 }}>
            Performance starts when a party checks off the first performed obligation. Before that, a signed agreement appears here only after someone marks the Signed Agreement Timeline ready for Agreement Performance.
          </p>
        </section>
      ) : (
        <div style={{ display: 'grid', gap: 14, marginBottom: 18 }}>
          {agreements.map((agreement) => {
            const counterparty = agreement.counterparty?.name || agreement.counterparty?.email || agreement.contract.counterparty_name || agreement.contract.counterparty_email || 'Counterparty not set'
            const selected = selectedAgreement?.id === agreement.id
            return (
              <section key={agreement.id} style={{ background: selected ? '#F0FDF4' : 'white', border: `1px solid ${selected ? '#86EFAC' : '#E5E7EB'}`, borderRadius: 8, padding: 18 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 14, flexWrap: 'wrap' }}>
                  <div style={{ minWidth: 0 }}>
                    <p style={{ fontSize: 11, fontWeight: 800, color: '#047857', textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 6px' }}>Ready for tracking</p>
                    <h2 style={{ fontSize: 18, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>{agreement.title || agreement.contract.title || 'Untitled contract'}</h2>
                    <p style={{ fontSize: 13, color: '#64748B', margin: '7px 0 0' }}>{counterparty}</p>
                  </div>
                  <button type="button" onClick={() => void openBoard(agreement)} style={{ height: 34, border: '1px solid #0F1F3D', borderRadius: 8, background: '#0F1F3D', color: '#FFFFFF', padding: '0 12px', fontSize: 12, fontWeight: 800, cursor: 'pointer' }}>
                    {selected ? 'Refresh Performance' : 'Open Performance'}
                  </button>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10, marginTop: 16 }}>
                  <SummaryCell label="Status" value={agreement.status} />
                  <SummaryCell label="Payments" value={`${agreement.payment_count || 0} payment item(s)`} />
                  <SummaryCell label="Work" value={`${agreement.work_count ?? agreement.work_item_count ?? 0} work item(s)`} />
                  <SummaryCell label="Deadlines" value={`${agreement.due_date_count || 0} deadline(s)`} />
                  <SummaryCell label="Activity" value={`${agreement.activity_count || 0} event(s)`} />
                  <SummaryCell label="Ready Since" value={formatDate(agreement.lifecycle_agreement?.performance_ready_at)} />
                </div>
              </section>
            )
          })}
        </div>
      )}

      <section style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 18, minHeight: 260 }}>
        {!selectedAgreement ? (
          <div style={{ border: '1px dashed #CBD5E1', borderRadius: 8, padding: 18, background: '#FFFFFF' }}>
            <p style={{ fontSize: 14, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>Select a signed agreement to view performance records.</p>
            <p style={{ fontSize: 13, color: '#64748B', margin: '7px 0 0' }}>Open Performance loads the board for payments, work, due dates, activity, and future changes.</p>
          </div>
        ) : boardLoading ? (
          <p style={{ fontSize: 13, color: '#64748B', margin: 0 }}>Opening Agreement Performance board...</p>
        ) : boardError ? (
          <p style={{ fontSize: 13, color: '#B91C1C', margin: 0 }}>{boardError}</p>
        ) : boardData ? (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 14 }}>
              <div>
                <p style={{ fontSize: 11, fontWeight: 800, color: '#047857', textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 5px' }}>Performance board</p>
                <h2 style={{ fontSize: 20, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>{boardData.contract?.title || selectedAgreement.contract.title || 'Untitled contract'}</h2>
                <p style={{ fontSize: 12, color: '#64748B', margin: '6px 0 0' }}>Status: {agreementPerformanceStatusLabel(boardData.lifecycle_agreement?.status)}</p>
              </div>
              <button type="button" onClick={() => setShowSource(true)} style={secondaryButtonStyle}>View Signed Source</button>
            </div>

            {feedback && <div style={{ background: '#ECFDF5', border: '1px solid #A7F3D0', borderRadius: 8, padding: 12, marginBottom: 12 }}><p style={{ fontSize: 13, color: '#047857', margin: 0 }}>{feedback}</p></div>}

            {!selectedItem && (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
                {BOARD_TABS.map((tab) => (
                  <button key={tab.key} type="button" onClick={() => setActiveTab(tab.key)} style={{ border: '1px solid #CBD5E1', borderRadius: 8, background: activeTab === tab.key ? '#0F1F3D' : '#FFFFFF', color: activeTab === tab.key ? '#FFFFFF' : '#334155', padding: '8px 11px', fontSize: 12, fontWeight: 800, cursor: 'pointer' }}>
                    {tab.label}
                  </button>
                ))}
              </div>
            )}

            {selectedItem ? (
              <PerformanceThread
                agreementTitle={boardData.contract?.title || selectedAgreement.contract.title || selectedAgreement.title || 'Untitled contract'}
                item={selectedItem}
                events={selectedItemEvents}
                attachments={selectedItemAttachments}
                attachmentsLoading={attachmentLoading === selectedItem.id}
                attachmentBusy={attachmentBusy === selectedItem.id}
                messages={selectedItemMessages}
                messagesLoading={messageLoading === selectedItem.id}
                messageSending={messageSending === selectedItem.id}
                messageError={messageError}
                responseBusy={responseBusy}
                busy={actionBusy}
                onBack={() => setSelectedItem(null)}
                onViewSource={() => setShowSource(true)}
                onAction={(action) => void runAction(selectedItem, action)}
                onUploadProof={(file, note) => uploadProof(selectedItem, file, note)}
                onSendMessage={(body) => void sendMessage(selectedItem, body)}
                onRespond={(response, note) => void submitProofResponse(selectedItem, response, note)}
              />
            ) : activeTab === 'activity' ? (
              <ActivityPanel events={events} items={rawBoardItems} agreementTitle={boardData.contract?.title || selectedAgreement.contract.title || selectedAgreement.title} />
            ) : activeTab === 'changes' ? (
              <div style={{ border: '1px dashed #CBD5E1', borderRadius: 8, padding: 18, background: '#FFFFFF' }}>
                <p style={{ fontSize: 13, color: '#64748B', margin: 0 }}>Changes and add-ons will be managed here.</p>
              </div>
            ) : activeTab === 'due_dates' ? (
              <DeadlinesPanel items={dueDates} onOpen={setSelectedItem} onViewSource={() => setShowSource(true)} />
            ) : activeItems.length === 0 ? (
              <div style={{ border: '1px dashed #CBD5E1', borderRadius: 8, padding: 18, background: '#FFFFFF' }}>
                <p style={{ fontSize: 13, color: '#64748B', margin: 0 }}>No records found for this panel.</p>
              </div>
            ) : (
              <div style={{ display: 'grid', gap: 10 }}>
                {activeItems.map((item) => (
                  <PerformanceCard
                    key={`${item.source || item.source_type}-${item.id}`}
                    item={item}
                    onOpen={() => setSelectedItem(item)}
                    onViewSource={() => setShowSource(true)}
                    reminderBusy={reminderBusy === item.id}
                    onReminder={(reminderAt) => void saveReminder(item, reminderAt)}
                  />
                ))}
              </div>
            )}
          </div>
        ) : null}
      </section>

      {showSource && (
        <Modal title="Signed agreement source" onClose={() => setShowSource(false)}>
          <pre style={{ maxHeight: '70vh', overflow: 'auto', whiteSpace: 'pre-wrap', background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 16, fontSize: 13, lineHeight: 1.6, color: '#334155', fontFamily: 'inherit' }}>{sourceText}</pre>
        </Modal>
      )}
    </div>
  )
}

function SummaryCell({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 12 }}>
      <p style={{ fontSize: 11, color: '#94A3B8', margin: 0, fontWeight: 800, textTransform: 'uppercase' }}>{label}</p>
      <p style={{ fontSize: 13, color: '#0F1F3D', margin: '5px 0 0', fontWeight: 800 }}>{value}</p>
    </div>
  )
}

function PerformanceCard({
  item,
  onOpen,
  onViewSource,
  onReminder,
  reminderBusy,
}: {
  item: TimelineItem
  onOpen: () => void
  onViewSource: () => void
  onReminder: (reminderAt: string | null) => void
  reminderBusy: boolean
}) {
  const action = itemAction(item)
  const [reminderDraft, setReminderDraft] = useState(toDateTimeInput(item.reminder_at))
  useEffect(() => {
    setReminderDraft(toDateTimeInput(item.reminder_at))
  }, [item.id, item.reminder_at])
  return (
    <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, padding: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
        <div style={{ minWidth: 0 }}>
          <p style={{ fontSize: 15, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>{item.title || humanize(item.item_type)}</p>
          <p style={{ fontSize: 11, color: '#94A3B8', margin: '5px 0 0' }}>{sourceLabel(item)}</p>
        </div>
        <span style={{ alignSelf: 'flex-start', borderRadius: 999, padding: '4px 9px', fontSize: 11, fontWeight: 800, ...statusStyle(item.status || item.lifecycle_state) }}>{performanceStatusLabel(item)}</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8, marginTop: 12 }}>
        <SmallFact label="Amount" value={formatMoney(item.amount, item.currency || 'USD')} />
        <SmallFact label="Due / Delivery" value={dueDateLabel(item.due_date)} />
        <SmallFact label="Responsible" value={item.responsible_party || 'Not set'} />
      </div>
      {item.description && <p style={{ fontSize: 12, color: '#475569', lineHeight: 1.5, margin: '10px 0 0' }}>{item.description}</p>}
      {!isCompletedPerformanceItem(item) && (
        <section style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 10, marginTop: 12 }}>
          <p style={{ fontSize: 10, color: '#64748B', margin: 0, fontWeight: 900, textTransform: 'uppercase' }}>Private reminder</p>
          <p style={{ fontSize: 12, color: '#334155', margin: '4px 0 8px', fontWeight: 800 }}>{reminderLabel(item.reminder_at)}</p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <input
              type="datetime-local"
              value={reminderDraft}
              onChange={(event) => setReminderDraft(event.target.value)}
              style={{ height: 34, minWidth: 190, border: '1px solid #CBD5E1', borderRadius: 8, padding: '0 10px', fontSize: 12, color: '#0F1F3D', background: '#FFFFFF' }}
            />
            <button type="button" onClick={() => onReminder(fromDateTimeInput(reminderDraft))} disabled={reminderBusy || !reminderDraft} style={{ ...amberButtonStyle, opacity: reminderBusy || !reminderDraft ? 0.65 : 1, cursor: reminderBusy || !reminderDraft ? 'default' : 'pointer' }}>
              {reminderBusy ? 'Saving...' : item.reminder_at ? 'Update Reminder' : 'Set Reminder'}
            </button>
            <button type="button" onClick={() => { setReminderDraft(''); onReminder(null) }} disabled={reminderBusy || !item.reminder_at} style={{ ...secondaryButtonStyle, opacity: reminderBusy || !item.reminder_at ? 0.55 : 1, cursor: reminderBusy || !item.reminder_at ? 'default' : 'pointer' }}>
              Clear
            </button>
          </div>
        </section>
      )}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
        <button type="button" onClick={onOpen} style={inspectButtonStyle}>Open Detail</button>
        <button type="button" onClick={onViewSource} style={secondaryButtonStyle}>View Source</button>
        {!action && <span style={{ fontSize: 11, color: '#64748B', alignSelf: 'center' }}>Action unavailable for this generated record.</span>}
      </div>
    </div>
  )
}

function SmallFact({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 10 }}>
      <p style={{ fontSize: 10, color: '#94A3B8', fontWeight: 800, textTransform: 'uppercase', margin: 0 }}>{label}</p>
      <p style={{ fontSize: 12, color: '#0F1F3D', fontWeight: 800, margin: '4px 0 0' }}>{value}</p>
    </div>
  )
}

function DeadlinesPanel({ items, onOpen, onViewSource }: { items: TimelineItem[]; onOpen: (item: TimelineItem) => void; onViewSource: () => void }) {
  const sorted = sortByDeadline(items.filter((item) => item.due_date))
  if (sorted.length === 0) {
    return <div style={{ border: '1px dashed #CBD5E1', borderRadius: 8, padding: 18, background: '#FFFFFF' }}><p style={{ fontSize: 13, color: '#64748B', margin: 0 }}>No upcoming deadlines found.</p></div>
  }

  let currentDate = ''
  return (
    <div style={{ display: 'grid', gap: 10 }}>
      {sorted.map((item) => {
        const key = deadlineDateKey(item.due_date)
        const showDateHeader = key !== currentDate
        currentDate = key
        const type = deadlineTypeLabel(item)
        const amount = item.amount ? formatMoney(item.amount, item.currency || 'USD') : ''
        return (
          <div key={`${item.source || item.source_type}-${item.id}`}>
            {showDateHeader && (
              <p style={{ fontSize: 12, fontWeight: 900, color: '#047857', margin: '4px 0 8px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                {dueDateLabel(item.due_date)}
              </p>
            )}
            <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, padding: 12, display: 'grid', gridTemplateColumns: '104px minmax(0, 1fr) auto', gap: 12, alignItems: 'center' }}>
              <div>
                <p style={{ fontSize: 20, lineHeight: 1, fontWeight: 900, color: '#0F1F3D', margin: 0 }}>{dueDateLabel(item.due_date)}</p>
                <p style={{ fontSize: 10, color: '#94A3B8', fontWeight: 800, margin: '5px 0 0', textTransform: 'uppercase' }}>Deadline</p>
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 5 }}>
                  <span style={{ borderRadius: 999, padding: '3px 8px', fontSize: 10, fontWeight: 900, ...deadlineTypeStyle(type) }}>{type}</span>
                  <span style={{ borderRadius: 999, padding: '3px 8px', fontSize: 10, fontWeight: 900, ...statusStyle(item.status || item.lifecycle_state) }}>{performanceStatusLabel(item)}</span>
                </div>
                <p style={{ fontSize: 14, fontWeight: 900, color: '#0F1F3D', margin: 0 }}>{item.title || humanize(item.item_type)}</p>
                <p style={{ fontSize: 12, color: '#64748B', margin: '5px 0 0' }}>Responsible: {item.responsible_party || 'Not set'}{amount ? ` · ${amount}` : ''}</p>
                {item.reminder_at && !isCompletedPerformanceItem(item) && <p style={{ fontSize: 11, color: '#475569', fontWeight: 900, margin: '5px 0 0' }}>Private reminder: {reminderLabel(item.reminder_at)}</p>}
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                <button type="button" onClick={() => onOpen(item)} style={secondaryButtonStyle}>Open Detail</button>
                <button type="button" onClick={onViewSource} style={secondaryButtonStyle}>View Source</button>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function ActivityPanel({ events, items, agreementTitle }: { events: TimelineEvent[]; items: TimelineItem[]; agreementTitle?: string }) {
  const itemById = new Map(items.map((item) => [item.id, item]))
  const performanceEvents = events.filter(isPerformanceActivityEvent)

  if (performanceEvents.length === 0) {
    return <div style={{ border: '1px dashed #CBD5E1', borderRadius: 8, padding: 18, background: '#FFFFFF' }}><p style={{ fontSize: 13, color: '#64748B', margin: 0 }}>No shared performance activity recorded yet.</p></div>
  }

  return (
    <div style={{ display: 'grid', gap: 8 }}>
      {performanceEvents.map((event) => {
        const itemId = metadataString(event.metadata, 'lifecycle_item_id') || metadataString(event.metadata, 'item_id')
        const item = itemById.get(itemId)
        const itemTitle = item?.title || metadataString(event.metadata, 'item_title') || event.description || 'this obligation'
        const actor = metadataString(event.metadata, 'actor_label') || item?.responsible_party || 'A party'
        const verb = performanceEventVerb(event)
        const result = metadataString(event.metadata, 'result_status') || metadataString(event.metadata, 'status')
        const sentence = verb ? `${actor} marked "${itemTitle}" as ${verb}.` : event.description || performanceEventActionLabel(event)
        return (
          <div key={event.id} style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, padding: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap', alignItems: 'flex-start' }}>
              <div style={{ minWidth: 0 }}>
                <p style={{ fontSize: 13, fontWeight: 900, color: '#0F1F3D', margin: 0 }}>{performanceEventActionLabel(event)}</p>
                <p style={{ fontSize: 12, color: '#334155', margin: '6px 0 0', lineHeight: 1.5 }}>{sentence}</p>
              </div>
              {result && <span style={{ borderRadius: 999, padding: '4px 9px', fontSize: 11, fontWeight: 900, ...statusStyle(result) }}>{performanceStatusLabel({ ...(item || {}), item_type: item?.item_type, status: result })}</span>}
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
              <span style={{ fontSize: 11, color: '#64748B', fontWeight: 800 }}>{eventTimeLabel(event.occurred_at)}</span>
              {agreementTitle && <span style={{ fontSize: 11, color: '#94A3B8' }}>{agreementTitle}</span>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function ItemHistoryPanel({ events, item }: { events: TimelineEvent[]; item: TimelineItem }) {
  if (events.length === 0) {
    return <div style={{ border: '1px dashed #CBD5E1', borderRadius: 8, padding: 14, background: '#FFFFFF' }}><p style={{ fontSize: 13, color: '#64748B', margin: 0 }}>No shared history recorded for this obligation yet.</p></div>
  }

  return (
    <div style={{ display: 'grid', gap: 8 }}>
      {events.map((event) => {
        const result = metadataString(event.metadata, 'result_status') || metadataString(event.metadata, 'status')
        const actor = metadataString(event.metadata, 'actor_label') || item.responsible_party || 'A party'
        const verb = performanceEventVerb(event)
        const sentence = verb ? `${actor} marked "${item.title || 'this obligation'}" as ${verb}.` : event.description || performanceEventActionLabel(event)
        return (
          <div key={event.id} style={{ border: '1px solid #E5E7EB', borderRadius: 8, background: '#FFFFFF', padding: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
              <div>
                <p style={{ fontSize: 12, fontWeight: 900, color: '#0F1F3D', margin: 0 }}>{performanceEventActionLabel(event)}</p>
                <p style={{ fontSize: 12, color: '#334155', margin: '5px 0 0', lineHeight: 1.5 }}>{sentence}</p>
              </div>
              {result && <span style={{ alignSelf: 'flex-start', borderRadius: 999, padding: '4px 9px', fontSize: 11, fontWeight: 900, ...statusStyle(result) }}>{performanceStatusLabel({ ...item, status: result })}</span>}
            </div>
            <p style={{ fontSize: 11, color: '#94A3B8', margin: '7px 0 0', fontWeight: 800 }}>{eventTimeLabel(event.occurred_at)}</p>
          </div>
        )
      })}
    </div>
  )
}

function PerformanceActionSection({
  action,
  actionBusy,
  onViewSource,
  onAction,
}: {
  item: TimelineItem
  action: { action: string; label: string } | null
  actionBusy: boolean
  onViewSource: () => void
  onAction: (action: string) => void
}) {
  return (
    <section style={{ borderBottom: '1px solid #E5E7EB', paddingBottom: 14 }}>
      <p style={{ fontSize: 12, color: '#94A3B8', margin: 0, fontWeight: 900, textTransform: 'uppercase' }}>Performance Action</p>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10, alignItems: 'center' }}>
        <button type="button" onClick={onViewSource} style={secondaryButtonStyle}>View Source</button>
        {action ? (
          <button type="button" onClick={() => onAction(action.action)} disabled={actionBusy} style={{ ...primaryButtonStyle, opacity: actionBusy ? 0.7 : 1, cursor: actionBusy ? 'default' : 'pointer' }}>
            {actionBusy ? 'Recording...' : action.label}
          </button>
        ) : (
          <span style={{ fontSize: 12, color: '#64748B', alignSelf: 'center' }}>No direct performance action is available for this item.</span>
        )}
      </div>
      {action && (
        <p style={{ fontSize: 12, color: '#64748B', margin: '8px 0 0', lineHeight: 1.5 }}>Upload proof or receipt below before marking this obligation performed.</p>
      )}
    </section>
  )
}

function fileSizeLabel(value?: number) {
  if (!value) return 'Size not recorded'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${Math.round(value / 102.4) / 10} KB`
  return `${Math.round(value / (1024 * 102.4)) / 10} MB`
}

function ProofReceiptsSection({
  attachments,
  loading,
  busy,
  canUpload,
  onUpload,
}: {
  attachments: LifecycleAttachment[]
  loading: boolean
  busy: boolean
  canUpload: boolean
  onUpload: (file: File, note: string) => Promise<void>
}) {
  const [file, setFile] = useState<File | null>(null)
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [inputKey, setInputKey] = useState(0)

  function handleFileChange(selectedFile: File | null) {
    setFile(selectedFile)
    setError(selectedFile ? proofFileValidationMessage(selectedFile) : '')
  }

  async function submitUpload() {
    const validation = proofFileValidationMessage(file)
    if (validation) {
      setError(validation)
      return
    }
    try {
      await onUpload(file as File, note)
      setFile(null)
      setNote('')
      setError('')
      setInputKey((value) => value + 1)
    } catch {
      // The page-level error banner reports the upload failure.
    }
  }

  return (
    <section style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, padding: 14 }}>
      <p style={{ fontSize: 12, color: '#94A3B8', margin: 0, fontWeight: 900, textTransform: 'uppercase' }}>Proof / Receipt</p>
      <div style={{ display: 'grid', gap: 8, marginTop: 10 }}>
        {loading ? (
          <p style={{ fontSize: 13, color: '#64748B', margin: 0 }}>Loading proof and receipts...</p>
        ) : attachments.length === 0 ? (
          <div style={{ border: '1px dashed #CBD5E1', borderRadius: 8, padding: 12, background: '#FFFFFF' }}>
            <p style={{ fontSize: 13, color: '#64748B', margin: 0 }}>No proof or receipts uploaded for this obligation yet.</p>
          </div>
        ) : attachments.map((attachment) => {
          const uploader = attachment.uploaded_by?.name || attachment.uploaded_by?.email || attachment.uploaded_by_email || 'A party'
          const filename = attachment.filename || attachment.original_filename || 'Attachment'
          return (
            <div key={attachment.id} style={{ border: '1px solid #E5E7EB', borderRadius: 8, background: '#F8FAFC', padding: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
                <div style={{ minWidth: 0 }}>
                  <p style={{ fontSize: 13, fontWeight: 900, color: '#0F1F3D', margin: 0, overflowWrap: 'anywhere' }}>{filename}</p>
                  <p style={{ fontSize: 11, color: '#64748B', margin: '5px 0 0' }}>Uploaded by {uploader} · {eventTimeLabel(attachment.created_at)} · {fileSizeLabel(attachment.file_size)}</p>
                </div>
                {attachment.file_url && (
                  <a href={attachment.file_url} target="_blank" rel="noreferrer" style={{ ...inspectButtonStyle, textDecoration: 'none', alignSelf: 'flex-start' }}>Open / View</a>
                )}
              </div>
              {attachment.note && <p style={{ fontSize: 12, color: '#334155', lineHeight: 1.5, margin: '8px 0 0' }}>{attachment.note}</p>}
            </div>
          )
        })}
      </div>

      {canUpload && (
        <div style={{ display: 'grid', gap: 10, background: '#FFF7ED', border: '1px solid #FED7AA', borderRadius: 8, padding: 12, marginTop: 14 }}>
          <p style={{ fontSize: 12, color: '#9A3412', margin: 0, fontWeight: 900 }}>Add another proof / receipt</p>
          <input
            key={inputKey}
            type="file"
            onChange={(event) => handleFileChange(event.target.files?.[0] || null)}
            style={{ border: '1px solid #CBD5E1', borderRadius: 8, padding: 10, background: '#FFFFFF', color: '#0F1F3D', fontSize: 12 }}
          />
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Optional note"
            rows={3}
            style={{ border: '1px solid #CBD5E1', borderRadius: 8, padding: 10, background: '#FFFFFF', color: '#0F1F3D', fontSize: 12, resize: 'vertical', fontFamily: 'inherit' }}
          />
          {error && <p style={{ fontSize: 12, color: '#B91C1C', margin: 0, fontWeight: 800 }}>{error}</p>}
          <div>
            <button type="button" onClick={() => void submitUpload()} disabled={busy || !file || Boolean(error)} style={{ ...amberButtonStyle, opacity: busy || !file || Boolean(error) ? 0.65 : 1, cursor: busy || !file || Boolean(error) ? 'default' : 'pointer' }}>
              {busy ? 'Uploading...' : 'Upload Proof / Receipt'}
            </button>
          </div>
        </div>
      )}
    </section>
  )
}

function proofResponseLabel(value?: string) {
  if (value === 'received') return 'Received'
  if (value === 'still_waiting') return 'Still waiting'
  if (value === 'not_received') return 'Not received'
  return value ? humanize(value) : 'No response yet'
}

function CounterpartyReviewSection({
  item,
  busy,
  onRespond,
}: {
  item: TimelineItem
  busy: string
  onRespond: (response: string, note: string) => void
}) {
  const [note, setNote] = useState('')
  const latest = item.latest_response
  const canRespond = Boolean(item.can_respond_to_proof && !latest)
  const options = [
    { value: 'received', label: 'Received' },
    { value: 'still_waiting', label: 'Still waiting' },
    { value: 'not_received', label: 'Not received' },
  ]

  return (
    <section style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, padding: 14 }}>
      <p style={{ fontSize: 12, color: '#94A3B8', margin: 0, fontWeight: 900, textTransform: 'uppercase' }}>Counterparty Review</p>
      {latest ? (
        <div style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 12, marginTop: 10 }}>
          <p style={{ fontSize: 13, color: '#0F1F3D', margin: 0, fontWeight: 900 }}>{proofResponseLabel(latest.response)}</p>
          <p style={{ fontSize: 11, color: '#64748B', margin: '5px 0 0' }}>Responded by {latest.responder?.name || latest.responder?.email || 'A party'} · {eventTimeLabel(latest.updated_at || latest.created_at)}</p>
          {latest.note && <p style={{ fontSize: 12, color: '#334155', margin: '8px 0 0', lineHeight: 1.5 }}>{latest.note}</p>}
        </div>
      ) : !canRespond ? (
        <p style={{ fontSize: 13, color: '#64748B', margin: '8px 0 0' }}>Waiting for counterparty response.</p>
      ) : null}

      {canRespond && (
        <div style={{ display: 'grid', gap: 10, marginTop: 12 }}>
          <p style={{ fontSize: 13, color: '#334155', margin: 0, fontWeight: 800 }}>Did you receive this?</p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {options.map((option) => {
              const isBusy = busy === `${item.id}:${option.value}`
              return (
                <button key={option.value} type="button" onClick={() => onRespond(option.value, note)} disabled={Boolean(busy)} style={{ ...inspectButtonStyle, opacity: busy && !isBusy ? 0.55 : 1, cursor: busy ? 'default' : 'pointer' }}>
                  {isBusy ? 'Saving...' : option.label}
                </button>
              )
            })}
          </div>
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Optional note"
            rows={3}
            style={{ border: '1px solid #CBD5E1', borderRadius: 8, padding: 10, background: '#FFFFFF', color: '#0F1F3D', fontSize: 12, resize: 'vertical', fontFamily: 'inherit' }}
          />
        </div>
      )}
    </section>
  )
}


function MessagesPanel({
  messages,
  loading,
  sending,
  error,
  onSend,
}: {
  messages: LifecycleMessage[]
  loading: boolean
  sending: boolean
  error: string
  onSend: (body: string) => void
}) {
  const [draft, setDraft] = useState('')
  const listRef = useRef<HTMLDivElement | null>(null)
  const safeMessages = Array.isArray(messages) ? messages.filter(Boolean) : []

  useEffect(() => {
    const node = listRef.current
    if (node) node.scrollTop = node.scrollHeight
  }, [safeMessages.length])

  function submit() {
    const trimmed = draft.trim()
    if (!trimmed || sending) return
    onSend(trimmed)
    setDraft('')
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== 'Enter' || event.shiftKey) return
    event.preventDefault()
    submit()
  }

  return (
    <section style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, padding: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'center', marginBottom: 10 }}>
        <p style={{ fontSize: 12, color: '#94A3B8', margin: 0, fontWeight: 900, textTransform: 'uppercase' }}>Messages</p>
        {loading && <span style={{ fontSize: 11, color: '#64748B', fontWeight: 800 }}>Loading...</span>}
      </div>
      <div ref={listRef} style={{ display: 'grid', gap: 10, maxHeight: 320, overflowY: 'auto', background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 12 }}>
        {safeMessages.length === 0 ? (
          <p style={{ fontSize: 13, color: '#64748B', margin: 0 }}>No messages yet. Start the conversation.</p>
        ) : safeMessages.map((message, index) => {
          const mine = Boolean(message.is_mine)
          const sender = message.sender?.name || message.sender?.email || message.sender_email || 'A party'
          const createdAt = message.created_at || message.updated_at || ''
          const body = typeof message.body === 'string' ? message.body : ''
          return (
            <div key={message.id || `${createdAt}-${index}`} style={{ display: 'grid', justifyItems: mine ? 'end' : 'start' }}>
              <div style={{ maxWidth: '78%', background: mine ? '#0F1F3D' : '#FFFFFF', color: mine ? '#FFFFFF' : '#0F1F3D', border: mine ? '1px solid #0F1F3D' : '1px solid #E5E7EB', borderRadius: 8, padding: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', marginBottom: 6, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 11, fontWeight: 900, color: mine ? '#DBEAFE' : '#334155' }}>{mine ? 'You' : sender}</span>
                  <span style={{ fontSize: 10, fontWeight: 800, color: mine ? '#BFDBFE' : '#94A3B8' }}>{eventTimeLabel(createdAt)}</span>
                </div>
                <p style={{ fontSize: 13, lineHeight: 1.5, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', margin: 0 }}>{body}</p>
              </div>
            </div>
          )
        })}
      </div>
      {error && <p style={{ fontSize: 12, color: '#B91C1C', margin: '10px 0 0', fontWeight: 800 }}>{error}</p>}
      <div style={{ display: 'grid', gap: 8, marginTop: 10 }}>
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Write a message"
          maxLength={2000}
          rows={3}
          style={{ border: '1px solid #CBD5E1', borderRadius: 8, padding: 10, background: '#FFFFFF', color: '#0F1F3D', fontSize: 13, resize: 'vertical', fontFamily: 'inherit' }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, color: '#94A3B8' }}>Press Enter to send. Shift+Enter adds a line.</span>
          <button type="button" onClick={submit} disabled={sending || !draft.trim()} style={{ ...primaryButtonStyle, opacity: sending || !draft.trim() ? 0.65 : 1, cursor: sending || !draft.trim() ? 'default' : 'pointer' }}>
            {sending ? 'Sending...' : 'Send'}
          </button>
        </div>
      </div>
    </section>
  )
}


function PlaceholderPanel({ title }: { title: string }) {
  return (
    <section style={{ background: '#FFFFFF', border: '1px dashed #CBD5E1', borderRadius: 8, padding: 14 }}>
      <p style={{ fontSize: 11, color: '#94A3B8', margin: 0, fontWeight: 900, textTransform: 'uppercase' }}>{title}</p>
      <p style={{ fontSize: 13, color: '#64748B', margin: '6px 0 0' }}>Coming soon</p>
    </section>
  )
}

function PerformanceThread({
  agreementTitle,
  item,
  events,
  attachments,
  attachmentsLoading,
  attachmentBusy,
  messages,
  messagesLoading,
  messageSending,
  messageError,
  responseBusy,
  busy,
  onBack,
  onViewSource,
  onAction,
  onUploadProof,
  onSendMessage,
  onRespond,
}: {
  agreementTitle: string
  item: TimelineItem
  events: TimelineEvent[]
  attachments: LifecycleAttachment[]
  attachmentsLoading: boolean
  attachmentBusy: boolean
  messages: LifecycleMessage[]
  messagesLoading: boolean
  messageSending: boolean
  messageError: string
  responseBusy: string
  busy: string
  onBack: () => void
  onViewSource: () => void
  onAction: (action: string) => void
  onUploadProof: (file: File, note: string) => Promise<void>
  onSendMessage: (body: string) => void
  onRespond: (response: string, note: string) => void
}) {
  const action = itemAction(item)
  const actionBusy = action ? busy === `${item.id}:${action.action}` : false

  return (
    <div style={{ display: 'grid', gap: 14 }}>
      <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, padding: 16 }}>
        <button type="button" onClick={onBack} style={{ ...secondaryButtonStyle, marginBottom: 12 }}>Back to Performance Board</button>
        <h3 style={{ margin: 0, fontSize: 22, fontWeight: 900, color: '#0F1F3D' }}>{item.title || humanize(item.item_type)}</h3>
        <p style={{ fontSize: 13, color: '#64748B', margin: '7px 0 0' }}>{agreementTitle}</p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
          <span style={{ borderRadius: 999, padding: '4px 9px', fontSize: 11, fontWeight: 900, background: '#EFF6FF', color: '#1D4ED8' }}>{itemTypeLabel(item)}</span>
          <span style={{ borderRadius: 999, padding: '4px 9px', fontSize: 11, fontWeight: 900, ...statusStyle(item.status || item.lifecycle_state) }}>{performanceStatusLabel(item)}</span>
        </div>
      </div>

      <section style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, padding: 16 }}>
        <div style={{ display: 'grid', gap: 14 }}>
          <section style={{ borderBottom: '1px solid #E5E7EB', paddingBottom: 14 }}>
            <p style={{ fontSize: 12, color: '#94A3B8', margin: 0, fontWeight: 900, textTransform: 'uppercase' }}>Obligation record</p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10, marginTop: 10 }}>
              <SummaryCell label="Responsible" value={item.responsible_party || 'Not set'} />
              <SummaryCell label="Amount" value={formatMoney(item.amount, item.currency || 'USD')} />
              <SummaryCell label="Due / Delivery" value={dueDateLabel(item.due_date)} />
              <SummaryCell label={completionDateTitle(item)} value={completionDateLabel(events, item)} />
              <SummaryCell label="Current Status" value={performanceStatusLabel(item)} />
            </div>
            <p style={{ fontSize: 13, color: '#334155', lineHeight: 1.55, margin: '12px 0 0' }}>{item.description || sourceLabel(item) || 'No additional detail recorded for this performance item.'}</p>
          </section>

          {action && (
            <PerformanceActionSection
              item={item}
              action={action}
              actionBusy={actionBusy}
              onViewSource={onViewSource}
              onAction={onAction}
            />
          )}

          <ProofReceiptsSection attachments={attachments} loading={attachmentsLoading} busy={attachmentBusy} canUpload={Boolean(item.can_upload_proof)} onUpload={onUploadProof} />
          <MessagesPanel messages={messages} loading={messagesLoading} sending={messageSending} error={messageError} onSend={onSendMessage} />
          <CounterpartyReviewSection item={item} busy={responseBusy} onRespond={onRespond} />

          <section style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, padding: 14 }}>
            <p style={{ fontSize: 12, color: '#94A3B8', margin: 0, fontWeight: 900, textTransform: 'uppercase' }}>Item History</p>
            <div style={{ marginTop: 10 }}>
              <ItemHistoryPanel events={events} item={item} />
            </div>
          </section>
        </div>
      </section>
    </div>
  )
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.45)', zIndex: 80, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }} onClick={onClose}>
      <div style={{ width: '100%', maxWidth: 820, maxHeight: '90vh', overflow: 'auto', background: '#FFFFFF', borderRadius: 12, border: '1px solid rgba(15,23,42,0.08)', boxShadow: '0 20px 60px rgba(15,23,42,0.3)', padding: 20 }} onClick={(event) => event.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          <h3 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: '#0F1F3D' }}>{title}</h3>
          <button type="button" onClick={onClose} style={secondaryButtonStyle}>Close</button>
        </div>
        {children}
      </div>
    </div>
  )
}

const primaryButtonStyle = {
  border: '1px solid #0F1F3D',
  borderRadius: 8,
  background: '#0F1F3D',
  color: '#FFFFFF',
  padding: '8px 12px',
  fontSize: 12,
  fontWeight: 800,
  cursor: 'pointer',
}

const amberButtonStyle = {
  border: '1px solid #B45309',
  borderRadius: 8,
  background: '#B45309',
  color: '#FFFFFF',
  padding: '8px 12px',
  fontSize: 12,
  fontWeight: 800,
  cursor: 'pointer',
}

const inspectButtonStyle = {
  border: '1px solid #BFDBFE',
  borderRadius: 8,
  background: '#EFF6FF',
  color: '#1D4ED8',
  padding: '8px 12px',
  fontSize: 12,
  fontWeight: 800,
  cursor: 'pointer',
}

const secondaryButtonStyle = {
  border: '1px solid #CBD5E1',
  borderRadius: 8,
  background: '#FFFFFF',
  color: '#334155',
  padding: '8px 12px',
  fontSize: 12,
  fontWeight: 800,
  cursor: 'pointer',
}

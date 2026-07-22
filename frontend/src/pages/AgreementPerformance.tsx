import { useEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent, type ReactNode } from 'react'
import api, { tokenStorage } from '@/api/client'
import { dateOnlyInputValue, dateOnlySortKey, formatDateOnly } from '@/lib/dateOnly'

type BoardTab = 'payments' | 'work' | 'due_dates' | 'my_obligations' | 'activity' | 'changes'

type BoardViewOptions = { resetView?: boolean }

const LAST_PERFORMANCE_AGREEMENT_KEY = 'agreementPerformance:lastAgreementId'

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
  responsible_user_id?: string | null
  assigned_to_current_user?: boolean
  is_mine?: boolean
  beneficiary_party?: string | null
  due_date?: string | null
  due_state?: string
  is_overdue?: boolean
  is_due_today?: boolean
  days_overdue?: number
  days_until_due?: number
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
  proof_attachment_count?: number
  proof_submitted?: boolean
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

type LifecycleChangeProposalMessage = {
  id: string
  proposal_id?: string
  lifecycle_agreement_id?: string
  contract_id?: string
  body: string
  sender?: { id?: string; email?: string; name?: string } | null
  sender_email?: string | null
  created_at?: string
  updated_at?: string
  is_mine?: boolean
}

type ProposalMessageListResponse = { results: LifecycleChangeProposalMessage[] }

type PartyOption = {
  value: 'initiator' | 'counterparty' | string
  label: string
  email?: string | null
}

type LifecycleChangeProposal = {
  id: string
  lifecycle_agreement_id?: string
  contract_id?: string
  contract_title?: string | null
  proposal_type: 'add_on' | 'change_order' | string
  status: 'proposed' | 'accepted' | 'rejected' | string
  proposed_by?: { id?: string; email?: string; name?: string } | null
  proposed_by_email?: string | null
  affected_item?: { id: string; title?: string; item_type?: string; status?: string; due_date?: string | null; amount?: string | null; responsible_party?: string | null } | null
  affected_item_id?: string | null
  created_item?: { id: string; title?: string; item_type?: string; status?: string; due_date?: string | null; amount?: string | null; responsible_party?: string | null } | null
  created_item_id?: string | null
  created_items?: Array<{ id: string; title?: string; item_type?: string; status?: string; due_date?: string | null; amount?: string | null; responsible_party?: string | null }>
  created_item_ids?: string[]
  generated_item_count?: number
  generation_mode?: 'single' | 'before_each_payment_deadline' | string
  title: string
  description: string
  responsible_party?: string | null
  responsible_party_label?: string | null
  amount?: string | null
  due_date?: string | null
  note?: string | null
  decision_note?: string | null
  final_due_date?: string | null
  final_amount?: string | null
  final_responsible_party?: string | null
  created_at?: string
  updated_at?: string
  decided_by?: { id?: string; email?: string; name?: string } | null
  decided_at?: string | null
  is_proposer?: boolean
  can_decide?: boolean
}

type ProposalListResponse = { results: LifecycleChangeProposal[]; party_options?: PartyOption[] }

type LifecycleBoardResponse = {
  contract?: { id: string; title?: string; counterparty_name?: string | null; counterparty_email?: string | null; status?: string }
  signed_version?: { label?: string; content_snapshot?: string }
  lifecycle_agreement?: { id: string; status?: string; performance_ready?: boolean }
  parties?: { initiator?: { id?: string; email?: string; name?: string } | null; counterparty?: { email?: string | null; name?: string | null } | null }
  views?: Partial<Record<'payments' | 'work_services' | 'due_dates' | 'my_obligations' | 'activity' | 'changes_add_ons', TimelineItem[] | TimelineEvent[]>>
  events?: TimelineEvent[]
}

const BOARD_TABS: Array<{ key: BoardTab; label: string }> = [
  { key: 'payments', label: 'Payments' },
  { key: 'work', label: 'Work / Services' },
  { key: 'due_dates', label: 'Deadlines' },
  { key: 'my_obligations', label: 'My Obligations' },
  { key: 'activity', label: 'Activity' },
  { key: 'changes', label: 'Changes / Add-ons' },
]

const MODULE_TAB_BACKGROUNDS: Partial<Record<BoardTab, string>> = {
  payments: '#E8EEF5',
  work: '#F5FBFF',
  my_obligations: '#F6FEF9',
}

function obligationDetailBackground(item: TimelineItem | null, activeTab: BoardTab) {
  if (!item) return '#F8FAFC'
  if (activeTab === 'my_obligations') return '#F6FEF9'
  if (isPaymentItem(item)) return '#E8EEF5'
  if (isWorkServiceItem(item)) return '#F5FBFF'
  return '#F8FAFC'
}

function boardTabButtonStyle(tab: BoardTab, isActive: boolean): CSSProperties {
  const moduleBackground = MODULE_TAB_BACKGROUNDS[tab]
  if (moduleBackground && !isActive) {
    return { border: '1px solid #CBD5E1', borderRadius: 8, background: moduleBackground, color: '#334155', padding: '8px 11px', fontSize: 12, fontWeight: 800, cursor: 'pointer' }
  }
  return { border: '1px solid #CBD5E1', borderRadius: 8, background: isActive ? '#243447' : '#FFFFFF', color: isActive ? '#FFFFFF' : '#334155', padding: '8px 11px', fontSize: 12, fontWeight: 800, cursor: 'pointer' }
}

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
  return formatDateOnly(value, 'No date set')
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
  const input = dateOnlyInputValue(item.due_date)
  if (!input) return ''
  const [year, month, day] = input.split('-').map(Number)
  if (!year || !month || !day) return ''
  const date = new Date(year, month - 1, day)
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

function proposalTypeLabel(value?: string) {
  if (value === 'add_on') return 'Add-on'
  if (value === 'change_order') return 'Change Order'
  return humanize(value)
}

function proposalStatusLabel(value?: string) {
  if (value === 'proposed') return 'Proposed'
  if (value === 'accepted') return 'Accepted'
  if (value === 'rejected') return 'Rejected'
  return humanize(value)
}

function proposalActionLabel(value?: string) {
  if (value === 'add_on') return 'Submit Add-on Proposal'
  return 'Submit Change Order Proposal'
}

function generationModeLabel(value?: string) {
  if (value === 'before_each_payment_deadline') return 'Before each remaining payment deadline'
  return 'One-time obligation'
}

function isLifecycleTimelineItem(item: TimelineItem) {
  const source = item.source || item.source_type
  return Boolean(
    item.id &&
      source !== 'contract_payment_obligation' &&
      source !== 'contract_service_obligation' &&
      source !== 'payment_record'
  )
}

function proposalPartyLabel(options: PartyOption[], value?: string | null) {
  if (!value) return ''
  return options.find((option) => option.value === value)?.label || humanize(value)
}

function partyOptionLabel(role: 'initiator' | 'counterparty', label?: string | null) {
  const roleLabel = role === 'initiator' ? 'Initiator' : 'Counterparty'
  const cleaned = (label || '').trim()
  return cleaned && cleaned.toLowerCase() !== roleLabel.toLowerCase() ? `${roleLabel} / ${cleaned}` : roleLabel
}

function dateInputValue(value?: string | null) {
  return dateOnlyInputValue(value)
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

function metadataBoolean(metadata: Record<string, unknown> | undefined, key: string) {
  const value = metadata?.[key]
  return value === true || value === 'true'
}

function uniqueTimelineItems(items: TimelineItem[]) {
  const seen = new Set<string>()
  return items.filter((item) => {
    if (seen.has(item.id)) return false
    seen.add(item.id)
    return true
  })
}

function isGeneratedAddOnItem(item: TimelineItem) {
  const source = item.source || item.source_type
  return source === 'add_on' && metadataBoolean(item.metadata, 'generated_from_add_on') && Boolean(metadataString(item.metadata, 'target_item_id'))
}

function generatedAddOnTargetId(item: TimelineItem) {
  return metadataString(item.metadata, 'target_item_id')
}

function generatedAddOnTargetTitle(item: TimelineItem) {
  return metadataString(item.metadata, 'target_item_title')
}

function generatedAddOnContextLabel(item: TimelineItem) {
  const targetTitle = generatedAddOnTargetTitle(item)
  if (!targetTitle) return 'Generated Add-on'
  return `for ${targetTitle}`
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
  if (event.event_type === 'change_order_accepted') return 'Change Order accepted'
  if (event.event_type === 'add_on_accepted') return 'Add-on accepted'
  if (event.event_type === 'change_proposal_accepted') return 'Proposal accepted'
  if (event.event_type === 'change_proposal_rejected') return 'Proposal rejected'
  return event.title || humanize(event.event_type)
}

function isPerformanceActivityEvent(event: TimelineEvent) {
  return ['payment_marked_paid', 'work_marked_performed', 'item_completed', 'proof_uploaded', 'proof_response', 'change_order_accepted', 'add_on_accepted', 'change_proposal_accepted', 'change_proposal_rejected'].includes(event.event_type || '')
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
  if (!["completed", "confirmed", "resolved", "cancelled", "rejected"].includes(normalized)) {
    if (item.proof_submitted) return 'Proof Submitted'
    if (item.due_state === 'overdue') return 'Overdue'
    if (item.due_state === 'due_today') return 'Due Today'
    if (item.due_state === 'upcoming') return 'Upcoming'
    if (item.due_state === 'no_due_date') return 'No Due Date'
  }
  return humanize(item.status || item.lifecycle_state)
}

function performanceStatusStyleKey(item: TimelineItem) {
  const normalized = (item.status || item.lifecycle_state || '').toLowerCase()
  if (!["completed", "confirmed", "resolved", "cancelled", "rejected"].includes(normalized) && item.due_state === 'overdue') return 'overdue'
  return item.status || item.lifecycle_state
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

function isPaymentItem(item: TimelineItem) {
  const source = item.source || item.source_type
  return item.item_type === 'payment' || source === 'contract_payment_obligation' || source === 'payment_record'
}

function isWorkServiceItem(item: TimelineItem) {
  return ['service', 'service_work'].includes(item.item_type || '')
}

function itemTypeLabel(item: TimelineItem) {
  if (item.item_type === 'payment') return 'Payment'
  if (isWorkServiceItem(item)) return 'Work / Service'
  return humanize(item.item_type)
}

function obligationIdentityTypeLabel(item: TimelineItem) {
  if (item.item_type === 'payment') return 'Payment Obligation'
  if (isWorkServiceItem(item)) return item.title || 'Work / Service Obligation'
  return item.title || humanize(item.item_type)
}

function obligationDisplayTitle(item: TimelineItem) {
  if (!item.due_date) return item.title || humanize(item.item_type)
  const parts = [dueDateLabel(item.due_date), obligationIdentityTypeLabel(item)]
  if (!isWorkServiceItem(item) && item.amount) parts.push(formatMoney(item.amount, item.currency || 'USD'))
  return parts.join(' • ')
}

function itemAction(item: TimelineItem): { action: string; label: string } | null {
  if (!item.can_upload_proof) return null
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
  if (isPaymentItem(item)) return 'Payment'
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
  return dateOnlyInputValue(value) || 'No date set'
}

function sortByDeadline(items: TimelineItem[]) {
  return [...items].sort((left, right) => dateOnlySortKey(left.due_date).localeCompare(dateOnlySortKey(right.due_date)))
}

function agreementNavigatorTitle(agreement: PerformanceAgreement) {
  return agreement.title || agreement.contract.title || 'Untitled contract'
}

function agreementNavigatorCounterparty(agreement: PerformanceAgreement) {
  return agreement.counterparty?.name || agreement.counterparty?.email || agreement.contract.counterparty_name || agreement.contract.counterparty_email || 'Counterparty not set'
}

function agreementNavigatorMatchText(agreement: PerformanceAgreement, query: string) {
  const title = agreementNavigatorTitle(agreement)
  const counterparty = agreementNavigatorCounterparty(agreement)
  if (title.toLowerCase().includes(query)) return title
  return counterparty
}

export default function AgreementPerformance() {
  const [agreements, setAgreements] = useState<PerformanceAgreement[]>([])
  const [selectedAgreement, setSelectedAgreement] = useState<PerformanceAgreement | null>(null)
  const [navigatorOpen, setNavigatorOpen] = useState(false)
  const [navigatorSearch, setNavigatorSearch] = useState('')
  const [navigatorHighlightIndex, setNavigatorHighlightIndex] = useState(0)
  const navigatorRef = useRef<HTMLElement | null>(null)
  const navigatorSearchRef = useRef<HTMLInputElement | null>(null)
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
  const [attachmentErrorsByItemId, setAttachmentErrorsByItemId] = useState<Record<string, string>>({})
  const [messagesByItemId, setMessagesByItemId] = useState<Record<string, LifecycleMessage[]>>({})
  const [messageLoading, setMessageLoading] = useState('')
  const [messageSending, setMessageSending] = useState('')
  const [messageError, setMessageError] = useState('')
  const [proposals, setProposals] = useState<LifecycleChangeProposal[]>([])
  const [proposalPartyOptions, setProposalPartyOptions] = useState<PartyOption[]>([])
  const [proposalLoading, setProposalLoading] = useState(false)
  const [proposalSaving, setProposalSaving] = useState(false)
  const [proposalError, setProposalError] = useState('')
  const [proposalMode, setProposalMode] = useState<'add_on' | 'change_order' | null>(null)
  const [selectedProposal, setSelectedProposal] = useState<LifecycleChangeProposal | null>(null)
  const [proposalMessagesByProposalId, setProposalMessagesByProposalId] = useState<Record<string, LifecycleChangeProposalMessage[]>>({})
  const [proposalMessageLoading, setProposalMessageLoading] = useState('')
  const [proposalMessageSending, setProposalMessageSending] = useState('')
  const [proposalMessageError, setProposalMessageError] = useState('')
  const [decisionBusy, setDecisionBusy] = useState('')
  const [decisionError, setDecisionError] = useState('')
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
    setNavigatorOpen(false)
    setNavigatorSearch('')
    setNavigatorHighlightIndex(0)
    window.localStorage.setItem(LAST_PERFORMANCE_AGREEMENT_KEY, agreement.id)
    setBoardLoading(true)
    setBoardError('')
    setFeedback('')
    if (options.resetView !== false) {
      setActiveTab('payments')
      setSelectedItem(null)
      setSelectedProposal(null)
      setProposalMode(null)
      setProposalMessageError('')
      setDecisionError('')
    }
    setProposals([])
    setProposalPartyOptions([])
    setProposalError('')
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
      ...((data?.views?.my_obligations || []) as TimelineItem[]),
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
      for (const key of ['payments', 'work_services', 'due_dates', 'my_obligations'] as const) {
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

  async function loadAttachments(item: TimelineItem) {
    if (!item?.id) return
    if (!isLifecycleTimelineItem(item)) {
      setAttachmentsByItemId((current) => ({ ...current, [item.id]: [] }))
      setAttachmentErrorsByItemId((current) => ({ ...current, [item.id]: '' }))
      return
    }
    setAttachmentLoading(item.id)
    setAttachmentErrorsByItemId((current) => ({ ...current, [item.id]: '' }))
    try {
      const response = await api.get<AttachmentListResponse>(`/lifecycle/items/${item.id}/attachments/`)
      setAttachmentsByItemId((current) => ({ ...current, [item.id]: response.data.results || [] }))
    } catch (err) {
      setAttachmentsByItemId((current) => ({ ...current, [item.id]: current[item.id] || [] }))
      setAttachmentErrorsByItemId((current) => ({ ...current, [item.id]: getErrorMessage(err, 'Unable to load proof and receipt attachments.') }))
    } finally {
      setAttachmentLoading('')
    }
  }

  async function uploadProof(item: TimelineItem, file: File, note: string) {
    setFeedback('')
    setBoardError('')
    setAttachmentErrorsByItemId((current) => ({ ...current, [item.id]: '' }))
    if (!isLifecycleTimelineItem(item)) {
      const message = 'Proof and receipt uploads are only available for active lifecycle obligations.'
      setAttachmentErrorsByItemId((current) => ({ ...current, [item.id]: message }))
      throw new Error(message)
    }
    setAttachmentBusy(item.id)
    const formData = new FormData()
    formData.append('file', file)
    if (note.trim()) formData.append('note', note.trim())
    try {
      await postMultipart<LifecycleAttachment>(`/lifecycle/items/${item.id}/attachments/`, formData)
      await loadAttachments(item)
      const refreshed = await refreshBoard({ resetView: false })
      setSelectedItem(findBoardItem(refreshed, item.id) || item)
      setFeedback('Proof uploaded.')
    } catch (err) {
      setAttachmentErrorsByItemId((current) => ({ ...current, [item.id]: getFetchErrorMessage(err, 'Unable to upload proof or receipt.') }))
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

  async function loadMessages(item: TimelineItem, options: { quiet?: boolean } = {}) {
    if (!item?.id) return
    if (!isLifecycleTimelineItem(item)) {
      setMessagesByItemId((current) => ({ ...current, [item.id]: [] }))
      if (!options.quiet) setMessageError('')
      return
    }
    if (!options.quiet) {
      setMessageLoading(item.id)
      setMessageError('')
    }
    try {
      const response = await api.get<MessageListResponse>(`/lifecycle/items/${item.id}/messages/`)
      setMessagesByItemId((current) => ({ ...current, [item.id]: response.data.results || [] }))
    } catch (err) {
      if (!options.quiet) setMessageError(getErrorMessage(err, 'Unable to load messages.'))
    } finally {
      if (!options.quiet) setMessageLoading('')
    }
  }

  async function loadProposals(lifecycleAgreementId?: string) {
    if (!lifecycleAgreementId) return
    setProposalLoading(true)
    setProposalError('')
    try {
      const response = await api.get<ProposalListResponse>(`/lifecycle/agreements/${lifecycleAgreementId}/proposals/`)
      setProposals(response.data.results || [])
      setProposalPartyOptions(response.data.party_options || [])
    } catch (err) {
      setProposalError(getErrorMessage(err, 'Unable to load change proposals.'))
    } finally {
      setProposalLoading(false)
    }
  }

  function updateProposalState(updated: LifecycleChangeProposal) {
    setProposals((current) => current.map((proposal) => (proposal.id === updated.id ? updated : proposal)))
    setSelectedProposal((current) => (current?.id === updated.id ? updated : current))
  }

  async function submitProposal(payload: Record<string, string>) {
    const lifecycleAgreementId = boardData?.lifecycle_agreement?.id
    if (!lifecycleAgreementId || !proposalMode) return
    setProposalSaving(true)
    setProposalError('')
    setFeedback('')
    try {
      const response = await api.post<LifecycleChangeProposal>(`/lifecycle/agreements/${lifecycleAgreementId}/proposals/`, {
        ...payload,
        proposal_type: proposalMode,
      })
      setProposals((current) => [response.data, ...current])
      setSelectedProposal(response.data)
      setProposalMode(null)
      setFeedback(`${proposalTypeLabel(response.data.proposal_type)} proposal submitted.`)
      void loadProposals(lifecycleAgreementId)
      void loadPerformanceAgreements()
    } catch (err) {
      setProposalError(getErrorMessage(err, 'Unable to submit proposal.'))
    } finally {
      setProposalSaving(false)
    }
  }

  async function loadProposalMessages(proposalId?: string, options: { quiet?: boolean } = {}) {
    if (!proposalId) return
    if (!options.quiet) {
      setProposalMessageLoading(proposalId)
      setProposalMessageError('')
    }
    try {
      const response = await api.get<ProposalMessageListResponse>(`/lifecycle/proposals/${proposalId}/messages/`)
      setProposalMessagesByProposalId((current) => ({ ...current, [proposalId]: response.data.results || [] }))
    } catch (err) {
      if (!options.quiet) setProposalMessageError(getErrorMessage(err, 'Unable to load proposal messages.'))
    } finally {
      if (!options.quiet) setProposalMessageLoading('')
    }
  }

  async function sendProposalMessage(proposal: LifecycleChangeProposal, body: string) {
    const trimmed = body.trim()
    if (!proposal?.id || !trimmed) return
    setProposalMessageSending(proposal.id)
    setProposalMessageError('')
    try {
      const response = await api.post<LifecycleChangeProposalMessage>(`/lifecycle/proposals/${proposal.id}/messages/`, { body: trimmed })
      setProposalMessagesByProposalId((current) => ({ ...current, [proposal.id]: [...(current[proposal.id] || []), response.data] }))
      setFeedback('Proposal message sent.')
      void loadProposalMessages(proposal.id, { quiet: true })
    } catch (err) {
      setProposalMessageError(getErrorMessage(err, 'Unable to send proposal message.'))
    } finally {
      setProposalMessageSending('')
    }
  }

  async function decideProposal(proposal: LifecycleChangeProposal, decision: 'accepted' | 'rejected', note: string, finalTerms: Record<string, string> = {}) {
    if (!proposal?.id) return
    setDecisionBusy(`${proposal.id}:${decision}`)
    setDecisionError('')
    setFeedback('')
    try {
      const response = await api.post<LifecycleChangeProposal>(`/lifecycle/proposals/${proposal.id}/decision/`, { decision, note: note.trim(), ...finalTerms })
      updateProposalState(response.data)
      setFeedback(decision === 'accepted' ? 'Proposal accepted.' : 'Proposal rejected.')
      if (boardData?.lifecycle_agreement?.id) void loadProposals(boardData.lifecycle_agreement.id)
      const refreshed = await refreshBoard({ resetView: false })
      if (selectedItem?.id) setSelectedItem(findBoardItem(refreshed, selectedItem.id) || selectedItem)
    } catch (err) {
      setDecisionError(getErrorMessage(err, 'Unable to save proposal decision.'))
    } finally {
      setDecisionBusy('')
    }
  }

  async function sendMessage(item: TimelineItem, body: string) {
    if (!item?.id || !isLifecycleTimelineItem(item)) {
      setMessageError('Messages are only available for active lifecycle obligations.')
      return
    }
    const trimmed = body.trim()
    if (!trimmed) return
    setMessageSending(item.id)
    setMessageError('')
    try {
      const response = await api.post<LifecycleMessage>(`/lifecycle/items/${item.id}/messages/`, { body: trimmed })
      setMessagesByItemId((current) => ({ ...current, [item.id]: [...(current[item.id] || []), response.data] }))
      void loadMessages(item, { quiet: true })
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
    if (isLoading || selectedAgreement || agreements.length === 0) return
    const savedAgreementId = window.localStorage.getItem(LAST_PERFORMANCE_AGREEMENT_KEY)
    if (!savedAgreementId) return
    const savedAgreement = agreements.find((agreement) => agreement.id === savedAgreementId)
    if (savedAgreement) void openBoard(savedAgreement)
  }, [agreements, isLoading, selectedAgreement])

  useEffect(() => {
    if (!navigatorOpen) return undefined
    setNavigatorSearch('')
    setNavigatorHighlightIndex(0)
    window.requestAnimationFrame(() => navigatorSearchRef.current?.focus())

    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === 'Escape') {
        setNavigatorOpen(false)
        setNavigatorSearch('')
        setNavigatorHighlightIndex(0)
      }
    }

    function handlePointerDown(event: MouseEvent) {
      const target = event.target
      if (target instanceof Node && navigatorRef.current?.contains(target)) return
      setNavigatorOpen(false)
      setNavigatorSearch('')
      setNavigatorHighlightIndex(0)
    }

    document.addEventListener('keydown', handleKeyDown)
    document.addEventListener('mousedown', handlePointerDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.removeEventListener('mousedown', handlePointerDown)
    }
  }, [navigatorOpen])

  useEffect(() => {
    if (!feedback) return undefined
    const timer = window.setTimeout(() => setFeedback(''), 4000)
    return () => window.clearTimeout(timer)
  }, [feedback])

  useEffect(() => {
    if (boardData?.lifecycle_agreement?.id) void loadProposals(boardData.lifecycle_agreement.id)
  }, [boardData?.lifecycle_agreement?.id])

  useEffect(() => {
    if (selectedItem) void loadAttachments(selectedItem)
  }, [selectedItem?.id])

  useEffect(() => {
    if (!selectedItem?.id) return
    void loadMessages(selectedItem)
    if (!isLifecycleTimelineItem(selectedItem)) return
    const intervalId = window.setInterval(() => {
      void loadMessages(selectedItem, { quiet: true })
    }, 4000)
    return () => window.clearInterval(intervalId)
  }, [selectedItem?.id])

  useEffect(() => {
    const selectedProposalId = selectedProposal?.id
    if (!selectedProposalId) return
    void loadProposalMessages(selectedProposalId)
    const intervalId = window.setInterval(() => {
      void loadProposalMessages(selectedProposalId, { quiet: true })
    }, 4000)
    return () => window.clearInterval(intervalId)
  }, [selectedProposal?.id])

  const rawBoardItems = useMemo(() => ([
    ...((boardData?.views?.payments || []) as TimelineItem[]),
    ...((boardData?.views?.work_services || []) as TimelineItem[]),
    ...((boardData?.views?.due_dates || []) as TimelineItem[]),
    ...((boardData?.views?.my_obligations || []) as TimelineItem[]),
  ]), [boardData])
  const payments = useMemo(() => ((boardData?.views?.payments || []) as TimelineItem[]).filter(isDisplayableItem), [boardData])
  const workItems = useMemo(() => ((boardData?.views?.work_services || []) as TimelineItem[]).filter(isDisplayableItem), [boardData])
  const dueDates = useMemo(() => ((boardData?.views?.due_dates || []) as TimelineItem[]).filter(isDisplayableItem), [boardData])
  const myObligations = useMemo(() => sortByDeadline(((boardData?.views?.my_obligations || []) as TimelineItem[]).filter(isDisplayableItem)), [boardData])
  const events = useMemo(() => ((boardData?.views?.activity || boardData?.events || []) as TimelineEvent[]), [boardData])
  const proposalAffectedItems = useMemo(() => rawBoardItems.filter(isLifecycleTimelineItem), [rawBoardItems])
  const availablePartyOptions = useMemo(() => {
    if (proposalPartyOptions.length > 0) return proposalPartyOptions
    const initiator = boardData?.parties?.initiator
    const counterparty = boardData?.parties?.counterparty || boardData?.contract || selectedAgreement?.counterparty || selectedAgreement?.contract
    return [
      { value: 'initiator', label: partyOptionLabel('initiator', initiator?.name || initiator?.email), email: initiator?.email || null },
      { value: 'counterparty', label: partyOptionLabel('counterparty', counterparty?.name || counterparty?.counterparty_name || counterparty?.email || counterparty?.counterparty_email), email: counterparty?.email || counterparty?.counterparty_email || null },
    ]
  }, [boardData, proposalPartyOptions, selectedAgreement])
  const filteredNavigatorAgreements = useMemo(() => {
    const query = navigatorSearch.trim().toLowerCase()
    if (!query) return agreements
    return agreements
      .filter((agreement) => {
        const title = agreementNavigatorTitle(agreement).toLowerCase()
        const counterparty = agreementNavigatorCounterparty(agreement).toLowerCase()
        return title.includes(query) || counterparty.includes(query)
      })
      .sort((left, right) => {
        const leftMatch = agreementNavigatorMatchText(left, query)
        const rightMatch = agreementNavigatorMatchText(right, query)
        return leftMatch.localeCompare(rightMatch, undefined, { sensitivity: 'base' })
          || agreementNavigatorTitle(left).localeCompare(agreementNavigatorTitle(right), undefined, { sensitivity: 'base' })
          || agreementNavigatorCounterparty(left).localeCompare(agreementNavigatorCounterparty(right), undefined, { sensitivity: 'base' })
      })
  }, [agreements, navigatorSearch])

  useEffect(() => {
    if (navigatorHighlightIndex >= filteredNavigatorAgreements.length) setNavigatorHighlightIndex(Math.max(filteredNavigatorAgreements.length - 1, 0))
  }, [filteredNavigatorAgreements.length, navigatorHighlightIndex])

  function handleNavigatorSearchKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setNavigatorHighlightIndex((index) => Math.min(index + 1, Math.max(filteredNavigatorAgreements.length - 1, 0)))
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      setNavigatorHighlightIndex((index) => Math.max(index - 1, 0))
      return
    }
    if (event.key === 'Enter') {
      event.preventDefault()
      const agreement = filteredNavigatorAgreements[navigatorHighlightIndex]
      if (agreement) void openBoard(agreement)
      return
    }
    if (event.key === 'Escape') {
      event.preventDefault()
      setNavigatorOpen(false)
      setNavigatorSearch('')
      setNavigatorHighlightIndex(0)
    }
  }

  function updateNavigatorSearch(value: string) {
    setNavigatorSearch(value)
    setNavigatorHighlightIndex(0)
  }

  function toggleNavigator() {
    setNavigatorOpen((open) => {
      if (open) {
        setNavigatorSearch('')
        setNavigatorHighlightIndex(0)
      }
      return !open
    })
  }

  const selectedItemEvents = selectedItem ? itemHistoryEvents(events, selectedItem) : []
  const selectedItemAttachments = selectedItem ? attachmentsByItemId[selectedItem.id] || [] : []
  const selectedItemMessages = selectedItem ? messagesByItemId[selectedItem.id] || [] : []
  const selectedItemAttachmentError = selectedItem ? attachmentErrorsByItemId[selectedItem.id] || '' : ''
  const activeItems = activeTab === 'payments' ? payments : activeTab === 'work' ? workItems : activeTab === 'my_obligations' ? myObligations : []
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

      {navigatorOpen && <div aria-hidden="true" style={{ position: 'fixed', inset: 0, background: 'rgba(15, 31, 61, 0.16)', zIndex: 20 }} />}

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
        <section ref={navigatorRef} style={{ position: 'relative', zIndex: navigatorOpen ? 30 : 1, background: '#FFFFFF', border: `1px solid ${navigatorOpen ? '#CBD5E1' : '#E5E7EB'}`, borderRadius: 8, padding: 14, marginBottom: 18, boxShadow: navigatorOpen ? '0 18px 44px rgba(15, 23, 42, 0.14)' : 'none' }}>
          <div style={{ display: 'grid', gap: 10, marginBottom: navigatorOpen ? 12 : 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 18, flexWrap: 'wrap' }}>
              <p style={{ flex: '0 0 240px', fontSize: 11, fontWeight: 800, color: '#047857', textTransform: 'uppercase', letterSpacing: '0.1em', margin: 0 }}>Agreement Navigator</p>
              <span aria-hidden="true" style={{ flex: '0 1 110px' }} />
              {navigatorOpen && (
                <label style={{ display: 'flex', alignItems: 'center', gap: 9, flex: '0 1 520px', minWidth: 340 }}>
                  <span style={{ flex: '0 0 auto', fontSize: 11, fontWeight: 900, color: '#334155', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Search</span>
                  <input
                    ref={navigatorSearchRef}
                    type="search"
                    value={navigatorSearch}
                    onChange={(event) => updateNavigatorSearch(event.target.value)}
                    onKeyDown={handleNavigatorSearchKeyDown}
                    placeholder="Search agreements or counterparty..."
                    aria-label="Search agreements or counterparty"
                    style={{ width: '100%', minHeight: 40, border: '1px solid #CBD5E1', borderRadius: 7, padding: '9px 10px', fontSize: 13, color: '#0F172A', outlineColor: '#94A3B8', background: '#FFFFFF' }}
                  />
                </label>
              )}
              <span aria-hidden="true" style={{ flex: '1 1 180px' }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
              <button type="button" onClick={toggleNavigator} aria-expanded={navigatorOpen} aria-haspopup="listbox" style={{ display: 'flex', alignItems: 'center', gap: 8, maxWidth: '100%', border: '1px solid #CBD5E1', borderRadius: 8, background: '#FFFFFF', color: '#243447', padding: '8px 10px', fontSize: 14, fontWeight: 900, cursor: 'pointer', boxShadow: navigatorOpen ? '0 1px 2px rgba(15, 23, 42, 0.08)' : 'none' }}>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{selectedAgreement ? agreementNavigatorTitle(selectedAgreement) : 'Select Agreement'}</span>
                <span style={{ color: '#64748B', fontSize: 12 }}>{navigatorOpen ? '▲' : '▼'}</span>
              </button>
              <span style={{ fontSize: 12, color: '#64748B', fontWeight: 800 }}>{agreements.length} ready</span>
            </div>
          </div>
          {navigatorOpen && (
            <div style={{ display: 'grid', gap: 10 }}>
              {filteredNavigatorAgreements.length === 0 ? (
                <div style={{ border: '1px dashed #CBD5E1', borderRadius: 8, background: '#F8FAFC', padding: 18 }}>
                  <p style={{ fontSize: 14, fontWeight: 900, color: '#0F1F3D', margin: 0 }}>No agreements found.</p>
                  <p style={{ fontSize: 12, color: '#64748B', margin: '5px 0 0' }}>Try another agreement name or counterparty.</p>
                </div>
              ) : (
                <div role="listbox" aria-label="Agreement Navigator" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 8 }}>
                  {filteredNavigatorAgreements.map((agreement, index) => {
                    const counterparty = agreementNavigatorCounterparty(agreement)
                    const selected = selectedAgreement?.id === agreement.id
                    const highlighted = index === navigatorHighlightIndex
                    return (
                      <button key={agreement.id} role="option" aria-selected={selected || highlighted} type="button" onMouseEnter={() => setNavigatorHighlightIndex(index)} onClick={() => void openBoard(agreement)} style={{ display: 'grid', gap: 4, textAlign: 'left', border: `1px solid ${highlighted ? '#94A3B8' : selected ? '#CBD5E1' : '#E5E7EB'}`, borderRadius: 8, background: highlighted ? '#F8FAFC' : selected ? '#F1F5F9' : '#FFFFFF', padding: '10px 12px', cursor: 'pointer', boxShadow: highlighted ? '0 2px 8px rgba(15, 23, 42, 0.08)' : 'none' }}>
                        <span style={{ fontSize: 13, fontWeight: 900, color: '#0F1F3D', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{agreementNavigatorTitle(agreement)}</span>
                        <span style={{ fontSize: 11, color: '#64748B', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{counterparty}</span>
                        <span style={{ justifySelf: 'start', borderRadius: 999, padding: '3px 7px', fontSize: 10, fontWeight: 900, background: selected ? '#E2E8F0' : '#F8FAFC', color: selected ? '#334155' : '#475569' }}>{selected ? 'Active' : agreement.status}</span>
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </section>
      )}


      <section style={{ background: obligationDetailBackground(selectedItem, activeTab), border: '1px solid #E5E7EB', borderRadius: 8, padding: 18, minHeight: 260 }}>
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
            <div style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 14, flexWrap: 'wrap', alignItems: 'flex-start' }}>
                <div>
                  <p style={{ fontSize: 11, fontWeight: 800, color: '#047857', textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 5px' }}>Performance board</p>
                  <h2 style={{ fontSize: 26, fontWeight: 900, color: '#0F1F3D', margin: 0 }}>{boardData.contract?.title || selectedAgreement.contract.title || selectedAgreement.title || 'Untitled contract'}</h2>
                  <p style={{ fontSize: 12, color: '#64748B', margin: '6px 0 0' }}>{agreementNavigatorCounterparty(selectedAgreement)}</p>
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                  {selectedItem && <button type="button" onClick={() => setSelectedItem(null)} style={secondaryButtonStyle}>Back to Performance Board</button>}
                  <button type="button" onClick={() => setShowSource(true)} style={secondaryButtonStyle}>View Signed Source</button>
                  <button type="button" onClick={() => void openBoard(selectedAgreement)} style={{ height: 34, border: '1px solid #243447', borderRadius: 8, background: '#243447', color: '#FFFFFF', padding: '0 12px', fontSize: 12, fontWeight: 800, cursor: 'pointer' }}>Refresh Performance</button>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10, marginTop: 12 }}>
                <SummaryCell label="Status" value={selectedAgreement.status} />
                <SummaryCell label="Payments" value={`${selectedAgreement.payment_count || 0} payment item(s)`} />
                <SummaryCell label="Work" value={`${selectedAgreement.work_count ?? selectedAgreement.work_item_count ?? 0} work item(s)`} />
                <SummaryCell label="Deadlines" value={`${selectedAgreement.due_date_count || 0} deadline(s)`} />
                <SummaryCell label="Activity" value={`${selectedAgreement.activity_count || 0} event(s)`} />
                <SummaryCell label="Ready Since" value={formatDate(selectedAgreement.lifecycle_agreement?.performance_ready_at)} />
              </div>
            </div>

            {feedback && <div style={{ background: '#F8FAFC', border: '1px solid #CBD5E1', borderRadius: 8, padding: 12, marginBottom: 12 }}><p style={{ fontSize: 13, color: '#334155', margin: 0, fontWeight: 800 }}>{feedback}</p></div>}

            {!selectedItem && (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
                {BOARD_TABS.map((tab) => (
                  <button key={tab.key} type="button" onClick={() => setActiveTab(tab.key)} style={boardTabButtonStyle(tab.key, activeTab === tab.key)}>
                    {tab.label}
                  </button>
                ))}
              </div>
            )}

            {selectedItem ? (
              <PerformanceThread
                item={selectedItem}
                isMyObligationsView={activeTab === 'my_obligations'}
                isWorkServicesView={activeTab === 'work'}
                events={selectedItemEvents}
                attachments={selectedItemAttachments}
                attachmentsLoading={attachmentLoading === selectedItem.id}
                attachmentError={selectedItemAttachmentError}
                attachmentBusy={attachmentBusy === selectedItem.id}
                messages={selectedItemMessages}
                messagesLoading={messageLoading === selectedItem.id}
                messageSending={messageSending === selectedItem.id}
                messageError={messageError}
                responseBusy={responseBusy}
                busy={actionBusy}
                onViewSource={() => setShowSource(true)}
                onAction={(action) => void runAction(selectedItem, action)}
                onUploadProof={(file, note) => uploadProof(selectedItem, file, note)}
                onSendMessage={(body) => void sendMessage(selectedItem, body)}
                onRespond={(response, note) => void submitProofResponse(selectedItem, response, note)}
              />
            ) : activeTab === 'activity' ? (
              <ActivityPanel events={events} items={rawBoardItems} agreementTitle={boardData.contract?.title || selectedAgreement.contract.title || selectedAgreement.title} />
            ) : activeTab === 'changes' ? (
              <ChangesAddOnsWorkspace
                proposals={proposals}
                loading={proposalLoading}
                saving={proposalSaving}
                error={proposalError}
                mode={proposalMode}
                selectedProposal={selectedProposal}
                proposalMessages={selectedProposal ? proposalMessagesByProposalId[selectedProposal.id] || [] : []}
                proposalMessagesLoading={selectedProposal ? proposalMessageLoading === selectedProposal.id : false}
                proposalMessageSending={selectedProposal ? proposalMessageSending === selectedProposal.id : false}
                proposalMessageError={proposalMessageError}
                decisionBusy={decisionBusy}
                decisionError={decisionError}
                partyOptions={availablePartyOptions}
                affectedItems={proposalAffectedItems}
                onModeChange={(mode) => { setProposalMode(mode); setSelectedProposal(null); setProposalError(''); setProposalMessageError(''); setDecisionError('') }}
                onSelectProposal={(proposal) => { setSelectedProposal(proposal); setProposalMode(null); setProposalMessageError(''); setDecisionError('') }}
                onBackToList={() => { setSelectedProposal(null); setProposalMode(null); setProposalMessageError(''); setDecisionError('') }}
                onSubmit={(payload) => void submitProposal(payload)}
                onSendProposalMessage={(proposal, body) => void sendProposalMessage(proposal, body)}
                onDecideProposal={(proposal, decision, note, finalTerms) => void decideProposal(proposal, decision, note, finalTerms)}
              />
            ) : activeTab === 'due_dates' ? (
              <DeadlinesPanel items={dueDates} onOpen={setSelectedItem} onViewSource={() => setShowSource(true)} />
            ) : activeItems.length === 0 ? (
              <div style={{ border: '1px dashed #CBD5E1', borderRadius: 8, padding: 18, background: '#FFFFFF' }}>
                <p style={{ fontSize: 13, color: '#64748B', margin: 0 }}>No records found for this panel.</p>
              </div>
            ) : (
              <div style={{ display: 'grid', gap: 12, background: '#E5E7EB', padding: 12, borderRadius: 8 }}>
                {activeItems.map((item) => (
                  <PerformanceCard
                    key={`${item.source || item.source_type}-${item.id}`}
                    item={item}
                    onOpen={() => setSelectedItem(item)}
                    onViewSource={() => setShowSource(true)}
                    reminderBusy={reminderBusy === item.id}
                    onReminder={(reminderAt) => void saveReminder(item, reminderAt)}
                    showTypeLabel={activeTab === 'my_obligations'}
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

function ChangesAddOnsWorkspace({
  proposals,
  loading,
  saving,
  error,
  mode,
  selectedProposal,
  proposalMessages,
  proposalMessagesLoading,
  proposalMessageSending,
  proposalMessageError,
  decisionBusy,
  decisionError,
  partyOptions,
  affectedItems,
  onModeChange,
  onSelectProposal,
  onBackToList,
  onSubmit,
  onSendProposalMessage,
  onDecideProposal,
}: {
  proposals: LifecycleChangeProposal[]
  loading: boolean
  saving: boolean
  error: string
  mode: 'add_on' | 'change_order' | null
  selectedProposal: LifecycleChangeProposal | null
  proposalMessages: LifecycleChangeProposalMessage[]
  proposalMessagesLoading: boolean
  proposalMessageSending: boolean
  proposalMessageError: string
  decisionBusy: string
  decisionError: string
  partyOptions: PartyOption[]
  affectedItems: TimelineItem[]
  onModeChange: (mode: 'add_on' | 'change_order') => void
  onSelectProposal: (proposal: LifecycleChangeProposal) => void
  onBackToList: () => void
  onSubmit: (payload: Record<string, string>) => void
  onSendProposalMessage: (proposal: LifecycleChangeProposal, body: string) => void
  onDecideProposal: (proposal: LifecycleChangeProposal, decision: 'accepted' | 'rejected', note: string, finalTerms?: Record<string, string>) => void
}) {
  if (selectedProposal) {
    return (
      <ProposalDetailCard
        proposal={selectedProposal}
        partyOptions={partyOptions}
        messages={proposalMessages}
        messagesLoading={proposalMessagesLoading}
        messageSending={proposalMessageSending}
        messageError={proposalMessageError}
        decisionBusy={decisionBusy}
        decisionError={decisionError}
        onBack={onBackToList}
        onSendMessage={(body) => onSendProposalMessage(selectedProposal, body)}
        onDecide={(decision, note, finalTerms) => onDecideProposal(selectedProposal, decision, note, finalTerms)}
      />
    )
  }

  return (
    <div style={{ display: 'grid', gap: 14 }}>
      <section style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, padding: 18 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 14, flexWrap: 'wrap', alignItems: 'flex-start' }}>
          <div style={{ minWidth: 0 }}>
            <h3 style={{ fontSize: 22, fontWeight: 900, color: '#0F1F3D', margin: 0 }}>Changes / Add-ons</h3>
            <p style={{ fontSize: 13, color: '#64748B', margin: '8px 0 0', lineHeight: 1.55 }}>Propose new obligations or request changes to existing obligations during performance.</p>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button type="button" onClick={() => onModeChange('add_on')} style={mode === 'add_on' ? primaryButtonStyle : secondaryButtonStyle}>Create Add-on</button>
            <button type="button" onClick={() => onModeChange('change_order')} style={mode === 'change_order' ? amberButtonStyle : secondaryButtonStyle}>Create Change Order</button>
          </div>
        </div>
      </section>

      {error && <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: 12 }}><p style={{ fontSize: 13, color: '#B91C1C', margin: 0 }}>{error}</p></div>}

      {mode && (
        <ProposalForm
          mode={mode}
          saving={saving}
          partyOptions={partyOptions}
          affectedItems={affectedItems}
          onSubmit={onSubmit}
        />
      )}

      <ProposalList proposals={proposals} loading={loading} onOpen={onSelectProposal} />
    </div>
  )
}

function ProposalForm({
  mode,
  saving,
  partyOptions,
  affectedItems,
  onSubmit,
}: {
  mode: 'add_on' | 'change_order'
  saving: boolean
  partyOptions: PartyOption[]
  affectedItems: TimelineItem[]
  onSubmit: (payload: Record<string, string>) => void
}) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [responsibleParty, setResponsibleParty] = useState('')
  const [generationMode, setGenerationMode] = useState('single')
  const [amount, setAmount] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [note, setNote] = useState('')
  const [affectedItemId, setAffectedItemId] = useState('')
  const [submitAttempted, setSubmitAttempted] = useState(false)
  const isAddOn = mode === 'add_on'
  const normalizedDueDate = dateInputValue(dueDate)
  const validationMessages = [
    !title.trim() ? 'Enter a title.' : '',
    !description.trim() ? (isAddOn ? 'Enter a description / scope.' : 'Enter a description / reason.') : '',
    isAddOn && !responsibleParty ? 'Select a responsible party.' : '',
    !isAddOn && !affectedItemId ? 'Select an affected obligation.' : '',
  ].filter(Boolean)
  const canSubmit = validationMessages.length === 0

  function submit() {
    setSubmitAttempted(true)
    if (!canSubmit || saving) return
    onSubmit({
      title: title.trim(),
      description: description.trim(),
      responsible_party: responsibleParty,
      generation_mode: isAddOn ? generationMode : 'single',
      amount: amount.trim(),
      due_date: normalizedDueDate,
      note: note.trim(),
      affected_item_id: affectedItemId,
    })
  }

  return (
    <section style={{ background: '#FFFFFF', border: '1px solid #CBD5E1', borderRadius: 8, padding: 18 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 14 }}>
        <div>
          <p style={{ fontSize: 11, color: '#64748B', margin: 0, fontWeight: 900, textTransform: 'uppercase' }}>{proposalTypeLabel(mode)}</p>
          <h4 style={{ fontSize: 18, color: '#0F1F3D', margin: '5px 0 0', fontWeight: 900 }}>{isAddOn ? 'Create Add-on' : 'Create Change Order'}</h4>
        </div>
      </div>

      <div style={{ display: 'grid', gap: 12 }}>
        {!isAddOn && (
          <label style={fieldLabelStyle}>
            Affected obligation
            <select value={affectedItemId} onChange={(event) => setAffectedItemId(event.target.value)} style={inputStyle} required>
              <option value="">Select an existing obligation</option>
              {affectedItems.map((item) => (
                <option key={item.id} value={item.id}>{item.title || humanize(item.item_type)}{item.due_date ? ` - ${dueDateLabel(item.due_date)}` : ''}</option>
              ))}
            </select>
          </label>
        )}
        <label style={fieldLabelStyle}>
          Title
          <input value={title} onChange={(event) => setTitle(event.target.value)} style={inputStyle} required />
        </label>
        <label style={fieldLabelStyle}>
          {isAddOn ? 'Description / scope' : 'Description / reason'}
          <textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={4} style={textareaStyle} required />
        </label>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 12 }}>
          <label style={fieldLabelStyle}>
            Responsible party{isAddOn ? '' : ' (optional)'}
            <select value={responsibleParty} onChange={(event) => setResponsibleParty(event.target.value)} style={inputStyle} required={isAddOn}>
              <option value="">{isAddOn ? 'Select a party' : 'No change'}</option>
              {partyOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
          {isAddOn && (
            <label style={fieldLabelStyle}>
              Add-on generation
              <select value={generationMode} onChange={(event) => setGenerationMode(event.target.value)} style={inputStyle}>
                <option value="single">One-time obligation</option>
                <option value="before_each_payment_deadline">Before each remaining payment deadline</option>
              </select>
            </label>
          )}
          <label style={fieldLabelStyle}>
            {isAddOn ? 'Amount (optional)' : 'Changed amount (optional)'}
            <input type="number" step="0.01" min="0" value={amount} onChange={(event) => setAmount(event.target.value)} style={inputStyle} />
          </label>
          <label style={fieldLabelStyle}>
            {isAddOn ? 'Due date (optional)' : 'Changed due date (optional)'}
            <input type="date" value={normalizedDueDate} onChange={(event) => setDueDate(event.target.value)} style={inputStyle} />
          </label>
        </div>
        <label style={fieldLabelStyle}>
          Optional note / message to counterparty
          <textarea value={note} onChange={(event) => setNote(event.target.value)} rows={3} style={textareaStyle} />
        </label>
        {!isAddOn && affectedItems.length === 0 && (
          <p style={{ fontSize: 12, color: '#B45309', margin: 0, fontWeight: 800 }}>No editable lifecycle obligations are available for a change order.</p>
        )}
        {(submitAttempted || validationMessages.length > 0) && validationMessages.length > 0 && (
          <div style={{ border: '1px solid #FDE68A', background: '#FFFBEB', borderRadius: 8, padding: 10 }}>
            {validationMessages.map((message) => (
              <p key={message} style={{ fontSize: 12, color: '#92400E', margin: '0 0 4px', fontWeight: 800 }}>{message}</p>
            ))}
          </div>
        )}
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <button type="button" onClick={submit} disabled={!canSubmit || saving} style={{ ...(isAddOn ? primaryButtonStyle : amberButtonStyle), opacity: !canSubmit || saving ? 0.6 : 1, cursor: !canSubmit || saving ? 'default' : 'pointer' }}>
            {saving ? 'Submitting...' : proposalActionLabel(mode)}
          </button>
          {saving && <span style={{ fontSize: 12, color: '#64748B', fontWeight: 800 }}>Submitting proposal...</span>}
        </div>
      </div>
    </section>
  )
}

function ProposalList({ proposals, loading, onOpen }: { proposals: LifecycleChangeProposal[]; loading: boolean; onOpen: (proposal: LifecycleChangeProposal) => void }) {
  const groups = [
    { key: 'proposed', label: 'Proposed' },
    { key: 'accepted', label: 'Accepted' },
    { key: 'rejected', label: 'Rejected' },
  ]

  return (
    <section style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, padding: 18 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap', marginBottom: 14 }}>
        <h4 style={{ fontSize: 16, color: '#0F1F3D', margin: 0, fontWeight: 900 }}>Proposal list</h4>
        {loading && <span style={{ fontSize: 12, color: '#64748B', fontWeight: 800 }}>Loading...</span>}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
        {groups.map((group) => {
          const items = proposals.filter((proposal) => proposal.status === group.key)
          return (
            <div key={group.key} style={{ border: '1px solid #E5E7EB', borderRadius: 8, background: '#F8FAFC', padding: 12, minHeight: 130 }}>
              <p style={{ fontSize: 12, color: '#0F1F3D', margin: 0, fontWeight: 900 }}>{group.label}</p>
              <div style={{ display: 'grid', gap: 8, marginTop: 10 }}>
                {items.length === 0 ? (
                  <p style={{ fontSize: 12, color: '#64748B', margin: 0 }}>No {group.label.toLowerCase()} proposals.</p>
                ) : items.map((proposal) => (
                  <button key={proposal.id} type="button" onClick={() => onOpen(proposal)} style={{ textAlign: 'left', border: '1px solid #CBD5E1', borderRadius: 8, background: '#FFFFFF', padding: 10, cursor: 'pointer' }}>
                    <p style={{ fontSize: 13, color: '#0F1F3D', margin: 0, fontWeight: 900 }}>{proposal.title}</p>
                    <p style={{ fontSize: 11, color: '#64748B', margin: '5px 0 0' }}>{proposalTypeLabel(proposal.proposal_type)} - {eventTimeLabel(proposal.created_at)}</p>
                  </button>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}

function ProposalDetailCard({
  proposal,
  partyOptions,
  messages,
  messagesLoading,
  messageSending,
  messageError,
  decisionBusy,
  decisionError,
  onBack,
  onSendMessage,
  onDecide,
}: {
  proposal: LifecycleChangeProposal
  partyOptions: PartyOption[]
  messages: LifecycleChangeProposalMessage[]
  messagesLoading: boolean
  messageSending: boolean
  messageError: string
  decisionBusy: string
  decisionError: string
  onBack: () => void
  onSendMessage: (body: string) => void
  onDecide: (decision: 'accepted' | 'rejected', note: string, finalTerms?: Record<string, string>) => void
}) {
  const proposedBy = proposal.proposed_by?.name || proposal.proposed_by?.email || proposal.proposed_by_email || 'A party'
  const responsible = proposal.responsible_party_label || proposalPartyLabel(partyOptions, proposal.responsible_party) || ''
  return (
    <div style={{ display: 'grid', gap: 14 }}>
      <section style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, padding: 18 }}>
        <button type="button" onClick={onBack} style={{ ...secondaryButtonStyle, marginBottom: 12 }}>Back to Changes / Add-ons</button>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'flex-start' }}>
          <div style={{ minWidth: 0 }}>
            <h3 style={{ fontSize: 22, fontWeight: 900, color: '#0F1F3D', margin: 0 }}>{proposal.title}</h3>
            <p style={{ fontSize: 13, color: '#64748B', margin: '7px 0 0' }}>{proposalTypeLabel(proposal.proposal_type)} proposed by {proposedBy}</p>
          </div>
          <span style={{ borderRadius: 999, padding: '4px 9px', fontSize: 11, fontWeight: 900, ...statusStyle(proposal.status) }}>{proposalStatusLabel(proposal.status)}</span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 10, marginTop: 14 }}>
          <SummaryCell label="Proposal Type" value={proposalTypeLabel(proposal.proposal_type)} />
          <SummaryCell label="Status" value={proposalStatusLabel(proposal.status)} />
          <SummaryCell label="Proposed By" value={proposedBy} />
          <SummaryCell label="Created" value={eventTimeLabel(proposal.created_at)} />
          <SummaryCell label="Responsible" value={responsible || 'Not provided'} />
          <SummaryCell label="Generation" value={generationModeLabel(proposal.generation_mode)} />
          <SummaryCell label="Amount" value={proposal.amount ? formatMoney(proposal.amount) : 'Not provided'} />
          <SummaryCell label="Due Date" value={proposal.due_date ? dueDateLabel(proposal.due_date) : 'Not provided'} />
        </div>
        {proposal.affected_item && (
          <div style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 12, marginTop: 14 }}>
            <p style={{ fontSize: 11, color: '#64748B', margin: 0, fontWeight: 900, textTransform: 'uppercase' }}>Affected obligation</p>
            <p style={{ fontSize: 13, color: '#0F1F3D', margin: '6px 0 0', fontWeight: 900 }}>{proposal.affected_item.title || 'Selected obligation'}</p>
            <p style={{ fontSize: 12, color: '#64748B', margin: '5px 0 0' }}>{humanize(proposal.affected_item.item_type)} - {proposalStatusLabel(proposal.affected_item.status)}</p>
          </div>
        )}
        <div style={{ marginTop: 14 }}>
          <p style={{ fontSize: 12, color: '#94A3B8', margin: 0, fontWeight: 900, textTransform: 'uppercase' }}>Description / reason</p>
          <p style={{ fontSize: 13, color: '#334155', lineHeight: 1.6, whiteSpace: 'pre-wrap', margin: '7px 0 0' }}>{proposal.description}</p>
        </div>
        {proposal.note && (
          <div style={{ marginTop: 14 }}>
            <p style={{ fontSize: 12, color: '#94A3B8', margin: 0, fontWeight: 900, textTransform: 'uppercase' }}>Latest note / message</p>
            <p style={{ fontSize: 13, color: '#334155', lineHeight: 1.6, whiteSpace: 'pre-wrap', margin: '7px 0 0' }}>{proposal.note}</p>
          </div>
        )}
      </section>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.45fr) minmax(260px, 0.85fr)', gap: 12 }}>
        <ProposalMessagesPanel
          messages={messages}
          loading={messagesLoading}
          sending={messageSending}
          error={messageError}
          onSend={onSendMessage}
        />
        <ProposalDecisionPanel
          proposal={proposal}
          partyOptions={partyOptions}
          busy={decisionBusy}
          error={decisionError}
          onDecide={onDecide}
        />
      </div>
      <PlaceholderPanel title="Attachments" />
    </div>
  )
}

const fieldLabelStyle = {
  display: 'grid',
  gap: 6,
  fontSize: 12,
  fontWeight: 900,
  color: '#334155',
}

const inputStyle = {
  width: '100%',
  boxSizing: 'border-box' as const,
  height: 38,
  border: '1px solid #CBD5E1',
  borderRadius: 8,
  padding: '0 10px',
  fontSize: 13,
  color: '#0F1F3D',
  background: '#FFFFFF',
}

const textareaStyle = {
  width: '100%',
  boxSizing: 'border-box' as const,
  border: '1px solid #CBD5E1',
  borderRadius: 8,
  padding: 10,
  fontSize: 13,
  color: '#0F1F3D',
  background: '#FFFFFF',
  resize: 'vertical' as const,
  fontFamily: 'inherit',
}

function SummaryCell({ label, value, surface = '#F8FAFC' }: { label: string; value: string; surface?: string }) {
  return (
    <div style={{ background: surface, border: '1px solid #E5E7EB', borderRadius: 8, padding: 12 }}>
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
  variant = 'default',
  contextLabel,
  showTypeLabel = false,
}: {
  item: TimelineItem
  onOpen: () => void
  onViewSource: () => void
  onReminder: (reminderAt: string | null) => void
  reminderBusy: boolean
  variant?: 'default' | 'child'
  contextLabel?: string
  showTypeLabel?: boolean
}) {
  const action = itemAction(item)
  const [reminderDraft, setReminderDraft] = useState(toDateTimeInput(item.reminder_at))
  useEffect(() => {
    setReminderDraft(toDateTimeInput(item.reminder_at))
  }, [item.id, item.reminder_at])
  const isChild = variant === 'child'
  const isWorkService = isWorkServiceItem(item)
  return (
    <div style={{ background: isChild ? '#FBFDFF' : '#FFFFFF', border: isChild ? '1px solid #D7E0E8' : '1px solid #E5E7EB', borderRadius: 8, padding: isChild ? 12 : 14, marginLeft: isChild ? 12 : 0, boxShadow: isChild ? 'inset 3px 0 0 #94A3B8' : 'none' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
        <div style={{ minWidth: 0 }}>
          <p style={{ fontSize: isChild ? 14 : 15, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>{obligationDisplayTitle(item)}</p>
          {contextLabel && <p style={{ fontSize: 11, color: '#64748B', margin: '5px 0 0', fontStyle: 'italic' }}>{contextLabel}</p>}
          <p style={{ fontSize: 11, color: '#94A3B8', margin: '5px 0 0' }}>{sourceLabel(item)}</p>
          {showTypeLabel && <span style={{ display: 'inline-flex', marginTop: 7, borderRadius: 999, padding: '4px 9px', fontSize: 11, fontWeight: 900, background: '#EFF6FF', color: '#1D4ED8' }}>{itemTypeLabel(item)}</span>}
        </div>
        <span style={{ alignSelf: 'flex-start', borderRadius: 999, padding: '4px 9px', fontSize: 11, fontWeight: 800, ...statusStyle(performanceStatusStyleKey(item)) }}>{performanceStatusLabel(item)}</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8, marginTop: 12 }}>
        {!isWorkService && <SmallFact label="Amount" value={formatMoney(item.amount, item.currency || 'USD')} />}
        <SmallFact label="Due / Delivery" value={dueDateLabel(item.due_date)} />
        <SmallFact label="Responsible" value={item.responsible_party || 'Not set'} />
      </div>
      {item.description && <p style={{ fontSize: 12, color: '#475569', lineHeight: 1.5, margin: '10px 0 0' }}>{item.description}</p>}
      {!isCompletedPerformanceItem(item) && (
        <section style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 10, marginTop: 12 }}>
          <p style={{ fontSize: 10, color: '#64748B', margin: 0, fontWeight: 900, textTransform: 'uppercase' }}>Private reminder</p>
          <p style={{ fontSize: 12, color: '#334155', margin: '4px 0 8px', fontWeight: 800 }}>{reminderLabel(item.reminder_at)}</p>
          <div className="agreement-performance-reminder-row" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8, alignItems: 'center' }}>
            <span className="agreement-performance-reminder-input-wrap" data-empty={reminderDraft ? 'false' : 'true'}>
              <input
                className="agreement-performance-reminder-input"
                type="datetime-local"
                value={reminderDraft}
                onChange={(event) => setReminderDraft(event.target.value)}
                placeholder="mm/dd/yyyy, --:-- --"
                style={{ height: 34, width: 286, minWidth: 286, border: '1px solid #CBD5E1', borderRadius: 8, padding: '0 10px', fontSize: 12, color: '#243447', background: '#FFFFFF' }}
              />
              <span className="agreement-performance-reminder-empty" aria-hidden="true">
                <span>mm/dd/yyyy, --:-- --</span>
                <span className="agreement-performance-reminder-calendar" />
              </span>
            </span>
            <div className="agreement-performance-reminder-actions" style={{ gridColumn: '2 / 3', justifySelf: 'end', transform: 'translateX(-50%)', display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <button type="button" onClick={() => onReminder(fromDateTimeInput(reminderDraft))} disabled={reminderBusy || !reminderDraft} style={{ ...amberButtonStyle, opacity: reminderBusy || !reminderDraft ? 0.65 : 1, cursor: reminderBusy || !reminderDraft ? 'default' : 'pointer' }}>
                {reminderBusy ? 'Saving...' : item.reminder_at ? 'Update Reminder' : 'Set Reminder'}
              </button>
              <button type="button" onClick={() => { setReminderDraft(''); onReminder(null) }} disabled={reminderBusy || !item.reminder_at} style={{ ...secondaryButtonStyle, opacity: reminderBusy || !item.reminder_at ? 0.55 : 1, cursor: reminderBusy || !item.reminder_at ? 'default' : 'pointer' }}>
                Clear
              </button>
            </div>
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
    <div style={{ display: 'grid', gap: 12, background: '#E5E7EB', padding: 12, borderRadius: 8 }}>
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
                  <span style={{ borderRadius: 999, padding: '3px 8px', fontSize: 10, fontWeight: 900, ...statusStyle(performanceStatusStyleKey(item)) }}>{performanceStatusLabel(item)}</span>
                </div>
                <p style={{ fontSize: 14, fontWeight: 900, color: '#0F1F3D', margin: 0 }}>{obligationDisplayTitle(item)}</p>
                <p style={{ fontSize: 12, color: '#64748B', margin: '5px 0 0' }}>Responsible: {item.responsible_party || 'Not set'}{amount ? ` · ${amount}` : ''}</p>
                {item.reminder_at && !isCompletedPerformanceItem(item) && <p style={{ fontSize: 11, color: '#475569', fontWeight: 900, margin: '5px 0 0' }}>Private reminder: {reminderLabel(item.reminder_at)}</p>}
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                <button type="button" onClick={() => onOpen(item)} style={secondaryButtonStyle}>View Obligation</button>
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
        const itemId = metadataString(event.metadata, 'lifecycle_item_id') || metadataString(event.metadata, 'item_id') || metadataString(event.metadata, 'affected_item_id')
        const item = itemById.get(itemId)
        const itemTitle = item?.title || metadataString(event.metadata, 'item_title') || event.description || 'this obligation'
        const proposalTitle = metadataString(event.metadata, 'proposal_title')
        const actor = metadataString(event.metadata, 'actor_label') || item?.responsible_party || 'A party'
        const verb = performanceEventVerb(event)
        const result = metadataString(event.metadata, 'result_status') || metadataString(event.metadata, 'status') || metadataString(event.metadata, 'decision')
        const sentence = proposalTitle && event.event_type === 'change_order_accepted'
          ? `${actor} accepted Change Order: ${proposalTitle}.`
          : proposalTitle && event.event_type === 'add_on_accepted'
            ? `${actor} accepted Add-on: ${proposalTitle}. New obligation added.`
          : proposalTitle && event.event_type === 'change_proposal_accepted'
            ? `${actor} accepted proposal: ${proposalTitle}.`
            : proposalTitle && event.event_type === 'change_proposal_rejected'
            ? `${actor} rejected proposal: ${proposalTitle}.`
            : verb ? `${actor} marked "${itemTitle}" as ${verb}.` : event.description || performanceEventActionLabel(event)
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
    <section style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, padding: 14, boxSizing: 'border-box' }}>
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
        <p style={{ fontSize: 12, color: '#64748B', margin: '8px 0 0', lineHeight: 1.5 }}>Upload proof or receipt before marking this obligation performed.</p>
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
  loadError,
  busy,
  canUpload,
  onUpload,
}: {
  attachments: LifecycleAttachment[]
  loading: boolean
  loadError: string
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
      // The proof section reports upload failures inline.
    }
  }

  return (
    <section style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, padding: 14, height: '100%', minWidth: 0, boxSizing: 'border-box' }}>
      <p style={{ fontSize: 12, color: '#94A3B8', margin: 0, fontWeight: 900, textTransform: 'uppercase' }}>Proof / Receipt</p>
      <div style={{ display: 'grid', gap: 8, marginTop: 10, minWidth: 0 }}>
        {loadError && (
          <div style={{ border: '1px solid #FECACA', borderRadius: 8, padding: 12, background: '#FEF2F2' }}>
            <p style={{ fontSize: 13, color: '#B91C1C', margin: 0 }}>{loadError}</p>
          </div>
        )}
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
        <div style={{ display: 'grid', gap: 10, background: '#FFF7ED', border: '1px solid #FED7AA', borderRadius: 8, padding: 12, marginTop: 14, minWidth: 0 }}>
          <p style={{ fontSize: 12, color: '#9A3412', margin: 0, fontWeight: 900 }}>Add another proof / receipt</p>
          <input
            key={inputKey}
            type="file"
            onChange={(event) => handleFileChange(event.target.files?.[0] || null)}
            style={{ width: '100%', maxWidth: '100%', minWidth: 0, border: '1px solid #CBD5E1', borderRadius: 8, padding: 10, background: '#FFFFFF', color: '#243447', fontSize: 12 }}
          />
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Optional note"
            rows={3}
            style={{ width: '100%', maxWidth: '100%', minWidth: 0, border: '1px solid #CBD5E1', borderRadius: 8, padding: 10, background: '#FFFFFF', color: '#243447', fontSize: 12, resize: 'vertical', fontFamily: 'inherit' }}
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
    <section style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, padding: 14, height: '100%', minHeight: 0, overflowY: 'auto', boxSizing: 'border-box' }}>
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
            style={{ border: '1px solid #CBD5E1', borderRadius: 8, padding: 10, background: '#FFFFFF', color: '#243447', fontSize: 12, resize: 'vertical', fontFamily: 'inherit' }}
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
              <div style={{ maxWidth: '78%', background: mine ? '#243447' : '#FFFFFF', color: mine ? '#FFFFFF' : '#243447', border: mine ? '1px solid #243447' : '1px solid #E5E7EB', borderRadius: 8, padding: 10 }}>
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
          style={{ border: '1px solid #CBD5E1', borderRadius: 8, padding: 10, background: '#FFFFFF', color: '#243447', fontSize: 13, resize: 'vertical', fontFamily: 'inherit' }}
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



function ProposalMessagesPanel({
  messages,
  loading,
  sending,
  error,
  onSend,
}: {
  messages: LifecycleChangeProposalMessage[]
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
        <p style={{ fontSize: 12, color: '#94A3B8', margin: 0, fontWeight: 900, textTransform: 'uppercase' }}>Proposal Chat</p>
        {loading && <span style={{ fontSize: 11, color: '#64748B', fontWeight: 800 }}>Loading...</span>}
      </div>
      <div ref={listRef} style={{ display: 'grid', gap: 10, maxHeight: 320, overflowY: 'auto', background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 12 }}>
        {safeMessages.length === 0 ? (
          <p style={{ fontSize: 13, color: '#64748B', margin: 0 }}>No proposal messages yet.</p>
        ) : safeMessages.map((message, index) => {
          const mine = Boolean(message.is_mine)
          const sender = message.sender?.name || message.sender?.email || message.sender_email || 'A party'
          const createdAt = message.created_at || message.updated_at || ''
          const body = typeof message.body === 'string' ? message.body : ''
          return (
            <div key={message.id || `${createdAt}-${index}`} style={{ display: 'grid', justifyItems: mine ? 'end' : 'start' }}>
              <div style={{ maxWidth: '78%', background: mine ? '#243447' : '#FFFFFF', color: mine ? '#FFFFFF' : '#243447', border: mine ? '1px solid #243447' : '1px solid #E5E7EB', borderRadius: 8, padding: 10 }}>
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
          placeholder="Write a proposal message"
          maxLength={2000}
          rows={3}
          style={{ border: '1px solid #CBD5E1', borderRadius: 8, padding: 10, background: '#FFFFFF', color: '#243447', fontSize: 13, resize: 'vertical', fontFamily: 'inherit' }}
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

function ProposalDecisionPanel({
  proposal,
  partyOptions,
  busy,
  error,
  onDecide,
}: {
  proposal: LifecycleChangeProposal
  partyOptions: PartyOption[]
  busy: string
  error: string
  onDecide: (decision: 'accepted' | 'rejected', note: string, finalTerms?: Record<string, string>) => void
}) {
  const [note, setNote] = useState('')
  const [finalDueDate, setFinalDueDate] = useState(dateInputValue(proposal.due_date))
  const [finalAmount, setFinalAmount] = useState(proposal.amount || '')
  const [finalResponsibleParty, setFinalResponsibleParty] = useState(proposal.proposal_type === 'add_on' ? (proposal.final_responsible_party || '') : (proposal.responsible_party || ''))
  const isProposed = proposal.status === 'proposed'
  const canDecide = Boolean(proposal.can_decide)
  const isProposer = Boolean(proposal.is_proposer)
  const isChangeOrder = proposal.proposal_type === 'change_order'
  const isAddOn = proposal.proposal_type === 'add_on'
  const acceptsFinalTerms = isChangeOrder || isAddOn
  const acceptBusy = busy === `${proposal.id}:accepted`
  const rejectBusy = busy === `${proposal.id}:rejected`
  const decidedBy = proposal.decided_by?.name || proposal.decided_by?.email || 'A party'
  const currentItem = proposal.affected_item
  const currentItemStatus = currentItem ? performanceStatusLabel(currentItem as TimelineItem) : 'Not provided'

  useEffect(() => {
    setNote('')
    setFinalDueDate(dateInputValue(proposal.final_due_date || proposal.due_date))
    setFinalAmount(proposal.final_amount || proposal.amount || '')
    setFinalResponsibleParty(proposal.proposal_type === 'add_on' ? (proposal.final_responsible_party || '') : (proposal.final_responsible_party || proposal.responsible_party || ''))
  }, [proposal.id, proposal.due_date, proposal.amount, proposal.responsible_party, proposal.final_due_date, proposal.final_amount, proposal.final_responsible_party])

  function acceptProposal() {
    const finalTerms: Record<string, string> = {}
    if (acceptsFinalTerms) {
      if (finalDueDate) finalTerms.final_due_date = finalDueDate
      if (finalAmount.trim()) finalTerms.final_amount = finalAmount.trim()
      if (finalResponsibleParty.trim()) finalTerms.final_responsible_party = finalResponsibleParty.trim()
    }
    onDecide('accepted', note, finalTerms)
  }

  return (
    <section style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, padding: 14 }}>
      <p style={{ fontSize: 12, color: '#94A3B8', margin: 0, fontWeight: 900, textTransform: 'uppercase' }}>Decision</p>
      {isProposed && canDecide ? (
        <div style={{ display: 'grid', gap: 12, marginTop: 10 }}>
          {acceptsFinalTerms && (
            <div style={{ display: 'grid', gap: 12 }}>
              <p style={{ fontSize: 13, color: '#334155', lineHeight: 1.5, margin: 0 }}>{isChangeOrder ? 'Chat can clarify terms. Enter the final accepted terms here before accepting this Change Order.' : 'Chat can clarify terms. Enter the final accepted terms for the new Add-on obligation.'}</p>
              {isChangeOrder && currentItem && (
                <div style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 12 }}>
                  <p style={{ fontSize: 11, color: '#64748B', margin: 0, fontWeight: 900, textTransform: 'uppercase' }}>Current affected obligation</p>
                  <div style={{ display: 'grid', gap: 8, marginTop: 10 }}>
                    <SummaryCell label="Agreement" value={proposal.contract_title || 'Not provided'} />
                    <SummaryCell label="Obligation" value={currentItem.title || 'Not provided'} />
                    <SummaryCell label="Current Due Date" value={currentItem.due_date ? dueDateLabel(currentItem.due_date) : 'Not provided'} />
                    <SummaryCell label="Current Amount" value={currentItem.amount ? formatMoney(currentItem.amount) : 'Not provided'} />
                    <SummaryCell label="Current Responsible" value={currentItem.responsible_party || 'Not provided'} />
                    <SummaryCell label="Current Status" value={currentItemStatus} />
                  </div>
                </div>
              )}
              <div style={{ background: '#FFF7ED', border: '1px solid #FED7AA', borderRadius: 8, padding: 12, display: 'grid', gap: 10 }}>
                <p style={{ fontSize: 12, color: '#9A3412', margin: 0, fontWeight: 900 }}>Final accepted terms</p>
                <label style={fieldLabelStyle}>
                  Final due date
                  <input type="date" value={finalDueDate} onChange={(event) => setFinalDueDate(event.target.value)} style={inputStyle} />
                </label>
                <label style={fieldLabelStyle}>
                  Final amount
                  <input type="number" step="0.01" min="0" value={finalAmount} onChange={(event) => setFinalAmount(event.target.value)} style={inputStyle} />
                </label>
                <label style={fieldLabelStyle}>
                  Final responsible party
                  <select value={finalResponsibleParty} onChange={(event) => setFinalResponsibleParty(event.target.value)} style={inputStyle}>
                    <option value="">No change</option>
                    {partyOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                </label>
              </div>
            </div>
          )}
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Decision note"
            rows={3}
            style={{ border: '1px solid #CBD5E1', borderRadius: 8, padding: 10, background: '#FFFFFF', color: '#243447', fontSize: 13, resize: 'vertical', fontFamily: 'inherit' }}
          />
          {error && <p style={{ fontSize: 12, color: '#B91C1C', margin: 0, fontWeight: 800 }}>{error}</p>}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button type="button" onClick={acceptProposal} disabled={Boolean(busy)} style={{ ...primaryButtonStyle, opacity: busy && !acceptBusy ? 0.55 : 1, cursor: busy ? 'default' : 'pointer' }}>
              {acceptBusy ? 'Accepting...' : isChangeOrder ? 'Accept Change Order' : 'Accept'}
            </button>
            <button type="button" onClick={() => onDecide('rejected', note)} disabled={Boolean(busy)} style={{ ...amberButtonStyle, opacity: busy && !rejectBusy ? 0.55 : 1, cursor: busy ? 'default' : 'pointer' }}>
              {rejectBusy ? 'Rejecting...' : isChangeOrder ? 'Reject Change Order' : 'Reject'}
            </button>
          </div>
        </div>
      ) : isProposed && isProposer ? (
        <p style={{ fontSize: 13, color: '#64748B', lineHeight: 1.5, margin: '10px 0 0' }}>Waiting for counterparty decision.</p>
      ) : isProposed ? (
        <p style={{ fontSize: 13, color: '#64748B', lineHeight: 1.5, margin: '10px 0 0' }}>Only the non-proposing agreement party can decide this proposal.</p>
      ) : (
        <div style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 12, marginTop: 10, display: 'grid', gap: 10 }}>
          <div>
            <p style={{ fontSize: 14, color: '#0F1F3D', margin: 0, fontWeight: 900 }}>{proposalStatusLabel(proposal.status)}</p>
            <p style={{ fontSize: 12, color: '#64748B', margin: '6px 0 0' }}>Decided by {decidedBy} · {eventTimeLabel(proposal.decided_at || undefined)}</p>
          </div>
          {acceptsFinalTerms && proposal.status === 'accepted' && (
            <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, padding: 12 }}>
              <p style={{ fontSize: 11, color: '#64748B', margin: 0, fontWeight: 900, textTransform: 'uppercase' }}>Accepted final terms</p>
              <div style={{ display: 'grid', gap: 8, marginTop: 10 }}>
                <SummaryCell label="Final Due Date" value={proposal.final_due_date ? dueDateLabel(proposal.final_due_date) : 'Unchanged'} />
                <SummaryCell label="Final Amount" value={proposal.final_amount ? formatMoney(proposal.final_amount) : 'Unchanged'} />
                <SummaryCell label="Final Responsible" value={proposal.final_responsible_party || proposal.responsible_party_label || 'Unchanged'} />
                <SummaryCell label="Generation" value={generationModeLabel(proposal.generation_mode)} />
              </div>
            </div>
          )}
          {(proposal.created_items?.length || proposal.created_item) && (
            <div style={{ background: '#FFFFFF', border: '1px solid #D1FAE5', borderRadius: 8, padding: 12 }}>
              <p style={{ fontSize: 11, color: '#047857', margin: 0, fontWeight: 900, textTransform: 'uppercase' }}>Created obligations</p>
              <div style={{ display: 'grid', gap: 8, marginTop: 10 }}>
                <SummaryCell label="Count" value={`${proposal.generated_item_count || proposal.created_items?.length || 1}`} />
                {(proposal.created_items && proposal.created_items.length > 0 ? proposal.created_items : proposal.created_item ? [proposal.created_item] : []).map((item) => (
                  <div key={item.id} style={{ border: '1px solid #E5E7EB', borderRadius: 8, padding: 10, background: '#F8FAFC' }}>
                    <p style={{ fontSize: 13, fontWeight: 900, color: '#0F1F3D', margin: 0 }}>{item.title || 'New obligation'}</p>
                    <p style={{ fontSize: 12, color: '#64748B', margin: '5px 0 0' }}>{humanize(item.item_type)} · {item.due_date ? dueDateLabel(item.due_date) : 'No due date'} · Responsible: {item.responsible_party || 'Not provided'}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
          {proposal.decision_note && <p style={{ fontSize: 12, color: '#334155', lineHeight: 1.5, whiteSpace: 'pre-wrap', margin: 0 }}>{proposal.decision_note}</p>}
        </div>
      )}
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
  item,
  isMyObligationsView,
  isWorkServicesView,
  events,
  attachments,
  attachmentsLoading,
  attachmentError,
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
  item: TimelineItem
  isMyObligationsView?: boolean
  isWorkServicesView?: boolean
  events: TimelineEvent[]
  attachments: LifecycleAttachment[]
  attachmentsLoading: boolean
  attachmentError: string
  attachmentBusy: boolean
  messages: LifecycleMessage[]
  messagesLoading: boolean
  messageSending: boolean
  messageError: string
  responseBusy: string
  busy: string
  onViewSource: () => void
  onAction: (action: string) => void
  onUploadProof: (file: File, note: string) => Promise<void>
  onSendMessage: (body: string) => void
  onRespond: (response: string, note: string) => void
}) {
  const isPaymentDetail = isPaymentItem(item)
  const isServiceDetail = isWorkServiceItem(item)
  const action = itemAction(item)
  const actionBusy = action ? busy === `${item.id}:${action.action}` : false
  const obligationRecordSurface = isMyObligationsView ? '#F6FEF9' : isPaymentDetail ? '#E8EEF5' : isServiceDetail || isWorkServicesView ? '#F5FBFF' : '#FFFFFF'
  const summaryCellSurface = '#FFFFFF'
  const obligationDetailColumnTemplate = 'minmax(360px, 1.35fr) minmax(494px, 1.5fr)'
  const executionGridStyle = { display: 'grid', gridTemplateColumns: obligationDetailColumnTemplate, gap: 14, alignItems: 'stretch' }
  const executionSideColumnStyle = { display: 'grid', gridTemplateRows: 'minmax(0, 1fr) auto', gap: 14, alignItems: 'stretch', height: '100%', minHeight: 0 }
  const finalRowGridStyle = { display: 'grid', gridTemplateColumns: obligationDetailColumnTemplate, gap: 14, alignItems: 'start' }

  return (
    <div style={{ display: 'grid', gap: 14 }}>
      <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, padding: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', minWidth: 0 }}>
            <h3 style={{ margin: 0, fontSize: 18, fontWeight: 900, color: '#0F1F3D' }}>{obligationDisplayTitle(item)}</h3>
            <span style={{ borderRadius: 999, padding: '4px 9px', fontSize: 11, fontWeight: 900, background: isServiceDetail ? '#F0FDF4' : isPaymentDetail ? '#EFF6FF' : '#F8FAFC', color: isServiceDetail ? '#15803D' : isPaymentDetail ? '#1D4ED8' : '#475569' }}>{isServiceDetail ? 'Service Obligation' : isPaymentDetail ? 'Payment Obligation' : itemTypeLabel(item)}</span>
          </div>
          <span style={{ borderRadius: 999, padding: '4px 9px', fontSize: 11, fontWeight: 900, ...statusStyle(performanceStatusStyleKey(item)) }}>{performanceStatusLabel(item)}</span>
        </div>
        <div style={{ marginTop: 10 }}>
          <p style={{ fontSize: 12, color: '#94A3B8', margin: 0, fontWeight: 900, textTransform: 'uppercase' }}>{sourceLabel(item)}</p>
          <p style={{ fontSize: 13, color: '#334155', lineHeight: 1.55, margin: '7px 0 0' }}>{item.description || 'No additional detail recorded for this performance item.'}</p>
        </div>
      </div>

      <section style={{ background: obligationRecordSurface, border: '1px solid #E5E7EB', borderRadius: 8, overflow: 'hidden' }}>
        <div style={{ background: `linear-gradient(90deg, #243447 0, #243447 168px, #3B4A5C 194px, ${obligationRecordSurface} 220px, ${obligationRecordSurface} 100%)`, padding: '10px 16px' }}>
          <p style={{ fontSize: 12, color: '#FFFFFF', margin: 0, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Obligation record</p>
        </div>
        <div style={{ display: 'grid', gap: 14, padding: 16 }}>
          <section style={{ borderBottom: '1px solid #E5E7EB', paddingBottom: 14 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10 }}>
              <SummaryCell label="Responsible" value={item.responsible_party || 'Not set'} surface={summaryCellSurface} />
              {!isServiceDetail && <SummaryCell label="Amount" value={formatMoney(item.amount, item.currency || 'USD')} surface={summaryCellSurface} />}
              <SummaryCell label="Due / Delivery" value={dueDateLabel(item.due_date)} surface={summaryCellSurface} />
              <SummaryCell label={completionDateTitle(item)} value={completionDateLabel(events, item)} surface={summaryCellSurface} />
              <SummaryCell label="Current Status" value={performanceStatusLabel(item)} surface={summaryCellSurface} />
            </div>
          </section>

          <div className="agreement-performance-detail-top-grid" style={executionGridStyle}>
            <ProofReceiptsSection attachments={attachments} loading={attachmentsLoading} loadError={attachmentError} busy={attachmentBusy} canUpload={Boolean(item.can_upload_proof)} onUpload={onUploadProof} />
            <div className="agreement-performance-detail-side-column" style={executionSideColumnStyle}>
              <CounterpartyReviewSection item={item} busy={responseBusy} onRespond={onRespond} />
              <PerformanceActionSection
                item={item}
                action={action}
                actionBusy={actionBusy}
                onViewSource={onViewSource}
                onAction={onAction}
              />
            </div>
          </div>

          <div className="agreement-performance-detail-bottom-grid" style={finalRowGridStyle}>
            <MessagesPanel messages={messages} loading={messagesLoading} sending={messageSending} error={messageError} onSend={onSendMessage} />
            <section style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, padding: 14 }}>
              <p style={{ fontSize: 12, color: '#94A3B8', margin: 0, fontWeight: 900, textTransform: 'uppercase' }}>Item History</p>
              <div style={{ marginTop: 10 }}>
                <ItemHistoryPanel events={events} item={item} />
              </div>
            </section>
          </div>
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
  border: '1px solid #243447',
  borderRadius: 8,
  background: '#243447',
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

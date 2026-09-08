// ============================================================
// PROTECTED FILE — DO NOT MODIFY WITHOUT EXPLICIT APPROVAL
// ============================================================
// This is the contract editor/workspace — the highest priority
// asset in the bonUP Blackboard frontend.
//
// NO refactoring, cleanup, splitting, renaming, bug fixes, or
// logic changes are permitted without explicit written approval
// from the project owner.
//
// This file is intentionally preserved exactly as-is.
// Known issues (wrong AI endpoint URLs, hardcoded USER_TIER,
// static ACTIVITY data, no content persistence) are documented
// in EDITOR_PROTECTION.md and are NOT to be fixed here without
// a dedicated, scoped approval.
//
// Reference: EDITOR_PROTECTION.md
// ============================================================

import { useState, useRef, useEffect } from 'react'
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom'
import { MagnifyingGlassIcon, PlusIcon, RectangleStackIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { useAuth } from '@/context/AuthContext'
import { useNotification } from '@/context/NotificationContext'
import api from '@/api/client'
import {
  loadContacts,
  saveContactFromParty,
  getContactInitials,
  getContactDisplayName,
  type Contact,
} from '@/lib/contacts'

// ── Data ──────────────────────────────────────────────────────────────────────

const FONTS = [
  'Arial', 'Georgia', 'Times New Roman', 'Helvetica', 'Courier New',
  'Verdana', 'Trebuchet MS', 'Impact', 'Comic Sans MS', 'Palatino',
  'Garamond', 'Bookman', 'Avant Garde', 'Optima', 'Futura', 'Gill Sans',
  'Century Gothic', 'Calibri', 'Cambria', 'Constantia', 'Candara',
  'Corbel', 'Segoe UI', 'Tahoma', 'Geneva', 'Lucida Grande',
  'Lucida Sans', 'Rockwell', 'Franklin Gothic', 'Baskerville',
]

const FONT_SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72]

// Tier slugs matching DB: 'trial' | 'sol_member' | 'per_contract' | 'starter' | 'professional' | 'business' | 'anchor'
const USER_TIER = 'business'

const CURRENCIES = [
  ['USD', 'US Dollar'], ['CAD', 'Canadian Dollar'], ['MXN', 'Mexican Peso'],
  ['BRL', 'Brazilian Real'], ['ARS', 'Argentine Peso'], ['COP', 'Colombian Peso'],
  ['CLP', 'Chilean Peso'], ['PEN', 'Peruvian Sol'], ['HTG', 'Haitian Gourde'],
  ['EUR', 'Euro'], ['GBP', 'British Pound'], ['CHF', 'Swiss Franc'],
  ['SEK', 'Swedish Krona'], ['NOK', 'Norwegian Krone'], ['DKK', 'Danish Krone'],
  ['AED', 'UAE Dirham'], ['SAR', 'Saudi Riyal'], ['EGP', 'Egyptian Pound'],
  ['MAD', 'Moroccan Dirham'], ['QAR', 'Qatari Riyal'], ['KWD', 'Kuwaiti Dinar'],
  ['ZAR', 'South African Rand'], ['NGN', 'Nigerian Naira'], ['GHS', 'Ghanaian Cedi'],
  ['KES', 'Kenyan Shilling'], ['UGX', 'Ugandan Shilling'], ['TZS', 'Tanzanian Shilling'],
  ['ETB', 'Ethiopian Birr'], ['XOF', 'West African CFA Franc'], ['XAF', 'Central African CFA Franc'],
  ['RWF', 'Rwandan Franc'], ['MZN', 'Mozambican Metical'], ['ZMW', 'Zambian Kwacha'],
  ['JPY', 'Japanese Yen'], ['CNY', 'Chinese Yuan'], ['INR', 'Indian Rupee'],
  ['KRW', 'South Korean Won'], ['SGD', 'Singapore Dollar'], ['HKD', 'Hong Kong Dollar'],
  ['AUD', 'Australian Dollar'], ['NZD', 'New Zealand Dollar'], ['TWD', 'Taiwan Dollar'],
  ['THB', 'Thai Baht'], ['IDR', 'Indonesian Rupiah'], ['MYR', 'Malaysian Ringgit'],
  ['PHP', 'Philippine Peso'], ['PKR', 'Pakistani Rupee'], ['BDT', 'Bangladeshi Taka'],
  ['VND', 'Vietnamese Dong'],
] as const

interface ContractSection { id: string; number: number; name: string }

interface TemplateItem {
  id: string
  name: string
  category: string
  description: string
  content: string
  tier_required: string
}

interface ObligationTemplateItem {
  id: string
  name: string
  description: string
  content: string
  category: string
  contract_template_id: string | null
}

interface PaymentTemplateItem {
  id: string
  name: string
  description: string
  content: string
  schedule_type: string
  category: string
  contract_template_id: string | null
}

interface ContractVersionPayload {
  id: string
  content_snapshot: string
  status: string
  version_number: number
}

interface ContractRetrievePayload {
  id: string
  title?: string
  status?: string
  state?: string
  counterparty_name?: string
  counterparty_email?: string
  structure_type?: string
  entity_type?: string
  entity?: string | null
  contract_type?: string
  language?: string
  start_date?: string | null
  end_date?: string | null
  contract_value?: string | null
  currency?: string
  jurisdiction?: string
  governing_law?: string
  confidentiality?: string
  dispute_resolution?: string
  description?: string
  latest_version?: ContractVersionPayload | null
}

interface ContractDocumentPayload {
  id: string
  upload_id: string
  file_url: string | null
  file_name: string
  file_type: string
  file_size?: number
  title?: string
  attached_at: string
}

interface PreparedTerm {
  description?: string
  amount?: string | null
  due_date?: string | null
  deadline?: string | null
  responsible_party?: string
  trigger_condition?: string
}

interface PreparedTerms {
  payment_terms?: PreparedTerm[]
  service_obligations?: PreparedTerm[]
  delivery_obligations?: PreparedTerm[]
  milestones?: PreparedTerm[]
  deadlines?: string[]
  trigger_conditions?: string[]
  extraction_method?: string
}

interface PersistedTemplateDraft {
  source?: string
  template_id?: string
  template_name?: string
  category?: string
  editor_html?: string
  sections?: ContractSection[]
  clauses?: { body?: string }[]
  prepared_terms?: PreparedTerms
  final_editor_html?: string
}

const DEFAULT_SECTIONS: ContractSection[] = [
  { id: 's1',  number: 1,  name: 'Introduction' },
  { id: 's2',  number: 2,  name: 'Parties' },
  { id: 's3',  number: 3,  name: 'Recitals / Background' },
  { id: 's4',  number: 4,  name: 'Terms and Conditions' },
  { id: 's5',  number: 5,  name: 'Obligations' },
  { id: 's6',  number: 6,  name: 'Payment Terms' },
  { id: 's7',  number: 7,  name: 'Confidentiality' },
  { id: 's8',  number: 8,  name: 'Intellectual Property' },
  { id: 's9',  number: 9,  name: 'Termination' },
  { id: 's10', number: 10, name: 'Dispute Resolution' },
  { id: 's11', number: 11, name: 'Governing Law' },
  { id: 's12', number: 12, name: 'Signatures' },
]

const CONTRACT_TOOLS = [
  { icon: '📋', label: 'Contract Details' },
  { icon: '📑', label: 'Contract Sections' },
  { icon: '👥', label: 'Parties' },
  { icon: '✓', label: 'Obligations' },
  { icon: '💰', label: 'Payments' },
  { icon: '📎', label: 'Attachments' },
  { icon: '📐', label: 'Contract Templates' },
  { icon: '🔢', label: 'Calculator' },
  { icon: '📅', label: 'Calendar' },
  { icon: '🔒', label: 'Permissions' },
  { icon: '📊', label: 'Analytics' },
  { icon: '🔍', label: 'Contract Analysis' },
  { icon: '⚡', label: 'Contract Counter' },
  { icon: '⚙️', label: 'Settings' },
  { icon: '🎬', label: 'Tutorial' },
]

const ACTIVITY = [
  { icon: '🟢', text: 'Contract created', time: 'just now' },
  { icon: '📎', text: 'File attached', time: '2m ago' },
  { icon: '👁', text: 'Viewed by Meridian Labs', time: '5m ago' },
  { icon: '✏️', text: 'Draft saved', time: '10m ago' },
  { icon: '👥', text: 'Party invited', time: '15m ago' },
]

// ── Helpers ───────────────────────────────────────────────────────────────────

function Divider() {
  return (
    <div style={{
      width: 1, height: 20, background: 'rgba(255,255,255,0.15)',
      marginLeft: 4, marginRight: 4, flexShrink: 0,
    }} />
  )
}

function TBtn({
  label, title, onClick,
}: {
  label: string
  title?: string
  onClick?: () => void
}) {
  return (
    <button
      title={title}
      onClick={onClick}
      style={{
        width: 28, height: 28, borderRadius: 4, border: 'none',
        background: 'transparent', color: 'rgba(255,255,255,0.75)', fontSize: 13,
        cursor: 'pointer', flexShrink: 0,
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.1)')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
    >
      {label}
    </button>
  )
}

function GhostActionBtn({ label, onClick }: { label: string; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        color: 'rgba(255,255,255,0.6)',
        border: '1px solid rgba(255,255,255,0.15)',
        fontSize: 12, height: 28, padding: '0 12px',
        borderRadius: 6, background: 'transparent',
        cursor: 'pointer', flexShrink: 0, whiteSpace: 'nowrap',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.07)')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
    >
      {label}
    </button>
  )
}

// ── Attachments panel helpers ────────────────────────────────────────────────

type AttachFileType = 'pdf' | 'docx' | 'xlsx' | 'image' | 'video' | 'other'

interface AttachmentFile {
  id: string
  name: string
  sizeStr: string
  sizeBytes: number
  date: string
  type: AttachFileType
  uploading?: boolean
  progress?: number
  uploadId?: string
  documentId?: string
  fileUrl?: string | null
  deleting?: boolean
  error?: string
}

interface VaultSelectionFile {
  id: string
  file_name: string
  file_type: string
  file_size: number
  uploaded_at: string
}

function getFileType(name: string): AttachFileType {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  if (ext === 'pdf') return 'pdf'
  if (ext === 'docx' || ext === 'doc') return 'docx'
  if (['xlsx', 'xls', 'csv'].includes(ext)) return 'xlsx'
  if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'].includes(ext)) return 'image'
  if (['mp4', 'mov', 'avi', 'webm'].includes(ext)) return 'video'
  return 'other'
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatVaultDate(value: string) {
  if (!value) return 'Unknown date'
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(value))
}

function vaultFileTypeLabel(fileType: string) {
  const normalized = fileType.toLowerCase()
  if (normalized === 'pdf') return 'PDF'
  if (normalized === 'image') return 'Image'
  if (normalized === 'video') return 'Video'
  if (normalized === 'audio') return 'Audio'
  if (normalized === 'slides') return 'Slides'
  if (normalized === 'document') return 'Document'
  return 'File'
}

function attachmentFromDocument(doc: ContractDocumentPayload): AttachmentFile {
  const name = doc.file_name || doc.title || 'Attached file'
  const sizeBytes = doc.file_size ?? 0
  return {
    id: doc.id,
    name,
    sizeStr: sizeBytes > 0 ? formatBytes(sizeBytes) : 'Unknown size',
    sizeBytes,
    date: formatVaultDate(doc.attached_at),
    type: getFileType(name),
    uploading: false,
    progress: 100,
    uploadId: doc.upload_id,
    documentId: doc.id,
    fileUrl: doc.file_url,
  }
}

const FILE_TYPE_META: Record<AttachFileType, { bg: string; icon: string }> = {
  pdf:   { bg: '#FEE2E2', icon: '📄' },
  docx:  { bg: '#DBEAFE', icon: '📝' },
  xlsx:  { bg: '#D1FAE5', icon: '📊' },
  image: { bg: '#FEF3C7', icon: '🖼' },
  video: { bg: '#EDE9FE', icon: '🎬' },
  other: { bg: '#F3F4F6', icon: '📎' },
}

const ATTACH_PLACEHOLDER: AttachmentFile[] = [
  { id: 'p1', name: 'Service_Agreement_Draft.pdf', sizeStr: '2.4 MB', sizeBytes: 2516582, date: 'Apr 5, 2026', type: 'pdf' },
  { id: 'p2', name: 'Company_Profile.docx',        sizeStr: '1.1 MB', sizeBytes: 1153434, date: 'Apr 4, 2026', type: 'docx' },
  { id: 'p3', name: 'Payment_Schedule.xlsx',       sizeStr: '0.8 MB', sizeBytes: 838861,  date: 'Apr 3, 2026', type: 'xlsx' },
]

type AttachFilter = 'all' | 'documents' | 'images' | 'videos' | 'other'

// ── Parties panel helpers ─────────────────────────────────────────────────────

const PARTY_ROLES = [
  'Provider', 'Client', 'Employer', 'Employee',
  'Buyer', 'Seller', 'Landlord', 'Tenant', 'Lender',
  'Borrower', 'Contractor', 'Subcontractor',
  'Licensor', 'Licensee', 'Partner', 'Other (type below)',
]

function getInitials(name: string) {
  const parts = name.trim().split(/\s+/)
  return parts.length >= 2
    ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    : name.substring(0, 2).toUpperCase()
}

interface SearchParty { name: string; bonId: string; initials: string }

interface PartySearchBlockProps {
  searchQuery: string
  onSearchQueryChange: (v: string) => void
  searchResult: SearchParty | null
  onSearchResultChange: (v: SearchParty | null) => void
  searchDone: boolean
  onSearchDoneChange: (v: boolean) => void
  added: boolean
  onAddedChange: (v: boolean) => void
  role: string
  onRoleChange: (v: string) => void
  customRole: string
  onCustomRoleChange: (v: string) => void
}

function PartySearchBlock({
  searchQuery, onSearchQueryChange,
  searchResult, onSearchResultChange,
  searchDone, onSearchDoneChange,
  added, onAddedChange,
  role, onRoleChange,
  customRole, onCustomRoleChange,
}: PartySearchBlockProps) {
  function doSearch() {
    if (!searchQuery.trim()) return
    // Mock — backend will replace
    const name = searchQuery.startsWith('#')
      ? `User ${searchQuery}`
      : searchQuery.charAt(0).toUpperCase() + searchQuery.slice(1)
    const bonId = searchQuery.startsWith('#')
      ? searchQuery
      : `#${searchQuery.toUpperCase().replace(/\s+/g, '').slice(0, 8)}`
    onSearchResultChange({ name, bonId, initials: getInitials(name) })
    onSearchDoneChange(true)
  }

  function siFocus(e: React.FocusEvent<HTMLInputElement>) {
    e.currentTarget.style.borderColor = '#243447'
    e.currentTarget.style.boxShadow = '0 0 0 2px rgba(15,31,61,0.08)'
  }
  function siBlur(e: React.FocusEvent<HTMLInputElement>) {
    e.currentTarget.style.borderColor = '#D1D5DB'
    e.currentTarget.style.boxShadow = 'none'
  }

  const AVATAR_S: React.CSSProperties = {
    width: 36, height: 36, borderRadius: '50%',
    background: '#243447', color: 'white', fontSize: 13, fontWeight: 600,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    flexShrink: 0,
  }

  return (
    <div style={{
      background: 'white', borderRadius: 8, padding: 12,
      marginBottom: 12, border: '1px solid #D1D5DB',
    }}>
      <p style={{ fontSize: 11, color: '#6B7280', margin: '0 0 6px' }}>
        Find by bonID or name
      </p>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchQueryChange(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') doSearch() }}
          placeholder="bonID or name"
          style={{
            flex: 1, border: '1px solid #D1D5DB', borderRadius: 6,
            padding: '8px 10px', fontSize: 12, outline: 'none',
            fontFamily: "'Outfit', sans-serif",
          }}
          onFocus={siFocus}
          onBlur={siBlur}
        />
        <button
          onClick={doSearch}
          style={{
            background: '#243447', color: 'white', border: 'none',
            borderRadius: 6, padding: '8px 12px', fontSize: 12,
            cursor: 'pointer', flexShrink: 0,
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = '#1a3460')}
          onMouseLeave={(e) => (e.currentTarget.style.background = '#243447')}
        >
          Search
        </button>
      </div>

      {searchDone && !searchResult && (
        <p style={{ fontSize: 12, color: '#9CA3AF', textAlign: 'center', padding: 8, margin: '8px 0 0' }}>
          No user found. Check the bonID or name.
        </p>
      )}

      {searchDone && searchResult && (
        <>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            marginTop: 12, paddingTop: 12, borderTop: '1px solid #F3F4F6',
          }}>
            <div style={AVATAR_S}>{searchResult.initials}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{
                fontSize: 13, fontWeight: 500, color: '#0F1F3D',
                margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {searchResult.name}
              </p>
              <p style={{ fontSize: 11, color: '#8B5CF6', fontFamily: "'DM Mono', monospace", margin: 0 }}>
                {searchResult.bonId}
              </p>
            </div>
            {added ? (
              <button
                onClick={() => onAddedChange(false)}
                style={{
                  background: 'transparent', border: '1px solid #DC2626',
                  color: '#DC2626', borderRadius: 6,
                  padding: '4px 10px', fontSize: 11, fontWeight: 600,
                  cursor: 'pointer', flexShrink: 0,
                }}
              >
                Remove
              </button>
            ) : (
              <button
                onClick={() => onAddedChange(true)}
                style={{
                  background: '#F5A623', color: '#0F1F3D', border: 'none',
                  borderRadius: 6, padding: '4px 10px', fontSize: 11,
                  fontWeight: 600, cursor: 'pointer', flexShrink: 0,
                }}
                onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.85')}
                onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
              >
                Add Party
              </button>
            )}
          </div>

          {added && (
            <div style={{ marginTop: 10 }}>
              <select
                value={role}
                onChange={(e) => onRoleChange(e.target.value)}
                style={{
                  width: '100%', fontSize: 12,
                  border: '1px solid #D1D5DB', borderRadius: 6,
                  padding: '6px 8px', background: 'white',
                  color: '#374151', outline: 'none', cursor: 'pointer',
                }}
              >
                <option value="">Select role...</option>
                {PARTY_ROLES.map((r) => <option key={r}>{r}</option>)}
              </select>
              {role === 'Other (type below)' && (
                <input
                  type="text"
                  value={customRole}
                  onChange={(e) => onCustomRoleChange(e.target.value)}
                  placeholder="Enter custom role"
                  style={{
                    width: '100%', background: 'white',
                    border: '1px solid #D1D5DB', borderRadius: 6,
                    padding: '6px 10px', fontSize: 12, color: '#374151',
                    fontFamily: "'Outfit', sans-serif", outline: 'none',
                    marginTop: 8, boxSizing: 'border-box',
                  }}
                  onFocus={siFocus}
                  onBlur={siBlur}
                />
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function CreateContract() {
  const [activeTool, setActiveTool] = useState<string | null>(null)
  const [templateDropdownOpen, setTemplateDropdownOpen] = useState(false)
  const [rightDrawerOpen, setRightDrawerOpen] = useState(true)
  const [activeEditor, setActiveEditor] = useState<'left' | 'right'>('left')
  const [aiPanelOpen, setAiPanelOpen] = useState(false)
  const [calcDisplay, setCalcDisplay] = useState('0')
  const [calcFormula, setCalcFormula] = useState('')
  const [calcOperator, setCalcOperator] = useState<string | null>(null)
  const [calcPrevValue, setCalcPrevValue] = useState<string | null>(null)
  const [calcJustCalc, setCalcJustCalc] = useState(false)
  const [aiPanelMessage, setAiPanelMessage] = useState('')
  const [aiPanelChat, setAiPanelChat] = useState([
    { role: 'ai', text: 'Hi! I can help you draft, review, and improve your contract. What would you like to do?' },
  ])
  const [contractTitle, setContractTitle] = useState('')
  const [contractStatus, setContractStatus] = useState('Draft')
  const [contractLifecycleState, setContractLifecycleState] = useState('created')
  const [contractVersion] = useState(1)
  const [hoverDescription] = useState('')
  const [fontFamily, setFontFamily] = useState('Arial')
  const [fontSize, setFontSize] = useState('14')
  const [leftEmpty, setLeftEmpty] = useState(true)
  const [rightEmpty, setRightEmpty] = useState(true)
  const [splitPercent, setSplitPercent] = useState(50)
  const [isDragging, setIsDragging] = useState(false)
  const [aiPanelHeight, setAiPanelHeight] = useState(280)
  const [focusMode, setFocusMode] = useState<'none' | 'left' | 'right'>('left')
  const [toolPanelWidth, setToolPanelWidth] = useState(280)
  const [toolPanelSnapping, setToolPanelSnapping] = useState(false)
  const [analysisResult, setAnalysisResult] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [counterText, setCounterText] = useState('')
  const [isSubmittingCounter, setIsSubmittingCounter] = useState(false)
  const [paygConfirmDismissed, setPaygConfirmDismissed] = useState(false)

  // Toolbar collapse state
  const [barsCollapsed, setBarsCollapsed] = useState(() => localStorage.getItem('bb_topbar_collapsed') === 'true')

  // Templates panel state
  const [templates, setTemplates] = useState<TemplateItem[]>([])
  const [templatesLoading, setTemplatesLoading] = useState(false)
  const [templateSearch, setTemplateSearch] = useState('')
  const [templateCategoryFilter, setTemplateCategoryFilter] = useState<string>('All')
  const [previewTemplate, setPreviewTemplate] = useState<TemplateItem | null>(null)
  const [preparedTerms, setPreparedTerms] = useState<PreparedTerms | null>(null)
  const [isPreparingContract, setIsPreparingContract] = useState(false)
  const [isSendingInvite, setIsSendingInvite] = useState(false)

  // Obligations panel state
  const [obligationTemplates, setObligationTemplates] = useState<ObligationTemplateItem[]>([])
  const [obligationTemplatesLoading, setObligationTemplatesLoading] = useState(false)
  const [insertedObligations, setInsertedObligations] = useState<string[]>([])
  const [previewObligationTemplate, setPreviewObligationTemplate] = useState<ObligationTemplateItem | null>(null)

  // Payments panel state
  const [paymentTemplates, setPaymentTemplates] = useState<PaymentTemplateItem[]>([])
  const [paymentTemplatesLoading, setPaymentTemplatesLoading] = useState(false)
  const [insertedPayments, setInsertedPayments] = useState<string[]>([])
  const [previewPaymentTemplate, setPreviewPaymentTemplate] = useState<PaymentTemplateItem | null>(null)

  // Contracting As — null = personal, string = entity id
  const [selectedEntity, setSelectedEntity] = useState<string | null>(null)
  // Mock entities — replace with API data when connected
  const MOCK_ENTITIES: { id: string; name: string; type: string }[] = []

  // Contract Details panel fields
  const [detailsType, setDetailsType] = useState('')
  const [detailsLanguage, setDetailsLanguage] = useState('English')
  const [detailsStartDate, setDetailsStartDate] = useState('')
  const [detailsEndDate, setDetailsEndDate] = useState('')
  const [detailsValue, setDetailsValue] = useState('')
  const [detailsCurrency, setDetailsCurrency] = useState('USD')
  const [detailsJurisdiction, setDetailsJurisdiction] = useState('')
  const [detailsGoverningLaw, setDetailsGoverningLaw] = useState('')
  const [detailsConfidentiality, setDetailsConfidentiality] = useState('Not confidential')
  const [detailsDispute, setDetailsDispute] = useState('Negotiation')
  const [detailsDescription, setDetailsDescription] = useState('')
  const [detailsCounterpartyName, setDetailsCounterpartyName] = useState('')
  const [detailsCounterpartyEmail, setDetailsCounterpartyEmail] = useState('')

  // Current contract identity loaded from the URL or saved editor state
  const [createdContractId, setCreatedContractId] = useState<string | null>(null)
  const [createdContractTitle, setCreatedContractTitle] = useState<string>('')
  const [contractLoaded, setContractLoaded] = useState(false)
  const [detailsSaving, setDetailsSaving] = useState(false)
  const [detailsSaveError, setDetailsSaveError] = useState('')
  const [detailsSaveMessage, setDetailsSaveMessage] = useState('')
  const [autosaveStatus, setAutosaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [autosaveError, setAutosaveError] = useState('')

  // Contacts state (shared with Contacts page via localStorage)
  const [contacts, setContacts] = useState<Contact[]>([])
  useEffect(() => { setContacts(loadContacts()) }, [])
  function reloadContacts() { setContacts(loadContacts()) }

  // Parties panel state
  const { user, hasTrialExpired, canCreateContract } = useAuth()
  const notify = useNotification()
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const entityParam = searchParams.get('entity')
  const contractIdParam = searchParams.get('id')
  const currentContractId = createdContractId || contractIdParam
  const draftEditingAllowed = !!currentContractId && contractLoaded && ['created', 'draft', 'drafting'].includes((contractLifecycleState || '').toLowerCase())
  const entityNameParam = searchParams.get('name')
  const entityLabel = entityParam === 'personal'
    ? 'Personal'
    : entityNameParam ?? null
  const [party1Role, setParty1Role] = useState('')
  const [party1CustomRole, setParty1CustomRole] = useState('')
  const [party2SearchQuery, setParty2SearchQuery] = useState('')
  const [party2SearchResult, setParty2SearchResult] = useState<{ name: string; bonId: string; initials: string } | null>(null)
  const [party2SearchDone, setParty2SearchDone] = useState(false)
  const [party2Added, setParty2Added] = useState(false)
  const [party2Role, setParty2Role] = useState('')
  const [party2CustomRole, setParty2CustomRole] = useState('')
  const [additionalParties, setAdditionalParties] = useState<Array<{
    searchQuery: string
    searchResult: { name: string; bonId: string; initials: string } | null
    searchDone: boolean
    added: boolean
    role: string
    customRole: string
  }>>([])

  // Contract Sections panel state
  const [sections, setSections] = useState<ContractSection[]>(DEFAULT_SECTIONS)
  const [activeSection, setActiveSection] = useState<string | null>(null)
  const [sectionsStripVisible, setSectionsStripVisible] = useState(true)
  const [editingSection, setEditingSection] = useState<string | null>(null)
  const [editingSectionName, setEditingSectionName] = useState('')
  const [addingSection, setAddingSection] = useState(false)
  const [newSectionInput, setNewSectionInput] = useState('')
  const [sectDragId, setSectDragId] = useState<string | null>(null)
  const [sectDragOverId, setSectDragOverId] = useState<string | null>(null)
  const [hoveredSection, setHoveredSection] = useState<string | null>(null)

  // Attachments panel state
  const [attachFiles, setAttachFiles] = useState<AttachmentFile[]>(ATTACH_PLACEHOLDER)
  const [attachFilter, setAttachFilter] = useState<AttachFilter>('all')
  const [attachDragOver, setAttachDragOver] = useState(false)
  const [attachError, setAttachError] = useState('')
  const [vaultPickerOpen, setVaultPickerOpen] = useState(false)
  const [vaultPickerFiles, setVaultPickerFiles] = useState<VaultSelectionFile[]>([])
  const [vaultPickerLoading, setVaultPickerLoading] = useState(false)
  const [vaultPickerError, setVaultPickerError] = useState('')
  const [vaultPickerSearch, setVaultPickerSearch] = useState('')
  const [vaultPickerAttachingId, setVaultPickerAttachingId] = useState('')
  const attachInputRef = useRef<HTMLInputElement>(null)

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function onFieldFocus(e: React.FocusEvent<any>) {
    e.currentTarget.style.borderColor = '#243447'
    e.currentTarget.style.boxShadow = '0 0 0 2px rgba(15,31,61,0.08)'
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function onFieldBlur(e: React.FocusEvent<any>) {
    e.currentTarget.style.borderColor = '#D1D5DB'
    e.currentTarget.style.boxShadow = 'none'
  }

  const leftEditorRef = useRef<HTMLDivElement>(null)
  const rightEditorRef = useRef<HTMLDivElement>(null)
  const editorsRowRef = useRef<HTMLDivElement>(null)
  const autosaveTimerRef = useRef<number | null>(null)
  const sectionRegenTimerRef = useRef<number | null>(null)
  const lastSectionSyncHtmlRef = useRef('')
  const sectionsRef = useRef<ContractSection[]>(DEFAULT_SECTIONS)
  const autosaveGuardRef = useRef(false)
  const lastSavedMetadataRef = useRef('')
  const lastSavedDraftRef = useRef('')
  const draftSnapshotBaseRef = useRef<Record<string, unknown>>({})


  function getActiveRef() {
    return activeEditor === 'left' ? leftEditorRef : rightEditorRef
  }

  function execCmd(cmd: string, value?: string) {
    getActiveRef().current?.focus()
    document.execCommand(cmd, false, value)
  }

  function enterFocus(side: 'left' | 'right') {
    setFocusMode(side)
  }

  function exitFocus() {
    setFocusMode('none')
  }

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && focusMode !== 'none') exitFocus()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [focusMode])

  useEffect(() => {
    function onCollapse(e: Event) {
      setBarsCollapsed((e as CustomEvent<boolean>).detail)
    }
    window.addEventListener('topbar-collapse', onCollapse)
    return () => window.removeEventListener('topbar-collapse', onCollapse)
  }, [])

  // Pre-fill Contract Details from navigation state (passed by Contracts.tsx modal)
  useEffect(() => {
    const state = location.state as {
      contractTitle?: string
      contractType?: string
      contractLanguage?: string
      startDate?: string
      endDate?: string
      contractValue?: string
      currency?: string
      jurisdiction?: string
      governingLaw?: string
      confidentiality?: string
      dispute?: string
      description?: string
    } | null
    if (!state) return
    if (state.contractTitle) setContractTitle(state.contractTitle)
    if (state.contractType) setDetailsType(state.contractType)
    if (state.contractLanguage) setDetailsLanguage(state.contractLanguage)
    if (state.startDate) setDetailsStartDate(state.startDate)
    if (state.endDate) setDetailsEndDate(state.endDate)
    if (state.contractValue) setDetailsValue(state.contractValue)
    if (state.currency) setDetailsCurrency(state.currency)
    if (state.jurisdiction) setDetailsJurisdiction(state.jurisdiction)
    if (state.governingLaw) setDetailsGoverningLaw(state.governingLaw)
    if (state.confidentiality) setDetailsConfidentiality(state.confidentiality)
    if (state.dispute) setDetailsDispute(state.dispute)
    if (state.description) setDetailsDescription(state.description)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // If arriving with a contract id param, load the persisted contract and latest draft version.
  useEffect(() => {
    if (!contractIdParam) return
    let cancelled = false
    autosaveGuardRef.current = true
    setContractLoaded(false)
    setCreatedContractId(contractIdParam)
    const stored = localStorage.getItem('bb_wip_contract_title')
    if (stored) setCreatedContractTitle(stored)
    setContractTitle((prev) => prev || stored || '')

    Promise.all([
      api.get<ContractRetrievePayload>(`/contracts/${contractIdParam}/`),
      api.get<ContractDocumentPayload[]>(`/contracts/${contractIdParam}/documents/`),
    ])
      .then(([contractResponse, documentsResponse]) => {
        if (cancelled) return
        const data = contractResponse.data
        applyContractMetadata(data, stored || '')
        lastSavedMetadataRef.current = JSON.stringify({
          title: data.title || stored || '',
          contract_type: data.contract_type || '',
          language: data.language || 'English',
          start_date: data.start_date || null,
          end_date: data.end_date || null,
          contract_value: data.contract_value ? String(data.contract_value) : null,
          currency: data.currency || 'USD',
          jurisdiction: data.jurisdiction || '',
          governing_law: data.governing_law || '',
          confidentiality: data.confidentiality || 'Not confidential',
          dispute_resolution: data.dispute_resolution || 'Negotiation',
          description: data.description || '',
          counterparty_name: data.counterparty_name || '',
          counterparty_email: data.counterparty_email || '',
          structure_type: data.structure_type || 'ONE_TIME',
          entity_type: data.entity_type || 'personal',
          entity: data.entity || null,
        })
        if (data.latest_version?.content_snapshot) {
          restoreDraftSnapshot(data.latest_version.content_snapshot)
          lastSavedDraftRef.current = data.latest_version.content_snapshot
        } else {
          lastSavedDraftRef.current = ''
          draftSnapshotBaseRef.current = {}
        }
        setAttachFiles(documentsResponse.data.map(attachmentFromDocument))
        setContractLoaded(true)
      })
      .catch(() => {
        if (!cancelled) notify.error('Unable to load saved draft')
      })
      .finally(() => {
        if (!cancelled) {
          setTimeout(() => {
            autosaveGuardRef.current = false
          }, 0)
        }
      })
    return () => { cancelled = true }
  }, [contractIdParam]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (activeTool === 'Contract Templates') {
      setTemplatesLoading(true)
      api.get<TemplateItem[]>('/templates/')
        .then(({ data }) => setTemplates(data))
        .catch(() => setTemplates([]))
        .finally(() => setTemplatesLoading(false))
    }
    if (activeTool === 'Obligations') {
      setObligationTemplatesLoading(true)
      api.get<ObligationTemplateItem[]>('/obligation-templates/')
        .then(({ data }) => setObligationTemplates(data))
        .catch(() => setObligationTemplates([]))
        .finally(() => setObligationTemplatesLoading(false))
    }
    if (activeTool === 'Payments') {
      setPaymentTemplatesLoading(true)
      api.get<PaymentTemplateItem[]>('/payment-templates/')
        .then(({ data }) => setPaymentTemplates(data))
        .catch(() => setPaymentTemplates([]))
        .finally(() => setPaymentTemplatesLoading(false))
    }
  }, [activeTool])

  function toTitleCase(s: string): string {
    return s.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase())
  }

  function escapeHtml(text: string): string {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  }

  function isAddressLikeSectionTitle(value: string) {
    const title = value.trim()
    return /^\d+\s+[\w\s.'-]+,\s*[A-Z]{2}\b/.test(title) || /\b(street|st\.|avenue|ave\.|road|rd\.|boulevard|blvd\.|suite|unit|zip)\b/i.test(title)
  }

  function isSignatureOnlySectionTitle(value: string) {
    return /^(provider|client|party|signature|signed|date)\s*:?\s*_*$/i.test(value.trim())
  }

  function templateSectionHeadingMatch(line: string) {
    return line.match(/^(\d+)\.\s+([A-Z][A-Z\s/&,().-]+)$/)
  }

  function isManualSectionHeading(line: string) {
    const trimmed = line.trim()
    if (trimmed.length < 4 || trimmed.length > 80) return false
    if (/[.!?]$/.test(trimmed)) return false
    if (/^[-_*\s]+$/.test(trimmed)) return false
    if (isAddressLikeSectionTitle(trimmed) || isSignatureOnlySectionTitle(trimmed)) return false
    const words = trimmed.split(/\s+/).filter(Boolean)
    if (words.length < 2 || words.length > 8) return false
    const hasContractKeyword = /\b(service|services|obligation|obligations|clause|payment|payments|terms|termination|warranty|liability|damages|insurance|confidentiality|notice|notices|governing|law|dispute|resolution|change|order|scope|deliverable|deliverables|schedule|workmanship)\b/i.test(trimmed)
    if (!hasContractKeyword) return false
    return words.every((word) => /^[A-Z][a-zA-Z0-9/&().-]*$/.test(word) || /^(and|or|of|the|to|for|in)$/i.test(word))
  }

  function sectionHeadingMatch(line: string) {
    const trimmed = line.trim()
    const match = trimmed.match(/^(?:(\d+)\.\s+([A-Z][A-Z0-9\s/&,().-]+|[A-Z][a-zA-Z0-9\s/&,().-]{2,80})|SECTION\s+(\d+)\s*[-:]\s*([A-Z][A-Z0-9\s/&,().-]+|[A-Z][a-zA-Z0-9\s/&,().-]{2,80})|([A-Z][A-Z0-9\s/&,().-]{3,80}))$/)
    if (match) return match
    if (!isManualSectionHeading(trimmed)) return null
    const manualMatch = [trimmed, undefined, undefined, undefined, undefined, trimmed] as unknown as RegExpMatchArray
    manualMatch.index = 0
    manualMatch.input = line
    return manualMatch
  }

  function sectionMatchTitle(match: RegExpMatchArray) {
    return (match[2] || match[4] || match[5] || '').trim()
  }

  function sectionMatchNumber(match: RegExpMatchArray, fallback: number) {
    return parseInt(match[1] || match[3] || String(fallback), 10)
  }

  function parsedSectionsFromMatches(matches: RegExpMatchArray[], prefix = 'ts'): ContractSection[] {
    return matches.map((m, i) => ({
      id: `${prefix}${i + 1}`,
      number: sectionMatchNumber(m, i + 1),
      name: toTitleCase(sectionMatchTitle(m)),
    }))
  }

  function parseCompatibleSections(content: string): ContractSection[] | null {
    const rawMatches = content.split(/\r?\n/)
      .map((line) => sectionHeadingMatch(line))
      .filter((m): m is RegExpMatchArray => Boolean(m))
      .filter((m) => {
        const title = sectionMatchTitle(m)
        return Boolean(title) && !isAddressLikeSectionTitle(title) && !isSignatureOnlySectionTitle(title)
      })

    const matches = rawMatches
    if (matches.length < 2) return null
    return parsedSectionsFromMatches(matches)
  }

  function parseTemplateSections(content: string): ContractSection[] {
    const regex = /^(\d+)\.\s+([A-Z][A-Z\s/&,().-]+)$/gm
    const matches = [...content.matchAll(regex)]
    if (matches.length >= 2) return parsedSectionsFromMatches(matches)
    return parseCompatibleSections(content) || []
  }

  function parseDraftEditorSections(content: string): ContractSection[] | null {
    return parseCompatibleSections(content)
  }

  function buildTemplateHtml(content: string, parsedSections: ContractSection[]): string {
    const byNum = new Map(parsedSections.map((s) => [s.number, s]))
    const byName = new Map(parsedSections.map((s) => [normalizeSectionHeadingText(s.name), s]))
    const usedAnchors = new Set<string>()
    return content.split('\n').map((line) => {
      const strictMatch = templateSectionHeadingMatch(line)
      const broadMatch = strictMatch || sectionHeadingMatch(line)
      if (broadMatch) {
        const title = sectionMatchTitle(broadMatch)
        const num = sectionMatchNumber(broadMatch, 0)
        const sec = (num ? byNum.get(num) : null) || byName.get(normalizeSectionHeadingText(title))
        if (sec && !usedAnchors.has(sec.id)) {
          usedAnchors.add(sec.id)
          return `<h2 id="section-${sec.id}" style="margin:20px 0 4px;font-size:14px;font-weight:700;color:#0F1F3D;">${escapeHtml(line)}</h2>`
        }
      }
      if (line.trim() === '') return '<div style="height:6px"></div>'
      return `<div style="font-size:14px;line-height:1.6;color:#374151;margin-bottom:2px;">${escapeHtml(line)}</div>`
    }).join('')
  }

  function buildInsertedSectionHtml(title: string, body: string, sectionId: string): string {
    const bodyHtml = body.split('\n').map((line) => {
      if (line.trim() === '') return '<div style="height:6px"></div>'
      return `<div style="font-size:14px;line-height:1.6;color:#374151;margin-bottom:2px;">${escapeHtml(line)}</div>`
    }).join('')
    return `<h2 id="section-${sectionId}" style="margin:20px 0 4px;font-size:14px;font-weight:700;color:#0F1F3D;">${escapeHtml(title)}</h2>${bodyHtml}`
  }

  function appendDraftSectionFromTemplate(title: string, body: string, prefix: string) {
    const editorEl = leftEditorRef.current
    if (!editorEl) return false
    const nextNumber = sectionsRef.current.length + 1
    const sectionId = `${prefix}${Date.now()}`
    const section: ContractSection = { id: sectionId, number: nextNumber, name: title }
    const nextSections = [...sectionsRef.current, section]

    editorEl.insertAdjacentHTML('beforeend', '<div style="height:10px"></div>' + buildInsertedSectionHtml(title, body, sectionId))
    const target = editorEl.querySelector<HTMLElement>(`#section-${sectionId}`)
    lastSectionSyncHtmlRef.current = editorEl.innerHTML || ''
    updateSections(nextSections)
    setActiveSection(sectionId)
    setLeftEmpty(false)
    if (target) window.requestAnimationFrame(() => scrollDraftSectionIntoView(target, editorEl))
    queueAutosave()
    return true
  }

  function insertDraftSectionFromTemplate(title: string, body: string, prefix: string) {
    setActiveEditor('left')
    if (focusMode === 'right') {
      setFocusMode('left')
      window.requestAnimationFrame(() => {
        window.requestAnimationFrame(() => appendDraftSectionFromTemplate(title, body, prefix))
      })
      return true
    }
    return appendDraftSectionFromTemplate(title, body, prefix)
  }

  function sectionsEqual(a: ContractSection[], b: ContractSection[]) {
    return a.length === b.length && a.every((section, index) => {
      const other = b[index]
      return other && section.id === other.id && section.number === other.number && section.name === other.name
    })
  }

  function updateSections(next: ContractSection[] | ((prev: ContractSection[]) => ContractSection[])) {
    const nextSections = typeof next === 'function' ? next(sectionsRef.current) : next
    sectionsRef.current = nextSections
    setSections((prev) => sectionsEqual(prev, nextSections) ? prev : nextSections)
  }

  function commitParsedSections(parsed: ContractSection[]) {
    updateSections(parsed)
  }

  function clearDraftSectionRegenTimer() {
    if (sectionRegenTimerRef.current !== null) {
      window.clearTimeout(sectionRegenTimerRef.current)
      sectionRegenTimerRef.current = null
    }
  }

  function queueDraftSectionRegeneration(delay = 450) {
    if (!draftEditingAllowed || autosaveGuardRef.current) return
    clearDraftSectionRegenTimer()
    sectionRegenTimerRef.current = window.setTimeout(() => {
      sectionRegenTimerRef.current = null
      window.requestAnimationFrame(() => regenerateDraftSectionsFromEditor())
    }, delay)
  }

  function normalizeSectionHeadingText(value: string) {
    return value.replace(/\s+/g, ' ').trim().toLowerCase()
  }

  function findDraftScrollContainer(target: HTMLElement, editorEl: HTMLDivElement): HTMLElement {
    let node: HTMLElement | null = target
    while (node && node !== document.body) {
      const style = window.getComputedStyle(node)
      const canScroll = /(auto|scroll)/.test(style.overflowY) && node.scrollHeight > node.clientHeight
      if (canScroll) return node
      node = node.parentElement
    }
    return editorEl
  }

  function scrollDraftSectionIntoView(target: HTMLElement, editorEl: HTMLDivElement) {
    const container = findDraftScrollContainer(target, editorEl)
    const containerRect = container.getBoundingClientRect()
    const targetRect = target.getBoundingClientRect()
    const nextTop = container.scrollTop + targetRect.top - containerRect.top - 16
    container.scrollTo({ top: Math.max(nextTop, 0), behavior: 'smooth' })
  }

  function draftEditorSectionText(editorEl: HTMLDivElement) {
    const blockTexts = Array.from(editorEl.querySelectorAll<HTMLElement>('h1,h2,h3,h4,p,div,li'))
      .map((el) => (el.textContent || '').trim())
      .filter(Boolean)
    if (blockTexts.length > 1) return blockTexts.join('\n')

    const htmlWithBreaks = editorEl.innerHTML
      .replace(/<br\s*\/?>/gi, '\n')
      .replace(/<\/(h1|h2|h3|h4|p|div|li)>/gi, '\n')
      .replace(/<[^>]+>/g, '')
    const decoder = document.createElement('textarea')
    decoder.innerHTML = htmlWithBreaks
    const decodedText = decoder.value.replace(/\n{3,}/g, '\n\n').trim()
    return decodedText || (editorEl.textContent || '')
  }

  function annotateDraftSectionAnchors(editorEl: HTMLDivElement, parsedSections: ContractSection[]) {
    const candidates = Array.from(editorEl.querySelectorAll<HTMLElement>('h1,h2,h3,h4,p,div,li'))
    candidates.forEach((el) => {
      if (el.id.startsWith('section-')) el.removeAttribute('id')
      delete el.dataset.sectionAnchorCandidate
    })
    const used = new Set<string>()
    parsedSections.forEach((section) => {
      const targetText = normalizeSectionHeadingText(`${section.number}. ${section.name}`)
      const targetName = normalizeSectionHeadingText(section.name)
      const match = candidates.find((el) => {
        if (used.has(el.dataset.sectionAnchorCandidate || '')) return false
        const rawText = el.textContent || ''
        const heading = sectionHeadingMatch(rawText)
        if (heading) {
          const headingNumber = sectionMatchNumber(heading, section.number)
          const headingName = normalizeSectionHeadingText(sectionMatchTitle(heading))
          if (headingNumber === section.number && headingName === targetName) return true
        }
        const text = normalizeSectionHeadingText(rawText)
        return text === targetText || text === targetName || text.startsWith(`${section.number}. ${targetName}`)
      })
      if (match) {
        match.id = `section-${section.id}`
        match.dataset.sectionAnchorCandidate = section.id
        used.add(section.id)
      }
    })
  }

  function regenerateDraftSectionsFromEditor(force = false) {
    const editorEl = leftEditorRef.current
    if (!editorEl) return
    const currentHtml = editorEl.innerHTML || ''
    if (!force && currentHtml === lastSectionSyncHtmlRef.current) return

    const text = draftEditorSectionText(editorEl)
    const parsed = parseDraftEditorSections(text)
    if (!parsed) return
    annotateDraftSectionAnchors(editorEl, parsed)
    lastSectionSyncHtmlRef.current = editorEl.innerHTML || currentHtml
    commitParsedSections(parsed)
  }

  function syncDraftSectionsAfterMutation(delay = 0) {
    window.setTimeout(() => {
      regenerateDraftSectionsFromEditor()
      queueAutosave()
    }, delay)
  }

  function handleDraftEditorFocus() {
    setActiveEditor('left')
  }

  function handleDraftEditorInput(e: React.FormEvent<HTMLDivElement>) {
    setLeftEmpty((e.currentTarget.textContent ?? '') === '')
    queueDraftSectionRegeneration()
    queueAutosave()
  }

  function handleDraftEditorPaste(e: React.ClipboardEvent<HTMLDivElement>) {
    if (!draftEditingAllowed) return
    const pastedText = e.clipboardData.getData('text/plain')
    const parsed = pastedText ? parseDraftEditorSections(pastedText) : null
    if (!parsed) {
      queueDraftSectionRegeneration(80)
      return
    }

    e.preventDefault()
    const html = buildTemplateHtml(pastedText, parsed)
    document.execCommand('insertHTML', false, html)
    lastSectionSyncHtmlRef.current = leftEditorRef.current?.innerHTML || ''
    commitParsedSections(parsed)
    setLeftEmpty(false)
    queueAutosave()
  }

  useEffect(() => () => clearDraftSectionRegenTimer(), []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    sectionsRef.current = sections
  }, [sections])

  function normalizePersistedSections(value: unknown): ContractSection[] | null {
    if (!Array.isArray(value)) return null
    const parsed = value
      .map((item, index) => {
        if (!item || typeof item !== 'object') return null
        const section = item as Partial<ContractSection>
        if (typeof section.name !== 'string') return null
        return {
          id: typeof section.id === 'string' ? section.id : `ps${index + 1}`,
          number: typeof section.number === 'number' ? section.number : index + 1,
          name: section.name,
        }
      })
      .filter((section): section is ContractSection => section !== null)
    return parsed.length > 0 ? parsed : null
  }

  function structureTypeFromContractType(contractType: string): string {
    if (contractType === 'Employment Contract') return 'ONGOING'
    if (contractType === 'Partnership Agreement' || contractType === 'Joint Venture Agreement') return 'COLLABORATIVE'
    if (contractType === 'Settlement Agreement') return 'RESOLUTION'
    return 'ONE_TIME'
  }

  function apiErrorMessage(err: unknown, fallback: string): string {
    const data = (err as { response?: { data?: unknown } })?.response?.data
    if (typeof data === 'string' && data.trim()) return data
    if (Array.isArray(data)) {
      const message = data.flat().filter(Boolean).join(' ')
      return message || fallback
    }
    if (data && typeof data === 'object') {
      const record = data as Record<string, unknown>
      const primary = record.error || record.detail || record.message
      if (typeof primary === 'string' && primary.trim()) return primary
      if (Array.isArray(primary)) {
        const message = primary.flat().filter(Boolean).join(' ')
        if (message) return message
      }
      const message = Object.values(record).flat().filter(Boolean).join(' ')
      return message || fallback
    }
    return fallback
  }

  function buildContractMetadataPayload() {
    return {
      title: contractTitle.trim(),
      contract_type: detailsType,
      language: detailsLanguage,
      start_date: detailsStartDate || null,
      end_date: detailsEndDate || null,
      contract_value: detailsValue === '' ? null : detailsValue,
      currency: detailsCurrency || 'USD',
      jurisdiction: detailsJurisdiction,
      governing_law: detailsGoverningLaw,
      confidentiality: detailsConfidentiality,
      dispute_resolution: detailsDispute,
      description: detailsDescription,
      counterparty_name: detailsCounterpartyName.trim(),
      counterparty_email: detailsCounterpartyEmail.trim(),
      structure_type: structureTypeFromContractType(detailsType),
      entity_type: selectedEntity ? 'business' : 'personal',
      entity: selectedEntity || null,
    }
  }

  function serializeDraftSnapshot(snapshot: Record<string, unknown>) {
    return JSON.stringify(snapshot)
  }

  function buildDraftSnapshot() {
    const base = draftSnapshotBaseRef.current && typeof draftSnapshotBaseRef.current === 'object'
      ? { ...draftSnapshotBaseRef.current }
      : {}
    const leftHtml = leftEditorRef.current?.innerHTML || ''
    const rightHtml = rightEditorRef.current?.innerHTML || ''
    const snapshot = {
      ...base,
      source: String(base.source || 'editor_autosave'),
      editor_html: leftHtml,
      sections: sectionsRef.current,
    } as Record<string, unknown>
    if (rightHtml.trim()) {
      snapshot.final_editor_html = rightHtml
    } else {
      delete snapshot.final_editor_html
    }
    if (preparedTerms) {
      snapshot.prepared_terms = preparedTerms
    }
    return snapshot
  }

  function clearAutosaveTimer() {
    if (autosaveTimerRef.current !== null) {
      window.clearTimeout(autosaveTimerRef.current)
      autosaveTimerRef.current = null
    }
  }

  function queueAutosave() {
    if (!draftEditingAllowed || !currentContractId || autosaveGuardRef.current) return
    clearAutosaveTimer()
    setAutosaveStatus('idle')
    setAutosaveError('')
    autosaveTimerRef.current = window.setTimeout(() => {
      autosaveTimerRef.current = null
      void flushAutosave()
    }, 900)
  }

  async function flushAutosave() {
    if (!draftEditingAllowed || !currentContractId || autosaveGuardRef.current) return

    const metadataPayload = buildContractMetadataPayload()
    const metadataPayloadKey = JSON.stringify(metadataPayload)
    const draftSnapshot = buildDraftSnapshot()
    const draftSnapshotKey = serializeDraftSnapshot(draftSnapshot)

    const metadataChanged = metadataPayloadKey !== lastSavedMetadataRef.current
    const draftChanged = draftSnapshotKey !== lastSavedDraftRef.current

    if (!metadataChanged && !draftChanged) return

    clearAutosaveTimer()
    setAutosaveStatus('saving')
    setAutosaveError('')

    const errors: string[] = []

    try {
      if (metadataChanged) {
        const { data } = await api.patch<ContractRetrievePayload>(`/contracts/${currentContractId}/`, metadataPayload)
        autosaveGuardRef.current = true
        applyContractMetadata(data, metadataPayload.title)
        lastSavedMetadataRef.current = JSON.stringify({
          title: data.title || metadataPayload.title,
          contract_type: data.contract_type || '',
          language: data.language || '',
          start_date: data.start_date || null,
          end_date: data.end_date || null,
          contract_value: data.contract_value ? String(data.contract_value) : null,
          currency: data.currency || 'USD',
          jurisdiction: data.jurisdiction || '',
          governing_law: data.governing_law || '',
          confidentiality: data.confidentiality || '',
          dispute_resolution: data.dispute_resolution || '',
          description: data.description || '',
          counterparty_name: data.counterparty_name || '',
          counterparty_email: data.counterparty_email || '',
          structure_type: data.structure_type || '',
          entity_type: data.entity_type || 'personal',
          entity: data.entity || null,
        })
      }
    } catch (err) {
      errors.push(apiErrorMessage(err, 'Failed to save contract details.'))
    } finally {
      autosaveGuardRef.current = false
    }

    try {
      if (draftChanged) {
        const { data } = await api.patch<{ version?: ContractVersionPayload; latest_version?: ContractVersionPayload; content_snapshot?: string }>(`/contracts/${currentContractId}/draft/`, {
          content_snapshot: draftSnapshotKey,
        })
        const savedSnapshot = data.content_snapshot || data.version?.content_snapshot || data.latest_version?.content_snapshot || draftSnapshotKey
        lastSavedDraftRef.current = savedSnapshot
        const parsedSnapshot = JSON.parse(savedSnapshot) as Record<string, unknown>
        draftSnapshotBaseRef.current = parsedSnapshot
      }
    } catch (err) {
      errors.push(apiErrorMessage(err, 'Failed to save draft body.'))
    }

    if (errors.length > 0) {
      setAutosaveStatus('error')
      setAutosaveError(errors.join(' '))
      return
    }

    setAutosaveStatus('saved')
    setAutosaveError('')
  }

  function applyContractMetadata(data: ContractRetrievePayload, storedTitle = '') {
    const title = data.title || storedTitle || ''
    if (title) {
      setCreatedContractTitle(title)
      setContractTitle(title)
      localStorage.setItem('bb_wip_contract_title', title)
    }
    setDetailsType(data.contract_type || '')
    setDetailsLanguage(data.language || 'English')
    setDetailsStartDate(data.start_date || '')
    setDetailsEndDate(data.end_date || '')
    setDetailsValue(data.contract_value ? String(data.contract_value) : '')
    setDetailsCurrency(data.currency || 'USD')
    setDetailsJurisdiction(data.jurisdiction || '')
    setDetailsGoverningLaw(data.governing_law || '')
    setDetailsConfidentiality(data.confidentiality || 'Not confidential')
    setDetailsDispute(data.dispute_resolution || 'Negotiation')
    setDetailsDescription(data.description || '')
    setDetailsCounterpartyName(data.counterparty_name || '')
    setDetailsCounterpartyEmail(data.counterparty_email || '')
    setSelectedEntity(data.entity_type === 'business' && data.entity ? String(data.entity) : null)
    setContractLifecycleState(data.state || 'created')
    if (data.status) setContractStatus(toTitleCase(data.status))
  }

  useEffect(() => {
    if (autosaveGuardRef.current || !currentContractId) return
    const metadataKey = JSON.stringify(buildContractMetadataPayload())
    const draftKey = serializeDraftSnapshot(buildDraftSnapshot())
    if (metadataKey === lastSavedMetadataRef.current && draftKey === lastSavedDraftRef.current) return
    queueAutosave()
  }, [
    contractTitle, detailsType, detailsLanguage, detailsStartDate, detailsEndDate, detailsValue,
    detailsCurrency, detailsJurisdiction, detailsGoverningLaw, detailsConfidentiality, detailsDispute,
    detailsDescription, detailsCounterpartyName, detailsCounterpartyEmail, selectedEntity, sections, preparedTerms, contractLoaded,
  ]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSaveContractDetails() {
    const contractId = currentContractId
    setDetailsSaveError('')
    setDetailsSaveMessage('')

    if (!contractId) {
      setDetailsSaveError('Create the contract record from Contract Details intake before editing it here.')
      return
    }

    const payload = buildContractMetadataPayload()

    setDetailsSaving(true)
    autosaveGuardRef.current = true
    try {
      const { data } = await api.patch<ContractRetrievePayload>(`/contracts/${contractId}/`, payload)
      setCreatedContractId(contractId)
      localStorage.setItem('bb_wip_contract_id', contractId)
      applyContractMetadata(data, payload.title)
      lastSavedMetadataRef.current = JSON.stringify({
        title: data.title || payload.title,
        contract_type: data.contract_type || '',
        language: data.language || '',
        start_date: data.start_date || null,
        end_date: data.end_date || null,
        contract_value: data.contract_value ? String(data.contract_value) : null,
        currency: data.currency || 'USD',
        jurisdiction: data.jurisdiction || '',
        governing_law: data.governing_law || '',
        confidentiality: data.confidentiality || '',
        dispute_resolution: data.dispute_resolution || '',
        description: data.description || '',
        counterparty_name: data.counterparty_name || '',
        counterparty_email: data.counterparty_email || '',
        structure_type: data.structure_type || '',
        entity_type: data.entity_type || 'personal',
        entity: data.entity || null,
      })
      setDetailsSaveMessage('Contract details saved.')
    } catch (err) {
      setDetailsSaveError(apiErrorMessage(err, 'Failed to save contract details.'))
    } finally {
      autosaveGuardRef.current = false
      setDetailsSaving(false)
    }
  }

  function restoreDraftSnapshot(contentSnapshot: string) {
    let snapshot: PersistedTemplateDraft | null = null
    try {
      snapshot = JSON.parse(contentSnapshot) as PersistedTemplateDraft
    } catch (err) {
      console.warn('Unable to parse saved draft snapshot', err)
      snapshot = null
    }

    draftSnapshotBaseRef.current = snapshot ? { ...snapshot } : { raw_content: contentSnapshot }
    if (draftSnapshotBaseRef.current && typeof draftSnapshotBaseRef.current === 'object') {
      if (draftSnapshotBaseRef.current.final_editor_html === '') {
        delete draftSnapshotBaseRef.current.final_editor_html
      }
    }
    setPreparedTerms(snapshot?.prepared_terms ?? null)

    const persistedSections = normalizePersistedSections(snapshot?.sections)
    if (persistedSections) updateSections(persistedSections)

    let html = snapshot?.editor_html
    const finalHtml = snapshot?.final_editor_html
    if (!html && Array.isArray(snapshot?.clauses)) {
      const content = snapshot.clauses.map((clause) => clause.body || '').join('\n\n')
      const parsed = parseTemplateSections(content)
      html = buildTemplateHtml(content, parsed)
      commitParsedSections(parsed)
    }
    if (!html && contentSnapshot.trim().startsWith('<')) html = contentSnapshot

    if (leftEditorRef.current) {
      leftEditorRef.current.innerHTML = html || ''
      lastSectionSyncHtmlRef.current = leftEditorRef.current.innerHTML || ''
      setLeftEmpty((leftEditorRef.current.textContent ?? '').trim() === '')
    }
    if (rightEditorRef.current) {
      rightEditorRef.current.innerHTML = finalHtml || ''
      setRightEmpty((rightEditorRef.current.textContent ?? '').trim() === '')
    }
  }

  async function loadTemplate(tmpl: TemplateItem) {
    const contractId = currentContractId
    if (!contractId) {
      notify.warning('Create the contract record before applying a template')
      return
    }
    if (!draftEditingAllowed) {
      notify.warning('Prepared contracts must use negotiation, not the normal editor')
      return
    }

    const currentText = (leftEditorRef.current?.textContent ?? '').trim()
    if (currentText && !window.confirm('Replace the current draft content with this template?')) {
      return
    }

    const parsed = parseTemplateSections(tmpl.content)
    const html = buildTemplateHtml(tmpl.content, parsed)
    const contentSnapshot = JSON.stringify({
      source: 'editor_template_apply',
      template_id: tmpl.id,
      template_name: tmpl.name,
      category: tmpl.category,
      editor_html: html,
      sections: parsed,
    })

    notify.info('Saving template draft...')
    autosaveGuardRef.current = true
    try {
      const { data } = await api.patch<{ version?: ContractVersionPayload; latest_version?: ContractVersionPayload; content_snapshot?: string; state?: string; status?: string }>(`/contracts/${contractId}/draft/`, {
        content_snapshot: contentSnapshot,
      })
      if (leftEditorRef.current) {
        leftEditorRef.current.innerHTML = html
        lastSectionSyncHtmlRef.current = html
        setLeftEmpty(false)
      }
      if (rightEditorRef.current) {
        rightEditorRef.current.innerHTML = ''
        setRightEmpty(true)
      }
      commitParsedSections(parsed)
      syncDraftSectionsAfterMutation()
      setPreparedTerms(null)
      setCreatedContractId(contractId)
      setContractLifecycleState(data.state || 'drafting')
      setContractStatus(toTitleCase(data.status || 'draft'))
      draftSnapshotBaseRef.current = {
        source: 'editor_template_apply',
        template_id: tmpl.id,
        template_name: tmpl.name,
        category: tmpl.category,
        editor_html: html,
        sections: parsed,
      }
      const savedSnapshot = data.content_snapshot || data.version?.content_snapshot || data.latest_version?.content_snapshot || contentSnapshot
      lastSavedDraftRef.current = savedSnapshot
      setPreviewTemplate(null)
      setActiveTool(null)
      notify.success('Template saved to draft')
    } catch (err) {
      const data = (err as { response?: { data?: unknown } })?.response?.data
      const msg = data && typeof data === 'object'
        ? Object.values(data as Record<string, unknown>).flat().join(' ')
        : 'Unable to save template draft'
      notify.error(String(msg))
    } finally {
      autosaveGuardRef.current = false
    }
  }

  async function handlePrepareContract() {
    const contractId = currentContractId
    if (!contractId) {
      notify.warning('Create the contract record before preparing it')
      return
    }
    if (!draftEditingAllowed) {
      notify.warning('Prepared contracts cannot be edited through the normal editor')
      return
    }

    const editorHtml = leftEditorRef.current?.innerHTML || ''
    const draftText = (leftEditorRef.current?.textContent || '').trim()
    if (!draftText) {
      notify.warning('Add draft content before preparing the contract')
      return
    }

    setIsPreparingContract(true)
    notify.info('Preparing contract...')
    try {
      const { data } = await api.post<{
        state: string
        status: string
        prepared_terms: PreparedTerms
      }>(`/contracts/${contractId}/prepare/`, {
        editor_html: editorHtml,
        sections,
        draft_text: draftText,
      })
      setPreparedTerms(data.prepared_terms)
      setContractLifecycleState(data.state || 'prepared')
      setContractStatus(data.state === 'prepared' ? 'Prepared' : toTitleCase(data.status || 'draft'))
      notify.success('Contract prepared for invite')
    } catch (err) {
      const data = (err as { response?: { data?: unknown } })?.response?.data
      const msg = data && typeof data === 'object'
        ? Object.values(data as Record<string, unknown>).flat().join(' ')
        : 'Unable to prepare contract'
      notify.error(String(msg))
    } finally {
      setIsPreparingContract(false)
    }
  }

  async function handleShareInvite() {
    const contractId = currentContractId
    const counterpartyEmail = detailsCounterpartyEmail.trim()
    if (!contractId) {
      notify.warning('Create the contract record before sending an invite')
      return
    }
    if (!counterpartyEmail) {
      notify.warning('Add a counterparty email before sending an invite')
      return
    }
    if (!draftEditingAllowed && contractLifecycleState !== 'prepared') {
      notify.warning('Normal editor invites are disabled for this contract state')
      return
    }
    if (!preparedTerms) {
      notify.warning('Prepare Contract before sending an invite')
      return
    }

    setIsSendingInvite(true)
    notify.info('Sending invite...')
    try {
      const { data } = await api.post<{
        contract_id?: string
        state?: string
        status?: string
        invite_url?: string
        shared_workflow_url?: string
        email_sent?: boolean
        invite_email?: string
        counterparty_email?: string
      }>(`/contracts/${contractId}/invite/`, {
        counterparty_email: counterpartyEmail,
      })

      if (data.state) setContractLifecycleState(data.state)
      if (data.status) setContractStatus(toTitleCase(data.status))

      if (data.email_sent) {
        notify.success(`Invite sent to ${data.invite_email || data.counterparty_email || counterpartyEmail}.`)
      } else if (data.invite_url) {
        notify.success('Invite link created.')
      } else {
        notify.success('Invite created.')
      }
    } catch (err) {
      const data = (err as { response?: { data?: unknown } })?.response?.data
      const msg = data && typeof data === 'object'
        ? Object.values(data as Record<string, unknown>).flat().join(' ')
        : 'Unable to send invite'
      notify.error(String(msg))
    } finally {
      setIsSendingInvite(false)
    }
  }


  useEffect(() => {
    document.documentElement.style.setProperty('--sidebar-w', '48px')
    window.dispatchEvent(new CustomEvent('sidebar-mode', { detail: 'icon-only' }))
    return () => {
      document.documentElement.style.removeProperty('--sidebar-w')
      window.dispatchEvent(new CustomEvent('sidebar-mode', { detail: 'normal' }))
    }
  }, [])

  // Pre-populate the left editor with section headings on mount
  useEffect(() => {
    if (leftEditorRef.current && leftEditorRef.current.innerHTML.trim() === '') {
      leftEditorRef.current.innerHTML = DEFAULT_SECTIONS.map((s) =>
        `<h2 id="section-${s.id}" style="margin:0 0 6px;font-size:16px;font-weight:600;color:#0F1F3D;">${s.name}</h2>` +
        `<p style="margin:0 0 28px;color:#9CA3AF;font-size:14px;">[ Content for ${s.name} ]</p>`
      ).join('')
      setLeftEmpty(false)
      sectionsRef.current = DEFAULT_SECTIONS
      if (!lastSavedDraftRef.current) {
        lastSavedDraftRef.current = serializeDraftSnapshot(buildDraftSnapshot())
      }
    }
  }, [])

  function onDividerMouseDown(e: React.MouseEvent) {
    e.preventDefault()
    setIsDragging(true)
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    function onMouseMove(ev: MouseEvent) {
      const container = editorsRowRef.current
      if (!container) return
      const rect = container.getBoundingClientRect()
      const x = ev.clientX - rect.left
      const pct = (x / rect.width) * 100
      setSplitPercent(Math.min(75, Math.max(25, pct)))
    }

    function onMouseUp() {
      setIsDragging(false)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }

  function onAiHandleMouseDown(e: React.MouseEvent) {
    e.preventDefault()
    const startY = e.clientY
    const startHeight = aiPanelHeight

    document.body.style.cursor = 'row-resize'
    document.body.style.userSelect = 'none'

    function onMouseMove(ev: MouseEvent) {
      const delta = ev.clientY - startY
      // dragging down (positive delta) shrinks the panel
      const newHeight = startHeight - delta
      setAiPanelHeight(Math.min(280, Math.max(187, newHeight)))
    }

    function onMouseUp() {
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }

  function toolPanelMax() {
    // In focus mode, cap so the document sheet never goes below 400px (+ 48px padding)
    const docMin = focusMode !== 'none' ? 400 + 48 : 0
    return Math.max(280, Math.min(560, window.innerWidth - 48 - 52 - docMin))
  }

  function onToolPanelHandleMouseDown(e: React.MouseEvent) {
    e.preventDefault()
    setToolPanelSnapping(false)
    const startX = e.clientX
    const startWidth = toolPanelWidth
    const maxW = toolPanelMax()

    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    function onMouseMove(ev: MouseEvent) {
      const delta = ev.clientX - startX
      setToolPanelWidth(Math.min(maxW, Math.max(280, startWidth + delta)))
    }

    function onMouseUp() {
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }

  function snapToolPanel() {
    setToolPanelSnapping(true)
    const maxW = toolPanelMax()
    setToolPanelWidth((w) => (w >= maxW ? 280 : maxW))
  }

  function calcInput(val: string) {
    if (calcJustCalc && /[0-9.]/.test(val)) {
      setCalcDisplay(val === '.' ? '0.' : val)
      setCalcFormula('')
      setCalcJustCalc(false)
      return
    }
    if (val === '.') {
      if (!calcDisplay.includes('.')) setCalcDisplay(calcDisplay + '.')
      return
    }
    setCalcDisplay(calcDisplay === '0' ? val : calcDisplay + val)
    setCalcJustCalc(false)
  }

  function calcOp(op: string) {
    setCalcPrevValue(calcDisplay)
    setCalcOperator(op)
    setCalcFormula(`${calcDisplay} ${op}`)
    setCalcJustCalc(true)
  }

  function calcEqual() {
    if (!calcOperator || !calcPrevValue) return
    const a = parseFloat(calcPrevValue)
    const b = parseFloat(calcDisplay)
    let result = 0
    if (calcOperator === '+') result = a + b
    else if (calcOperator === '−') result = a - b
    else if (calcOperator === '×') result = a * b
    else if (calcOperator === '÷') result = b !== 0 ? a / b : 0
    const r = String(parseFloat(result.toFixed(10)))
    setCalcFormula(`${calcPrevValue} ${calcOperator} ${calcDisplay} =`)
    setCalcDisplay(r)
    setCalcOperator(null)
    setCalcPrevValue(null)
    setCalcJustCalc(true)
  }

  function calcClear() {
    setCalcDisplay('0')
    setCalcFormula('')
    setCalcOperator(null)
    setCalcPrevValue(null)
    setCalcJustCalc(false)
  }

  const TOGGLE_BTN: React.CSSProperties = {
    width: 16, height: 48, border: 'none', background: '#2E4156',
    color: 'rgba(255,255,255,0.5)', fontSize: 10, cursor: 'pointer',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    flexShrink: 0, alignSelf: 'center',
  }

  return (
    <>
      {/* ── TRIAL EXPIRED MODAL ── */}
      {hasTrialExpired() && !canCreateContract() && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 1000,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            background: 'white', borderRadius: 12, padding: 32,
            textAlign: 'center', maxWidth: 400, width: '90%',
          }}>
            <div style={{ fontSize: 48 }}>⚠️</div>
            <p style={{ fontSize: 18, fontWeight: 600, color: '#0F1F3D', margin: '12px 0 8px' }}>
              Your trial has ended
            </p>
            <p style={{ fontSize: 13, color: '#6B7280', marginBottom: 24 }}>
              Subscribe to Blackbòd Basic or higher to create new contracts.
            </p>
            <button
              onClick={() => navigate('/settings')}
              style={{
                background: '#243447', color: 'white',
                width: '100%', height: 40,
                borderRadius: 8, fontSize: 14, fontWeight: 600, border: 'none',
                cursor: 'pointer',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.85')}
              onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
            >
              Choose a Plan
            </button>
            <p
              onClick={() => navigate('/dashboard')}
              style={{
                fontSize: 12, color: '#9CA3AF', cursor: 'pointer',
                textDecoration: 'underline', marginTop: 12,
              }}
            >
              Back to Dashboard
            </p>
          </div>
        </div>
      )}

      {/* ── PAYG CHARGE NOTICE MODAL ── */}
      {USER_TIER === 'per_contract' && !paygConfirmDismissed && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 1000,
          background: 'rgba(0,0,0,0.45)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            background: 'white', borderRadius: 12, padding: 32,
            maxWidth: 400, width: '90%',
            boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
          }}>
            <p style={{ fontSize: 16, fontWeight: 700, color: '#0F1F3D', marginBottom: 8 }}>
              Pay As You Go Charge
            </p>
            <p style={{ fontSize: 13, color: '#6B7280', marginBottom: 16, lineHeight: 1.5 }}>
              Creating this contract will be charged to your account.
            </p>
            <div style={{
              background: '#FEF3C7', border: '1px solid #F59E0B',
              borderRadius: 8, padding: '10px 14px', marginBottom: 20,
              fontSize: 12, color: '#D97706',
            }}>
              $25 per contract (includes AI assistant, all templates, analysis, counter & export)
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                onClick={() => setPaygConfirmDismissed(true)}
                style={{
                  flex: 1, height: 38, background: '#243447', color: 'white',
                  border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer',
                }}
              >
                Continue — $25
              </button>
              <button
                onClick={() => navigate('/dashboard')}
                style={{
                  flex: 1, height: 38, background: '#F3F4F6', color: '#374151',
                  border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 500, cursor: 'pointer',
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── WORKSPACE: fixed below top bars, above status bar ── */}
      <div style={{
        position: 'fixed', top: barsCollapsed ? 65 : 114, left: 48, right: 0, bottom: 32,
        display: 'flex', flexDirection: 'column', zIndex: 20, overflow: 'hidden',
        background: '#ffffff',
        transition: 'top 0.3s ease',
      }}>

        {/* ── BREADCRUMB BAR ── */}
        <div style={{
          height: 28, flexShrink: 0,
          background: '#132030',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          display: 'flex', alignItems: 'center',
          padding: '0 16px', gap: 6,
        }}>
          <span
            onClick={() => navigate('/contracts')}
            style={{
              fontSize: 11, color: 'rgba(255,255,255,0.45)',
              cursor: 'pointer', textDecoration: 'none',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.8)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.45)')}
          >
            Contracts
          </span>
          <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.25)' }}>›</span>
          <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.75)', fontWeight: 500 }}>
            Create Contract
          </span>
          <>
            <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.25)' }}>›</span>
            <span style={{ fontSize: 11, color: '#F5A623', fontWeight: 500 }}>
              {entityLabel ?? 'Personal'}
            </span>
          </>
        </div>

        {/* ── TOOLBAR 1: Contract Actions ── */}
        <div style={{
          minHeight: 44, flexShrink: 0,
          background: '#172334',
          display: 'flex', flexDirection: 'column',
          padding: '8px 16px 10px', gap: 8,
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 8,
            flexWrap: 'wrap',
            minWidth: 0,
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              flex: '1 1 560px',
              minWidth: 0,
              flexWrap: 'wrap',
            }}>
              {/* Title */}
              <input
                type="text"
                value={contractTitle}
                onChange={(e) => setContractTitle(e.target.value)}
                readOnly={!draftEditingAllowed}
                placeholder="Untitled Contract"
                style={{
                  background: 'transparent',
                  border: 'none',
                  borderBottom: '1px solid rgba(255,255,255,0.2)',
                  color: 'white', fontSize: 14, fontWeight: 600,
                  flex: '1 1 260px',
                  minWidth: 220,
                  maxWidth: '100%',
                  padding: '4px 8px', outline: 'none',
                }}
              />
              {/* Version */}
              <span style={{
                background: 'rgba(255,255,255,0.1)',
                color: 'rgba(255,255,255,0.6)',
                fontSize: 11, padding: '2px 8px', borderRadius: 4, flexShrink: 0,
              }}>
                v{contractVersion}
              </span>

              {/* Status dropdown */}
              <select
                value={contractStatus}
                onChange={(e) => setContractStatus(e.target.value)}
                disabled
                style={{
                  background: 'rgba(255,255,255,0.08)',
                  color: 'rgba(255,255,255,0.7)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 6, fontSize: 12, padding: '4px 10px',
                  cursor: 'pointer', outline: 'none', flexShrink: 0,
                }}
              >
                <option>Draft</option>
                <option>Active</option>
                <option>Pending</option>
                <option>Completed</option>
              </select>

              {(autosaveStatus !== 'idle' || autosaveError) && (
                <div style={{
                  display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0,
                  flexShrink: 1, marginLeft: 6, maxWidth: 260,
                }}>
                  <span style={{
                    fontSize: 11, fontWeight: 600,
                    color: autosaveStatus === 'error' ? '#FCA5A5' : autosaveStatus === 'saving' ? '#FDE68A' : '#86EFAC',
                    lineHeight: 1.2,
                  }}>
                    {autosaveStatus === 'saving' ? 'Saving...' : autosaveStatus === 'saved' ? 'Saved' : 'Save failed'}
                  </span>
                  {autosaveStatus === 'error' && autosaveError && (
                    <span style={{
                      fontSize: 10, color: '#FCA5A5', lineHeight: 1.2,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }} title={autosaveError}>
                      {autosaveError}
                    </span>
                  )}
                </div>
              )}

              {/* Currently building indicator — shown once contract is created */}
              {createdContractId && (
                <span style={{
                  fontSize: 11, color: 'rgba(255,255,255,0.5)',
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 6, padding: '3px 10px',
                  flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  maxWidth: 240,
                }}>
                  📄 {createdContractTitle ? createdContractTitle : 'In Progress'}
                </span>
              )}
            </div>

            {/* Right buttons */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-end',
              gap: 8,
              flex: '1 1 420px',
              minWidth: 0,
              flexWrap: 'wrap',
            }}>
              <GhostActionBtn label={isSendingInvite ? 'Sending...' : 'Share / Invite'} onClick={handleShareInvite} />
              <GhostActionBtn label="🔍 Analyze" onClick={() => setActiveTool('Contract Analysis')} />
              <GhostActionBtn label="⚡ Counter" onClick={() => setActiveTool('Contract Counter')} />
              <button style={{
                background: '#F5A623', color: '#0F1F3D',
                fontSize: 12, fontWeight: 600, height: 28, padding: '0 14px',
                borderRadius: 6, border: 'none', cursor: draftEditingAllowed ? 'pointer' : 'not-allowed', flexShrink: 0,
                opacity: draftEditingAllowed ? 1 : 0.55,
              }} disabled={!draftEditingAllowed}>
                Sign
              </button>
              <GhostActionBtn label="Export" />
              <button onClick={() => void flushAutosave()} style={{
                background: '#000000', color: 'white',
                fontSize: 12, fontWeight: 600, height: 28, padding: '0 14px',
                borderRadius: 6, border: 'none', cursor: draftEditingAllowed ? 'pointer' : 'not-allowed', flexShrink: 0,
                opacity: draftEditingAllowed ? 1 : 0.55,
              }} disabled={!draftEditingAllowed || !currentContractId}>
                Save
              </button>
            </div>
          </div>

          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            flexWrap: 'wrap',
            minWidth: 0,
          }}>
            {/* Choose a Template — gold dropdown */}
            <div style={{ position: 'relative', flexShrink: 0 }}>
              <button
                onClick={() => { if (draftEditingAllowed) setTemplateDropdownOpen((v) => !v) }}
                disabled={!draftEditingAllowed}
                style={{
                  height: 28, padding: '0 12px', borderRadius: 6,
                  fontSize: 12, fontWeight: 500, cursor: 'pointer',
                  background: 'rgba(245,166,35,0.12)',
                  border: '1px solid rgba(245,166,35,0.4)',
                  color: '#F5A623',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'rgba(245,166,35,0.2)'
                  e.currentTarget.style.borderColor = 'rgba(245,166,35,0.6)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'rgba(245,166,35,0.12)'
                  e.currentTarget.style.borderColor = 'rgba(245,166,35,0.4)'
                }}
              >
                ⊟ Choose a Template ▾
              </button>
              {templateDropdownOpen && (
                <div
                  style={{
                    position: 'absolute', top: '100%', left: 0, marginTop: 4,
                    background: '#243447', border: '1px solid rgba(245,166,35,0.3)',
                    borderRadius: 6, overflow: 'hidden', zIndex: 200, minWidth: 180,
                  }}
                >
                  {([
                    { icon: '📄', label: 'Contract Templates', tool: 'Contract Templates' },
                    { icon: '✓', label: 'Obligation Template', tool: 'Obligations' },
                    { icon: '💰', label: 'Payment Template', tool: 'Payments' },
                  ] as { icon: string; label: string; tool: string }[]).map(({ icon, label, tool }) => (
                    <button
                      key={tool}
                      onClick={() => { setActiveTool(tool); setTemplateDropdownOpen(false) }}
                      style={{
                        display: 'block', width: '100%', textAlign: 'left',
                        padding: '7px 12px', fontSize: 12, cursor: 'pointer',
                        background: 'transparent', border: 'none', color: 'rgba(255,255,255,0.85)',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(245,166,35,0.12)')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    >
                      {icon} {label}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Start from Scratch */}
            <button
              onClick={() => {
                if (!draftEditingAllowed) return
                if (leftEditorRef.current) {
                  leftEditorRef.current.innerHTML = ''
                  setLeftEmpty(true)
                  queueAutosave()
                }
              }}
              disabled={!draftEditingAllowed}
              style={{
                height: 28, padding: '0 12px', borderRadius: 6,
                fontSize: 12, cursor: 'pointer', flexShrink: 0,
                background: 'transparent',
                border: '1px solid rgba(255,255,255,0.15)',
                color: 'rgba(255,255,255,0.7)',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.08)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              ✎ Start from Scratch
            </button>

            {/* Ask AI */}
            <button
              onClick={() => { if (draftEditingAllowed) setAiPanelOpen((v) => !v) }}
              disabled={!draftEditingAllowed}
              style={{
                height: 28, padding: '0 12px', borderRadius: 6,
                fontSize: 12, cursor: 'pointer', flexShrink: 0,
                background: 'transparent',
                border: '1px solid rgba(255,255,255,0.15)',
                color: 'rgba(255,255,255,0.7)',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.08)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              ✦ Ask AI
            </button>
          </div>
        </div>

        {/* ── TOOLBAR 2: Rich Text ── */}
        <div style={{
          height: 42, flexShrink: 0,
          background: '#172334',
          borderBottom: '1px solid rgba(255,255,255,0.08)',
          display: 'flex', alignItems: 'center',
          padding: '0 12px', gap: 2, overflowX: 'auto',
        }}>
          {/* G1: Font Family */}
          <select
            value={fontFamily}
            onChange={(e) => { setFontFamily(e.target.value); execCmd('fontName', e.target.value) }}
            style={{
              minWidth: 140, height: 26, fontSize: 12,
              border: '1px solid rgba(255,255,255,0.15)', borderRadius: 4,
              color: 'rgba(255,255,255,0.85)', background: 'rgba(255,255,255,0.08)',
              cursor: 'pointer', flexShrink: 0, padding: '0 4px',
            }}
          >
            {FONTS.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
          <Divider />

          {/* G2: Font Size */}
          <select
            value={fontSize}
            onChange={(e) => { setFontSize(e.target.value); execCmd('fontSize', e.target.value) }}
            style={{
              width: 52, height: 26, fontSize: 12,
              border: '1px solid rgba(255,255,255,0.15)', borderRadius: 4,
              color: 'rgba(255,255,255,0.85)', background: 'rgba(255,255,255,0.08)',
              cursor: 'pointer', flexShrink: 0, padding: '0 2px',
            }}
          >
            {FONT_SIZES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <Divider />

          {/* G3: Style */}
          <TBtn label="B" title="Bold" onClick={() => execCmd('bold')} />
          <TBtn label="I" title="Italic" onClick={() => execCmd('italic')} />
          <TBtn label="U" title="Underline" onClick={() => execCmd('underline')} />
          <TBtn label="S̶" title="Strikethrough" onClick={() => execCmd('strikeThrough')} />
          <TBtn label="X²" title="Superscript" onClick={() => execCmd('superscript')} />
          <TBtn label="X₂" title="Subscript" onClick={() => execCmd('subscript')} />
          <Divider />

          {/* G4: Color */}
          <TBtn label="A" title="Text Color" />
          <TBtn label="🖊" title="Highlight" />
          <TBtn label="🎨" title="Background Color" />
          <Divider />

          {/* G5: Spacing */}
          <TBtn label="↕" title="Line Height" />
          <TBtn label="⇔" title="Letter Spacing" />
          <TBtn label="⟺" title="Word Spacing" />
          <TBtn label="¶" title="Paragraph Spacing" />
          <Divider />

          {/* G6: Alignment */}
          <TBtn label="≡" title="Align Left" onClick={() => execCmd('justifyLeft')} />
          <TBtn label="☰" title="Align Center" onClick={() => execCmd('justifyCenter')} />
          <TBtn label="≣" title="Align Right" onClick={() => execCmd('justifyRight')} />
          <TBtn label="⊟" title="Justify" onClick={() => execCmd('justifyFull')} />
          <Divider />

          {/* G7: Lists */}
          <TBtn label="•" title="Bullet List" onClick={() => execCmd('insertUnorderedList')} />
          <TBtn label="1." title="Numbered List" onClick={() => execCmd('insertOrderedList')} />
          <TBtn label="☑" title="Checklist" />
          <Divider />

          {/* G8: Structure */}
          <TBtn label="H1" title="Heading 1" onClick={() => execCmd('formatBlock', 'h1')} />
          <TBtn label="H2" title="Heading 2" onClick={() => execCmd('formatBlock', 'h2')} />
          <TBtn label="H3" title="Heading 3" onClick={() => execCmd('formatBlock', 'h3')} />
          <TBtn label="H4" title="Heading 4" onClick={() => execCmd('formatBlock', 'h4')} />
          <TBtn label="P" title="Paragraph" onClick={() => execCmd('formatBlock', 'p')} />
          <TBtn label="❝" title="Blockquote" onClick={() => execCmd('formatBlock', 'blockquote')} />
          <TBtn label="—" title="Horizontal Rule" onClick={() => execCmd('insertHorizontalRule')} />
          <Divider />

          {/* G9: Indent */}
          <TBtn label="→" title="Indent" onClick={() => execCmd('indent')} />
          <TBtn label="←" title="Outdent" onClick={() => execCmd('outdent')} />
          <Divider />

          {/* G10: Insert */}
          <TBtn label="🔗" title="Link" />
          <TBtn label="⊞" title="Table" />
          <TBtn label="🖼" title="Image" />
          <TBtn label="Ω" title="Special Character" />
          <TBtn label="📅" title="Date Stamp" />
          <Divider />

          {/* G11: History */}
          <TBtn label="↩" title="Undo" onClick={() => execCmd('undo')} />
          <TBtn label="↪" title="Redo" onClick={() => execCmd('redo')} />
          <TBtn label="✕" title="Clear Formatting" onClick={() => execCmd('removeFormat')} />
          <Divider />

          {/* G12: View */}
          <TBtn label="🔍+" title="Zoom In" />
          <TBtn label="🔍-" title="Zoom Out" />
          <TBtn label="⛶" title="Fullscreen" />
        </div>

        {/* ── MAIN WORKSPACE ROW ── */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'row', minHeight: 0 }}>

          {/* TOOL ICON STRIP */}
          <div style={{
            width: 52, flexShrink: 0,
            background: '#243447',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center', paddingTop: 8,
            gap: 2,
            zIndex: 10,
          }}>
            {CONTRACT_TOOLS.map((tool) => {
              const isActive = activeTool === tool.label
              return (
                <div key={tool.label} style={{ position: 'relative', width: '100%', display: 'flex', justifyContent: 'center' }}>
                  <button
                    onClick={() => setActiveTool(isActive ? null : tool.label)}
                    style={{
                      width: 40, height: 40,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      borderRadius: 8, border: 'none',
                      background: isActive ? 'rgba(245,166,35,0.15)' : 'transparent',
                      color: isActive ? '#F5A623' : 'rgba(255,255,255,0.55)',
                      fontSize: 16, cursor: 'pointer',
                    }}
                    onMouseEnter={(e) => {
                      if (!isActive) {
                        e.currentTarget.style.background = 'rgba(255,255,255,0.08)'
                        e.currentTarget.style.color = 'white'
                      }
                      const tt = e.currentTarget.nextElementSibling as HTMLElement
                      if (tt) tt.style.display = 'block'
                    }}
                    onMouseLeave={(e) => {
                      if (!isActive) {
                        e.currentTarget.style.background = 'transparent'
                        e.currentTarget.style.color = 'rgba(255,255,255,0.55)'
                      }
                      const tt = e.currentTarget.nextElementSibling as HTMLElement
                      if (tt) tt.style.display = 'none'
                    }}
                  >
                    {tool.icon}
                  </button>
                  <div style={{
                    display: 'none',
                    position: 'absolute',
                    left: 48, top: '50%', transform: 'translateY(-50%)',
                    background: '#243447', color: 'white',
                    fontSize: 11, padding: '4px 10px',
                    borderRadius: 6, whiteSpace: 'nowrap',
                    zIndex: 500, pointerEvents: 'none',
                    border: '1px solid rgba(255,255,255,0.12)',
                  }}>
                    {tool.label}
                  </div>
                </div>
              )
            })}
          </div>

          {/* TOOL PANEL */}
          <div style={{
            width: activeTool ? toolPanelWidth : 0,
            flexShrink: 0,
            transition: toolPanelSnapping ? 'width 0.3s ease' : 'none',
            overflow: 'hidden',
            background: '#4E6E7A',
            boxShadow: '4px 0 12px rgba(0,0,0,0.08)',
            position: 'relative',
          }}>
            <div style={{ width: toolPanelWidth, height: '100%', display: 'flex', flexDirection: 'column', position: 'relative' }}>
              {activeTool && (
                <>
                  {/* Panel header */}
                  <div style={{
                    padding: '16px 16px 12px',
                    borderBottom: '1px solid rgba(255,255,255,0.1)',
                    display: 'flex', alignItems: 'center', flexShrink: 0,
                  }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: '#ffffff', flex: 1 }}>
                      {activeTool}
                    </span>
                    <button
                      onClick={snapToolPanel}
                      title={toolPanelWidth >= 560 ? 'Collapse panel' : 'Expand panel'}
                      style={{
                        background: 'transparent', border: 'none',
                        color: 'rgba(255,255,255,0.55)', fontSize: 14,
                        cursor: 'pointer', padding: '0 4px', lineHeight: 1, marginRight: 4,
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = 'white')}
                      onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.55)')}
                    >
                      ⇔
                    </button>
                    <button
                      onClick={() => setActiveTool(null)}
                      style={{
                        background: 'transparent', border: 'none',
                        color: 'rgba(255,255,255,0.55)', fontSize: 16,
                        cursor: 'pointer', padding: 0, lineHeight: 1,
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = 'white')}
                      onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.55)')}
                    >
                      ✕
                    </button>
                  </div>

                  {/* Drag handle on right edge */}
                  <div
                    onMouseDown={onToolPanelHandleMouseDown}
                    style={{
                      position: 'absolute', right: 0, top: 0, bottom: 0,
                      width: 6, cursor: 'col-resize',
                      background: '#243447',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      zIndex: 5,
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = '#263d52')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = '#243447')}
                  >
                    <div style={{
                      width: 3, height: 40,
                      background: 'rgba(255,255,255,0.2)',
                      borderRadius: 3, pointerEvents: 'none',
                    }} />
                  </div>

                  {/* Panel content */}
                  <div style={{
                    flex: 1, overflowY: 'auto', padding: 16,
                    pointerEvents: activeTool === 'Contract Details' && !draftEditingAllowed ? 'none' : 'auto',
                    opacity: activeTool === 'Contract Details' && !draftEditingAllowed ? 0.55 : 1,
                  }}>
                    {activeTool === 'Calculator' ? (
                      <>
                        {/* Display screen */}
                        <div style={{
                          background: '#243447', borderRadius: 10,
                          padding: 16, marginBottom: 14, minHeight: 80,
                          display: 'flex', flexDirection: 'column',
                          justifyContent: 'flex-end', alignItems: 'flex-end',
                        }}>
                          <div style={{
                            fontSize: 11, color: 'rgba(255,255,255,0.4)',
                            fontFamily: "'DM Mono', monospace",
                            marginBottom: 4, minHeight: 16,
                          }}>
                            {calcFormula}
                          </div>
                          <div style={{
                            fontSize: 28, fontWeight: 500, color: '#ffffff',
                            fontFamily: "'DM Mono', monospace",
                            letterSpacing: '-0.02em', wordBreak: 'break-all',
                          }}>
                            {calcDisplay}
                          </div>
                        </div>

                        {/* Button grid — flat array, CSS grid handles layout */}
                        <div style={{
                          display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
                          gap: 8, marginBottom: 14,
                        }}>
                          {([
                            { l: 'C', t: 'clear' }, { l: '±', t: 'sign' }, { l: '%', t: 'pct' }, { l: '÷', t: 'op' },
                            { l: '7', t: 'num'   }, { l: '8', t: 'num'  }, { l: '9', t: 'num'  }, { l: '×', t: 'op' },
                            { l: '4', t: 'num'   }, { l: '5', t: 'num'  }, { l: '6', t: 'num'  }, { l: '−', t: 'op' },
                            { l: '1', t: 'num'   }, { l: '2', t: 'num'  }, { l: '3', t: 'num'  }, { l: '+', t: 'op' },
                            { l: '0', t: 'zero'  }, { l: '.', t: 'num'  }, { l: '=', t: 'eq'   },
                          ] as { l: string; t: string }[]).map(({ l, t }) => {
                            let bg = '#ffffff'; let color = '#0F1F3D'
                            if (t === 'op')               { bg = 'rgba(245,166,35,0.15)'; color = '#92650A' }
                            if (t === 'eq')               { bg = '#243447';               color = '#ffffff'  }
                            if (t === 'clear')            { bg = 'rgba(239,68,68,0.1)';   color = '#DC2626'  }
                            if (t === 'sign' || t === 'pct') { bg = 'rgba(15,31,61,0.08)'; color = '#0F1F3D' }
                            return (
                              <button
                                key={l}
                                onClick={() => {
                                  if (t === 'num' || t === 'zero') calcInput(l)
                                  else if (t === 'op')   calcOp(l)
                                  else if (t === 'eq')   calcEqual()
                                  else if (t === 'clear') calcClear()
                                  else if (t === 'sign') setCalcDisplay(String(parseFloat(calcDisplay) * -1))
                                  else if (t === 'pct')  setCalcDisplay(String(parseFloat(calcDisplay) / 100))
                                }}
                                style={{
                                  height: 46, border: 'none', borderRadius: 8,
                                  fontSize: t === 'eq' ? 18 : 15, fontWeight: 500,
                                  cursor: 'pointer', fontFamily: "'DM Mono', monospace",
                                  transition: 'all 0.1s',
                                  display: 'flex', alignItems: 'center',
                                  justifyContent: t === 'zero' ? 'flex-start' : 'center',
                                  gridColumn: t === 'zero' ? 'span 2' : undefined,
                                  paddingLeft: t === 'zero' ? 18 : undefined,
                                  background: bg, color,
                                }}
                                onMouseEnter={(e) => {
                                  const el = e.currentTarget
                                  if (t === 'num' || t === 'zero') el.style.background = '#F3F4F6'
                                  else if (t === 'op')    el.style.background = 'rgba(245,166,35,0.25)'
                                  else if (t === 'eq')    el.style.background = '#1a3460'
                                  else if (t === 'clear') el.style.background = 'rgba(239,68,68,0.18)'
                                  else                    el.style.background = 'rgba(15,31,61,0.14)'
                                }}
                                onMouseLeave={(e) => {
                                  e.currentTarget.style.background = bg
                                  e.currentTarget.style.transform = 'scale(1)'
                                }}
                                onMouseDown={(e) => {
                                  if (t === 'num' || t === 'zero') e.currentTarget.style.background = '#E5E7EB'
                                  else if (t === 'op') e.currentTarget.style.background = 'rgba(245,166,35,0.35)'
                                  e.currentTarget.style.transform = 'scale(0.97)'
                                }}
                                onMouseUp={(e) => { e.currentTarget.style.transform = 'scale(1)' }}
                              >
                                {l}
                              </button>
                            )
                          })}
                        </div>

                        {/* Financial tools */}
                        <div style={{ height: 1, background: '#D1D5DB', margin: '4px 0 12px' }} />
                        <p style={{
                          fontSize: 10, color: 'rgba(255,255,255,0.35)', fontWeight: 600,
                          textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8,
                        }}>
                          Financial
                        </p>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                          {(['PMT', 'PV', 'FV', '%'] as const).map((l) => (
                            <button
                              key={l}
                              style={{
                                height: 36, borderRadius: 8, fontSize: 11, fontWeight: 600,
                                border: '1px solid rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.07)', color: 'rgba(255,255,255,0.85)',
                                cursor: 'pointer', fontFamily: "'Outfit', sans-serif",
                                transition: 'all 0.1s',
                              }}
                              onMouseEnter={(e) => {
                                e.currentTarget.style.background = 'rgba(255,255,255,0.14)'
                                e.currentTarget.style.borderColor = 'rgba(255,255,255,0.22)'
                                e.currentTarget.style.color = 'white'
                              }}
                              onMouseLeave={(e) => {
                                e.currentTarget.style.background = 'rgba(255,255,255,0.07)'
                                e.currentTarget.style.borderColor = 'rgba(255,255,255,0.12)'
                                e.currentTarget.style.color = 'rgba(255,255,255,0.85)'
                              }}
                            >
                              {l}
                            </button>
                          ))}
                        </div>
                      </>
                    ) : activeTool === 'Contract Analysis' ? (
                      <>
                        <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.55)', marginBottom: 16 }}>
                          Write or paste your contract in the editor, then click Analyze for a full AI breakdown.
                        </p>
                        {USER_TIER === 'per_contract' && (
                          <p style={{ fontSize: 11, color: '#065F46', marginBottom: 12 }}>
                            ✓ Included with your $25 contract
                          </p>
                        )}
                        <button
                          onClick={async () => {
                            setIsAnalyzing(true)
                            setAnalysisResult('')
                            try {
                              const text = leftEditorRef.current?.innerText ?? ''
                              const res = await fetch('/api/contracts/analyze/', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ contract_text: text }),
                              })
                              const data = await res.json()
                              setAnalysisResult(data.result ?? JSON.stringify(data))
                            } catch {
                              setAnalysisResult('Analysis failed. Please try again.')
                            } finally {
                              setIsAnalyzing(false)
                            }
                          }}
                          disabled={isAnalyzing}
                          style={{
                            width: '100%', height: 36,
                            background: isAnalyzing ? '#6B7280' : '#243447',
                            color: 'white', border: 'none',
                            borderRadius: 8, fontSize: 13, fontWeight: 600,
                            cursor: isAnalyzing ? 'default' : 'pointer',
                            marginBottom: 12,
                          }}
                          onMouseEnter={(e) => { if (!isAnalyzing) e.currentTarget.style.background = '#1a3460' }}
                          onMouseLeave={(e) => { if (!isAnalyzing) e.currentTarget.style.background = '#243447' }}
                        >
                          {isAnalyzing ? 'Analyzing…' : 'Analyze Contract'}
                        </button>
                        <div style={{
                          background: 'rgba(255,255,255,0.07)', borderRadius: 8, padding: 12,
                          minHeight: 120, border: '1px solid rgba(255,255,255,0.12)',
                          fontSize: 12, color: analysisResult ? 'rgba(255,255,255,0.85)' : 'rgba(255,255,255,0.35)',
                        }}>
                          {analysisResult || 'Analysis results will appear here…'}
                        </div>
                      </>
                    ) : activeTool === 'Contract Counter' ? (
                      <>
                        {USER_TIER === 'starter' ? (
                          <div style={{ textAlign: 'center' }}>
                            <div style={{ fontSize: 32, marginBottom: 12 }}>🔒</div>
                            <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.85)', marginBottom: 16 }}>
                              Contract Counter is available on Blackbòd Pro and above.
                            </p>
                            <button
                              style={{
                                width: '100%', height: 36,
                                background: '#F5A623', color: '#0F1F3D',
                                border: 'none', borderRadius: 8,
                                fontSize: 13, fontWeight: 600, cursor: 'pointer',
                              }}
                              onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.9')}
                              onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
                            >
                              Upgrade to Blackbòd Pro — $149/month
                            </button>
                          </div>
                        ) : (
                          <>
                            <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.55)', marginBottom: 12 }}>
                              Review the contract and propose your counter terms.
                            </p>
                            {USER_TIER === 'per_contract' && (
                              <p style={{ fontSize: 11, color: '#065F46', marginBottom: 12 }}>
                                ✓ Included with your $25 contract
                              </p>
                            )}
                            <textarea
                              value={counterText}
                              onChange={(e) => setCounterText(e.target.value)}
                              placeholder="Enter your counter terms…"
                              style={{
                                width: '100%', minHeight: 100,
                                border: '1px solid rgba(255,255,255,0.12)',
                                borderRadius: 8, padding: 10,
                                fontSize: 12, resize: 'vertical',
                                outline: 'none', fontFamily: 'inherit',
                                boxSizing: 'border-box',
                                marginBottom: 12,
                                background: 'rgba(255,255,255,0.07)',
                                color: 'white',
                              }}
                            />
                            <button
                              onClick={async () => {
                                setIsSubmittingCounter(true)
                                try {
                                  const text = leftEditorRef.current?.innerText ?? ''
                                  await fetch('/api/contracts/counter/', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ contract_text: text, counter_terms: counterText }),
                                  })
                                } finally {
                                  setIsSubmittingCounter(false)
                                }
                              }}
                              disabled={isSubmittingCounter}
                              style={{
                                width: '100%', height: 36,
                                background: isSubmittingCounter ? '#6B7280' : '#243447',
                                color: 'white', border: 'none',
                                borderRadius: 8, fontSize: 13, fontWeight: 600,
                                cursor: isSubmittingCounter ? 'default' : 'pointer',
                              }}
                              onMouseEnter={(e) => { if (!isSubmittingCounter) e.currentTarget.style.background = '#1a3460' }}
                              onMouseLeave={(e) => { if (!isSubmittingCounter) e.currentTarget.style.background = '#243447' }}
                            >
                              {isSubmittingCounter ? 'Submitting…' : 'Submit Counter'}
                            </button>
                          </>
                        )}
                      </>
                    ) : activeTool === 'Parties' ? (() => {
                      const SECTION_HDR: React.CSSProperties = {
                        fontSize: 11, fontWeight: 600, color: 'rgba(255,255,255,0.55)',
                        textTransform: 'uppercase', letterSpacing: '0.06em',
                        margin: '0 0 10px',
                      }
                      const ROLE_SELECT: React.CSSProperties = {
                        width: 120, fontSize: 12,
                        border: '1px solid rgba(255,255,255,0.12)', borderRadius: 6,
                        padding: '4px 8px', background: 'rgba(255,255,255,0.07)',
                        color: 'white', outline: 'none', flexShrink: 0,
                        cursor: 'pointer',
                      }
                      const AVATAR: React.CSSProperties = {
                        width: 36, height: 36, borderRadius: '50%',
                        background: '#243447', color: 'white', fontSize: 13,
                        fontWeight: 600, display: 'flex', alignItems: 'center',
                        justifyContent: 'center', flexShrink: 0,
                      }
                      const CUSTOM_ROLE_INPUT: React.CSSProperties = {
                        width: '100%', background: 'rgba(255,255,255,0.07)',
                        border: '1px solid rgba(255,255,255,0.12)', borderRadius: 8,
                        padding: '8px 12px', fontSize: 13, color: 'white',
                        fontFamily: "'Outfit', sans-serif", outline: 'none',
                        marginBottom: 12, boxSizing: 'border-box',
                      }

                      const p1Name = user
                        ? [user.first_name, user.last_name].filter(Boolean).join(' ') || user.username
                        : 'You'
                      const p1BonId = user?.bon_id ?? '—'
                      const partyCount = 1
                        + (party2Added ? 1 : 0)
                        + additionalParties.filter((p) => p.added).length

                      return (
                        <>
                          {/* Party count indicator */}
                          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
                            <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.55)' }}>
                              {partyCount} of 6 parties added
                            </span>
                          </div>

                          {/* Party 1 — logged-in user */}
                          <p style={SECTION_HDR}>Party 1 (You)</p>
                          <div style={{
                            background: 'white', borderRadius: 8, padding: 12,
                            marginBottom: party1Role === 'Other (type below)' ? 8 : 16,
                            border: '1px solid #D1D5DB',
                            display: 'flex', alignItems: 'center', gap: 10,
                          }}>
                            <div style={AVATAR}>{getInitials(p1Name)}</div>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <p style={{
                                fontSize: 13, fontWeight: 500, color: '#0F1F3D',
                                margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                              }}>
                                {p1Name}
                              </p>
                              <p style={{ fontSize: 11, color: '#8B5CF6', fontFamily: "'DM Mono', monospace", margin: 0 }}>
                                {p1BonId}
                              </p>
                            </div>
                            <select
                              value={party1Role}
                              onChange={(e) => setParty1Role(e.target.value)}
                              style={ROLE_SELECT}
                            >
                              <option value="">Select role...</option>
                              {PARTY_ROLES.map((r) => <option key={r}>{r}</option>)}
                            </select>
                          </div>
                          {party1Role === 'Other (type below)' && (
                            <input
                              type="text"
                              value={party1CustomRole}
                              onChange={(e) => setParty1CustomRole(e.target.value)}
                              placeholder="Enter custom role"
                              style={CUSTOM_ROLE_INPUT}
                              onFocus={onFieldFocus}
                              onBlur={onFieldBlur}
                            />
                          )}

                          {/* Party 2 — search */}
                          <p style={{ ...SECTION_HDR, marginTop: 4 }}>Party 2</p>
                          <PartySearchBlock
                            searchQuery={party2SearchQuery}
                            onSearchQueryChange={setParty2SearchQuery}
                            searchResult={party2SearchResult}
                            onSearchResultChange={setParty2SearchResult}
                            searchDone={party2SearchDone}
                            onSearchDoneChange={setParty2SearchDone}
                            added={party2Added}
                            onAddedChange={(v) => {
                              setParty2Added(v)
                              if (v && party2SearchResult) {
                                saveContactFromParty({ name: party2SearchResult.name, bonId: party2SearchResult.bonId })
                                reloadContacts()
                              }
                            }}
                            role={party2Role}
                            onRoleChange={setParty2Role}
                            customRole={party2CustomRole}
                            onCustomRoleChange={setParty2CustomRole}
                          />

                          {/* Your Contacts */}
                          {!party2Added && contacts.length > 0 && (
                            <div style={{ marginBottom: 16 }}>
                              <p style={{ ...SECTION_HDR, marginTop: 8, marginBottom: 8 }}>Your Contacts</p>
                              <div style={{ maxHeight: 220, overflowY: 'auto' }}>
                                {contacts.map((c) => (
                                  <div
                                    key={c.id}
                                    style={{
                                      display: 'flex', alignItems: 'center', gap: 8,
                                      background: 'rgba(255,255,255,0.07)',
                                      borderRadius: 8, padding: '8px 10px',
                                      marginBottom: 6,
                                    }}
                                  >
                                    <div style={{
                                      width: 30, height: 30, borderRadius: '50%',
                                      background: '#243447', color: 'white',
                                      fontSize: 11, fontWeight: 700,
                                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                                      flexShrink: 0,
                                    }}>
                                      {getContactInitials(c)}
                                    </div>
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                      <div style={{
                                        fontSize: 12, fontWeight: 500, color: 'white',
                                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                                      }}>
                                        {getContactDisplayName(c)}
                                      </div>
                                      {c.bonId && (
                                        <div style={{ fontSize: 10, color: '#8B5CF6', fontFamily: "'DM Mono', monospace" }}>
                                          {c.bonId}
                                        </div>
                                      )}
                                    </div>
                                    <button
                                      onClick={() => {
                                        const name = getContactDisplayName(c)
                                        const bonId = c.bonId || `#${name.toUpperCase().replace(/\s+/g, '').slice(0, 8)}`
                                        setParty2SearchResult({ name, bonId, initials: getContactInitials(c) })
                                        setParty2SearchDone(true)
                                        setParty2Added(true)
                                        setParty2SearchQuery(name)
                                        saveContactFromParty({ name, bonId })
                                        reloadContacts()
                                      }}
                                      style={{
                                        height: 22, padding: '0 8px', fontSize: 10, fontWeight: 500,
                                        borderRadius: 4, border: '1px solid #243447',
                                        background: '#243447', color: 'white', cursor: 'pointer',
                                        flexShrink: 0,
                                      }}
                                      onMouseEnter={(e) => (e.currentTarget.style.background = '#1a3460')}
                                      onMouseLeave={(e) => (e.currentTarget.style.background = '#243447')}
                                    >
                                      Select
                                    </button>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Additional parties */}
                          {additionalParties.map((p, idx) => (
                            <div key={idx}>
                              <div style={{ display: 'flex', alignItems: 'center', marginBottom: 10, marginTop: 4 }}>
                                <p style={{ ...SECTION_HDR, margin: 0 }}>Party {idx + 3}</p>
                                <button
                                  onClick={() => setAdditionalParties((prev) => prev.filter((_, i) => i !== idx))}
                                  style={{
                                    marginLeft: 'auto', background: 'transparent', border: 'none',
                                    color: '#9CA3AF', fontSize: 14, cursor: 'pointer',
                                    lineHeight: 1, padding: 0,
                                  }}
                                  onMouseEnter={(e) => (e.currentTarget.style.color = '#DC2626')}
                                  onMouseLeave={(e) => (e.currentTarget.style.color = '#9CA3AF')}
                                  title="Remove party slot"
                                >
                                  ✕
                                </button>
                              </div>
                              <PartySearchBlock
                                searchQuery={p.searchQuery}
                                onSearchQueryChange={(v) => setAdditionalParties((prev) => prev.map((ap, i) => i === idx ? { ...ap, searchQuery: v } : ap))}
                                searchResult={p.searchResult}
                                onSearchResultChange={(v) => setAdditionalParties((prev) => prev.map((ap, i) => i === idx ? { ...ap, searchResult: v } : ap))}
                                searchDone={p.searchDone}
                                onSearchDoneChange={(v) => setAdditionalParties((prev) => prev.map((ap, i) => i === idx ? { ...ap, searchDone: v } : ap))}
                                added={p.added}
                                onAddedChange={(v) => {
                                  setAdditionalParties((prev) => prev.map((ap, i) => i === idx ? { ...ap, added: v } : ap))
                                  if (v && p.searchResult) {
                                    saveContactFromParty({ name: p.searchResult.name, bonId: p.searchResult.bonId })
                                    reloadContacts()
                                  }
                                }}
                                role={p.role}
                                onRoleChange={(v) => setAdditionalParties((prev) => prev.map((ap, i) => i === idx ? { ...ap, role: v } : ap))}
                                customRole={p.customRole}
                                onCustomRoleChange={(v) => setAdditionalParties((prev) => prev.map((ap, i) => i === idx ? { ...ap, customRole: v } : ap))}
                              />
                            </div>
                          ))}

                          {/* Add Another Party */}
                          {party2Added && partyCount < 6 && (
                            <button
                              onClick={() => setAdditionalParties((prev) => [...prev, {
                                searchQuery: '', searchResult: null, searchDone: false,
                                added: false, role: '', customRole: '',
                              }])}
                              style={{
                                width: '100%', height: 32, background: 'transparent',
                                border: '1px dashed #D1D5DB', borderRadius: 8,
                                fontSize: 12, color: '#6B7280', cursor: 'pointer',
                                marginBottom: 12,
                              }}
                              onMouseEnter={(e) => {
                                e.currentTarget.style.borderColor = '#243447'
                                e.currentTarget.style.color = '#0F1F3D'
                              }}
                              onMouseLeave={(e) => {
                                e.currentTarget.style.borderColor = '#D1D5DB'
                                e.currentTarget.style.color = '#6B7280'
                              }}
                            >
                              + Add Another Party
                            </button>
                          )}

                        </>
                      )
                    })() : activeTool === 'Contract Details' ? (() => {
                      const LABEL: React.CSSProperties = {
                        fontSize: 11, fontWeight: 500, color: 'rgba(255,255,255,0.55)',
                        marginBottom: 4, display: 'block',
                        textTransform: 'uppercase', letterSpacing: '0.06em',
                      }
                      const FIELD: React.CSSProperties = {
                        width: '100%', background: 'rgba(255,255,255,0.07)',
                        border: '1px solid rgba(255,255,255,0.12)', borderRadius: 8,
                        padding: '8px 12px', fontSize: 13, color: 'white',
                        fontFamily: "'Outfit', sans-serif", outline: 'none',
                        marginBottom: 12, boxSizing: 'border-box',
                      }
                      const TIER_ALLOWS_BUSINESS = ['trial', 'per_contract', 'professional', 'business', 'anchor'].includes(USER_TIER)

                      const userInitials =
                        [user?.first_name?.[0], user?.last_name?.[0]].filter(Boolean).join('').toUpperCase() ||
                        user?.username?.[0]?.toUpperCase() || '?'
                      const userDisplayName =
                        user?.first_name ? `${user.first_name} ${user.last_name}`.trim() : user?.username ?? 'You'

                      function bizInitials(name: string) {
                        const words = name.trim().split(/\s+/)
                        return words.length >= 2
                          ? (words[0][0] + words[words.length - 1][0]).toUpperCase()
                          : name.substring(0, 2).toUpperCase()
                      }

                      const CARD_BASE: React.CSSProperties = {
                        background: 'white', borderRadius: 8, padding: '10px 12px',
                        border: '1px solid #D1D5DB',
                        display: 'flex', alignItems: 'center', gap: 10,
                        cursor: 'pointer', marginBottom: 6,
                        transition: 'all 0.15s',
                      }
                      const CARD_SELECTED: React.CSSProperties = {
                        ...CARD_BASE,
                        borderColor: '#243447', background: '#F0F4F8',
                        boxShadow: '0 0 0 2px rgba(15,31,61,0.1)',
                      }

                      return (
                        <>
                          {/* 0. Contracting As */}
                          <label style={{
                            ...LABEL,
                            textTransform: 'uppercase' as const,
                            letterSpacing: '0.06em',
                            marginBottom: 8,
                          }}>Contracting As</label>

                          {/* Personal card */}
                          <div
                            onClick={() => setSelectedEntity(null)}
                            style={selectedEntity === null ? CARD_SELECTED : CARD_BASE}
                          >
                            <div style={{
                              width: 32, height: 32, borderRadius: '50%',
                              background: '#243447', color: 'white',
                              fontSize: 12, fontWeight: 600,
                              display: 'flex', alignItems: 'center', justifyContent: 'center',
                              flexShrink: 0,
                            }}>
                              {userInitials}
                            </div>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <span style={{ fontSize: 13, fontWeight: 500, color: '#0F1F3D' }}>
                                {userDisplayName}
                              </span>
                              <span style={{
                                marginLeft: 6, background: '#E5E7EB', color: '#374151',
                                fontSize: 10, padding: '2px 6px', borderRadius: 4,
                              }}>Personal</span>
                            </div>
                            {user?.bon_id && (
                              <span style={{ fontSize: 10, color: '#8B5CF6', fontFamily: "'DM Mono', monospace", flexShrink: 0 }}>
                                {user.bon_id}
                              </span>
                            )}
                          </div>

                          {/* Business entity cards */}
                          {MOCK_ENTITIES.map((entity) => (
                            <div
                              key={entity.id}
                              onClick={() => setSelectedEntity(entity.id)}
                              style={selectedEntity === entity.id ? CARD_SELECTED : CARD_BASE}
                            >
                              <div style={{
                                width: 32, height: 32, borderRadius: '50%',
                                background: '#1E3A55', color: 'white',
                                fontSize: 12, fontWeight: 600,
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                flexShrink: 0,
                              }}>
                                {bizInitials(entity.name)}
                              </div>
                              <div style={{ flex: 1, minWidth: 0 }}>
                                <span style={{ fontSize: 13, fontWeight: 500, color: '#0F1F3D' }}>
                                  {entity.name}
                                </span>
                                <span style={{
                                  marginLeft: 6, background: '#EFF6FF', color: '#1D4ED8',
                                  fontSize: 10, padding: '2px 6px', borderRadius: 4,
                                }}>{entity.type}</span>
                              </div>
                            </div>
                          ))}

                          {/* Add a Business card — tier allows, no entities */}
                          {TIER_ALLOWS_BUSINESS && MOCK_ENTITIES.length === 0 && (
                            <div
                              style={{
                                ...CARD_BASE,
                                border: '1px dashed #D1D5DB',
                                color: '#6B7280', fontSize: 13,
                              }}
                              onMouseEnter={(e) => {
                                e.currentTarget.style.borderColor = '#243447'
                                e.currentTarget.style.color = '#0F1F3D'
                              }}
                              onMouseLeave={(e) => {
                                e.currentTarget.style.borderColor = '#D1D5DB'
                                e.currentTarget.style.color = '#6B7280'
                              }}
                              onClick={() => navigate('/entities')}
                            >
                              <div style={{
                                width: 32, height: 32, borderRadius: '50%',
                                background: '#F3F4F6',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                fontSize: 16, flexShrink: 0,
                              }}>+</div>
                              + Add a Business Entity
                            </div>
                          )}

                          {/* Locked card — tier does not allow */}
                          {!TIER_ALLOWS_BUSINESS && (
                            <div
                              style={{
                                background: '#F9FAFB', borderRadius: 8, padding: '10px 12px',
                                border: '1px solid #E5E7EB',
                                display: 'flex', alignItems: 'center', gap: 10,
                                color: '#9CA3AF', fontSize: 12, marginBottom: 6,
                              }}
                              onClick={() => navigate('/settings')}
                            >
                              <span style={{ fontSize: 16 }}>🔒</span>
                              Business entities available on Blackbòd Pro ($149/month)
                            </div>
                          )}

                          <div style={{ marginBottom: 8 }} />

                          {/* 1. Contract Title */}
                          <label style={LABEL}>Contract Title</label>
                          <input
                            type="text"
                            value={contractTitle}
                            onChange={(e) => setContractTitle(e.target.value)}
                            placeholder="Enter contract title"
                            style={FIELD}
                            onFocus={onFieldFocus}
                            onBlur={onFieldBlur}
                          />

                          {/* 2. Contract Type */}
                          <label style={LABEL}>Contract Type</label>
                          <select
                            value={detailsType}
                            onChange={(e) => setDetailsType(e.target.value)}
                            style={FIELD}
                            onFocus={onFieldFocus}
                            onBlur={onFieldBlur}
                          >
                            <option value="">Select type...</option>
                            <option>Service Agreement</option>
                            <option>Employment Contract</option>
                            <option>Freelance Contract</option>
                            <option>NDA / Confidentiality</option>
                            <option>Partnership Agreement</option>
                            <option>Sales Contract</option>
                            <option>Lease Agreement</option>
                            <option>Loan Agreement</option>
                            <option>Settlement Agreement</option>
                            <option>Consulting Agreement</option>
                            <option>Licensing Agreement</option>
                            <option>Distribution Agreement</option>
                            <option>Joint Venture</option>
                            <option>Purchase Agreement</option>
                            <option>Other</option>
                          </select>

                          {/* 3. Language */}
                          <label style={LABEL}>Language</label>
                          <select
                            value={detailsLanguage}
                            onChange={(e) => setDetailsLanguage(e.target.value)}
                            style={FIELD}
                            onFocus={onFieldFocus}
                            onBlur={onFieldBlur}
                          >
                            <option>English</option>
                            <option>Haitian Creole</option>
                            <option>Spanish</option>
                            <option>French</option>
                            <option>Portuguese</option>
                            <option>Arabic</option>
                            <option>Swahili</option>
                          </select>

                          {/* 4. Start Date */}
                          <label style={LABEL}>Start Date</label>
                          <input
                            type="date"
                            value={detailsStartDate}
                            onChange={(e) => setDetailsStartDate(e.target.value)}
                            style={FIELD}
                            onFocus={onFieldFocus}
                            onBlur={onFieldBlur}
                          />

                          {/* 5. End Date */}
                          <label style={LABEL}>End Date</label>
                          <input
                            type="date"
                            value={detailsEndDate}
                            onChange={(e) => setDetailsEndDate(e.target.value)}
                            style={FIELD}
                            onFocus={onFieldFocus}
                            onBlur={onFieldBlur}
                          />

                          {/* 6. Contract Value */}
                          <label style={LABEL}>Contract Value</label>
                          <input
                            type="number"
                            value={detailsValue}
                            onChange={(e) => setDetailsValue(e.target.value)}
                            placeholder="0.00"
                            step={0.01}
                            min={0}
                            style={FIELD}
                            onFocus={onFieldFocus}
                            onBlur={onFieldBlur}
                          />

                          {/* 7. Currency */}
                          <label style={LABEL}>Currency</label>
                          <select
                            value={detailsCurrency}
                            onChange={(e) => setDetailsCurrency(e.target.value)}
                            style={FIELD}
                            onFocus={onFieldFocus}
                            onBlur={onFieldBlur}
                          >
                            {CURRENCIES.map(([code, name]) => (
                              <option key={code} value={code}>{code} — {name}</option>
                            ))}
                          </select>

                          {/* 8. Jurisdiction */}
                          <label style={LABEL}>Jurisdiction</label>
                          <input
                            type="text"
                            value={detailsJurisdiction}
                            onChange={(e) => setDetailsJurisdiction(e.target.value)}
                            placeholder="e.g. New York, USA"
                            style={FIELD}
                            onFocus={onFieldFocus}
                            onBlur={onFieldBlur}
                          />

                          {/* 9. Governing Law */}
                          <label style={LABEL}>Governing Law</label>
                          <input
                            type="text"
                            value={detailsGoverningLaw}
                            onChange={(e) => setDetailsGoverningLaw(e.target.value)}
                            placeholder="e.g. Laws of New York State"
                            style={FIELD}
                            onFocus={onFieldFocus}
                            onBlur={onFieldBlur}
                          />

                          {/* 10. Confidentiality */}
                          <label style={LABEL}>Confidentiality</label>
                          <select
                            value={detailsConfidentiality}
                            onChange={(e) => setDetailsConfidentiality(e.target.value)}
                            style={FIELD}
                            onFocus={onFieldFocus}
                            onBlur={onFieldBlur}
                          >
                            <option>Not confidential</option>
                            <option>Confidential</option>
                            <option>Strictly confidential</option>
                          </select>

                          {/* 11. Dispute Resolution */}
                          <label style={LABEL}>Dispute Resolution</label>
                          <select
                            value={detailsDispute}
                            onChange={(e) => setDetailsDispute(e.target.value)}
                            style={FIELD}
                            onFocus={onFieldFocus}
                            onBlur={onFieldBlur}
                          >
                            <option>Negotiation</option>
                            <option>Mediation</option>
                            <option>Arbitration</option>
                            <option>Litigation</option>
                            <option>Arbitration then Litigation</option>
                          </select>

                          {/* 12. Counterparty */}
                          <label style={LABEL}>Counterparty Name</label>
                          <input
                            type="text"
                            value={detailsCounterpartyName}
                            onChange={(e) => setDetailsCounterpartyName(e.target.value)}
                            placeholder="Counterparty name"
                            style={FIELD}
                            onFocus={onFieldFocus}
                            onBlur={onFieldBlur}
                          />

                          <label style={LABEL}>Counterparty Email</label>
                          <input
                            type="email"
                            value={detailsCounterpartyEmail}
                            onChange={(e) => setDetailsCounterpartyEmail(e.target.value)}
                            placeholder="counterparty@example.com"
                            style={FIELD}
                            onFocus={onFieldFocus}
                            onBlur={onFieldBlur}
                          />

                          {/* 13. Description / Notes */}
                          <label style={LABEL}>Description</label>
                          <textarea
                            value={detailsDescription}
                            onChange={(e) => setDetailsDescription(e.target.value)}
                            placeholder="Brief description of this contract..."
                            rows={3}
                            style={{ ...FIELD, resize: 'vertical' }}
                            onFocus={onFieldFocus}
                            onBlur={onFieldBlur}
                          />

                          {detailsSaveError && (
                            <div style={{ fontSize: 11, color: '#F87171', marginBottom: 8 }}>
                              {detailsSaveError}
                            </div>
                          )}
                          {detailsSaveMessage && (
                            <div style={{
                              fontSize: 11, color: '#34D399', marginBottom: 8,
                              display: 'flex', alignItems: 'center', gap: 4,
                            }}>
                              ✓ {detailsSaveMessage}
                            </div>
                          )}
                          {!createdContractId && !contractIdParam && (
                            <div style={{
                              fontSize: 11, color: 'rgba(255,255,255,0.66)', marginBottom: 8,
                              lineHeight: 1.4,
                            }}>
                              Create the contract record through full Contract Details intake before saving editor details.
                            </div>
                          )}
                          <button
                            disabled={detailsSaving}
                            onClick={() => {
                              if (!createdContractId && !contractIdParam) {
                                navigate('/contracts/new')
                                return
                              }
                              handleSaveContractDetails()
                            }}
                            style={{
                              width: '100%', height: 36,
                              background: '#243447',
                              color: 'white', border: 'none', borderRadius: 8,
                              fontSize: 13, fontWeight: 600,
                              cursor: detailsSaving ? 'wait' : 'pointer', marginTop: 4,
                              opacity: detailsSaving ? 0.7 : 1,
                            }}
                            onMouseEnter={(e) => { if (!detailsSaving) e.currentTarget.style.background = '#1a3460' }}
                            onMouseLeave={(e) => { e.currentTarget.style.background = '#243447' }}
                          >
                            {detailsSaving ? 'Saving...' : (!createdContractId && !contractIdParam) ? 'Open Contract Intake' : 'Save Details'}
                          </button>
                        </>
                      )
                    })() : activeTool === 'Contract Sections' ? (() => {
                      function scrollToSection(id: string) {
                        const editorEl = leftEditorRef.current
                        const target = editorEl?.querySelector<HTMLElement>(`#section-${id}`)
                        if (!editorEl || !target) {
                          setActiveSection(null)
                          return
                        }
                        scrollDraftSectionIntoView(target, editorEl)
                        setActiveSection(id)
                      }

                      function startRename(s: ContractSection) {
                        setEditingSection(s.id)
                        setEditingSectionName(s.name)
                      }

                      function commitRename() {
                        if (editingSection && editingSectionName.trim()) {
                          updateSections((prev) => prev.map((s) =>
                            s.id === editingSection ? { ...s, name: editingSectionName.trim() } : s
                          ))
                          // Update the heading in the editor
                          const el = document.getElementById(`section-${editingSection}`)
                          if (el) el.textContent = editingSectionName.trim()
                          queueAutosave()
                        }
                        setEditingSection(null)
                        setEditingSectionName('')
                      }

                      function cancelRename() {
                        setEditingSection(null)
                        setEditingSectionName('')
                      }

                      function commitAdd() {
                        const name = newSectionInput.trim()
                        if (!name) { setAddingSection(false); return }
                        const newNum = sections.length + 1
                        const newId = `s${Date.now()}`
                        const newSec: ContractSection = { id: newId, number: newNum, name }
                        updateSections((prev) => [...prev, newSec])
                        // Append heading to editor
                        if (leftEditorRef.current) {
                          leftEditorRef.current.innerHTML +=
                            `<h2 id="section-${newId}" style="margin:0 0 6px;font-size:16px;font-weight:600;color:#0F1F3D;">${name}</h2>` +
                            `<p style="margin:0 0 28px;color:#9CA3AF;font-size:14px;">[ Content for ${name} ]</p>`
                          setLeftEmpty(false)
                        }
                        queueAutosave()
                        setNewSectionInput('')
                        setAddingSection(false)
                      }

                      function reorder(fromId: string, toId: string) {
                        if (fromId === toId) return
                        updateSections((prev) => {
                          const arr = [...prev]
                          const fi = arr.findIndex((s) => s.id === fromId)
                          const ti = arr.findIndex((s) => s.id === toId)
                          if (fi < 0 || ti < 0) return prev
                          const [item] = arr.splice(fi, 1)
                          arr.splice(ti, 0, item)
                          return arr.map((s, i) => ({ ...s, number: i + 1 }))
                        })
                        queueAutosave()
                      }

                      function deleteSection(id: string) {
                        updateSections((prev) => prev.filter((s) => s.id !== id).map((s, i) => ({ ...s, number: i + 1 })))
                        if (activeSection === id) setActiveSection(null)
                        queueAutosave()
                      }

                      return (
                        <div style={{ margin: -16, minHeight: 'calc(100% + 32px)', display: 'flex', flexDirection: 'column' }}>
                          {/* Dark navy header */}
                          <div style={{
                            background: '#243447', padding: '14px 16px',
                            display: 'flex', alignItems: 'center', flexShrink: 0,
                          }}>
                            <span style={{
                              fontSize: 12, fontWeight: 600, color: 'white',
                              textTransform: 'uppercase', letterSpacing: '0.08em',
                              flex: 1,
                            }}>
                              Contract Sections
                            </span>
                            <button
                              onClick={() => { setAddingSection(true); setNewSectionInput('') }}
                              style={{
                                fontSize: 11, color: 'rgba(255,255,255,0.65)', background: 'transparent',
                                border: 'none', cursor: 'pointer', fontWeight: 500, padding: 0,
                              }}
                              onMouseEnter={(e) => (e.currentTarget.style.color = 'white')}
                              onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.65)')}
                            >
                              + Add Section
                            </button>
                          </div>

                          {/* Light body */}
                          <div style={{ flex: 1, background: '#F0F2F5', padding: 16 }}>
                            {/* Section count */}
                            <p style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 10 }}>
                              {sections.length} {sections.length === 1 ? 'section' : 'sections'}
                            </p>

                            {/* Sections list */}
                            {sections.length === 0 && (
                              <div style={{ fontSize: 12, color: '#6B7280', lineHeight: 1.5, background: 'white', borderRadius: 8, padding: 12, border: '1px solid #E5E7EB' }}>
                                No contract sections found. Add clear section headings in the Draft Editor.
                              </div>
                            )}
                            {sections.map((s) => {
                              const isActive = activeSection === s.id
                              const isEditing = editingSection === s.id
                              const isHovered = hoveredSection === s.id
                              const isDragTarget = sectDragOverId === s.id && sectDragId !== s.id
                              return (
                                <div
                                  key={s.id}
                                  draggable
                                  onDragStart={() => setSectDragId(s.id)}
                                  onDragOver={(e) => { e.preventDefault(); setSectDragOverId(s.id) }}
                                  onDrop={() => {
                                    if (sectDragId) reorder(sectDragId, s.id)
                                    setSectDragId(null); setSectDragOverId(null)
                                  }}
                                  onDragEnd={() => { setSectDragId(null); setSectDragOverId(null) }}
                                  onClick={() => { if (!isEditing) scrollToSection(s.id) }}
                                  onMouseEnter={() => setHoveredSection(s.id)}
                                  onMouseLeave={() => setHoveredSection(null)}
                                  style={{
                                    background: isActive ? '#FFFBF0' : 'white',
                                    borderRadius: 8,
                                    padding: '10px 14px',
                                    marginBottom: 6,
                                    border: isDragTarget ? '1px dashed #243447' : '1px solid #E5E7EB',
                                    borderLeft: isActive ? '3px solid #F5A623' : isDragTarget ? '3px solid #9CA3AF' : 'none',
                                    display: 'flex', alignItems: 'center', gap: 10,
                                    cursor: isEditing ? 'default' : 'pointer',
                                    transition: 'all 0.15s ease',
                                    opacity: sectDragId === s.id ? 0.4 : 1,
                                    boxShadow: isHovered
                                      ? '0 2px 8px rgba(0,0,0,0.1)'
                                      : '0 1px 3px rgba(0,0,0,0.06)',
                                    transform: isHovered && !isEditing ? 'translateY(-1px)' : 'none',
                                    ...(isHovered && !isEditing && { borderColor: '#243447' }),
                                  }}
                                >
                                  {/* Drag handle */}
                                  <span style={{ fontSize: 14, color: '#D1D5DB', cursor: 'grab', flexShrink: 0, lineHeight: 1 }}>
                                    ⠿
                                  </span>

                                  {/* Number */}
                                  <span style={{ fontSize: 11, color: '#9CA3AF', minWidth: 20, flexShrink: 0 }}>
                                    {s.number}
                                  </span>

                                  {/* Name / rename input */}
                                  {isEditing ? (
                                    <input
                                      autoFocus
                                      value={editingSectionName}
                                      onChange={(e) => setEditingSectionName(e.target.value)}
                                      onKeyDown={(e) => {
                                        if (e.key === 'Enter') { e.preventDefault(); commitRename() }
                                        if (e.key === 'Escape') cancelRename()
                                      }}
                                      onBlur={commitRename}
                                      style={{
                                        flex: 1, fontSize: 13, border: 'none', outline: 'none',
                                        background: 'transparent', color: '#243447',
                                        fontFamily: 'inherit',
                                      }}
                                      onClick={(e) => e.stopPropagation()}
                                    />
                                  ) : (
                                    <span style={{
                                      flex: 1, fontSize: 13,
                                      color: '#0F1F3D',
                                      fontWeight: 400,
                                    }}>
                                      {s.name}
                                    </span>
                                  )}

                                  {/* Action buttons — show on hover */}
                                  {isHovered && !isEditing && (
                                    <div style={{ display: 'flex', gap: 2, flexShrink: 0 }}>
                                      <button
                                        title="Rename"
                                        onClick={(e) => { e.stopPropagation(); startRename(s) }}
                                        style={{
                                          background: 'transparent', border: 'none',
                                          cursor: 'pointer', fontSize: 12, padding: '2px 3px',
                                          color: '#9CA3AF', lineHeight: 1,
                                        }}
                                        onMouseEnter={(e) => (e.currentTarget.style.color = '#374151')}
                                        onMouseLeave={(e) => (e.currentTarget.style.color = '#9CA3AF')}
                                      >
                                        ✏️
                                      </button>
                                      <button
                                        title="Delete"
                                        onClick={(e) => { e.stopPropagation(); deleteSection(s.id) }}
                                        style={{
                                          background: 'transparent', border: 'none',
                                          cursor: 'pointer', fontSize: 12, padding: '2px 3px',
                                          color: '#9CA3AF', lineHeight: 1,
                                        }}
                                        onMouseEnter={(e) => (e.currentTarget.style.color = '#DC2626')}
                                        onMouseLeave={(e) => (e.currentTarget.style.color = '#9CA3AF')}
                                      >
                                        🗑
                                      </button>
                                    </div>
                                  )}
                                </div>
                              )
                            })}

                            {/* Add section input row */}
                            {addingSection && (
                              <div style={{
                                background: 'white', borderRadius: 8, padding: '10px 14px',
                                marginBottom: 6,
                                border: '1px dashed #243447',
                                borderLeft: '3px solid #243447',
                                display: 'flex', alignItems: 'center', gap: 10,
                                boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
                              }}>
                                <span style={{ fontSize: 14, color: '#D1D5DB', flexShrink: 0 }}>⠿</span>
                                <span style={{ fontSize: 11, color: '#9CA3AF', minWidth: 20, flexShrink: 0 }}>
                                  {sections.length + 1}
                                </span>
                                <input
                                  autoFocus
                                  value={newSectionInput}
                                  onChange={(e) => setNewSectionInput(e.target.value)}
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter') { e.preventDefault(); commitAdd() }
                                    if (e.key === 'Escape') { setAddingSection(false); setNewSectionInput('') }
                                  }}
                                  onBlur={commitAdd}
                                  placeholder="Section name..."
                                  style={{
                                    flex: 1, fontSize: 13, border: 'none', outline: 'none',
                                    background: 'transparent', color: '#243447',
                                    fontFamily: 'inherit',
                                  }}
                                />
                              </div>
                            )}
                          </div>
                        </div>
                      )
                    })() : activeTool === 'Attachments' ? (() => {
                      function uploadTypeForAttachment(type: AttachFileType) {
                        if (type === 'docx' || type === 'xlsx') return 'document'
                        return type
                      }

                      async function loadVaultFiles() {
                        setVaultPickerLoading(true)
                        setVaultPickerError('')
                        try {
                          const { data } = await api.get<VaultSelectionFile[]>('/uploads/?canonical=true')
                          setVaultPickerFiles(data)
                        } catch {
                          setVaultPickerError('Could not load bonUP Vault files.')
                        } finally {
                          setVaultPickerLoading(false)
                        }
                      }

                      function openVaultPicker() {
                        if (!currentContractId) {
                          setAttachError('Save the contract before adding documents.')
                          return
                        }
                        setAttachError('')
                        setVaultPickerSearch('')
                        setVaultPickerError('')
                        setVaultPickerOpen(true)
                        void loadVaultFiles()
                      }

                      function closeVaultPicker() {
                        setVaultPickerOpen(false)
                        setVaultPickerSearch('')
                        setVaultPickerError('')
                      }

                      async function attachVaultFile(file: VaultSelectionFile) {
                        if (!currentContractId) {
                          setVaultPickerError('Save the contract before adding documents.')
                          return
                        }
                        if (vaultPickerAttachingId) return
                        setVaultPickerAttachingId(file.id)
                        setVaultPickerError('')
                        try {
                          const { data } = await api.post(`/contracts/${currentContractId}/documents/`, {
                            upload_id: file.id,
                            source: 'vault',
                            title: file.file_name,
                          })
                          setAttachFiles((prev) => [
                            {
                              id: `${Date.now()}-${Math.random()}`,
                              name: file.file_name,
                              sizeStr: formatBytes(file.file_size),
                              sizeBytes: file.file_size,
                              date: formatVaultDate(file.uploaded_at),
                              type: getFileType(file.file_name),
                              uploading: false,
                              progress: 100,
                              uploadId: data.upload_id,
                              documentId: data.id,
                              fileUrl: data.file_url,
                            },
                            ...prev,
                          ])
                          closeVaultPicker()
                        } catch {
                          setVaultPickerError('Could not attach this bonUP Vault file.')
                        } finally {
                          setVaultPickerAttachingId('')
                        }
                      }

                      async function processFiles(rawFiles: FileList | File[]) {
                        if (!currentContractId) {
                          setAttachError('Save the contract before adding documents.')
                          return
                        }

                        setAttachError('')
                        const arr = Array.from(rawFiles)
                        arr.forEach((raw) => {
                          const id = `${Date.now()}-${Math.random()}`
                          const type = getFileType(raw.name)
                          const newFile: AttachmentFile = {
                            id,
                            name: raw.name,
                            sizeStr: formatBytes(raw.size),
                            sizeBytes: raw.size,
                            date: new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
                            type,
                            uploading: true,
                            progress: 0,
                          }
                          setAttachFiles((prev) => [newFile, ...prev])

                          const form = new FormData()
                          form.append('file', raw)
                          form.append('file_type', uploadTypeForAttachment(type))
                          form.append('title', raw.name)

                          api.post(`/contracts/${currentContractId}/documents/`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
                            .then(({ data }) => {
                              setAttachFiles((prev) => prev.map((f) => f.id === id ? {
                                ...f,
                                uploading: false,
                                progress: 100,
                                uploadId: data.upload_id,
                                documentId: data.id,
                                fileUrl: data.file_url,
                              } : f))
                            })
                            .catch((error) => {
                              const code = error?.response?.data?.code
                              const message = code === 'storage_capacity_exceeded'
                                ? 'Storage capacity exceeded.'
                                : 'Upload failed.'
                              setAttachFiles((prev) => prev.map((f) => f.id === id ? { ...f, uploading: false, progress: 0, error: message } : f))
                              setAttachError(message)
                            })
                        })
                      }

                      function viewAttachment(file: AttachmentFile) {
                        if (!file.fileUrl) {
                          setAttachError('This attachment is not available for viewing.')
                          return
                        }
                        setAttachError('')
                        window.open(file.fileUrl, '_blank', 'noopener,noreferrer')
                      }

                      async function deleteAttachment(file: AttachmentFile) {
                        if (!currentContractId || !file.documentId || file.deleting) return
                        setAttachError('')
                        setAttachFiles((prev) => prev.map((f) => f.id === file.id ? { ...f, deleting: true, error: undefined } : f))
                        try {
                          await api.delete(`/contracts/${currentContractId}/documents/${file.documentId}/`)
                          setAttachFiles((prev) => prev.filter((f) => f.id !== file.id))
                        } catch {
                          setAttachFiles((prev) => prev.map((f) => f.id === file.id ? { ...f, deleting: false, error: 'Delete failed.' } : f))
                          setAttachError('Could not remove this attachment from the contract.')
                        }
                      }

                      const vaultSearch = vaultPickerSearch.trim().toLowerCase()
                      const visibleVaultFiles = vaultPickerFiles
                        .filter((file) => {
                          if (!vaultSearch) return true
                          return file.file_name.toLowerCase().includes(vaultSearch) || vaultFileTypeLabel(file.file_type).toLowerCase().includes(vaultSearch)
                        })
                        .sort((a, b) => new Date(b.uploaded_at).getTime() - new Date(a.uploaded_at).getTime())

                      const FILTER_TYPES: Record<AttachFilter, AttachFileType[]> = {
                        all: ['pdf', 'docx', 'xlsx', 'image', 'video', 'other'],
                        documents: ['pdf', 'docx', 'xlsx'],
                        images: ['image'],
                        videos: ['video'],
                        other: ['other'],
                      }
                      const filtered = attachFiles.filter((f) => FILTER_TYPES[attachFilter].includes(f.type))
                      const totalBytes = filtered.filter((f) => !f.uploading).reduce((s, f) => s + f.sizeBytes, 0)

                      const FILTER_TABS: { key: AttachFilter; label: string }[] = [
                        { key: 'all', label: 'All' },
                        { key: 'documents', label: 'Documents' },
                        { key: 'images', label: 'Images' },
                        { key: 'videos', label: 'Videos' },
                        { key: 'other', label: 'Other' },
                      ]

                      return (
                        <>
                          {/* Action buttons */}
                          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
                            <button
                              type="button"
                              onClick={() => attachInputRef.current?.click()}
                              style={{
                                height: 38,
                                borderRadius: 8,
                                border: '1px solid #243447',
                                background: '#243447',
                                color: 'white',
                                fontSize: 13,
                                fontWeight: 600,
                                padding: '0 14px',
                                cursor: 'pointer',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 8,
                              }}
                            >
                              <PlusIcon className="h-4 w-4" />
                              Upload from this device
                            </button>
                            <button
                              type="button"
                              onClick={openVaultPicker}
                              style={{
                                height: 38,
                                borderRadius: 8,
                                border: '1px solid #D1D5DB',
                                background: 'white',
                                color: '#243447',
                                fontSize: 13,
                                fontWeight: 600,
                                padding: '0 14px',
                                cursor: 'pointer',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 8,
                              }}
                            >
                              <RectangleStackIcon className="h-4 w-4" />
                              Choose from bonUP Vault
                            </button>
                          </div>
                          <input
                            ref={attachInputRef}
                            type="file"
                            multiple
                            style={{ display: 'none' }}
                            onChange={(e) => {
                              if (e.target.files) processFiles(e.target.files)
                              e.target.value = ''
                            }}
                          />

                          {/* Drop zone */}
                          {attachError && (
                            <p style={{ fontSize: 12, color: '#FCA5A5', margin: '0 0 10px', lineHeight: 1.4 }}>
                              {attachError}
                            </p>
                          )}
                          <div
                            onClick={() => attachInputRef.current?.click()}
                            onDragOver={(e) => { e.preventDefault(); setAttachDragOver(true) }}
                            onDragLeave={() => setAttachDragOver(false)}
                            onDrop={(e) => {
                              e.preventDefault()
                              setAttachDragOver(false)
                              processFiles(e.dataTransfer.files)
                            }}
                            style={{
                              background: attachDragOver ? 'rgba(255,255,255,0.1)' : 'rgba(255,255,255,0.05)',
                              borderRadius: 10,
                              border: `2px dashed ${attachDragOver ? 'rgba(255,255,255,0.4)' : 'rgba(255,255,255,0.15)'}`,
                              padding: '28px 16px',
                              textAlign: 'center',
                              cursor: 'pointer',
                              marginBottom: 16,
                              transition: 'border-color 0.2s, background 0.2s',
                            }}
                          >
                            <span style={{ fontSize: 28, display: 'block', marginBottom: 8 }}>📎</span>
                            <p style={{ fontSize: 13, fontWeight: 500, color: 'rgba(255,255,255,0.85)', margin: 0 }}>
                              Drop files here
                            </p>
                            <p style={{ fontSize: 12, color: '#9CA3AF', margin: '4px 0 0' }}>
                              or click to browse
                            </p>
                            <p style={{ fontSize: 11, color: '#9CA3AF', margin: '8px 0 0' }}>
                              PDF, DOCX, XLSX, JPG, PNG, MP4
                            </p>
                            <p style={{ fontSize: 11, color: '#9CA3AF', margin: '2px 0 0' }}>
                              Max 50MB per file
                            </p>
                          </div>

                          {/* Filter tabs */}
                          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 12 }}>
                            {FILTER_TABS.map(({ key, label }) => (
                              <button
                                key={key}
                                onClick={() => setAttachFilter(key)}
                                style={{
                                  fontSize: 11, padding: '4px 10px',
                                  borderRadius: 20, cursor: 'pointer',
                                  border: 'none',
                                  background: attachFilter === key ? 'rgba(255,255,255,0.12)' : 'transparent',
                                  color: attachFilter === key ? 'white' : 'rgba(255,255,255,0.55)',
                                }}
                              >
                                {label}
                              </button>
                            ))}
                          </div>

                          {/* File count + total */}
                          {filtered.length > 0 && (
                            <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.55)', marginBottom: 8 }}>
                              {filtered.length} {filtered.length === 1 ? 'file' : 'files'}
                              {totalBytes > 0 && ` · ${formatBytes(totalBytes)} total`}
                            </p>
                          )}

                          {/* Empty state */}
                          {filtered.length === 0 && (
                            <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.35)', textAlign: 'center', padding: 16 }}>
                              No files attached yet
                            </p>
                          )}

                          {/* File list */}
                          {filtered.map((file) => (
                            <div key={file.id} style={{
                              background: 'white', borderRadius: 8,
                              padding: '10px 12px', marginBottom: 8,
                              border: '1px solid #E5E7EB',
                            }}>
                              {file.uploading ? (
                                <>
                                  <p style={{ fontSize: 12, color: '#374151', margin: '0 0 6px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                    {file.name}
                                  </p>
                                  <div style={{ height: 4, background: '#E5E7EB', borderRadius: 2 }}>
                                    <div style={{
                                      height: '100%', borderRadius: 2,
                                      background: '#243447',
                                      width: '66%',
                                      transition: 'width 0.14s linear',
                                    }} />
                                  </div>
                                  <p style={{ fontSize: 11, color: '#6B7280', textAlign: 'right', margin: '4px 0 0' }}>
                                    Uploading
                                  </p>
                                </>
                              ) : (
                                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                  {/* Type icon */}
                                  <div style={{
                                    width: 36, height: 36, borderRadius: 6, flexShrink: 0,
                                    background: FILE_TYPE_META[file.type].bg,
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    fontSize: 18,
                                  }}>
                                    {FILE_TYPE_META[file.type].icon}
                                  </div>
                                  {/* Info */}
                                  <div style={{ flex: 1, minWidth: 0 }}>
                                    <p style={{
                                      fontSize: 12, fontWeight: 500, color: '#374151',
                                      margin: 0, maxWidth: 140,
                                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                                    }}>
                                      {file.name}
                                    </p>
                                    <p style={{ fontSize: 11, color: file.error ? '#DC2626' : '#9CA3AF', margin: '2px 0 0' }}>
                                      {file.error || `${file.sizeStr} · ${file.date}`}
                                    </p>
                                  </div>
                                  {/* Actions */}
                                  <div style={{ display: 'flex', gap: 2, flexShrink: 0 }}>
                                    <button
                                      type="button"
                                      title="View / Download"
                                      onClick={() => viewAttachment(file)}
                                      disabled={!file.fileUrl}
                                      style={{
                                        background: 'transparent', border: 'none',
                                        cursor: file.fileUrl ? 'pointer' : 'not-allowed', fontSize: 14, padding: 4,
                                        color: '#6B7280', opacity: file.fileUrl ? 1 : 0.45,
                                      }}
                                      onMouseEnter={(e) => { if (file.fileUrl) e.currentTarget.style.color = '#0F1F3D' }}
                                      onMouseLeave={(e) => (e.currentTarget.style.color = '#6B7280')}
                                    >
                                      👁
                                    </button>
                                    <button
                                      type="button"
                                      title="Delete"
                                      onClick={() => void deleteAttachment(file)}
                                      disabled={file.deleting || !file.documentId}
                                      style={{
                                        background: 'transparent', border: 'none',
                                        cursor: file.deleting || !file.documentId ? 'not-allowed' : 'pointer', fontSize: 14, padding: 4,
                                        color: '#6B7280', opacity: file.deleting || !file.documentId ? 0.45 : 1,
                                      }}
                                      onMouseEnter={(e) => { if (!file.deleting && file.documentId) e.currentTarget.style.color = '#DC2626' }}
                                      onMouseLeave={(e) => (e.currentTarget.style.color = '#6B7280')}
                                    >
                                      {file.deleting ? '...' : '🗑'}
                                    </button>
                                  </div>
                                </div>
                              )}
                            </div>
                          ))}

                          {vaultPickerOpen && (
                            <div style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(15, 23, 42, 0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
                              <div style={{ width: '100%', maxWidth: 760, maxHeight: '85vh', overflow: 'hidden', borderRadius: 12, background: 'white', boxShadow: '0 24px 60px rgba(15, 23, 42, 0.28)', display: 'flex', flexDirection: 'column' }}>
                                <div style={{ display: 'flex', alignItems: 'start', justifyContent: 'space-between', gap: 16, padding: '20px 20px 0' }}>
                                  <div>
                                    <p style={{ margin: 0, fontSize: 12, fontWeight: 700, letterSpacing: 0, textTransform: 'uppercase', color: '#D4900A' }}>bonUP Vault</p>
                                    <h3 style={{ margin: '4px 0 0', fontSize: 20, lineHeight: 1.2, color: '#243447' }}>Choose a file</h3>
                                    <p style={{ margin: '8px 0 0', fontSize: 13, color: '#6B7280' }}>Select an active Vault file to attach to this contract.</p>
                                  </div>
                                  <button
                                    type="button"
                                    onClick={closeVaultPicker}
                                    style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: '#6B7280', padding: 4 }}
                                    aria-label="Close Vault picker"
                                  >
                                    <XMarkIcon className="h-5 w-5" />
                                  </button>
                                </div>
                                <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 12, overflow: 'hidden' }}>
                                  <label style={{ position: 'relative', display: 'block' }}>
                                    <MagnifyingGlassIcon style={{ position: 'absolute', left: 12, top: '50%', width: 16, height: 16, transform: 'translateY(-50%)', color: '#9CA3AF', pointerEvents: 'none' }} />
                                    <input
                                      value={vaultPickerSearch}
                                      onChange={(e) => setVaultPickerSearch(e.target.value)}
                                      placeholder="Search bonUP Vault"
                                      style={{ width: '100%', height: 40, borderRadius: 8, border: '1px solid #D1D5DB', padding: '0 12px 0 36px', fontSize: 14, outline: 'none' }}
                                    />
                                  </label>
                                  {vaultPickerError && (
                                    <p style={{ margin: 0, fontSize: 12, color: '#DC2626' }}>{vaultPickerError}</p>
                                  )}
                                  <div style={{ border: '1px solid #E5E7EB', borderRadius: 10, overflow: 'hidden', maxHeight: 420, overflowY: 'auto', background: '#F9FAFB' }}>
                                    {vaultPickerLoading && (
                                      <div style={{ padding: 20, fontSize: 13, color: '#6B7280' }}>Loading bonUP Vault files...</div>
                                    )}
                                    {!vaultPickerLoading && visibleVaultFiles.length === 0 && (
                                      <div style={{ padding: 20, fontSize: 13, color: '#6B7280' }}>No active bonUP Vault files are available.</div>
                                    )}
                                    {!vaultPickerLoading && visibleVaultFiles.map((file) => (
                                      <button
                                        key={file.id}
                                        type="button"
                                        onClick={() => void attachVaultFile(file)}
                                        disabled={Boolean(vaultPickerAttachingId)}
                                        style={{
                                          width: '100%',
                                          textAlign: 'left',
                                          display: 'flex',
                                          alignItems: 'center',
                                          gap: 12,
                                          padding: '14px 16px',
                                          border: 'none',
                                          borderBottom: '1px solid #E5E7EB',
                                          background: 'white',
                                          cursor: vaultPickerAttachingId ? 'not-allowed' : 'pointer',
                                        }}
                                      >
                                        <div style={{ width: 42, height: 42, borderRadius: 8, background: '#F3F4F6', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#243447', fontSize: 11, fontWeight: 700, flexShrink: 0 }}>
                                          {vaultFileTypeLabel(file.file_type)}
                                        </div>
                                        <div style={{ flex: 1, minWidth: 0 }}>
                                          <p style={{ margin: 0, fontSize: 14, fontWeight: 600, color: '#243447', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{file.file_name}</p>
                                          <p style={{ margin: '3px 0 0', fontSize: 12, color: '#6B7280' }}>{formatBytes(file.file_size)} · {formatVaultDate(file.uploaded_at)}</p>
                                        </div>
                                        <div style={{ flexShrink: 0, fontSize: 12, fontWeight: 700, color: '#243447' }}>
                                          {vaultPickerAttachingId === file.id ? 'Attaching...' : 'Attach'}
                                        </div>
                                      </button>
                                    ))}
                                  </div>
                                  <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                                    <button
                                      type="button"
                                      onClick={closeVaultPicker}
                                      style={{ height: 38, borderRadius: 8, border: '1px solid #D1D5DB', background: 'white', color: '#243447', fontSize: 13, fontWeight: 600, padding: '0 14px', cursor: 'pointer' }}
                                    >
                                      Close
                                    </button>
                                  </div>
                                </div>
                              </div>
                            </div>
                          )}
                        </>
                      )
                    })() : activeTool === 'Contract Templates' ? (() => {
                      const TAB_CATS: Record<string, string[]> = {
                        'All':                [],
                        'Personal':           ['Personal', 'lending', 'barter'],
                        'Business':           ['Business', 'freelancer'],
                        'Creative Services':  ['creative_services'],
                        'Financial Services': ['financial_services'],
                        'Real Estate':        ['rental'],
                        'Employment':         ['education_tutoring'],
                        'Technology':         ['technology_services'],
                        'Legal':              [],
                        'Healthcare':         ['health_wellness'],
                        'Construction':       ['manual_labor'],
                      }
                      const TAB_LABELS = Object.keys(TAB_CATS)
                      const filtered = templates.filter((t) => {
                        const cats = TAB_CATS[templateCategoryFilter] ?? []
                        const matchCat = templateCategoryFilter === 'All' || cats.includes(t.category)
                        const q = templateSearch.trim().toLowerCase()
                        const matchSearch = !q || t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q)
                        return matchCat && matchSearch
                      })
                      return (
                        <>
                          {/* Search */}
                          <input
                            type="text"
                            value={templateSearch}
                            onChange={(e) => setTemplateSearch(e.target.value)}
                            placeholder="Search templates..."
                            style={{
                              width: '100%', height: 34, background: 'rgba(255,255,255,0.07)',
                              border: '1px solid rgba(255,255,255,0.12)', borderRadius: 8,
                              padding: '0 12px', fontSize: 12, outline: 'none',
                              boxSizing: 'border-box', marginBottom: 12, color: 'white',
                            }}
                          />

                          {/* Category tabs — horizontally scrollable */}
                          <div style={{
                            display: 'flex', gap: 4, marginBottom: 12,
                            overflowX: 'auto', flexShrink: 0,
                            msOverflowStyle: 'none',
                          }}>
                            {TAB_LABELS.map((tab) => (
                              <button
                                key={tab}
                                onClick={() => setTemplateCategoryFilter(tab)}
                                style={{
                                  fontSize: 11, padding: '4px 10px',
                                  borderRadius: 20, cursor: 'pointer', border: 'none',
                                  background: templateCategoryFilter === tab ? 'rgba(255,255,255,0.12)' : 'transparent',
                                  color: templateCategoryFilter === tab ? 'white' : 'rgba(255,255,255,0.55)',
                                  whiteSpace: 'nowrap', flexShrink: 0,
                                }}
                              >
                                {tab}
                              </button>
                            ))}
                          </div>

                          {/* Template list */}
                          {templatesLoading ? (
                            <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.35)', textAlign: 'center', padding: 24 }}>
                              Loading templates…
                            </div>
                          ) : filtered.length === 0 ? (
                            <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.35)', textAlign: 'center', padding: 24 }}>
                              No templates available
                            </div>
                          ) : (
                            filtered.map((tmpl) => {
                              const isPersonalCat = TAB_CATS['Personal'].includes(tmpl.category)
                              const badgeLabel = isPersonalCat ? 'Personal' : 'Business'
                              const badgeBg = isPersonalCat ? '#EFF6FF' : '#F0FDF4'
                              const badgeColor = isPersonalCat ? '#1E40AF' : '#166534'
                              return (
                                <div
                                  key={tmpl.id}
                                  style={{
                                    position: 'relative',
                                    background: 'white', borderRadius: 8,
                                    padding: '12px 14px 36px', marginBottom: 8,
                                    border: '1px solid #E5E7EB',
                                  }}
                                  onMouseEnter={(e) => {
                                    e.currentTarget.style.borderColor = '#243447'
                                    e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.06)'
                                  }}
                                  onMouseLeave={(e) => {
                                    e.currentTarget.style.borderColor = '#E5E7EB'
                                    e.currentTarget.style.boxShadow = 'none'
                                  }}
                                >
                                  {/* Category badge */}
                                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 4 }}>
                                    <span style={{
                                      background: badgeBg, color: badgeColor,
                                      fontSize: 10, padding: '2px 8px', borderRadius: 4,
                                    }}>
                                      {badgeLabel}
                                    </span>
                                  </div>
                                  {/* Name */}
                                  <div style={{ fontSize: 13, fontWeight: 600, color: '#0F1F3D', marginBottom: 4 }}>
                                    {tmpl.name}
                                  </div>
                                  {/* Description */}
                                  <div style={{ fontSize: 11, color: '#6B7280' }}>
                                    {tmpl.description}
                                  </div>
                                  {/* Action buttons */}
                                  <div style={{ position: 'absolute', bottom: 8, right: 10, display: 'flex', gap: 6 }}>
                                    <button
                                      onClick={() => setPreviewTemplate(tmpl)}
                                      style={{
                                        height: 22, padding: '0 8px', fontSize: 10, fontWeight: 500,
                                        borderRadius: 4, border: '1px solid #D1D5DB',
                                        background: 'transparent', color: '#6B7280', cursor: 'pointer',
                                      }}
                                      onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#243447'; e.currentTarget.style.color = '#0F1F3D' }}
                                      onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#D1D5DB'; e.currentTarget.style.color = '#6B7280' }}
                                    >
                                      Preview
                                    </button>
                                    <button
                                      onClick={() => loadTemplate(tmpl)}
                                      style={{
                                        height: 22, padding: '0 8px', fontSize: 10, fontWeight: 500,
                                        borderRadius: 4, border: '1px solid #243447',
                                        background: '#243447', color: 'white', cursor: 'pointer',
                                      }}
                                      onMouseEnter={(e) => (e.currentTarget.style.background = '#1a3460')}
                                      onMouseLeave={(e) => (e.currentTarget.style.background = '#243447')}
                                    >
                                      Use
                                    </button>
                                  </div>
                                </div>
                              )
                            })
                          )}
                        </>
                      )
                    })() : activeTool === 'Obligations' ? (() => {
                      function insertObligation(tmpl: ObligationTemplateItem) {
                        insertDraftSectionFromTemplate(tmpl.name, tmpl.content, 'ob')
                        setInsertedObligations((prev) => prev.includes(tmpl.id) ? prev : [...prev, tmpl.id])
                      }
                      return (
                        <div style={{ margin: -16, minHeight: 'calc(100% + 32px)', display: 'flex', flexDirection: 'column' }}>
                          <div style={{ background: '#243447', padding: '14px 16px' }}>
                            <span style={{ fontSize: 12, fontWeight: 600, color: 'white', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                              Obligation Templates
                            </span>
                            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)', marginTop: 4 }}>
                              Select a template to insert at cursor
                            </div>
                          </div>
                          <div style={{ flex: 1, background: '#F0F2F5', padding: 12 }}>
                            {obligationTemplatesLoading ? (
                              <div style={{ fontSize: 12, color: '#6B7280', textAlign: 'center', marginTop: 30 }}>Loading…</div>
                            ) : obligationTemplates.length === 0 ? (
                              <div style={{ fontSize: 12, color: '#6B7280', textAlign: 'center', marginTop: 30 }}>No obligation templates found.</div>
                            ) : (
                              obligationTemplates.map((tmpl) => {
                                const inserted = insertedObligations.includes(tmpl.id)
                                return (
                                  <div
                                    key={tmpl.id}
                                    style={{
                                      position: 'relative',
                                      background: inserted ? '#FFFBF0' : 'white',
                                      borderLeft: inserted ? '3px solid #F5A623' : 'none',
                                      borderRadius: 6,
                                      padding: '10px 12px 36px',
                                      marginBottom: 8,
                                      boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
                                      transition: 'box-shadow 0.15s, transform 0.15s',
                                    }}
                                    onMouseEnter={(e) => { e.currentTarget.style.boxShadow = '0 3px 8px rgba(0,0,0,0.12)'; e.currentTarget.style.transform = 'translateY(-1px)' }}
                                    onMouseLeave={(e) => { e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.08)'; e.currentTarget.style.transform = 'none' }}
                                  >
                                    <div style={{ fontSize: 12, fontWeight: 600, color: '#111827', marginBottom: 3 }}>{tmpl.name}</div>
                                    <div style={{ fontSize: 11, color: '#6B7280', marginBottom: 4 }}>{tmpl.category}</div>
                                    {tmpl.description ? (
                                      <div style={{ fontSize: 11, color: '#9CA3AF', lineHeight: 1.4 }}>{tmpl.description}</div>
                                    ) : null}
                                    {inserted && (
                                      <div style={{ fontSize: 10, color: '#F5A623', fontWeight: 600, marginTop: 4 }}>✓ Inserted</div>
                                    )}
                                    {/* Action buttons */}
                                    <div style={{ position: 'absolute', bottom: 8, right: 10, display: 'flex', gap: 6 }}>
                                      <button
                                        onClick={(e) => { e.stopPropagation(); setPreviewObligationTemplate(tmpl) }}
                                        style={{
                                          height: 22, padding: '0 8px', fontSize: 10, fontWeight: 500,
                                          borderRadius: 4, border: '1px solid #D1D5DB',
                                          background: 'transparent', color: '#6B7280', cursor: 'pointer',
                                        }}
                                        onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#243447'; e.currentTarget.style.color = '#0F1F3D' }}
                                        onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#D1D5DB'; e.currentTarget.style.color = '#6B7280' }}
                                      >
                                        Preview
                                      </button>
                                      <button
                                        onClick={(e) => { e.stopPropagation(); insertObligation(tmpl) }}
                                        style={{
                                          height: 22, padding: '0 8px', fontSize: 10, fontWeight: 500,
                                          borderRadius: 4, border: '1px solid #243447',
                                          background: '#243447', color: 'white', cursor: 'pointer',
                                        }}
                                        onMouseEnter={(e) => (e.currentTarget.style.background = '#1a3460')}
                                        onMouseLeave={(e) => (e.currentTarget.style.background = '#243447')}
                                      >
                                        Use
                                      </button>
                                    </div>
                                  </div>
                                )
                              })
                            )}
                          </div>
                        </div>
                      )
                    })() : activeTool === 'Payments' ? (() => {
                      const SCHEDULE_LABELS: Record<string, string> = {
                        one_time: 'One-Time',
                        installment: 'Installment',
                        recurring: 'Recurring',
                        milestone: 'Milestone',
                      }
                      function insertPayment(tmpl: PaymentTemplateItem) {
                        const ref = activeEditor === 'left' ? leftEditorRef : rightEditorRef
                        if (ref.current) {
                          ref.current.focus()
                          document.execCommand('insertText', false, '\n\n' + tmpl.content)
                          if (activeEditor === 'left') syncDraftSectionsAfterMutation()
                          else queueAutosave()
                        }
                        setInsertedPayments((prev) => prev.includes(tmpl.id) ? prev : [...prev, tmpl.id])
                      }
                      return (
                        <div style={{ margin: -16, minHeight: 'calc(100% + 32px)', display: 'flex', flexDirection: 'column' }}>
                          <div style={{ background: '#243447', padding: '14px 16px' }}>
                            <span style={{ fontSize: 12, fontWeight: 600, color: 'white', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                              Payment Templates
                            </span>
                            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)', marginTop: 4 }}>
                              Select a template to insert at cursor
                            </div>
                          </div>
                          <div style={{ flex: 1, background: '#F0F2F5', padding: 12 }}>
                            {paymentTemplatesLoading ? (
                              <div style={{ fontSize: 12, color: '#6B7280', textAlign: 'center', marginTop: 30 }}>Loading…</div>
                            ) : paymentTemplates.length === 0 ? (
                              <div style={{ fontSize: 12, color: '#6B7280', textAlign: 'center', marginTop: 30 }}>No payment templates found.</div>
                            ) : (
                              paymentTemplates.map((tmpl) => {
                                const inserted = insertedPayments.includes(tmpl.id)
                                return (
                                  <div
                                    key={tmpl.id}
                                    style={{
                                      position: 'relative',
                                      background: inserted ? '#FFFBF0' : 'white',
                                      borderLeft: inserted ? '3px solid #F5A623' : 'none',
                                      borderRadius: 6,
                                      padding: '10px 12px 36px',
                                      marginBottom: 8,
                                      boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
                                      transition: 'box-shadow 0.15s, transform 0.15s',
                                    }}
                                    onMouseEnter={(e) => { e.currentTarget.style.boxShadow = '0 3px 8px rgba(0,0,0,0.12)'; e.currentTarget.style.transform = 'translateY(-1px)' }}
                                    onMouseLeave={(e) => { e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.08)'; e.currentTarget.style.transform = 'none' }}
                                  >
                                    <div style={{ fontSize: 12, fontWeight: 600, color: '#111827', marginBottom: 3 }}>{tmpl.name}</div>
                                    <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 4 }}>
                                      <span style={{ fontSize: 10, color: '#6B7280' }}>{tmpl.category}</span>
                                      <span style={{
                                        fontSize: 10, padding: '1px 6px', borderRadius: 10,
                                        background: '#E5E7EB', color: '#374151', fontWeight: 500,
                                      }}>{SCHEDULE_LABELS[tmpl.schedule_type] ?? tmpl.schedule_type}</span>
                                    </div>
                                    {tmpl.description ? (
                                      <div style={{ fontSize: 11, color: '#9CA3AF', lineHeight: 1.4 }}>{tmpl.description}</div>
                                    ) : null}
                                    {inserted && (
                                      <div style={{ fontSize: 10, color: '#F5A623', fontWeight: 600, marginTop: 4 }}>✓ Inserted</div>
                                    )}
                                    {/* Action buttons */}
                                    <div style={{ position: 'absolute', bottom: 8, right: 10, display: 'flex', gap: 6 }}>
                                      <button
                                        onClick={(e) => { e.stopPropagation(); setPreviewPaymentTemplate(tmpl) }}
                                        style={{
                                          height: 22, padding: '0 8px', fontSize: 10, fontWeight: 500,
                                          borderRadius: 4, border: '1px solid #D1D5DB',
                                          background: 'transparent', color: '#6B7280', cursor: 'pointer',
                                        }}
                                        onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#243447'; e.currentTarget.style.color = '#0F1F3D' }}
                                        onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#D1D5DB'; e.currentTarget.style.color = '#6B7280' }}
                                      >
                                        Preview
                                      </button>
                                      <button
                                        onClick={(e) => { e.stopPropagation(); insertPayment(tmpl) }}
                                        style={{
                                          height: 22, padding: '0 8px', fontSize: 10, fontWeight: 500,
                                          borderRadius: 4, border: '1px solid #243447',
                                          background: '#243447', color: 'white', cursor: 'pointer',
                                        }}
                                        onMouseEnter={(e) => (e.currentTarget.style.background = '#1a3460')}
                                        onMouseLeave={(e) => (e.currentTarget.style.background = '#243447')}
                                      >
                                        Use
                                      </button>
                                    </div>
                                  </div>
                                )
                              })
                            )}
                          </div>
                        </div>
                      )
                    })() : (
                      <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.55)', textAlign: 'center', marginTop: 40 }}>
                        {activeTool} coming soon
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>

          {/* SECTIONS STRIP */}
          <div style={{
            width: sectionsStripVisible ? 140 : 0,
            flexShrink: 0,
            overflow: 'hidden',
            transition: 'width 0.2s ease',
            position: 'relative',
          }}>
            <div style={{
              width: 140,
              height: '100%',
              background: 'transparent',
              borderRight: '1px solid #E5E7EB',
              padding: '8px 0',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
            }}>
              {/* Toggle button */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', paddingRight: 6, marginBottom: 4 }}>
                <button
                  onClick={() => setSectionsStripVisible(false)}
                  title="Hide sections"
                  style={{
                    background: 'transparent', border: 'none', cursor: 'pointer',
                    fontSize: 11, color: 'rgba(0,0,0,0.25)', padding: '0 4px', lineHeight: 1,
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = '#0F1F3D')}
                  onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(0,0,0,0.25)')}
                >
                  ‹
                </button>
              </div>
              {/* Header */}
              <div style={{
                fontSize: 9, fontWeight: 600, color: 'rgba(0,0,0,0.25)',
                letterSpacing: '0.12em', textTransform: 'uppercase',
                padding: '0 10px 8px',
                borderBottom: '1px solid #F0F0F0',
                marginBottom: 6,
              }}>
                Sections
              </div>
              {/* Items */}
              {sections.map((s) => {
                const isActive = activeSection === s.id
                return (
                  <div
                    key={s.id}
                    onClick={() => {
                      const editorEl = leftEditorRef.current
                      const target = editorEl?.querySelector<HTMLElement>(`#section-${s.id}`)
                      if (!editorEl || !target) {
                        setActiveSection(null)
                        return
                      }
                      scrollDraftSectionIntoView(target, editorEl)
                      setActiveSection(s.id)
                    }}
                    style={{
                      padding: '6px 10px',
                      fontSize: 11,
                      color: isActive ? '#243447' : '#6B7280',
                      fontWeight: isActive ? 500 : 400,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                    onMouseEnter={(e) => {
                      if (!isActive) {
                        e.currentTarget.style.color = '#0F1F3D'
                        const dot = e.currentTarget.querySelector<HTMLElement>('.sec-dot')
                        if (dot) dot.style.background = '#F5A623'
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isActive) {
                        e.currentTarget.style.color = '#6B7280'
                        const dot = e.currentTarget.querySelector<HTMLElement>('.sec-dot')
                        if (dot) dot.style.background = '#D1D5DB'
                      }
                    }}
                  >
                    <span
                      className="sec-dot"
                      style={{
                        width: 4, height: 4, borderRadius: '50%',
                        background: isActive ? '#F5A623' : '#D1D5DB',
                        flexShrink: 0,
                        display: 'inline-block',
                      }}
                    />
                    {s.name}
                  </div>
                )
              })}
            </div>
          </div>

          {/* SECTIONS STRIP SHOW BUTTON — visible only when strip is hidden */}
          {!sectionsStripVisible && (
            <button
              onClick={() => setSectionsStripVisible(true)}
              title="Show sections"
              style={{
                position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)',
                zIndex: 10,
                width: 16, height: 40,
                background: '#F0F2F5',
                border: '1px solid #E5E7EB',
                borderLeft: 'none',
                borderRadius: '0 4px 4px 0',
                cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 10, color: 'rgba(0,0,0,0.35)',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = '#0F1F3D')}
              onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(0,0,0,0.35)')}
            >
              ›
            </button>
          )}

          {/* CENTER AREA */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0, position: 'relative' }}>

            {/* EDITOR HEADER ROW — always visible, never inside a display:none container */}
            <div style={{
              display: 'flex', height: 36, flexShrink: 0,
              background: '#ffffff',
              borderBottom: '1px solid #E5E7EB',
            }}>
              {/* Draft Editor header — hidden when right-focused */}
              {focusMode !== 'right' && (
                <div style={{
                  width: focusMode === 'none' ? `${splitPercent}%` : '100%',
                  flexShrink: 0, padding: '0 12px',
                  display: 'flex', alignItems: 'center', gap: 8,
                  overflow: 'hidden', minWidth: 0,
                  borderRight: focusMode === 'none' ? '1px solid #E5E7EB' : 'none',
                  transition: 'width 0.3s ease',
                }}>
                  <span style={{ fontSize: 12, color: '#6B7280', fontWeight: 500 }}>Draft Editor</span>
                  {activeEditor === 'left' && (
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#2DD4BF' }} />
                  )}
                  <button
                    onClick={() => focusMode === 'left' ? exitFocus() : enterFocus('left')}
                    title={focusMode === 'left' ? 'Exit focus mode' : 'Focus mode'}
                    style={{
                      background: 'transparent', border: 'none',
                      color: '#9CA3AF', fontSize: 14, cursor: 'pointer', padding: 4,
                      marginLeft: 'auto',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = '#374151')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = '#9CA3AF')}
                  >
                    {focusMode === 'left' ? 'Exit Focus' : '⛶'}
                  </button>
                </div>
              )}
              {/* Final Editor header — hidden when left-focused */}
              {focusMode !== 'left' && (
                <div style={{
                  flex: 1, padding: '0 12px',
                  display: 'flex', alignItems: 'center', gap: 8,
                  overflow: 'hidden', minWidth: 0,
                }}>
                  <span style={{ fontSize: 12, color: '#6B7280', fontWeight: 500 }}>Final Editor</span>
                  {activeEditor === 'right' && (
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#2DD4BF' }} />
                  )}
                  <button
                    onClick={() => focusMode === 'right' ? exitFocus() : enterFocus('right')}
                    title={focusMode === 'right' ? 'Exit focus mode' : 'Focus mode'}
                    style={{
                      background: 'transparent', border: 'none',
                      color: '#9CA3AF', fontSize: 14, cursor: 'pointer', padding: 4,
                      marginLeft: 'auto',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = '#374151')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = '#9CA3AF')}
                  >
                    {focusMode === 'right' ? 'Exit Focus' : '⛶'}
                  </button>
                </div>
              )}
            </div>

            {/* Editors + AI panel wrapper */}
            <div style={{ flex: 1, position: 'relative', overflow: 'hidden', minHeight: 0 }}>

            {/* Editors row — shrinks to make room when AI panel is open */}
            <div
              ref={editorsRowRef}
              style={{
                height: aiPanelOpen ? `calc(100% - ${aiPanelHeight}px)` : '100%',
                transition: 'height 0.35s ease',
                display: 'flex', flexDirection: 'row', overflow: 'hidden',
                minHeight: 200,
              }}
            >

              {/* DRAFT EDITOR */}
              <div style={focusMode === 'right' ? { display: 'none' } : {
                width: focusMode === 'left' ? '100%' : `${splitPercent}%`,
                flexShrink: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0,
                transition: 'width 0.3s ease',
              }}>
                {focusMode === 'left' ? (
                  <div style={{ flex: 1, overflowY: 'auto', background: '#F0F2F5', padding: 24 }}>
                    <div
                      ref={leftEditorRef}
                      contentEditable={draftEditingAllowed}
                      suppressContentEditableWarning
                      onFocus={handleDraftEditorFocus}
                      onInput={handleDraftEditorInput}
                      onPaste={handleDraftEditorPaste}
                      style={{
                        maxWidth: 760, margin: '0 auto', display: 'block',
                        background: 'white',
                        boxShadow: '0 0 0 1px rgba(0,0,0,0.06), 0 4px 24px rgba(0,0,0,0.08)',
                        borderRadius: 4, padding: '48px 64px',
                        minHeight: 'calc(100vh - 300px)',
                        fontSize: 16, color: '#374151', lineHeight: 1.8,
                        outline: 'none',
                      }}
                    />
                  </div>
                ) : (
                  <div style={{ flex: 1, position: 'relative', overflow: 'hidden', minHeight: 0 }}>
                    <div
                      ref={leftEditorRef}
                      contentEditable={draftEditingAllowed}
                      suppressContentEditableWarning
                      onFocus={handleDraftEditorFocus}
                      onInput={handleDraftEditorInput}
                      onPaste={handleDraftEditorPaste}
                      style={{
                        position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
                        background: 'white', borderRight: '1px solid #E5E7EB',
                        padding: '24px 32px', fontSize: 14, color: '#374151',
                        lineHeight: 1.6, outline: 'none', overflowY: 'auto',
                      }}
                    />
                  </div>
                )}
              </div>

              {/* CENTER DIVIDER — draggable resizer */}
              <div
                onMouseDown={onDividerMouseDown}
                onMouseEnter={(e) => { if (!isDragging) (e.currentTarget.style.background = '#B8BFC8') }}
                onMouseLeave={(e) => { if (!isDragging) (e.currentTarget.style.background = '#C8CDD4') }}
                style={{
                  width: 6, flexShrink: 0,
                  background: isDragging ? '#B8BFC8' : '#C8CDD4',
                  cursor: 'col-resize',
                  position: 'relative',
                  display: focusMode !== 'none' ? 'none' : 'flex',
                  alignItems: 'center', justifyContent: 'center',
                }}
              >
                <div style={{
                  width: 3, height: 32,
                  background: '#9CA3AF',
                  borderRadius: 3,
                  pointerEvents: 'none',
                }} />
              </div>

              {/* FINAL EDITOR */}
              <div style={focusMode === 'left' ? { display: 'none' } : {
                flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0,
              }}>
                {focusMode === 'right' ? (
                  <div style={{ flex: 1, overflowY: 'auto', background: '#F0F2F5', padding: 24 }}>
                    <div
                      ref={rightEditorRef}
                      contentEditable={draftEditingAllowed}
                      suppressContentEditableWarning
                      onFocus={() => setActiveEditor('right')}
                      onInput={(e) => {
                        setRightEmpty((e.currentTarget.textContent ?? '') === '')
                        queueAutosave()
                      }}
                      style={{
                        maxWidth: 760, margin: '0 auto', display: 'block',
                        background: 'white',
                        boxShadow: '0 0 0 1px rgba(0,0,0,0.06), 0 4px 24px rgba(0,0,0,0.08)',
                        borderRadius: 4, padding: '48px 64px',
                        minHeight: 'calc(100vh - 300px)',
                        fontSize: 16, color: '#374151', lineHeight: 1.8,
                        outline: 'none',
                      }}
                    />
                  </div>
                ) : (
                  <div style={{ flex: 1, position: 'relative', overflow: 'hidden', minHeight: 0 }}>
                    <div
                      ref={rightEditorRef}
                      contentEditable={draftEditingAllowed}
                      suppressContentEditableWarning
                      onFocus={() => setActiveEditor('right')}
                      onInput={(e) => {
                        setRightEmpty((e.currentTarget.textContent ?? '') === '')
                        queueAutosave()
                      }}
                      style={{
                        position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
                        background: 'white', borderLeft: '1px solid #E5E7EB',
                        padding: '24px 32px', fontSize: 14, color: '#374151',
                        lineHeight: 1.6, outline: 'none', overflowY: 'auto',
                      }}
                    />
                  </div>
                )}
              </div>

            </div>

              {/* AI PANEL — slides up from bottom of center area */}
              <div style={{
                position: 'absolute', bottom: 0, left: 0, right: 0,
                height: aiPanelHeight,
                background: '#ffffff',
                borderTop: '2px solid #E5E7EB',
                boxShadow: '0 -4px 20px rgba(0,0,0,0.08)',
                borderRadius: '12px 12px 0 0',
                transform: aiPanelOpen ? 'translateY(0)' : 'translateY(100%)',
                transition: 'transform 0.35s ease',
                display: 'flex', flexDirection: 'column',
                zIndex: 10,
              }}>
                {/* Drag handle */}
                <div
                  onMouseDown={onAiHandleMouseDown}
                  style={{
                    height: 6, width: '100%',
                    cursor: 'row-resize',
                    background: '#F3F4F6',
                    borderRadius: '12px 12px 0 0',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    flexShrink: 0,
                  }}
                >
                  <div style={{ width: 32, height: 3, background: '#D1D5DB', borderRadius: 3, pointerEvents: 'none' }} />
                </div>

                {/* Header */}
                <div style={{
                  padding: '12px 16px',
                  borderBottom: '1px solid #F3F4F6',
                  display: 'flex', alignItems: 'center', flexShrink: 0,
                }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: '#0F1F3D', flex: 1 }}>
                    AI Assistant
                  </span>
                  <button
                    onClick={() => setAiPanelOpen(false)}
                    style={{
                      background: 'transparent', border: 'none',
                      color: '#9CA3AF', fontSize: 16, cursor: 'pointer',
                      lineHeight: 1, padding: '0 2px',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = '#374151')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = '#9CA3AF')}
                  >
                    ✕
                  </button>
                </div>

                {/* Chat area */}
                <div style={{
                  flex: 1, overflowY: 'auto',
                  padding: '12px 16px',
                  display: 'flex', flexDirection: 'column', gap: 8,
                }}>
                  {aiPanelChat.map((msg, i) => (
                    <div key={i} style={{
                      display: 'flex',
                      justifyContent: msg.role === 'ai' ? 'flex-start' : 'flex-end',
                    }}>
                      <span style={{
                        background: msg.role === 'ai' ? '#EFF6FF' : '#243447',
                        color: msg.role === 'ai' ? '#1E40AF' : '#fff',
                        borderRadius: 8, padding: '8px 12px',
                        fontSize: 13, maxWidth: '80%', lineHeight: 1.5,
                      }}>
                        {msg.text}
                      </span>
                    </div>
                  ))}
                </div>

                {/* Input row */}
                <div style={{
                  padding: '12px 16px',
                  borderTop: '1px solid #F3F4F6',
                  display: 'flex', gap: 8, flexShrink: 0,
                }}>
                  <input
                    type="text"
                    value={aiPanelMessage}
                    onChange={(e) => setAiPanelMessage(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        const t = aiPanelMessage.trim()
                        if (!t) return
                        setAiPanelChat((prev) => [...prev, { role: 'user', text: t }])
                        setAiPanelMessage('')
                        setTimeout(() => setAiPanelChat((prev) => [...prev, { role: 'ai', text: 'AI assistant coming soon. Stay tuned!' }]), 600)
                      }
                    }}
                    placeholder="Ask AI anything about this contract..."
                    style={{
                      flex: 1, border: '1px solid #E5E7EB',
                      borderRadius: 8, padding: '8px 12px',
                      fontSize: 13, outline: 'none',
                    }}
                  />
                  <button
                    onClick={() => {
                      const t = aiPanelMessage.trim()
                      if (!t) return
                      setAiPanelChat((prev) => [...prev, { role: 'user', text: t }])
                      setAiPanelMessage('')
                      setTimeout(() => setAiPanelChat((prev) => [...prev, { role: 'ai', text: 'AI assistant coming soon. Stay tuned!' }]), 600)
                    }}
                    style={{
                      background: '#000000', color: 'white',
                      border: 'none', borderRadius: 8,
                      padding: '8px 16px', fontSize: 12,
                      fontWeight: 500, cursor: 'pointer', flexShrink: 0,
                    }}
                  >
                    Send
                  </button>
                </div>
              </div>

            </div>{/* end editors+panel wrapper */}
          </div>

          {/* RIGHT DRAWER TOGGLE */}
          <button
            onClick={() => setRightDrawerOpen((v) => !v)}
            style={{ ...TOGGLE_BTN, borderRadius: '4px 0 0 4px' }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#3D5068'
              e.currentTarget.style.color = 'white'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#2E4156'
              e.currentTarget.style.color = 'rgba(255,255,255,0.5)'
            }}
          >
            {rightDrawerOpen ? '›' : '‹'}
          </button>

          {/* RIGHT DRAWER */}
          <div style={{
            width: rightDrawerOpen ? 280 : 0,
            flexShrink: 0,
            transition: 'width 0.3s ease',
            overflow: 'hidden',
            background: '#F8FAFC',
            borderLeft: '1px solid #E5E7EB',
          }}>
            <div style={{ width: 280, height: '100%', display: 'flex', flexDirection: 'column' }}>

              {/* Activity Feed */}
              <div style={{
                height: '50%',
                overflow: 'hidden',
                flexShrink: 0,
                borderBottom: '1px solid #E5E7EB',
                display: 'flex', flexDirection: 'column',
                padding: 16,
              }}>
                <p style={{
                  fontSize: 12, fontWeight: 600, color: '#374151',
                  textTransform: 'uppercase', letterSpacing: '0.08em',
                  margin: '0 0 8px 0', flexShrink: 0,
                }}>
                  Activity
                </p>
                <div style={{ overflowY: 'auto', flex: 1 }}>
                  {ACTIVITY.map((item, i) => (
                    <div key={i} style={{
                      display: 'flex', gap: 8, padding: '8px 0',
                      borderBottom: '1px solid #F3F4F6',
                      fontSize: 12, color: '#6B7280',
                    }}>
                      <span>{item.icon}</span>
                      <span style={{ flex: 1 }}>{item.text}</span>
                      <span style={{ color: '#9CA3AF', flexShrink: 0 }}>{item.time}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Party Info */}
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 0 }}>
                <div style={{
                  padding: '16px 16px 8px',
                  borderBottom: '1px solid #E5E7EB',
                  flexShrink: 0,
                }}>
                  <p style={{
                    fontSize: 12, fontWeight: 600, color: '#374151',
                    textTransform: 'uppercase', letterSpacing: '0.08em',
                    margin: 0,
                  }}>
                    Party Info
                  </p>
                </div>

                <div style={{ padding: 16 }}>
                  {/* Avatar */}
                  <div style={{
                    width: 44, height: 44, borderRadius: '50%',
                    background: '#E5E7EB',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 16, color: '#6B7280',
                    marginBottom: 10,
                  }}>
                    ?
                  </div>

                  <p style={{ fontSize: 12, color: '#9CA3AF', margin: '0 0 16px 0' }}>
                    No party selected yet
                  </p>

                  <button
                    style={{
                      width: '100%', height: 32,
                      background: 'transparent',
                      border: '1px solid #D1D5DB',
                      borderRadius: 8, fontSize: 12,
                      color: '#374151', cursor: 'pointer',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = '#F9FAFB')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  >
                    + Add Party
                  </button>
                </div>
              </div>

            </div>
          </div>
        </div>
      </div>

      {createdContractId && (
        <button
          type="button"
          onClick={handlePrepareContract}
          disabled={isPreparingContract}
          style={{
            position: 'fixed', right: 24, bottom: 48, zIndex: 220,
            height: 40, padding: '0 18px', borderRadius: 9,
            border: '1px solid rgba(15,31,61,0.18)',
            background: isPreparingContract ? '#94A3B8' : '#243447',
            color: 'white', fontSize: 13, fontWeight: 700,
            cursor: isPreparingContract ? 'default' : 'pointer',
            boxShadow: '0 10px 24px rgba(15,31,61,0.22)',
          }}
        >
          {isPreparingContract ? 'Preparing...' : 'Prepare Contract'}
        </button>
      )}


      {/* ── STATUS BAR ── */}
      <div style={{
        position: 'fixed', bottom: 0, left: 0, right: 0, height: 32,
        background: '#243447', zIndex: 100,
        display: 'flex', alignItems: 'center', padding: '0 16px', gap: 16,
      }}>
        <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)', flex: 1 }}>
          {hoverDescription || 'Hover over any element for a description'}
        </span>
        <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', flexShrink: 0 }}>
          Contact · Advertising · Disclaimer · Help
        </span>
        <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', flexShrink: 0 }}>
          bonUP © 2026
        </span>
      </div>

      {/* Template preview modal */}
      {previewTemplate && (
        <div
          onClick={() => setPreviewTemplate(null)}
          style={{
            position: 'fixed', inset: 0, zIndex: 600,
            background: 'rgba(0,0,0,0.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 24,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: 600, maxHeight: '80vh',
              background: 'white', borderRadius: 12,
              padding: 28, boxShadow: '0 8px 40px rgba(0,0,0,0.15)',
              display: 'flex', flexDirection: 'column',
              overflow: 'hidden',
            }}
          >
            {/* Modal header */}
            <div style={{ display: 'flex', alignItems: 'flex-start', marginBottom: 16, flexShrink: 0 }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 16, fontWeight: 700, color: '#0F1F3D', marginBottom: 4 }}>
                  {previewTemplate.name}
                </div>
                <div style={{ fontSize: 12, color: '#6B7280' }}>
                  {previewTemplate.description}
                </div>
              </div>
              <button
                onClick={() => setPreviewTemplate(null)}
                style={{
                  background: 'transparent', border: 'none',
                  color: '#9CA3AF', fontSize: 20, cursor: 'pointer',
                  padding: '0 0 0 12px', lineHeight: 1, flexShrink: 0,
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = '#374151')}
                onMouseLeave={(e) => (e.currentTarget.style.color = '#9CA3AF')}
              >
                ✕
              </button>
            </div>

            {/* Contract text */}
            <div style={{
              flex: 1, overflowY: 'auto',
              borderTop: '1px solid #E5E7EB',
              borderBottom: '1px solid #E5E7EB',
              padding: '16px 0',
              marginBottom: 16,
            }}>
              <pre style={{
                fontFamily: 'Georgia, serif',
                fontSize: 13, lineHeight: 1.7,
                color: '#374151', whiteSpace: 'pre-wrap',
                wordBreak: 'break-word', margin: 0,
              }}>
                {previewTemplate.content}
              </pre>
            </div>

            {/* Use button */}
            <button
              onClick={() => loadTemplate(previewTemplate)}
              style={{
                width: '100%', height: 40,
                background: '#243447', color: 'white',
                border: 'none', borderRadius: 8,
                fontSize: 14, fontWeight: 600, cursor: 'pointer',
                flexShrink: 0,
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = '#1a3460')}
              onMouseLeave={(e) => (e.currentTarget.style.background = '#243447')}
            >
              Use This Template
            </button>
          </div>
        </div>
      )}

      {/* Obligation template preview modal */}
      {previewObligationTemplate && (
        <div
          onClick={() => setPreviewObligationTemplate(null)}
          style={{
            position: 'fixed', inset: 0, zIndex: 600,
            background: 'rgba(0,0,0,0.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 24,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: 600, maxHeight: '80vh',
              background: 'white', borderRadius: 12,
              padding: 28, boxShadow: '0 8px 40px rgba(0,0,0,0.15)',
              display: 'flex', flexDirection: 'column',
              overflow: 'hidden',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', marginBottom: 16, flexShrink: 0 }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 16, fontWeight: 700, color: '#0F1F3D', marginBottom: 4 }}>
                  {previewObligationTemplate.name}
                </div>
                <div style={{ fontSize: 12, color: '#6B7280' }}>
                  {previewObligationTemplate.description}
                </div>
              </div>
              <button
                onClick={() => setPreviewObligationTemplate(null)}
                style={{
                  background: 'transparent', border: 'none',
                  color: '#9CA3AF', fontSize: 20, cursor: 'pointer',
                  padding: '0 0 0 12px', lineHeight: 1, flexShrink: 0,
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = '#374151')}
                onMouseLeave={(e) => (e.currentTarget.style.color = '#9CA3AF')}
              >
                ✕
              </button>
            </div>
            <div style={{
              flex: 1, overflowY: 'auto',
              borderTop: '1px solid #E5E7EB',
              borderBottom: '1px solid #E5E7EB',
              padding: '16px 0',
              marginBottom: 16,
            }}>
              <pre style={{
                fontFamily: 'Georgia, serif',
                fontSize: 13, lineHeight: 1.7,
                color: '#374151', whiteSpace: 'pre-wrap',
                wordBreak: 'break-word', margin: 0,
              }}>
                {previewObligationTemplate.content}
              </pre>
            </div>
            <button
              onClick={() => {
                insertDraftSectionFromTemplate(previewObligationTemplate.name, previewObligationTemplate.content, 'ob')
                setInsertedObligations((prev) => prev.includes(previewObligationTemplate.id) ? prev : [...prev, previewObligationTemplate.id])
                setPreviewObligationTemplate(null)
              }}
              style={{
                width: '100%', height: 40,
                background: '#243447', color: 'white',
                border: 'none', borderRadius: 8,
                fontSize: 14, fontWeight: 600, cursor: 'pointer',
                flexShrink: 0,
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = '#1a3460')}
              onMouseLeave={(e) => (e.currentTarget.style.background = '#243447')}
            >
              Use This Template
            </button>
          </div>
        </div>
      )}

      {/* Payment template preview modal */}
      {previewPaymentTemplate && (
        <div
          onClick={() => setPreviewPaymentTemplate(null)}
          style={{
            position: 'fixed', inset: 0, zIndex: 600,
            background: 'rgba(0,0,0,0.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 24,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: 600, maxHeight: '80vh',
              background: 'white', borderRadius: 12,
              padding: 28, boxShadow: '0 8px 40px rgba(0,0,0,0.15)',
              display: 'flex', flexDirection: 'column',
              overflow: 'hidden',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', marginBottom: 16, flexShrink: 0 }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 16, fontWeight: 700, color: '#0F1F3D', marginBottom: 4 }}>
                  {previewPaymentTemplate.name}
                </div>
                <div style={{ fontSize: 12, color: '#6B7280' }}>
                  {previewPaymentTemplate.description}
                </div>
              </div>
              <button
                onClick={() => setPreviewPaymentTemplate(null)}
                style={{
                  background: 'transparent', border: 'none',
                  color: '#9CA3AF', fontSize: 20, cursor: 'pointer',
                  padding: '0 0 0 12px', lineHeight: 1, flexShrink: 0,
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = '#374151')}
                onMouseLeave={(e) => (e.currentTarget.style.color = '#9CA3AF')}
              >
                ✕
              </button>
            </div>
            <div style={{
              flex: 1, overflowY: 'auto',
              borderTop: '1px solid #E5E7EB',
              borderBottom: '1px solid #E5E7EB',
              padding: '16px 0',
              marginBottom: 16,
            }}>
              <pre style={{
                fontFamily: 'Georgia, serif',
                fontSize: 13, lineHeight: 1.7,
                color: '#374151', whiteSpace: 'pre-wrap',
                wordBreak: 'break-word', margin: 0,
              }}>
                {previewPaymentTemplate.content}
              </pre>
            </div>
            <button
              onClick={() => {
                const ref = activeEditor === 'left' ? leftEditorRef : rightEditorRef
                if (ref.current) {
                  ref.current.focus(); document.execCommand('insertText', false, '\n\n' + previewPaymentTemplate.content)
                  if (activeEditor === 'left') syncDraftSectionsAfterMutation()
                  else queueAutosave()
                }
                setInsertedPayments((prev) => prev.includes(previewPaymentTemplate.id) ? prev : [...prev, previewPaymentTemplate.id])
                setPreviewPaymentTemplate(null)
              }}
              style={{
                width: '100%', height: 40,
                background: '#243447', color: 'white',
                border: 'none', borderRadius: 8,
                fontSize: 14, fontWeight: 600, cursor: 'pointer',
                flexShrink: 0,
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = '#1a3460')}
              onMouseLeave={(e) => (e.currentTarget.style.background = '#243447')}
            >
              Use This Template
            </button>
          </div>
        </div>
      )}
    </>
  )
}

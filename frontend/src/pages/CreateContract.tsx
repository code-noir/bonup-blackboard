import { useState, useRef, useEffect } from 'react'

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

// Tier: 'As You Go' | 'Blackboard Basic' | 'Blackboard Pro' | 'Blackboard Business' | 'Blackboard Premium'
const USER_TIER = 'Blackboard Business'

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

const CONTRACT_TOOLS = [
  { icon: '📋', label: 'Contract Details' },
  { icon: '👥', label: 'Parties' },
  { icon: '✓', label: 'Obligations' },
  { icon: '💰', label: 'Payments' },
  { icon: '📎', label: 'Attachments' },
  { icon: '📐', label: 'Templates' },
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
      width: 1, height: 20, background: '#E5E7EB',
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
        background: 'transparent', color: '#374151', fontSize: 13,
        cursor: 'pointer', flexShrink: 0,
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = '#F3F4F6')}
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

// ── Main Component ────────────────────────────────────────────────────────────

export default function CreateContract() {
  const [activeTool, setActiveTool] = useState<string | null>(null)
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

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function onFieldFocus(e: React.FocusEvent<any>) {
    e.currentTarget.style.borderColor = '#0F1F3D'
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
    document.documentElement.style.setProperty('--sidebar-w', '48px')
    window.dispatchEvent(new CustomEvent('sidebar-mode', { detail: 'icon-only' }))
    return () => {
      document.documentElement.style.removeProperty('--sidebar-w')
      window.dispatchEvent(new CustomEvent('sidebar-mode', { detail: 'normal' }))
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
      {/* ── FOCUS MODE FLOATING BUTTONS ── */}
      {focusMode !== 'none' && (
        <div style={{
          position: 'fixed', right: 24, bottom: 48, zIndex: 300,
          display: 'flex', gap: 8,
        }}>
          <button
            onClick={() => setAiPanelOpen((v) => !v)}
            style={{
              background: '#000000', color: 'white', border: 'none',
              borderRadius: 8, height: 34, padding: '0 16px',
              fontSize: 12, fontWeight: 500, cursor: 'pointer',
            }}
          >
            ✦ Ask AI
          </button>
          <button
            onClick={exitFocus}
            style={{
              background: 'rgba(0,0,0,0.6)', color: 'white', border: 'none',
              borderRadius: 8, height: 34, padding: '0 16px',
              fontSize: 12, cursor: 'pointer',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(0,0,0,0.8)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(0,0,0,0.6)')}
          >
            ⛶ Exit Focus
          </button>
        </div>
      )}

      {/* ── WORKSPACE: fixed below top bars, above status bar ── */}
      <div style={{
        position: 'fixed', top: 159, left: 48, right: 0, bottom: 32,
        display: 'flex', flexDirection: 'column', zIndex: 20, overflow: 'hidden',
        background: '#F8FAFC',
      }}>

        {/* ── TOOLBAR 1: Contract Actions ── */}
        <div style={{
          height: 44, flexShrink: 0,
          background: '#1C2B3A',
          borderBottom: '1px solid rgba(255,255,255,0.07)',
          display: 'flex', alignItems: 'center', padding: '0 16px', gap: 8,
        }}>
          {/* Title */}
          <input
            type="text"
            value={contractTitle}
            onChange={(e) => setContractTitle(e.target.value)}
            placeholder="Untitled Contract"
            style={{
              background: 'transparent',
              border: 'none',
              borderBottom: '1px solid rgba(255,255,255,0.2)',
              color: 'white', fontSize: 14, fontWeight: 600,
              width: 200, padding: '4px 8px', outline: 'none',
              flexShrink: 0,
            }}
          />
          {/* Version */}
          <span style={{
            background: 'rgba(255,255,255,0.1)',
            color: 'rgba(255,255,255,0.6)',
            fontSize: 11, padding: '2px 8px', borderRadius: 4, flexShrink: 0,
          }}>
            v1
          </span>

          {/* Status — center */}
          <div style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
            <select
              value={contractStatus}
              onChange={(e) => setContractStatus(e.target.value)}
              style={{
                background: 'rgba(255,255,255,0.08)',
                color: 'rgba(255,255,255,0.7)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: 6, fontSize: 12, padding: '4px 10px',
                cursor: 'pointer', outline: 'none',
              }}
            >
              <option>Draft</option>
              <option>Active</option>
              <option>Pending</option>
              <option>Completed</option>
            </select>
          </div>

          {/* Right buttons */}
          <GhostActionBtn label="Share / Invite" />
          <GhostActionBtn label="🔍 Analyze" onClick={() => setActiveTool('Contract Analysis')} />
          <GhostActionBtn label="⚡ Counter" onClick={() => setActiveTool('Contract Counter')} />
          <button style={{
            background: '#F5A623', color: '#0F1F3D',
            fontSize: 12, fontWeight: 600, height: 28, padding: '0 14px',
            borderRadius: 6, border: 'none', cursor: 'pointer', flexShrink: 0,
          }}>
            Sign
          </button>
          <GhostActionBtn label="Export" />
          <button style={{
            background: '#000000', color: 'white',
            fontSize: 12, fontWeight: 600, height: 28, padding: '0 14px',
            borderRadius: 6, border: 'none', cursor: 'pointer', flexShrink: 0,
          }}>
            Save
          </button>
        </div>

        {/* ── TOOLBAR 2: Rich Text ── */}
        <div style={{
          height: 42, flexShrink: 0,
          background: '#ffffff',
          borderBottom: '1px solid #E5E7EB',
          display: 'flex', alignItems: 'center',
          padding: '0 12px', gap: 2, overflowX: 'auto',
        }}>
          {/* Active editor pill */}
          <span style={{
            background: '#F0F4F8', color: '#374151',
            fontSize: 10, padding: '2px 8px', borderRadius: 4,
            marginRight: 8, flexShrink: 0, whiteSpace: 'nowrap',
          }}>
            {activeEditor === 'left' ? 'Left Editor' : 'Right Editor'}
          </span>

          {/* G1: Font Family */}
          <select
            value={fontFamily}
            onChange={(e) => { setFontFamily(e.target.value); execCmd('fontName', e.target.value) }}
            style={{
              minWidth: 140, height: 26, fontSize: 12,
              border: '1px solid #E5E7EB', borderRadius: 4,
              color: '#374151', background: 'white',
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
              border: '1px solid #E5E7EB', borderRadius: 4,
              color: '#374151', background: 'white',
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
            background: '#1C2B3A',
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
                    background: '#1C2B3A', color: 'white',
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
            background: '#E8EFF5',
            boxShadow: '4px 0 12px rgba(0,0,0,0.08)',
            position: 'relative',
          }}>
            <div style={{ width: toolPanelWidth, height: '100%', display: 'flex', flexDirection: 'column', position: 'relative' }}>
              {activeTool && (
                <>
                  {/* Panel header */}
                  <div style={{
                    padding: '16px 16px 12px',
                    borderBottom: '1px solid rgba(0,0,0,0.08)',
                    display: 'flex', alignItems: 'center', flexShrink: 0,
                  }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: '#0F1F3D', flex: 1 }}>
                      {activeTool}
                    </span>
                    <button
                      onClick={snapToolPanel}
                      title={toolPanelWidth >= 560 ? 'Collapse panel' : 'Expand panel'}
                      style={{
                        background: 'transparent', border: 'none',
                        color: '#6B7280', fontSize: 14,
                        cursor: 'pointer', padding: '0 4px', lineHeight: 1, marginRight: 4,
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = '#0F1F3D')}
                      onMouseLeave={(e) => (e.currentTarget.style.color = '#6B7280')}
                    >
                      ⇔
                    </button>
                    <button
                      onClick={() => setActiveTool(null)}
                      style={{
                        background: 'transparent', border: 'none',
                        color: '#6B7280', fontSize: 16,
                        cursor: 'pointer', padding: 0, lineHeight: 1,
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = '#0F1F3D')}
                      onMouseLeave={(e) => (e.currentTarget.style.color = '#6B7280')}
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
                      background: 'rgba(255,255,255,0.05)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      zIndex: 5,
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.15)')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.05)')}
                  >
                    <div style={{
                      width: 3, height: 40,
                      background: 'rgba(255,255,255,0.2)',
                      borderRadius: 3, pointerEvents: 'none',
                    }} />
                  </div>

                  {/* Panel content */}
                  <div style={{ flex: 1, overflowY: 'auto', padding: activeTool === 'Calculator' ? 12 : 16 }}>
                    {activeTool === 'Calculator' ? (
                      <>
                        {/* Secondary display */}
                        <div style={{
                          fontSize: 11, color: '#6B7280',
                          textAlign: 'right', marginBottom: 4, minHeight: 16,
                          fontFamily: "'DM Mono', monospace",
                        }}>
                          {calcFormula}
                        </div>
                        {/* Main display */}
                        <div style={{
                          background: '#0F1F3D', color: '#F5A623',
                          fontSize: 28, fontFamily: "'DM Mono', monospace",
                          textAlign: 'right', padding: '12px 16px',
                          borderRadius: 8, marginBottom: 10,
                          minHeight: 60, display: 'flex', alignItems: 'center', justifyContent: 'flex-end',
                          overflowX: 'hidden', wordBreak: 'break-all',
                        }}>
                          {calcDisplay}
                        </div>
                        {/* Button grid */}
                        {[
                          [{ l: 'C', t: 'clear' }, { l: '±', t: 'sign' }, { l: '%', t: 'pct' }, { l: '÷', t: 'op' }],
                          [{ l: '7', t: 'num' }, { l: '8', t: 'num' }, { l: '9', t: 'num' }, { l: '×', t: 'op' }],
                          [{ l: '4', t: 'num' }, { l: '5', t: 'num' }, { l: '6', t: 'num' }, { l: '−', t: 'op' }],
                          [{ l: '1', t: 'num' }, { l: '2', t: 'num' }, { l: '3', t: 'num' }, { l: '+', t: 'op' }],
                          [{ l: '0', t: 'zero' }, { l: '.', t: 'num' }, { l: '=', t: 'eq' }],
                        ].map((row, ri) => (
                          <div key={ri} style={{ display: 'grid', gridTemplateColumns: ri === 4 ? '2fr 1fr 1fr' : 'repeat(4, 1fr)', gap: 6, marginBottom: 6 }}>
                            {row.map(({ l, t }) => {
                              let bg = 'rgba(255,255,255,0.08)'
                              let color = 'white'
                              if (t === 'op') { bg = 'rgba(245,166,35,0.2)'; color = '#F5A623' }
                              if (t === 'eq') { bg = '#F5A623'; color = '#0F1F3D' }
                              if (t === 'clear') { bg = 'rgba(239,68,68,0.2)'; color = '#F87171' }
                              return (
                                <button
                                  key={l}
                                  onClick={() => {
                                    if (t === 'num' || t === 'zero') calcInput(l)
                                    else if (t === 'op') calcOp(l)
                                    else if (t === 'eq') calcEqual()
                                    else if (t === 'clear') calcClear()
                                    else if (t === 'sign') {
                                      setCalcDisplay(String(parseFloat(calcDisplay) * -1))
                                    }
                                    else if (t === 'pct') {
                                      setCalcDisplay(String(parseFloat(calcDisplay) / 100))
                                    }
                                  }}
                                  style={{
                                    background: bg, color, border: 'none',
                                    borderRadius: 8, height: 44, fontSize: 15,
                                    cursor: 'pointer', fontFamily: "'DM Mono', monospace",
                                    fontWeight: t === 'eq' ? 700 : 400,
                                  }}
                                  onMouseEnter={(e) => {
                                    e.currentTarget.style.opacity = '0.85'
                                  }}
                                  onMouseLeave={(e) => {
                                    e.currentTarget.style.opacity = '1'
                                  }}
                                >
                                  {l}
                                </button>
                              )
                            })}
                          </div>
                        ))}
                      </>
                    ) : activeTool === 'Contract Analysis' ? (
                      <>
                        <p style={{ fontSize: 12, color: '#6B7280', marginBottom: 16 }}>
                          Write or paste your contract in the editor, then click Analyze for a full AI breakdown.
                        </p>
                        {USER_TIER === 'As You Go' && (
                          <p style={{ fontSize: 11, color: '#D97706', marginBottom: 12 }}>
                            ⚠️ $15 per analysis
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
                            background: isAnalyzing ? '#6B7280' : '#0F1F3D',
                            color: 'white', border: 'none',
                            borderRadius: 8, fontSize: 13, fontWeight: 600,
                            cursor: isAnalyzing ? 'default' : 'pointer',
                            marginBottom: 12,
                          }}
                          onMouseEnter={(e) => { if (!isAnalyzing) e.currentTarget.style.background = '#1a3460' }}
                          onMouseLeave={(e) => { if (!isAnalyzing) e.currentTarget.style.background = '#0F1F3D' }}
                        >
                          {isAnalyzing ? 'Analyzing…' : 'Analyze Contract'}
                        </button>
                        <div style={{
                          background: 'white', borderRadius: 8, padding: 12,
                          minHeight: 120, border: '1px solid #E5E7EB',
                          fontSize: 12, color: analysisResult ? '#374151' : '#9CA3AF',
                        }}>
                          {analysisResult || 'Analysis results will appear here…'}
                        </div>
                      </>
                    ) : activeTool === 'Contract Counter' ? (
                      <>
                        {USER_TIER === 'Blackboard Basic' ? (
                          <div style={{ textAlign: 'center' }}>
                            <div style={{ fontSize: 32, marginBottom: 12 }}>🔒</div>
                            <p style={{ fontSize: 13, color: '#374151', marginBottom: 16 }}>
                              Contract Counter is available on Blackboard Pro and above.
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
                              Upgrade to Blackboard Pro
                            </button>
                          </div>
                        ) : (
                          <>
                            <p style={{ fontSize: 12, color: '#6B7280', marginBottom: 12 }}>
                              Review the contract and propose your counter terms.
                            </p>
                            {USER_TIER === 'As You Go' && (
                              <p style={{ fontSize: 11, color: '#D97706', marginBottom: 12 }}>
                                ⚠️ $15 per counter
                              </p>
                            )}
                            <textarea
                              value={counterText}
                              onChange={(e) => setCounterText(e.target.value)}
                              placeholder="Enter your counter terms…"
                              style={{
                                width: '100%', minHeight: 100,
                                border: '1px solid #E5E7EB',
                                borderRadius: 8, padding: 10,
                                fontSize: 12, resize: 'vertical',
                                outline: 'none', fontFamily: 'inherit',
                                boxSizing: 'border-box',
                                marginBottom: 12,
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
                                background: isSubmittingCounter ? '#6B7280' : '#0F1F3D',
                                color: 'white', border: 'none',
                                borderRadius: 8, fontSize: 13, fontWeight: 600,
                                cursor: isSubmittingCounter ? 'default' : 'pointer',
                              }}
                              onMouseEnter={(e) => { if (!isSubmittingCounter) e.currentTarget.style.background = '#1a3460' }}
                              onMouseLeave={(e) => { if (!isSubmittingCounter) e.currentTarget.style.background = '#0F1F3D' }}
                            >
                              {isSubmittingCounter ? 'Submitting…' : 'Submit Counter'}
                            </button>
                          </>
                        )}
                      </>
                    ) : activeTool === 'Contract Details' ? (() => {
                      const LABEL: React.CSSProperties = {
                        fontSize: 11, fontWeight: 500, color: '#4B5563',
                        marginBottom: 4, display: 'block',
                        textTransform: 'uppercase', letterSpacing: '0.06em',
                      }
                      const FIELD: React.CSSProperties = {
                        width: '100%', background: 'white',
                        border: '1px solid #D1D5DB', borderRadius: 8,
                        padding: '8px 12px', fontSize: 13, color: '#374151',
                        fontFamily: "'Outfit', sans-serif", outline: 'none',
                        marginBottom: 12, boxSizing: 'border-box',
                      }
                      return (
                        <>
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

                          {/* 12. Description / Notes */}
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

                          {/* Save button */}
                          <button
                            style={{
                              width: '100%', height: 36,
                              background: '#0F1F3D', color: 'white',
                              border: 'none', borderRadius: 8,
                              fontSize: 13, fontWeight: 600,
                              cursor: 'pointer', marginTop: 4,
                            }}
                            onMouseEnter={(e) => (e.currentTarget.style.background = '#1a3460')}
                            onMouseLeave={(e) => (e.currentTarget.style.background = '#0F1F3D')}
                          >
                            Save Details
                          </button>
                        </>
                      )
                    })() : (
                      <div style={{ fontSize: 12, color: '#6B7280', textAlign: 'center', marginTop: 40 }}>
                        {activeTool} coming soon
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>

          {/* CENTER AREA */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>

            {/* Top action buttons */}
            <div style={{
              padding: 16, background: '#F8FAFC',
              borderBottom: '1px solid #E5E7EB',
              display: focusMode !== 'none' ? 'none' : 'flex',
              justifyContent: 'center', gap: 16, flexShrink: 0,
            }}>
              {['⊟ Choose a Template', '✎ Start from Scratch'].map((label) => (
                <button
                  key={label}
                  style={{
                    height: 36, padding: '0 20px', borderRadius: 8,
                    fontSize: 13, fontWeight: 500, cursor: 'pointer',
                    border: '1px solid #D1D5DB', background: 'white', color: '#374151',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = '#F9FAFB'
                    e.currentTarget.style.borderColor = '#9CA3AF'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'white'
                    e.currentTarget.style.borderColor = '#D1D5DB'
                  }}
                >
                  {label}
                </button>
              ))}
              {/* Ask AI — toggles the slide-up panel */}
              <button
                onClick={() => setAiPanelOpen((v) => !v)}
                style={{
                  height: 36, padding: '0 20px', borderRadius: 8,
                  fontSize: 13, fontWeight: 500, cursor: 'pointer',
                  border: aiPanelOpen ? '1px solid #BFDBFE' : '1px solid #D1D5DB',
                  background: aiPanelOpen ? '#EFF6FF' : 'white',
                  color: aiPanelOpen ? '#1E40AF' : '#374151',
                }}
              >
                ✦ Ask AI
              </button>
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

              {/* LEFT EDITOR */}
              <div style={focusMode === 'right' ? { display: 'none' } : {
                width: focusMode === 'left' ? '100%' : `${splitPercent}%`,
                flexShrink: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0,
                transition: 'width 0.3s ease',
              }}>
                <div style={{
                  height: 36, flexShrink: 0,
                  background: '#F8FAFC',
                  borderBottom: '1px solid #E5E7EB',
                  borderRight: focusMode === 'left' ? 'none' : '1px solid #E5E7EB',
                  padding: '0 16px',
                  display: 'flex', alignItems: 'center', gap: 8,
                }}>
                  <span style={{ fontSize: 12, color: '#6B7280', fontWeight: 500 }}>Left Editor</span>
                  {activeEditor === 'left' && focusMode !== 'left' && (
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#2DD4BF' }} />
                  )}
                  <div style={{ marginLeft: 'auto' }}>
                    <button
                      onClick={() => focusMode === 'left' ? exitFocus() : enterFocus('left')}
                      title="Focus mode"
                      style={{
                        background: 'transparent', border: 'none',
                        color: '#9CA3AF', fontSize: 14, cursor: 'pointer', padding: 4,
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = '#374151')}
                      onMouseLeave={(e) => (e.currentTarget.style.color = '#9CA3AF')}
                    >
                      ⛶
                    </button>
                  </div>
                </div>
                {focusMode === 'left' ? (
                  <div style={{ flex: 1, overflowY: 'auto', background: '#F0F2F5', padding: 24 }}>
                    <div
                      ref={leftEditorRef}
                      contentEditable
                      suppressContentEditableWarning
                      onFocus={() => setActiveEditor('left')}
                      onInput={(e) => setLeftEmpty((e.currentTarget.textContent ?? '') === '')}
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
                      contentEditable
                      suppressContentEditableWarning
                      onFocus={() => setActiveEditor('left')}
                      onInput={(e) => setLeftEmpty((e.currentTarget.textContent ?? '') === '')}
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
                onMouseEnter={(e) => { if (!isDragging) (e.currentTarget.style.background = '#CBD5E1') }}
                onMouseLeave={(e) => { if (!isDragging) (e.currentTarget.style.background = '#E5E7EB') }}
                style={{
                  width: 6, flexShrink: 0,
                  background: isDragging ? '#CBD5E1' : '#E5E7EB',
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

              {/* RIGHT EDITOR */}
              <div style={focusMode === 'left' ? { display: 'none' } : {
                flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0,
              }}>
                <div style={{
                  height: 36, flexShrink: 0,
                  background: '#F8FAFC',
                  borderBottom: '1px solid #E5E7EB',
                  borderLeft: focusMode === 'right' ? 'none' : '1px solid #E5E7EB',
                  padding: '0 16px',
                  display: 'flex', alignItems: 'center', gap: 8,
                }}>
                  <span style={{ fontSize: 12, color: '#6B7280', fontWeight: 500 }}>Right Editor</span>
                  {activeEditor === 'right' && focusMode !== 'right' && (
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#2DD4BF' }} />
                  )}
                  <div style={{ marginLeft: 'auto' }}>
                    <button
                      onClick={() => focusMode === 'right' ? exitFocus() : enterFocus('right')}
                      title="Focus mode"
                      style={{
                        background: 'transparent', border: 'none',
                        color: '#9CA3AF', fontSize: 14, cursor: 'pointer', padding: 4,
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = '#374151')}
                      onMouseLeave={(e) => (e.currentTarget.style.color = '#9CA3AF')}
                    >
                      ⛶
                    </button>
                  </div>
                </div>
                {focusMode === 'right' ? (
                  <div style={{ flex: 1, overflowY: 'auto', background: '#F0F2F5', padding: 24 }}>
                    <div
                      ref={rightEditorRef}
                      contentEditable
                      suppressContentEditableWarning
                      onFocus={() => setActiveEditor('right')}
                      onInput={(e) => setRightEmpty((e.currentTarget.textContent ?? '') === '')}
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
                      contentEditable
                      suppressContentEditableWarning
                      onFocus={() => setActiveEditor('right')}
                      onInput={(e) => setRightEmpty((e.currentTarget.textContent ?? '') === '')}
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
                        background: msg.role === 'ai' ? '#EFF6FF' : '#0F1F3D',
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

      {/* ── STATUS BAR ── */}
      <div style={{
        position: 'fixed', bottom: 0, left: 0, right: 0, height: 32,
        background: '#1C2B3A', zIndex: 100,
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
    </>
  )
}

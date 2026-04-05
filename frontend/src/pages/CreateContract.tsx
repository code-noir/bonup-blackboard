import { useState, useRef } from 'react'

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

const CONTRACT_TOOLS = [
  { icon: '📋', label: 'Contract Details' },
  { icon: '👥', label: 'Parties' },
  { icon: '📅', label: 'Obligations' },
  { icon: '💰', label: 'Payments' },
  { icon: '📎', label: 'Attachments' },
  { icon: '🔒', label: 'Permissions' },
  { icon: '📊', label: 'Analytics' },
  { icon: '⚙️', label: 'Settings' },
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
  const [leftDrawerOpen, setLeftDrawerOpen] = useState(true)
  const [rightDrawerOpen, setRightDrawerOpen] = useState(true)
  const [activeEditor, setActiveEditor] = useState<'left' | 'right'>('left')
  const [videoExpanded, setVideoExpanded] = useState(false)
  const [aiExpanded, setAiExpanded] = useState(false)
  const [aiPanelOpen, setAiPanelOpen] = useState(false)
  const [aiPanelMessage, setAiPanelMessage] = useState('')
  const [aiPanelChat, setAiPanelChat] = useState([
    { role: 'ai', text: 'Hi! I can help you draft, review, and improve your contract. What would you like to do?' },
  ])
  const [contractTitle, setContractTitle] = useState('')
  const [contractStatus, setContractStatus] = useState('Draft')
  const [hoverDescription] = useState('')
  const [aiMessage, setAiMessage] = useState('')
  const [aiChat, setAiChat] = useState([
    { role: 'ai', text: "I can help you draft, review, and improve your contract. What do you need?" },
  ])
  const [fontFamily, setFontFamily] = useState('Arial')
  const [fontSize, setFontSize] = useState('14')
  const [leftEmpty, setLeftEmpty] = useState(true)
  const [rightEmpty, setRightEmpty] = useState(true)

  const leftEditorRef = useRef<HTMLDivElement>(null)
  const rightEditorRef = useRef<HTMLDivElement>(null)

  function getActiveRef() {
    return activeEditor === 'left' ? leftEditorRef : rightEditorRef
  }

  function execCmd(cmd: string, value?: string) {
    getActiveRef().current?.focus()
    document.execCommand(cmd, false, value)
  }

  function sendAiMessage() {
    const trimmed = aiMessage.trim()
    if (!trimmed) return
    setAiChat((prev) => [...prev, { role: 'user', text: trimmed }])
    setAiMessage('')
    setTimeout(() => {
      setAiChat((prev) => [...prev, { role: 'ai', text: 'AI assistant coming soon. Stay tuned!' }])
    }, 600)
  }

  const TOGGLE_BTN: React.CSSProperties = {
    width: 16, height: 48, border: 'none', background: '#2E4156',
    color: 'rgba(255,255,255,0.5)', fontSize: 10, cursor: 'pointer',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    flexShrink: 0, alignSelf: 'center',
  }

  return (
    <>
      {/* ── WORKSPACE: fixed below top bars, above status bar ── */}
      <div style={{
        position: 'fixed', top: 159, left: 216, right: 0, bottom: 32,
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
        <div style={{ flex: 1, display: 'flex', flexDirection: 'row', overflow: 'hidden', minHeight: 0 }}>

          {/* LEFT DRAWER */}
          <div style={{
            width: leftDrawerOpen ? 280 : 0,
            flexShrink: 0,
            transition: 'width 0.3s ease',
            overflow: 'hidden',
            background: '#1E3A55',
          }}>
            <div style={{
              width: 280, height: '100%',
              display: 'flex', flexDirection: 'column', overflowY: 'auto',
            }}>
              {/* Section title */}
              <div style={{ padding: '16px 16px 8px', flexShrink: 0 }}>
                <p style={{
                  fontSize: 12, color: 'rgba(255,255,255,0.5)',
                  textTransform: 'uppercase', letterSpacing: '0.1em', margin: 0,
                }}>
                  Contract Tools
                </p>
              </div>

              {/* Tool items */}
              {CONTRACT_TOOLS.map((tool) => (
                <button
                  key={tool.label}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '10px 16px', background: 'transparent',
                    border: 'none', color: 'rgba(255,255,255,0.75)',
                    fontSize: 13, cursor: 'pointer',
                    textAlign: 'left', width: '100%',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.08)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  <span style={{ fontSize: 15 }}>{tool.icon}</span>
                  <span>{tool.label}</span>
                </button>
              ))}

              <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', margin: '8px 0', flexShrink: 0 }} />

              {/* Video Player */}
              <div style={{ padding: '0 16px 16px', flexShrink: 0 }}>
                <button
                  onClick={() => setVideoExpanded((v) => !v)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    background: 'transparent', border: 'none',
                    color: 'rgba(255,255,255,0.6)', fontSize: 12,
                    cursor: 'pointer', padding: '8px 0', width: '100%',
                  }}
                >
                  <span>▶</span>
                  <span>Tutorial</span>
                  <span style={{ marginLeft: 'auto', fontSize: 10 }}>
                    {videoExpanded ? '▲' : '▼'}
                  </span>
                </button>
                {videoExpanded && (
                  <div style={{ marginTop: 8 }}>
                    <div style={{
                      width: '100%', aspectRatio: '16/9',
                      background: '#0F1F3D', borderRadius: 8,
                      display: 'flex', flexDirection: 'column',
                      alignItems: 'center', justifyContent: 'center', gap: 8,
                    }}>
                      <div style={{
                        width: 36, height: 36, borderRadius: '50%',
                        background: 'rgba(255,255,255,0.15)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                      }}>
                        <span style={{ color: 'white', fontSize: 14, marginLeft: 2 }}>▶</span>
                      </div>
                      <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', margin: 0 }}>
                        Tutorial coming soon
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* LEFT DRAWER TOGGLE */}
          <button
            onClick={() => setLeftDrawerOpen((v) => !v)}
            style={{ ...TOGGLE_BTN, borderRadius: '0 4px 4px 0' }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#3D5068'
              e.currentTarget.style.color = 'white'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#2E4156'
              e.currentTarget.style.color = 'rgba(255,255,255,0.5)'
            }}
          >
            {leftDrawerOpen ? '‹' : '›'}
          </button>

          {/* CENTER AREA */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>

            {/* Top action buttons */}
            <div style={{
              padding: 16, background: '#F8FAFC',
              borderBottom: '1px solid #E5E7EB',
              display: 'flex', justifyContent: 'center', gap: 16, flexShrink: 0,
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
            <div style={{
              height: aiPanelOpen ? 'calc(100% - 280px)' : '100%',
              transition: 'height 0.35s ease',
              display: 'flex', flexDirection: 'row', overflow: 'hidden',
              minHeight: 200,
            }}>

              {/* LEFT EDITOR */}
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
                <div style={{
                  height: 36, flexShrink: 0,
                  background: '#F8FAFC',
                  borderBottom: '1px solid #E5E7EB',
                  borderRight: '1px solid #E5E7EB',
                  padding: '0 16px',
                  display: 'flex', alignItems: 'center', gap: 8,
                }}>
                  <span style={{ fontSize: 12, color: '#6B7280', fontWeight: 500 }}>Left Editor</span>
                  {activeEditor === 'left' && (
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#2DD4BF' }} />
                  )}
                </div>
                <div style={{ flex: 1, position: 'relative', overflow: 'hidden', minHeight: 0 }}>
                  {leftEmpty && (
                    <div style={{
                      position: 'absolute', top: 24, left: 32, right: 32,
                      fontSize: 14, color: '#9CA3AF', lineHeight: 1.6,
                      pointerEvents: 'none', userSelect: 'none', zIndex: 1,
                    }}>
                      Start writing your contract here, choose a template, or ask AI to help...
                    </div>
                  )}
                  <div
                    ref={leftEditorRef}
                    contentEditable
                    suppressContentEditableWarning
                    onFocus={() => setActiveEditor('left')}
                    onInput={(e) => setLeftEmpty((e.currentTarget.textContent ?? '') === '')}
                    style={{
                      position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
                      background: 'white',
                      borderRight: '1px solid #E5E7EB',
                      padding: '24px 32px',
                      fontSize: 14, color: '#374151', lineHeight: 1.6,
                      outline: 'none', overflowY: 'auto',
                    }}
                  />
                </div>
              </div>

              {/* CENTER DIVIDER */}
              <div
                style={{ width: 4, flexShrink: 0, background: '#E5E7EB', cursor: 'col-resize' }}
                onMouseEnter={(e) => (e.currentTarget.style.background = '#D1D5DB')}
                onMouseLeave={(e) => (e.currentTarget.style.background = '#E5E7EB')}
              />

              {/* RIGHT EDITOR */}
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
                <div style={{
                  height: 36, flexShrink: 0,
                  background: '#F8FAFC',
                  borderBottom: '1px solid #E5E7EB',
                  borderLeft: '1px solid #E5E7EB',
                  padding: '0 16px',
                  display: 'flex', alignItems: 'center', gap: 8,
                }}>
                  <span style={{ fontSize: 12, color: '#6B7280', fontWeight: 500 }}>Right Editor</span>
                  {activeEditor === 'right' && (
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#2DD4BF' }} />
                  )}
                </div>
                <div style={{ flex: 1, position: 'relative', overflow: 'hidden', minHeight: 0 }}>
                  {rightEmpty && (
                    <div style={{
                      position: 'absolute', top: 24, left: 32, right: 32,
                      fontSize: 14, color: '#9CA3AF', lineHeight: 1.6,
                      pointerEvents: 'none', userSelect: 'none', zIndex: 1,
                    }}>
                      Start writing your contract here, choose a template, or ask AI to help...
                    </div>
                  )}
                  <div
                    ref={rightEditorRef}
                    contentEditable
                    suppressContentEditableWarning
                    onFocus={() => setActiveEditor('right')}
                    onInput={(e) => setRightEmpty((e.currentTarget.textContent ?? '') === '')}
                    style={{
                      position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
                      background: 'white',
                      borderLeft: '1px solid #E5E7EB',
                      padding: '24px 32px',
                      fontSize: 14, color: '#374151', lineHeight: 1.6,
                      outline: 'none', overflowY: 'auto',
                    }}
                  />
                </div>
              </div>

            </div>

              {/* AI PANEL — slides up from bottom of center area */}
              <div style={{
                position: 'absolute', bottom: 0, left: 0, right: 0,
                height: 280,
                background: '#ffffff',
                borderTop: '2px solid #E5E7EB',
                boxShadow: '0 -4px 20px rgba(0,0,0,0.08)',
                borderRadius: '12px 12px 0 0',
                transform: aiPanelOpen ? 'translateY(0)' : 'translateY(100%)',
                transition: 'transform 0.35s ease',
                display: 'flex', flexDirection: 'column',
                zIndex: 10,
              }}>
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
                height: aiExpanded ? 0 : '50%',
                overflow: 'hidden',
                flexShrink: 0,
                borderBottom: '1px solid #E5E7EB',
                display: 'flex', flexDirection: 'column',
                transition: 'height 0.3s ease',
                padding: aiExpanded ? 0 : 16,
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

              {/* AI Assistant */}
              <div style={{
                flex: 1, display: 'flex', flexDirection: 'column',
                padding: 16, overflow: 'hidden', minHeight: 0,
              }}>
                <div style={{
                  display: 'flex', alignItems: 'center',
                  marginBottom: 8, flexShrink: 0,
                }}>
                  <p style={{
                    fontSize: 12, fontWeight: 600, color: '#374151',
                    textTransform: 'uppercase', letterSpacing: '0.08em',
                    margin: 0, flex: 1,
                  }}>
                    AI Assistant
                  </p>
                  <button
                    onClick={() => setAiExpanded((v) => !v)}
                    title={aiExpanded ? 'Collapse' : 'Expand'}
                    style={{
                      background: 'transparent', border: 'none',
                      color: '#9CA3AF', fontSize: 13,
                      cursor: 'pointer', padding: '2px 4px', borderRadius: 4,
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = '#374151')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = '#9CA3AF')}
                  >
                    {aiExpanded ? '⊟' : '⊞'}
                  </button>
                </div>

                {/* Chat messages */}
                <div style={{
                  flex: 1, overflowY: 'auto',
                  background: 'white', borderRadius: 8,
                  padding: 12, marginBottom: 8,
                  minHeight: 120, display: 'flex', flexDirection: 'column', gap: 8,
                }}>
                  {aiChat.map((msg, i) => (
                    <div key={i} style={{
                      display: 'flex',
                      justifyContent: msg.role === 'ai' ? 'flex-start' : 'flex-end',
                    }}>
                      <span style={{
                        background: msg.role === 'ai' ? '#EFF6FF' : '#0F1F3D',
                        color: msg.role === 'ai' ? '#1E40AF' : '#fff',
                        borderRadius: 8, padding: '8px 12px',
                        fontSize: 12, maxWidth: '85%', lineHeight: 1.5,
                      }}>
                        {msg.text}
                      </span>
                    </div>
                  ))}
                </div>

                {/* Input */}
                <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                  <input
                    type="text"
                    value={aiMessage}
                    onChange={(e) => setAiMessage(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && sendAiMessage()}
                    placeholder="Ask AI..."
                    style={{
                      flex: 1, border: '1px solid #E5E7EB',
                      borderRadius: 8, padding: '8px 12px',
                      fontSize: 12, outline: 'none',
                    }}
                  />
                  <button
                    onClick={sendAiMessage}
                    style={{
                      background: '#000000', color: 'white',
                      border: 'none', borderRadius: 8,
                      padding: '8px 14px', fontSize: 12, cursor: 'pointer',
                    }}
                  >
                    Send
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

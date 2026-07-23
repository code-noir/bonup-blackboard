import { useState } from 'react'

type ResourceTab = 'forms' | 'processes'

interface ResourceItem {
  name: string
  description: string
}

const FORM_CATEGORIES: ResourceItem[] = [
  {
    name: 'Court Forms',
    description: 'Common court-related paperwork organized for future form access.',
  },
  {
    name: 'Affidavits',
    description: 'Sworn statement forms and supporting affidavit materials.',
  },
  {
    name: 'Consumer Dispute Forms',
    description: 'Forms for billing, service, purchase, and account disputes.',
  },
  {
    name: 'Financial Forms',
    description: 'Personal finance paperwork and supporting form categories.',
  },
  {
    name: 'Employment / Work Forms',
    description: 'Workplace forms, letters, and employment-related documents.',
  },
  {
    name: 'Trust & Estate Documents',
    description: 'Planning document categories for trust and estate situations.',
  },
  {
    name: 'Form Generator',
    description: 'Guided form creation tools will be organized here.',
  },
  {
    name: 'Saved Forms',
    description: 'Drafted and saved Resource forms will appear here later.',
  },
  {
    name: 'PDF Exports',
    description: 'Completed form exports will be collected here when available.',
  },
]

const PROCESS_CATEGORIES: ResourceItem[] = [
  {
    name: 'Buy a Car',
    description: 'Paperwork, checklists, and guides for vehicle purchase situations.',
  },
  {
    name: 'Buy a Home',
    description: 'Documents and steps for preparing and tracking a home purchase.',
  },
  {
    name: 'Dispute a Bill',
    description: 'Letters, records, and steps for billing or account disputes.',
  },
  {
    name: 'Prepare for Court',
    description: 'Forms and checklists for organizing court-related paperwork.',
  },
  {
    name: 'Organize Work / Pay Records',
    description: 'Tools for collecting employment, pay, and workplace records.',
  },
  {
    name: 'Start a Business',
    description: 'Process materials for early business setup paperwork.',
  },
  {
    name: 'Set Up Trust / Estate Paperwork',
    description: 'Guided planning categories for trust and estate documents.',
  },
  {
    name: 'Financial Readiness',
    description: 'Checklists and guides for organizing financial paperwork.',
  },
]

const TABS: { id: ResourceTab; label: string }[] = [
  { id: 'forms', label: 'Forms' },
  { id: 'processes', label: 'Processes' },
]

export default function Resource() {
  const [activeTab, setActiveTab] = useState<ResourceTab>('forms')
  const [selectedForm, setSelectedForm] = useState<ResourceItem>(FORM_CATEGORIES[0])
  const [selectedProcess, setSelectedProcess] = useState<ResourceItem>(PROCESS_CATEGORIES[0])

  const isForms = activeTab === 'forms'
  const items = isForms ? FORM_CATEGORIES : PROCESS_CATEGORIES
  const selectedItem = isForms ? selectedForm : selectedProcess
  const emptyState = isForms
    ? 'Forms for this category will appear here.'
    : 'Forms, packets, checklists, and guides for this process will appear here.'

  function selectItem(item: ResourceItem) {
    if (isForms) setSelectedForm(item)
    else setSelectedProcess(item)
  }

  return (
    <div style={{ padding: '32px 0' }}>
      <div style={{ maxWidth: 1180, marginBottom: 24 }}>
        <p style={{
          margin: '0 0 8px',
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          color: '#D4900A',
        }}>
          Resource
        </p>
        <h1 style={{ fontSize: 28, fontWeight: 800, color: '#0F1F3D', margin: 0, letterSpacing: 0 }}>
          Find the paperwork you need.
        </h1>
        <p style={{ fontSize: 14, color: '#64748B', margin: '9px 0 0', maxWidth: 760, lineHeight: 1.55 }}>
          Browse forms, packets, letters, checklists, and guides for personal, financial, work, and legal situations.
        </p>
      </div>


      <div style={{
        display: 'grid',
        gridTemplateColumns: '170px minmax(0, 1fr)',
        gap: 28,
        alignItems: 'start',
      }}>
        <aside style={{
          background: 'white',
          border: '1px solid #E5E7EB',
          borderRadius: 10,
          padding: 8,
          boxShadow: '0 1px 3px rgba(15,23,42,0.05)',
          position: 'sticky',
          top: 132,
        }}>
          {TABS.map((tab) => {
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                style={{
                  width: '100%',
                  height: 38,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'flex-start',
                  padding: '0 12px',
                  borderRadius: 7,
                  border: 'none',
                  borderLeft: isActive ? '3px solid #D4900A' : '3px solid transparent',
                  background: isActive ? 'rgba(245,166,35,0.12)' : 'transparent',
                  color: isActive ? '#243447' : '#475569',
                  fontSize: 13,
                  fontWeight: isActive ? 800 : 600,
                  cursor: 'pointer',
                  textAlign: 'left',
                  marginBottom: tab.id === 'forms' ? 4 : 0,
                }}
                onMouseEnter={(e) => {
                  if (!isActive) e.currentTarget.style.background = '#F8FAFC'
                }}
                onMouseLeave={(e) => {
                  if (!isActive) e.currentTarget.style.background = 'transparent'
                }}
              >
                {tab.label}
              </button>
            )
          })}
        </aside>

        <div>
          <input
            type="search"
            placeholder="Search forms, packets, letters, or guides..."
            style={{
              width: '100%',
              height: 42,
              border: '1px solid #D1D5DB',
              borderRadius: 8,
              padding: '0 14px',
              fontSize: 13,
              outline: 'none',
              marginBottom: 18,
              boxSizing: 'border-box',
              color: '#374151',
              background: 'white',
              boxShadow: '0 1px 2px rgba(15,23,42,0.04)',
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = '#243447'
              e.currentTarget.style.boxShadow = '0 0 0 2px rgba(15,31,61,0.08)'
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = '#D1D5DB'
              e.currentTarget.style.boxShadow = '0 1px 2px rgba(15,23,42,0.04)'
            }}
          />

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1fr) 320px',
            gap: 18,
            alignItems: 'start',
          }}>
            <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))',
            gap: 12,
          }}>
            {items.map((item) => {
              const isSelected = selectedItem.name === item.name
              return (
                <button
                  key={item.name}
                  type="button"
                  onClick={() => selectItem(item)}
                  style={{
                    textAlign: 'left',
                    minHeight: 112,
                    background: 'white',
                    borderRadius: 8,
                    border: isSelected ? '1px solid #243447' : '1px solid #E5E7EB',
                    padding: '14px 14px 12px',
                    boxShadow: isSelected ? '0 8px 18px rgba(15,31,61,0.10)' : '0 1px 3px rgba(15,23,42,0.05)',
                    cursor: 'pointer',
                    transition: 'box-shadow 0.15s ease, border-color 0.15s ease, transform 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = '#CBD5E1'
                    e.currentTarget.style.boxShadow = '0 6px 14px rgba(15,23,42,0.08)'
                    e.currentTarget.style.transform = 'translateY(-1px)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = isSelected ? '#243447' : '#E5E7EB'
                    e.currentTarget.style.boxShadow = isSelected ? '0 8px 18px rgba(15,31,61,0.10)' : '0 1px 3px rgba(15,23,42,0.05)'
                    e.currentTarget.style.transform = 'translateY(0)'
                  }}
                >
                  <span style={{ display: 'block', fontSize: 14, fontWeight: 700, color: '#0F1F3D', lineHeight: 1.25 }}>
                    {item.name}
                  </span>
                  <span style={{ display: 'block', fontSize: 12, color: '#64748B', lineHeight: 1.45, marginTop: 7 }}>
                    {item.description}
                  </span>
                </button>
              )
            })}
          </div>

            <section style={{
          background: 'white',
          border: '1px solid #E5E7EB',
          borderRadius: 10,
          padding: 18,
          boxShadow: '0 1px 3px rgba(15,23,42,0.05)',
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: '#0F1F3D', lineHeight: 1.25 }}>
              {selectedItem.name}
            </h2>
            <span style={{
              flexShrink: 0,
              borderRadius: 999,
              background: '#FEF3C7',
              color: '#B45309',
              fontSize: 11,
              fontWeight: 700,
              padding: '4px 9px',
              whiteSpace: 'nowrap',
            }}>
              Coming soon
            </span>
          </div>
          <p style={{ margin: '10px 0 0', fontSize: 13, color: '#64748B', lineHeight: 1.55 }}>
            {selectedItem.description}
          </p>
          <div style={{
            marginTop: 18,
            border: '1px dashed #CBD5E1',
            borderRadius: 8,
            padding: '26px 18px',
            textAlign: 'center',
            background: '#F8FAFC',
            color: '#64748B',
            fontSize: 13,
            lineHeight: 1.5,
          }}>
            {emptyState}
          </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  )
}

import { useEffect, useMemo, useState } from 'react'
import api from '@/api/client'

type ContractSectionOption = {
  id: string
  number: number
  name: string
}

type TemplateOption = {
  key: string
  label: string
  default_text: string
}

type TemplateResponse = {
  categories: Record<string, TemplateOption[]>
}

type AgreementExchangeSaveResponse = {
  request: AgreementExchangeSavedRequest
  exchange?: unknown
}

export type AgreementExchangeSavedRequest = {
  id?: string
  target_section_id?: string | null
  target_section_title?: string
  request_category?: string
  action_type?: string
  template_key?: string | null
  proposed_text?: string
  reason?: string | null
  status?: string
}

type AgreementExchangeRequestBuilderProps = {
  exchangeId: string
  sections: ContractSectionOption[]
  onSaved: (request: AgreementExchangeSavedRequest, exchange?: unknown) => void
}

const CATEGORY_LABELS: Record<string, string> = {
  recitals_background: 'Recitals / Background',
  terms_and_conditions: 'Terms and Conditions',
  obligations: 'Obligations',
  payment_terms: 'Payment Terms',
  confidentiality: 'Confidentiality',
  intellectual_property: 'Intellectual Property',
  termination: 'Termination',
  dispute_resolution: 'Dispute Resolution',
  governing_law: 'Governing Law',
}

const ACTION_OPTIONS = [
  ['replace_clause', 'Replace existing clause'],
  ['add_clause', 'Add new clause'],
  ['clarify_clause', 'Clarify existing language'],
  ['remove_clause', 'Remove clause'],
] as const

export default function AgreementExchangeRequestBuilder({ exchangeId, sections, onSaved }: AgreementExchangeRequestBuilderProps) {
  const [templates, setTemplates] = useState<Record<string, TemplateOption[]>>({})
  const [isLoadingTemplates, setIsLoadingTemplates] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [selectedSectionId, setSelectedSectionId] = useState(sections[0]?.id || '')
  const [category, setCategory] = useState('recitals_background')
  const [templateKey, setTemplateKey] = useState('')
  const [actionType, setActionType] = useState('replace_clause')
  const [proposedText, setProposedText] = useState('')
  const [reason, setReason] = useState('')

  useEffect(() => {
    setSelectedSectionId((current) => current || sections[0]?.id || '')
  }, [sections])

  useEffect(() => {
    let cancelled = false
    setIsLoadingTemplates(true)
    api.get<TemplateResponse>('/agreement-exchange/templates/')
      .then(({ data }) => {
        if (!cancelled) setTemplates(data.categories || {})
      })
      .catch(() => {
        if (!cancelled) setError('Request templates could not be loaded.')
      })
      .finally(() => {
        if (!cancelled) setIsLoadingTemplates(false)
      })
    return () => { cancelled = true }
  }, [])

  const categoryTemplates = templates[category] || []
  const selectedTemplate = useMemo(() => categoryTemplates.find((template) => template.key === templateKey), [categoryTemplates, templateKey])
  const selectedSection = sections.find((section) => section.id === selectedSectionId)

  useEffect(() => {
    const first = categoryTemplates[0]
    setTemplateKey(first?.key || '')
    setProposedText(first?.default_text || '')
  }, [category])

  useEffect(() => {
    if (selectedTemplate) setProposedText(selectedTemplate.default_text)
  }, [selectedTemplate])

  async function submitRequest() {
    if (!proposedText.trim()) {
      setError('Proposed text is required.')
      return
    }

    setIsSubmitting(true)
    setError('')
    setSuccess('')
    try {
      const { data } = await api.post<AgreementExchangeSaveResponse>(`/agreement-exchange/${exchangeId}/requests/`, {
        target_section_id: selectedSection?.id || null,
        target_section_title: selectedSection?.name || '',
        request_category: category,
        action_type: actionType,
        template_key: templateKey || null,
        proposed_text: proposedText,
        reason,
      })
      onSaved(data.request, data.exchange)
      setSuccess('Request sent to initiator.')
    } catch (err: any) {
      setError(err?.response?.data?.proposed_text?.[0] || err?.response?.data?.detail || err?.response?.data?.error || 'Request could not be saved.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <div>
        <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.12em', color: '#64748B', fontWeight: 800, margin: '0 0 6px' }}>Contract section</p>
        {sections.length ? (
          <select value={selectedSectionId} onChange={(event) => setSelectedSectionId(event.target.value)} style={{ width: '100%', height: 34, border: '1px solid #CBD5E1', borderRadius: 8, padding: '0 9px', fontSize: 12, color: '#243447', background: 'white' }}>
            {sections.map((section) => <option key={section.id} value={section.id}>{section.number}. {section.name}</option>)}
          </select>
        ) : (
          <p style={{ fontSize: 12, color: '#9CA3AF', margin: 0 }}>No contract sections available yet.</p>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 10 }}>
        <div>
          <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.12em', color: '#64748B', fontWeight: 800, margin: '0 0 6px' }}>Category</p>
          <select value={category} onChange={(event) => setCategory(event.target.value)} style={{ width: '100%', height: 34, border: '1px solid #CBD5E1', borderRadius: 8, padding: '0 9px', fontSize: 12, color: '#243447', background: 'white' }}>
            {Object.entries(CATEGORY_LABELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select>
        </div>
        <div>
          <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.12em', color: '#64748B', fontWeight: 800, margin: '0 0 6px' }}>Proposed Text Template</p>
          <select value={templateKey} onChange={(event) => setTemplateKey(event.target.value)} disabled={isLoadingTemplates || !categoryTemplates.length} style={{ width: '100%', height: 34, border: '1px solid #CBD5E1', borderRadius: 8, padding: '0 9px', fontSize: 12, color: '#243447', background: 'white' }}>
            {categoryTemplates.map((template) => <option key={template.key} value={template.key}>{template.label}</option>)}
          </select>
        </div>
      </div>

      <div>
        <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.12em', color: '#64748B', fontWeight: 800, margin: '0 0 6px' }}>Action type</p>
        <select value={actionType} onChange={(event) => setActionType(event.target.value)} style={{ width: '100%', height: 34, border: '1px solid #CBD5E1', borderRadius: 8, padding: '0 9px', fontSize: 12, color: '#243447', background: 'white' }}>
          {ACTION_OPTIONS.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
      </div>

      <div>
        <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.12em', color: '#64748B', fontWeight: 800, margin: '0 0 6px' }}>Proposed text</p>
        <textarea value={proposedText} onChange={(event) => setProposedText(event.target.value)} style={{ width: '100%', minHeight: 96, border: '1px solid #CBD5E1', borderRadius: 8, padding: 10, fontSize: 12, color: '#0F1F3D', lineHeight: 1.5, fontFamily: 'inherit', resize: 'vertical', boxSizing: 'border-box' }} />
      </div>

      <div>
        <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.12em', color: '#64748B', fontWeight: 800, margin: '0 0 6px' }}>Reason</p>
        <textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Optional reason or message" style={{ width: '100%', minHeight: 70, border: '1px solid #CBD5E1', borderRadius: 8, padding: 10, fontSize: 12, color: '#0F1F3D', lineHeight: 1.5, fontFamily: 'inherit', resize: 'vertical', boxSizing: 'border-box' }} />
      </div>

      {error && <p style={{ fontSize: 12, color: '#B91C1C', margin: 0 }}>{error}</p>}
      {success && <p style={{ fontSize: 12, color: '#047857', margin: 0 }}>{success}</p>}
      <button type="button" onClick={submitRequest} disabled={isSubmitting || !proposedText.trim()} style={{ justifySelf: 'start', height: 34, padding: '0 12px', border: 'none', borderRadius: 8, background: isSubmitting || !proposedText.trim() ? '#94A3B8' : '#243447', color: 'white', fontSize: 12, fontWeight: 800, cursor: isSubmitting || !proposedText.trim() ? 'default' : 'pointer' }}>
        {isSubmitting ? 'Submitting...' : 'Submit Request'}
      </button>
    </div>
  )
}

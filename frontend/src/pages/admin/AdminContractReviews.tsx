import { useEffect, useMemo, useState } from 'react'
import { AdminBadge, AdminTable } from './adminShared'

type ReviewType = 'analysis_only' | 'analysis_plus_counter'

type ReviewClause = {
  clause_reference?: string
  concern?: string
  counter_language?: string
}

type ReviewStrategy = {
  push_on?: string[]
  concede?: string[]
}

type AnalysisResult = {
  summary?: string
  key_terms?: Record<string, unknown>
  red_flags?: string[]
  questions?: string[]
}

type CounterResult = {
  summary?: string
  concerning_clauses?: ReviewClause[]
  negotiation_strategy?: ReviewStrategy
  revised_contract?: string
}

type SavedContractReview = {
  id: string
  backend_contract_id?: string
  title?: string
  review_type?: ReviewType
  source_label?: string
  original_contract_text?: string
  analysis_result?: AnalysisResult
  counter_result?: CounterResult
  summary?: string
  concerning_clauses?: ReviewClause[]
  negotiation_strategy?: ReviewStrategy
  revised_contract?: string
  saved_at?: string
}

const CONTRACT_REVIEWS_STORAGE_KEY = 'bb_contract_reviews'
const LEGACY_COUNTER_DRAFTS_STORAGE_KEY = 'bb_counter_drafts'

function normalizeReview(review: SavedContractReview): SavedContractReview {
  return {
    ...review,
    id: review.id || `local-review-${Date.now()}`,
    title: review.title || 'Contract Review',
    review_type: review.review_type || 'analysis_plus_counter',
    source_label: review.source_label || 'Saved review',
    saved_at: review.saved_at || new Date().toISOString(),
  }
}

function loadStoredReviews(): SavedContractReview[] {
  const saved = JSON.parse(localStorage.getItem(CONTRACT_REVIEWS_STORAGE_KEY) || '[]')
  const savedReviews = Array.isArray(saved) ? saved.map(normalizeReview) : []

  const legacy = JSON.parse(localStorage.getItem(LEGACY_COUNTER_DRAFTS_STORAGE_KEY) || '[]')
  const legacyReviews = Array.isArray(legacy)
    ? legacy.map((draft: SavedContractReview) => normalizeReview({
        ...draft,
        review_type: 'analysis_plus_counter',
        source_label: draft.source_label || 'Legacy counter draft',
        counter_result: draft.counter_result || {
          summary: draft.summary,
          concerning_clauses: draft.concerning_clauses || [],
          negotiation_strategy: draft.negotiation_strategy || {},
          revised_contract: draft.revised_contract,
        },
      }))
    : []

  return [...savedReviews, ...legacyReviews].sort((a, b) => {
    return new Date(b.saved_at || 0).getTime() - new Date(a.saved_at || 0).getTime()
  })
}

function getReviewTypeLabel(review: SavedContractReview) {
  return review.review_type === 'analysis_only' ? 'Analysis only' : 'Analysis + Counter'
}

function getSummary(review: SavedContractReview) {
  return review.analysis_result?.summary || review.counter_result?.summary || review.summary || ''
}

function getClauses(review: SavedContractReview) {
  return review.counter_result?.concerning_clauses || review.concerning_clauses || []
}

function getStrategy(review: SavedContractReview) {
  return review.counter_result?.negotiation_strategy || review.negotiation_strategy || {}
}

function getRevisedContract(review: SavedContractReview) {
  return review.counter_result?.revised_contract || review.revised_contract || ''
}

function hasCounterDetails(review: SavedContractReview) {
  return Boolean(
    review.counter_result ||
    getClauses(review).length ||
    getStrategy(review).push_on?.length ||
    getStrategy(review).concede?.length ||
    getRevisedContract(review),
  )
}

function formatSavedAt(value?: string) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString()
}

export default function AdminContractReviews() {
  const [reviews, setReviews] = useState<SavedContractReview[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [loadError, setLoadError] = useState('')

  useEffect(() => {
    try {
      const loaded = loadStoredReviews()
      setReviews(loaded)
      setSelectedId((current) => current || loaded[0]?.id || '')
      setLoadError('')
    } catch {
      setReviews([])
      setSelectedId('')
      setLoadError('Could not load local contract review records.')
    }
  }, [])

  const selectedReview = useMemo(
    () => reviews.find((review) => review.id === selectedId) || null,
    [reviews, selectedId],
  )

  return (
    <div className="space-y-4">
      <div style={{
        background: '#fff',
        borderRadius: 11,
        border: '1px solid rgba(0,0,0,0.07)',
        padding: 18,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'flex-start' }}>
          <div>
            <p style={{
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
              color: '#9CA3AF',
              margin: '0 0 8px',
            }}>
              Operator Console
            </p>
            <h2 style={{ fontSize: 20, fontWeight: 700, color: '#0F1F3D', margin: 0 }}>
              Contract Reviews
            </h2>
            <p style={{ fontSize: 13, color: '#6B7280', lineHeight: 1.6, margin: '8px 0 0', maxWidth: 720 }}>
              Shows locally saved Contract Review records from this browser, including analysis-only reviews and reviews with counter-contract drafts.
            </p>
          </div>
          <AdminBadge label={`${reviews.length} local`} style="sky" />
        </div>
        <div style={{
          marginTop: 14,
          borderRadius: 8,
          border: '1px solid #E5E7EB',
          background: '#F9FAFB',
          padding: '10px 12px',
          fontSize: 12,
          color: '#6B7280',
          lineHeight: 1.5,
        }}>
          Backend operator-wide records are not wired yet. This page is the interim admin view for reviews saved by the current local workflow.
        </div>
      </div>

      {loadError && <p style={{ fontSize: 13, color: '#B91C1C' }}>{loadError}</p>}

      <AdminTable
        loading={false}
        empty={!loadError && reviews.length === 0}
        headers={['Review', 'Type', 'Source', 'Record', 'Saved', 'Status']}
      >
        {reviews.map((review) => (
          <tr
            key={review.id}
            className="hover:bg-slate-50"
            style={{ cursor: 'pointer' }}
            onClick={() => setSelectedId(review.id)}
          >
            <td className="px-4 py-3 text-sm font-medium text-slate-800">
              {review.title || 'Contract Review'}
            </td>
            <td className="px-4 py-3">
              <AdminBadge
                label={getReviewTypeLabel(review)}
                style={review.review_type === 'analysis_only' ? 'blue' : 'navy'}
              />
            </td>
            <td className="px-4 py-3 text-sm text-slate-500">{review.source_label || 'Saved review'}</td>
            <td className="px-4 py-3 font-mono text-xs text-slate-400">
              {review.backend_contract_id ? `Contract ${review.backend_contract_id}` : review.id}
            </td>
            <td className="px-4 py-3 text-xs text-slate-400">{formatSavedAt(review.saved_at)}</td>
            <td className="px-4 py-3">
              <AdminBadge label="Local" style="yellow" />
            </td>
          </tr>
        ))}
      </AdminTable>

      {selectedReview && (
        <div style={{
          background: '#fff',
          borderRadius: 11,
          border: '1px solid rgba(0,0,0,0.07)',
          padding: 22,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'flex-start', marginBottom: 20 }}>
            <div>
              <h3 style={{ fontSize: 17, fontWeight: 700, color: '#0F1F3D', margin: 0 }}>
                {selectedReview.title || 'Contract Review'}
              </h3>
              <p style={{ fontSize: 12, color: '#9CA3AF', margin: '5px 0 0', fontFamily: 'monospace' }}>
                {selectedReview.backend_contract_id ? `Contract ${selectedReview.backend_contract_id}` : selectedReview.id}
              </p>
            </div>
            <AdminBadge label={getReviewTypeLabel(selectedReview)} style={selectedReview.review_type === 'analysis_only' ? 'blue' : 'navy'} />
          </div>

          <div className="space-y-5 text-sm text-slate-700">
            <section>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Summary</h4>
              <p className="whitespace-pre-wrap leading-6">{getSummary(selectedReview) || 'No summary saved.'}</p>
            </section>

            {selectedReview.analysis_result?.red_flags?.length ? (
              <section>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Red Flags</h4>
                <ul className="space-y-2">
                  {selectedReview.analysis_result.red_flags.map((flag, index) => (
                    <li key={index} className="rounded-md bg-slate-50 p-3">{flag}</li>
                  ))}
                </ul>
              </section>
            ) : null}

            {hasCounterDetails(selectedReview) ? (
              <>
                <section>
                  <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Concerning Clauses</h4>
                  {getClauses(selectedReview).length ? (
                    <ul className="space-y-3">
                      {getClauses(selectedReview).map((clause, index) => (
                        <li key={index} className="rounded-md bg-slate-50 p-3">
                          <p className="font-semibold text-slate-800">{clause.clause_reference || 'Clause'}</p>
                          <p className="mt-1 leading-6">{clause.concern || 'No concern saved.'}</p>
                          {clause.counter_language && (
                            <p className="mt-2 leading-6 text-slate-500">Counter language: {clause.counter_language}</p>
                          )}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-slate-500">Counter details were saved, but no clause list was included.</p>
                  )}
                </section>

                <section>
                  <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Negotiation Strategy</h4>
                  <p className="mb-1">
                    <span className="font-semibold text-slate-800">Push on:</span>{' '}
                    {(getStrategy(selectedReview).push_on || []).join(', ') || 'No push strategy saved.'}
                  </p>
                  <p>
                    <span className="font-semibold text-slate-800">Concede:</span>{' '}
                    {(getStrategy(selectedReview).concede || []).join(', ') || 'No concession strategy saved.'}
                  </p>
                </section>

                <section>
                  <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Revised Contract</h4>
                  <div className="max-h-[520px] overflow-auto rounded-md bg-slate-50 p-4 text-xs leading-6 text-slate-700 whitespace-pre-wrap">
                    {getRevisedContract(selectedReview) || 'No revised contract saved.'}
                  </div>
                </section>
              </>
            ) : (
              <section>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Counter-Contract</h4>
                <p className="text-slate-500">This saved review does not include a generated counter-contract.</p>
              </section>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

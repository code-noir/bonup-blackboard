import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import api from '@/api/client'
import type { BillingInterval, PackageDraft, StoreCheckoutCreateResponse, StoreQuote, StoreQuoteError, StoreQuoteItem, StoreQuoteRequest, StoreReviewLocationState } from '@/types/subscriptionCatalog'

type QuoteState =
  | { status: 'idle'; quote: null; error: null }
  | { status: 'loading'; quote: null; error: null }
  | { status: 'success'; quote: StoreQuote; error: null }
  | { status: 'error'; quote: null; error: StoreQuoteError }

function isPackageDraft(value: unknown): value is PackageDraft {
  if (!value || typeof value !== 'object') return false
  const draft = value as PackageDraft
  return (
    Array.isArray(draft.toolSlugs) &&
    draft.toolSlugs.every((slug) => typeof slug === 'string') &&
    (draft.storageProductSlug === null || typeof draft.storageProductSlug === 'string') &&
    (draft.aiProductSlug === null || typeof draft.aiProductSlug === 'string') &&
    (draft.billingInterval === 'monthly' || draft.billingInterval === 'annual')
  )
}

function displayInterval(value: BillingInterval) {
  return value === 'annual' ? 'Annual' : 'Monthly'
}

function formatMoney(amount: string, currency: string) {
  return currency === 'USD' ? `$${amount}` : `${amount} ${currency}`
}

function buildQuoteRequest(draft: PackageDraft): StoreQuoteRequest {
  return {
    tools: draft.toolSlugs.map((slug) => ({
      slug,
      billing_interval: draft.billingInterval,
    })),
    storage_product_slug: draft.storageProductSlug,
    ai_product_slug: draft.aiProductSlug,
  }
}

function isQuoteError(value: unknown): value is StoreQuoteError {
  return !!value && typeof value === 'object'
}

function quoteErrorFrom(error: unknown): StoreQuoteError {
  if (error && typeof error === 'object' && 'response' in error) {
    const response = (error as { response?: { data?: unknown } }).response
    if (isQuoteError(response?.data)) return response.data
  }
  return { detail: 'Store quote could not be loaded.' }
}

function quoteErrorMessage(error: StoreQuoteError) {
  if (error.code === 'storage_ineligible') return 'Selected additional Storage cannot currently be purchased.'
  if (error.detail) return error.detail
  return 'Store quote could not be loaded.'
}

type CheckoutError = {
  code?: string
  detail?: string
  error?: unknown
}

function isCheckoutError(value: unknown): value is CheckoutError {
  return !!value && typeof value === 'object'
}

function checkoutErrorFrom(error: unknown): CheckoutError {
  if (error && typeof error === 'object' && 'response' in error) {
    const response = (error as { response?: { data?: unknown } }).response
    if (isCheckoutError(response?.data)) return response.data
  }
  return { detail: 'Payment checkout could not be started.' }
}

function checkoutErrorMessage(error: CheckoutError) {
  if (error.code === 'payment_checkout_not_configured') return 'Payment checkout is not configured yet.'
  if (error.code === 'storage_ineligible') return 'Selected additional Storage cannot currently be purchased.'
  if (error.detail) return error.detail
  if (typeof error.error === 'string') return error.error
  return 'Payment checkout could not be started.'
}

export default function StoreReview() {
  const location = useLocation()
  const navigate = useNavigate()
  const draft = useMemo(() => {
    const state = location.state as StoreReviewLocationState | null
    return isPackageDraft(state?.draft) ? state.draft : null
  }, [location.state])
  const [quoteState, setQuoteState] = useState<QuoteState>({ status: draft ? 'loading' : 'idle', quote: null, error: null })
  const [quoteLoadKey, setQuoteLoadKey] = useState(0)
  const [checkoutPending, setCheckoutPending] = useState(false)
  const [checkoutError, setCheckoutError] = useState<string | null>(null)

  useEffect(() => {
    if (!draft) return
    let cancelled = false

    async function loadQuote() {
      setQuoteState({ status: 'loading', quote: null, error: null })
      try {
        const response = await api.post<StoreQuote>('/billing/quote/', buildQuoteRequest(draft))
        if (cancelled) return
        setQuoteState({ status: 'success', quote: response.data, error: null })
      } catch (error) {
        if (cancelled) return
        setQuoteState({ status: 'error', quote: null, error: quoteErrorFrom(error) })
      }
    }

    loadQuote()

    return () => {
      cancelled = true
    }
  }, [draft, quoteLoadKey])

  function editStore() {
    navigate('/store', draft ? { state: { draft } } : undefined)
  }

  async function continueToPayment() {
    if (!draft || quoteState.status !== 'success' || checkoutPending || quoteState.quote.items.length === 0) return
    setCheckoutPending(true)
    setCheckoutError(null)
    try {
      const response = await api.post<StoreCheckoutCreateResponse>('/billing/checkout/', buildQuoteRequest(draft))
      window.location.assign(response.data.checkout_url)
    } catch (error) {
      setCheckoutError(checkoutErrorMessage(checkoutErrorFrom(error)))
      setCheckoutPending(false)
    }
  }

  if (!draft) {
    return <EmptyReview onEdit={editStore} />
  }

  if (quoteState.status === 'loading') {
    return (
      <ReviewShell onEdit={editStore}>
        <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-semibold text-slate-700">Loading Store quote...</p>
          <p className="mt-1 text-sm text-slate-500">Validating your selections with bonUP.</p>
        </section>
      </ReviewShell>
    )
  }

  if (quoteState.status === 'error') {
    return (
      <ReviewShell onEdit={editStore}>
        <section className="rounded-lg border border-red-200 bg-red-50 p-6 shadow-sm">
          <p className="text-sm font-bold text-red-700">Store quote could not be loaded.</p>
          <p className="mt-1 text-sm text-red-700">{quoteErrorMessage(quoteState.error)}</p>
          <div className="mt-4 flex flex-wrap gap-3">
            <button type="button" onClick={() => setQuoteLoadKey((value) => value + 1)} className="h-10 rounded-lg bg-slate-900 px-4 text-sm font-bold text-white hover:bg-slate-800">
              Retry quote
            </button>
            <button type="button" onClick={editStore} className="h-10 rounded-lg border border-red-200 bg-white px-4 text-sm font-bold text-red-700 hover:bg-red-50">
              Return to Store
            </button>
          </div>
        </section>
      </ReviewShell>
    )
  }

  if (quoteState.status !== 'success') {
    return <EmptyReview onEdit={editStore} />
  }

  return (
    <ReviewShell onEdit={editStore}>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="mb-6">
            <p className="text-xs font-bold uppercase text-slate-400">Review</p>
            <h2 className="mt-1 text-2xl font-bold text-slate-900">Selected resources</h2>
          </div>

          <div className="space-y-5">
            <QuoteGroup title="Tools">
              {quoteState.quote.items.filter((item) => item.kind === 'tool').length > 0 ? quoteState.quote.items.filter((item) => item.kind === 'tool').map((item) => (
                <ToolReview key={item.product_slug} item={item} />
              )) : <EmptyLine>No Tools selected</EmptyLine>}
            </QuoteGroup>

            <QuoteGroup title="Additional Storage">
              {quoteState.quote.items.filter((item) => item.kind === 'storage').length > 0 ? quoteState.quote.items.filter((item) => item.kind === 'storage').map((item) => (
                <StorageReview key={item.product_slug} item={item} />
              )) : <EmptyLine>No additional Storage selected</EmptyLine>}
            </QuoteGroup>

            <QuoteGroup title="AI">
              {quoteState.quote.items.filter((item) => item.kind === 'ai').length > 0 ? quoteState.quote.items.filter((item) => item.kind === 'ai').map((item) => (
                <ReviewLine key={item.product_slug} label={item.name} value={formatMoney(item.amount, item.currency)} />
              )) : <EmptyLine>No additional AI selected</EmptyLine>}
            </QuoteGroup>
          </div>
        </section>

        <aside className="lg:sticky lg:top-6">
          <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
            <p className="text-xs font-bold uppercase text-slate-400">Quote</p>
            <h2 className="mt-1 text-2xl font-bold text-slate-900">Store review</h2>
            <div className="mt-6 space-y-4">
              <SummaryGroup label="Monthly recurring" value={formatMoney(quoteState.quote.totals.recurring.monthly, quoteState.quote.currency)} />
              <SummaryGroup label="Annual recurring" value={formatMoney(quoteState.quote.totals.recurring.annual, quoteState.quote.currency)} />
              <SummaryGroup label="One-time charge" value={formatMoney(quoteState.quote.totals.one_time, quoteState.quote.currency)} />
              <SummaryGroup label="Due today" value={formatMoney(quoteState.quote.totals.due_today, quoteState.quote.currency)} />
            </div>
            <button
              type="button"
              onClick={continueToPayment}
              disabled={checkoutPending || quoteState.quote.items.length === 0}
              className="mt-6 h-11 w-full rounded-lg bg-slate-900 px-5 text-sm font-bold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {checkoutPending ? 'Starting payment...' : 'Continue to payment'}
            </button>
            {checkoutError ? (
              <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3">
                <p className="text-xs font-semibold leading-5 text-red-700">{checkoutError}</p>
                <button type="button" onClick={editStore} className="mt-2 text-xs font-bold text-red-700 underline">
                  Return to Store
                </button>
              </div>
            ) : (
              <p className="mt-3 text-xs leading-5 text-slate-500">You will complete payment in Stripe Checkout.</p>
            )}
          </section>
        </aside>
      </div>
    </ReviewShell>
  )
}

function ToolReview({ item }: { item: Extract<StoreQuoteItem, { kind: 'tool' }> }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <span className="break-words text-sm font-semibold text-slate-900">{item.name}</span>
        <span className="break-words text-sm font-bold text-slate-700">{formatMoney(item.amount, item.currency)}</span>
      </div>
      <div className="mt-3 grid gap-2 text-xs font-semibold text-slate-600 sm:grid-cols-3">
        <span className="rounded-full bg-white px-2.5 py-1">{displayInterval(item.billing_interval)}</span>
        <span className="rounded-full bg-white px-2.5 py-1">Includes {item.included_storage_gib} GiB Storage</span>
        <span className="rounded-full bg-white px-2.5 py-1">{item.included_ai || 'AI'} AI included</span>
      </div>
    </div>
  )
}

function StorageReview({ item }: { item: Extract<StoreQuoteItem, { kind: 'storage' }> }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <span className="break-words text-sm font-semibold text-slate-900">{item.name}</span>
        <span className="break-words text-sm font-bold text-slate-700">{formatMoney(item.amount, item.currency)}</span>
      </div>
      <p className="mt-3 text-xs font-semibold text-slate-600">Adds {item.capacity_gib} GiB Storage.</p>
    </div>
  )
}

function ReviewShell({ children, onEdit }: { children: ReactNode; onEdit: () => void }) {
  return (
    <div className="mx-auto max-w-6xl py-8">
      <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="mb-2 text-xs font-bold uppercase text-[#D4900A]">bonUP</p>
          <h1 className="text-3xl font-bold text-slate-900">Review your Store selections</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-600">Confirm your selected Tools, Storage, AI resources, and charges.</p>
        </div>
        <button type="button" onClick={onEdit} className="h-10 rounded-lg border border-slate-300 bg-white px-4 text-sm font-bold text-slate-700 hover:bg-slate-50">
          Edit Store
        </button>
      </header>
      {children}
    </div>
  )
}

function EmptyReview({ onEdit }: { onEdit: () => void }) {
  return (
    <ReviewShell onEdit={onEdit}>
      <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-sm font-bold text-slate-900">No Store selections are ready to review.</p>
        <p className="mt-1 text-sm text-slate-600">Choose what you need in the Store before reviewing your total.</p>
        <button type="button" onClick={onEdit} className="mt-4 h-10 rounded-lg bg-slate-900 px-4 text-sm font-bold text-white hover:bg-slate-800">
          Go to Store
        </button>
      </section>
    </ReviewShell>
  )
}

function QuoteGroup({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-t border-slate-200 pt-5 first:border-t-0 first:pt-0">
      <h3 className="text-xs font-bold uppercase text-slate-400">{title}</h3>
      <div className="mt-3 space-y-3">{children}</div>
    </section>
  )
}

function ReviewLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-slate-200 bg-slate-50 p-4 sm:flex-row sm:items-center sm:justify-between">
      <span className="break-words text-sm font-semibold text-slate-900">{label}</span>
      <span className="break-words text-sm font-bold text-slate-700">{value}</span>
    </div>
  )
}

function EmptyLine({ children }: { children: ReactNode }) {
  return <p className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">{children}</p>
}

function SummaryGroup({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-t border-slate-200 pt-4 first:border-t-0 first:pt-0">
      <p className="text-xs font-bold uppercase text-slate-400">{label}</p>
      <p className="mt-1 break-words text-sm font-semibold text-slate-900">{value}</p>
    </div>
  )
}

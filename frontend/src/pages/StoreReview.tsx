import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import api from '@/api/client'
import type { BillingInterval, PackageDraft, StorageCatalogItem, StoreReviewLocationState, SubscriptionCatalog, ToolCatalogItem } from '@/types/subscriptionCatalog'

type CatalogState =
  | { status: 'idle'; data: null }
  | { status: 'loading'; data: null }
  | { status: 'success'; data: SubscriptionCatalog }
  | { status: 'error'; data: null }

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

function recurringLabel(value: BillingInterval) {
  return value === 'annual' ? 'year' : 'month'
}

function priceWithCurrency(amount: string, currency: string) {
  return currency === 'USD' ? `$${amount}` : `${amount} ${currency}`
}

function toolPrice(tool: ToolCatalogItem, interval: BillingInterval) {
  return interval === 'annual' ? tool.pricing.annual : tool.pricing.monthly
}

function allowanceLabel(value: string) {
  return value ? `${value.charAt(0).toUpperCase()}${value.slice(1)} AI` : 'AI'
}

function storagePrice(storage: StorageCatalogItem | null) {
  return storage ? Number(storage.price.amount) : 0
}

export default function StoreReview() {
  const location = useLocation()
  const navigate = useNavigate()
  const draft = useMemo(() => {
    const state = location.state as StoreReviewLocationState | null
    return isPackageDraft(state?.draft) ? state.draft : null
  }, [location.state])
  const [catalogState, setCatalogState] = useState<CatalogState>({ status: draft ? 'loading' : 'idle', data: null })

  useEffect(() => {
    if (!draft) return
    let cancelled = false

    async function loadCatalog() {
      setCatalogState({ status: 'loading', data: null })
      try {
        const response = await api.get<SubscriptionCatalog>('/billing/catalog/')
        if (cancelled) return
        setCatalogState({ status: 'success', data: response.data })
      } catch {
        if (cancelled) return
        setCatalogState({ status: 'error', data: null })
      }
    }

    loadCatalog()

    return () => {
      cancelled = true
    }
  }, [draft])

  function editStore() {
    navigate('/store', draft ? { state: { draft } } : undefined)
  }

  if (!draft) {
    return <EmptyReview onEdit={editStore} />
  }

  if (catalogState.status === 'loading') {
    return (
      <ReviewShell onEdit={editStore}>
        <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-semibold text-slate-700">Loading Store review...</p>
          <p className="mt-1 text-sm text-slate-500">Fetching the latest bonUP resources.</p>
        </section>
      </ReviewShell>
    )
  }

  if (catalogState.status === 'error') {
    return (
      <ReviewShell onEdit={editStore}>
        <section className="rounded-lg border border-red-200 bg-red-50 p-6 shadow-sm">
          <p className="text-sm font-bold text-red-700">Store review could not be loaded.</p>
          <p className="mt-1 text-sm text-red-700">Please return to the Store and try again.</p>
          <button type="button" onClick={editStore} className="mt-4 h-10 rounded-lg bg-slate-900 px-4 text-sm font-bold text-white">
            Edit Store
          </button>
        </section>
      </ReviewShell>
    )
  }

  if (catalogState.status !== 'success') {
    return <EmptyReview onEdit={editStore} />
  }

  const selectedTools = catalogState.data.tools.filter((tool) => draft.toolSlugs.includes(tool.slug))
  const selectedStorage = catalogState.data.storage.find((option) => option.slug === draft.storageProductSlug) ?? null
  const selectedAI = catalogState.data.ai.find((option) => option.slug === draft.aiProductSlug) ?? null
  const hasValidSelection = selectedTools.length > 0 || selectedStorage !== null || selectedAI !== null

  if (!hasValidSelection) {
    return <EmptyReview onEdit={editStore} />
  }

  const recurringItems = selectedTools.map((tool) => toolPrice(tool, draft.billingInterval))
  const recurringAmount = recurringItems.reduce((total, price) => total + Number(price.amount), 0)
  const recurringCurrency = recurringItems[0]?.currency ?? 'USD'
  const recurringValue = recurringItems.length > 0
    ? `${priceWithCurrency(recurringAmount.toFixed(2), recurringCurrency)} / ${recurringLabel(draft.billingInterval)}`
    : 'No recurring charge'
  const oneTimeValue = selectedStorage
    ? priceWithCurrency(storagePrice(selectedStorage).toFixed(2), selectedStorage.price.currency)
    : 'No one-time charge'

  return (
    <ReviewShell onEdit={editStore}>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="mb-6">
            <p className="text-xs font-bold uppercase text-slate-400">Review</p>
            <h2 className="mt-1 text-2xl font-bold text-slate-900">Selected resources</h2>
          </div>

          <div className="space-y-5">
            <ReviewGroup title="Tools">
              {selectedTools.length > 0 ? selectedTools.map((tool) => (
                <ReviewLine key={tool.slug} label={tool.name} value={priceWithCurrency(toolPrice(tool, draft.billingInterval).amount, toolPrice(tool, draft.billingInterval).currency)} />
              )) : <EmptyLine>No tools selected</EmptyLine>}
            </ReviewGroup>

            {selectedTools.map((tool) => (
              <ReviewGroup key={`${tool.slug}-included`} title={`Included with ${tool.name}`}>
                <ReviewLine label="Storage" value={`${tool.included_storage.gib} GiB`} />
                <ReviewLine label="AI" value={allowanceLabel(tool.included_ai_allowance || 'starter')} />
              </ReviewGroup>
            ))}

            <ReviewGroup title="Additional storage">
              {selectedStorage ? (
                <ReviewLine label={selectedStorage.name} value={priceWithCurrency(selectedStorage.price.amount, selectedStorage.price.currency)} />
              ) : <EmptyLine>No additional storage selected</EmptyLine>}
            </ReviewGroup>

            <ReviewGroup title="AI">
              {selectedAI ? <ReviewLine label={selectedAI.name} value="Selected" /> : <EmptyLine>No additional AI selected</EmptyLine>}
            </ReviewGroup>

            <ReviewGroup title="Billing">
              <ReviewLine label="Interval" value={displayInterval(draft.billingInterval)} />
            </ReviewGroup>
          </div>
        </section>

        <aside className="lg:sticky lg:top-6">
          <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
            <p className="text-xs font-bold uppercase text-slate-400">Total</p>
            <h2 className="mt-1 text-2xl font-bold text-slate-900">Store review</h2>
            <div className="mt-6 space-y-4">
              <SummaryGroup label="Recurring charge" value={recurringValue} />
              <SummaryGroup label="One-time charge" value={oneTimeValue} />
            </div>
            <button type="button" disabled className="mt-6 h-11 w-full rounded-lg bg-slate-900 px-5 text-sm font-bold text-white opacity-50">
              Continue to payment
            </button>
            <p className="mt-3 text-xs leading-5 text-slate-500">Payment is not connected yet.</p>
          </section>
        </aside>
      </div>
    </ReviewShell>
  )
}

function ReviewShell({ children, onEdit }: { children: ReactNode; onEdit: () => void }) {
  return (
    <div className="mx-auto max-w-6xl py-8">
      <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="mb-2 text-xs font-bold uppercase text-[#D4900A]">bonUP</p>
          <h1 className="text-3xl font-bold text-slate-900">Review your Store selections</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-600">Confirm your selected Tools, storage, AI resources, and charges.</p>
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

function ReviewGroup({ title, children }: { title: string; children: ReactNode }) {
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

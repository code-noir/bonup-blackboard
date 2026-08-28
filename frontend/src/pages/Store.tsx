import { useEffect, useMemo, useState } from 'react'
import { useLocation } from 'react-router-dom'
import api from '@/api/client'
import PackageBuilder from '@/components/subscription/PackageBuilder'
import type { BillingInterval, CustomerStoreState, PackageDraft, StoreReviewLocationState, SubscriptionCatalog } from '@/types/subscriptionCatalog'

type SubscriptionResponse =
  | {
      billing_period?: string | null
    }
  | { subscription: null }

type StoreLoadState =
  | { status: 'loading'; data: null }
  | { status: 'success'; data: { catalog: SubscriptionCatalog; storeState: CustomerStoreState } }
  | { status: 'error'; data: null }

function isSubscriptionResponse(value: SubscriptionResponse): value is { billing_period?: string | null } {
  return !('subscription' in value)
}

function normalizeBillingInterval(value: string | null | undefined): BillingInterval {
  return value === 'annual' || value === 'yearly' ? 'annual' : 'monthly'
}

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

export default function Store() {
  const location = useLocation()
  const initialDraft = useMemo(() => {
    const state = location.state as StoreReviewLocationState | null
    return isPackageDraft(state?.draft) ? state.draft : null
  }, [location.state])
  const [initialBillingInterval, setInitialBillingInterval] = useState<BillingInterval>('monthly')
  const [storeLoadState, setStoreLoadState] = useState<StoreLoadState>({ status: 'loading', data: null })
  const [catalogLoadKey, setCatalogLoadKey] = useState(0)

  useEffect(() => {
    let cancelled = false

    async function loadBillingInterval() {
      try {
        const response = await api.get<SubscriptionResponse>('/billing/subscription/')
        if (cancelled || !isSubscriptionResponse(response.data)) return
        setInitialBillingInterval(normalizeBillingInterval(response.data.billing_period))
      } catch {
        if (cancelled) return
        setInitialBillingInterval('monthly')
      }
    }

    loadBillingInterval()

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function loadStore() {
      setStoreLoadState({ status: 'loading', data: null })
      try {
        const [catalogResponse, stateResponse] = await Promise.all([
          api.get<SubscriptionCatalog>('/billing/catalog/'),
          api.get<CustomerStoreState>('/billing/store/state/'),
        ])
        if (cancelled) return
        setStoreLoadState({ status: 'success', data: { catalog: catalogResponse.data, storeState: stateResponse.data } })
      } catch {
        if (cancelled) return
        setStoreLoadState({ status: 'error', data: null })
      }
    }

    loadStore()

    return () => {
      cancelled = true
    }
  }, [catalogLoadKey])

  return (
    <div className="mx-auto max-w-6xl py-8">
      <header className="mb-8">
        <p className="mb-2 text-xs font-bold uppercase text-[#D4900A]">bonUP</p>
        <h1 className="text-3xl font-bold text-slate-900">Store</h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-600">
          Choose the Tools and resources you want.
        </p>
      </header>

      {storeLoadState.status === 'loading' && <CatalogLoadingState />}

      {storeLoadState.status === 'error' && (
        <CatalogErrorState onRetry={() => setCatalogLoadKey((value) => value + 1)} />
      )}

      {storeLoadState.status === 'success' && (
        <PackageBuilder
          catalog={storeLoadState.data.catalog}
          storeState={storeLoadState.data.storeState}
          initialBillingInterval={initialBillingInterval}
          initialDraft={initialDraft}
        />
      )}
    </div>
  )
}

function CatalogLoadingState() {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <p className="text-sm font-semibold text-slate-700">Loading Store options...</p>
      <p className="mt-1 text-sm text-slate-500">Fetching the latest bonUP resources.</p>
    </section>
  )
}

function CatalogErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <section className="rounded-lg border border-red-200 bg-red-50 p-6 shadow-sm">
      <p className="text-sm font-bold text-red-700">Store options could not be loaded.</p>
      <p className="mt-1 text-sm text-red-700">Please try again. If this continues, contact support.</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-4 h-10 rounded-lg bg-slate-900 px-4 text-sm font-bold text-white"
      >
        Retry
      </button>
    </section>
  )
}

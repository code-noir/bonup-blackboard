import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import api from '@/api/client'
import type { StoreCheckoutStatus, StoreCheckoutStatusItem } from '@/types/subscriptionCatalog'

type PaymentState =
  | { status: 'loading'; data: null; error: null }
  | { status: 'success'; data: StoreCheckoutStatus; error: null }
  | { status: 'error'; data: null; error: string }

function statusTitle(data: StoreCheckoutStatus) {
  if (data.fulfilled) return 'Your purchase is ready.'
  if (data.status === 'failed' || data.status === 'expired') return 'Payment was not completed.'
  if (data.status === 'paid') return 'Payment confirmed.'
  return 'Processing payment...'
}

function fulfilledMessage(items: StoreCheckoutStatusItem[]) {
  const hasTool = items.some((item) => item.kind === 'tool')
  const storage = items.find((item) => item.kind === 'storage')
  if (hasTool && storage) return 'Blackbòd is active and your additional Storage has been added to your Vault.'
  if (hasTool) return 'Blackbòd is now active.'
  if (storage?.capacity_gib) return `${storage.capacity_gib} GiB has been added to your Vault.`
  return 'Your Store purchase is ready.'
}

export default function StorePaymentSuccess() {
  const [searchParams] = useSearchParams()
  const sessionId = searchParams.get('session_id')
  const [paymentState, setPaymentState] = useState<PaymentState>({ status: 'loading', data: null, error: null })

  useEffect(() => {
    if (!sessionId) {
      setPaymentState({ status: 'error', data: null, error: 'Checkout session was not found.' })
      return
    }

    let cancelled = false
    async function loadStatus() {
      try {
        const response = await api.get<StoreCheckoutStatus>(`/billing/checkout/${encodeURIComponent(sessionId)}/status/`)
        if (!cancelled) setPaymentState({ status: 'success', data: response.data, error: null })
      } catch {
        if (!cancelled) setPaymentState({ status: 'error', data: null, error: 'Payment status could not be loaded.' })
      }
    }

    loadStatus()
    const interval = window.setInterval(loadStatus, 3000)
    return () => {
      cancelled = true
      window.clearInterval(interval)
    }
  }, [sessionId])

  const items = useMemo(() => paymentState.data?.items ?? [], [paymentState.data])
  const hasTool = items.some((item) => item.kind === 'tool')
  const hasStorage = items.some((item) => item.kind === 'storage')

  return (
    <div className="mx-auto max-w-3xl py-8">
      <header className="mb-8">
        <p className="mb-2 text-xs font-bold uppercase text-[#D4900A]">bonUP</p>
        <h1 className="text-3xl font-bold text-slate-900">Payment result</h1>
      </header>

      <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        {paymentState.status === 'loading' ? (
          <div>
            <p className="text-lg font-bold text-slate-900">Processing payment...</p>
            <p className="mt-2 text-sm text-slate-600">Waiting for bonUP payment confirmation.</p>
          </div>
        ) : paymentState.status === 'error' ? (
          <div>
            <p className="text-lg font-bold text-slate-900">Payment status unavailable.</p>
            <p className="mt-2 text-sm text-slate-600">{paymentState.error}</p>
          </div>
        ) : (
          <div>
            <p className="text-lg font-bold text-slate-900">{statusTitle(paymentState.data)}</p>
            <p className="mt-2 text-sm text-slate-600">
              {paymentState.data.fulfilled
                ? fulfilledMessage(items)
                : paymentState.data.status === 'failed' || paymentState.data.status === 'expired'
                  ? 'No Store resources were granted.'
                  : 'Your browser return does not prove payment; fulfillment waits for Stripe verification.'}
            </p>
          </div>
        )}

        <div className="mt-6 flex flex-wrap gap-3">
          <Link to="/store" className="inline-flex h-10 items-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-bold text-slate-700 hover:bg-slate-50">
            View Your Products
          </Link>
          {hasStorage ? (
            <Link to="/vault" className="inline-flex h-10 items-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-bold text-slate-700 hover:bg-slate-50">
              Open Vault
            </Link>
          ) : null}
          {hasTool ? (
            <Link to="/apps/blackbod" className="inline-flex h-10 items-center rounded-lg bg-slate-900 px-4 text-sm font-bold text-white hover:bg-slate-800">
              Open Blackbòd
            </Link>
          ) : null}
        </div>
      </section>
    </div>
  )
}

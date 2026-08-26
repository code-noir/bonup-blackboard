import { useEffect, useState } from 'react'
import api from '@/api/client'
import { useAuth } from '@/context/AuthContext'
import PackageBuilder, { type BillingInterval } from '@/components/subscription/PackageBuilder'

type SubscriptionResponse =
  | {
      billing_period?: string | null
    }
  | { subscription: null }

function isSubscriptionResponse(value: SubscriptionResponse): value is { billing_period?: string | null } {
  return !('subscription' in value)
}

function normalizeBillingInterval(value: string | null | undefined): BillingInterval {
  return value === 'annual' || value === 'yearly' ? 'annual' : 'monthly'
}

export default function Subscription() {
  const { user } = useAuth()
  const [initialBillingInterval, setInitialBillingInterval] = useState<BillingInterval>('monthly')

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

  return (
    <div className="mx-auto max-w-6xl py-8">
      <header className="mb-8">
        <p className="mb-2 text-xs font-bold uppercase text-[#D4900A]">bonUP</p>
        <h1 className="text-3xl font-bold text-slate-900">Subscription</h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-600">Build your bonUP package.</p>
      </header>

      <PackageBuilder
        hasBlackbodAccess={user?.has_blackbod_access === true}
        accessKnown={typeof user?.has_blackbod_access === 'boolean'}
        initialBillingInterval={initialBillingInterval}
      />
    </div>
  )
}

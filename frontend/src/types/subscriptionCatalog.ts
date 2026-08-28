export type BillingInterval = 'monthly' | 'annual'

export type CatalogMoney = {
  amount: string
  currency: string
}

export type ToolCatalogItem = {
  slug: string
  name: string
  product_type: 'tool'
  active: boolean
  pricing: {
    monthly: CatalogMoney
    annual: CatalogMoney
  }
  included_storage: {
    bytes: number
    gib: number
  }
  included_ai_allowance: string
}

export type StorageCatalogItem = {
  slug: string
  name: string
  product_type: 'storage'
  capacity: {
    bytes: number
    gib: number
  }
  price: {
    type: 'one_time' | string
    amount: string
    currency: string
  }
}

export type AICatalogItem = {
  slug: string
  name: string
  product_type?: 'ai' | string
  [key: string]: unknown
}

export type SubscriptionCatalog = {
  tools: ToolCatalogItem[]
  storage: StorageCatalogItem[]
  ai: AICatalogItem[]
}

export type PackageDraft = {
  toolSlugs: string[]
  storageProductSlug: string | null
  aiProductSlug: string | null
  billingInterval: BillingInterval
}

export type StoreReviewLocationState = {
  draft?: PackageDraft
}

export type StoreQuoteToolSelection = {
  slug: string
  billing_interval: BillingInterval
}

export type StoreQuoteRequest = {
  tools: StoreQuoteToolSelection[]
  storage_product_slug: string | null
  ai_product_slug: string | null
}

export type StoreQuoteItem =
  | {
      kind: 'tool'
      product_slug: string
      name: string
      billing_interval: BillingInterval
      charge_type: 'recurring'
      amount: string
      currency: string
      included_storage_bytes: number
      included_storage_gib: number
      included_ai: string
    }
  | {
      kind: 'storage'
      product_slug: string
      name: string
      charge_type: 'one_time'
      amount: string
      currency: string
      capacity_bytes: number
      capacity_gib: number
      eligibility?: {
        eligible: boolean
        reason: string
      }
    }
  | {
      kind: 'ai'
      product_slug: string
      name: string
      charge_type: 'recurring' | 'one_time'
      amount: string
      currency: string
      [key: string]: unknown
    }

export type StoreQuote = {
  currency: string
  items: StoreQuoteItem[]
  totals: {
    recurring: {
      monthly: string
      annual: string
    }
    one_time: string
    due_today: string
  }
}

export type StoreQuoteError = {
  code?: string
  detail?: string
  error?: unknown
}

export type StoreEligibilityRequest = {
  tools: StoreQuoteToolSelection[]
  ai_product_slug: string | null
  storage_product_slugs: string[]
}

export type StoreStorageEligibilityResult = {
  eligible: boolean
  code: string
  message: string
}

export type StoreEligibility = {
  storage: Record<string, StoreStorageEligibilityResult>
}

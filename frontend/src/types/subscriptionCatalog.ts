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

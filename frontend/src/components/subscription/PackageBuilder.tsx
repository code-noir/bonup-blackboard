import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { ReactNode } from 'react'
import api from '@/api/client'
import type { BillingInterval, CustomerStoreState, PackageDraft, StorageCatalogItem, StoreEligibility, StoreEligibilityRequest, StoreStorageEligibilityResult, StoreToolState, SubscriptionCatalog, ToolCatalogItem } from '@/types/subscriptionCatalog'

export type { BillingInterval } from '@/types/subscriptionCatalog'

type PackageBuilderProps = {
  catalog: SubscriptionCatalog
  storeState: CustomerStoreState
  initialBillingInterval: BillingInterval
  initialDraft?: PackageDraft | null
}

type EligibilityState =
  | { status: 'loading'; data: null }
  | { status: 'success'; data: StoreEligibility }
  | { status: 'error'; data: null }

const STORAGE_ELIGIBILITY_ERROR_MESSAGE = 'Storage availability could not be checked. Additional Storage is temporarily unavailable.'

function toolStateFor(storeState: CustomerStoreState, slug: string): StoreToolState | null {
  return storeState.tools[slug] ?? null
}

function toolIsPurchasable(storeState: CustomerStoreState, slug: string) {
  return toolStateFor(storeState, slug)?.purchasable !== false
}

function sanitizeDraft(draft: PackageDraft, storeState: CustomerStoreState): PackageDraft {
  const toolSlugs = draft.toolSlugs.filter((slug) => toolIsPurchasable(storeState, slug))
  return {
    ...draft,
    toolSlugs,
    aiProductSlug: toolSlugs.length > 0 ? draft.aiProductSlug : null,
  }
}

function activeToolAiAllowance(catalog: SubscriptionCatalog, storeState: CustomerStoreState) {
  return catalog.tools.find((tool) => toolStateFor(storeState, tool.slug)?.active && toolStateFor(storeState, tool.slug)?.included_ai)?.included_ai_allowance ?? ''
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

function formatToolPrice(tool: ToolCatalogItem, interval: BillingInterval) {
  const price = toolPrice(tool, interval)
  return `${priceWithCurrency(price.amount, price.currency)} / ${recurringLabel(interval)}`
}

function formatStoragePrice(storage: StorageCatalogItem) {
  return `${priceWithCurrency(storage.price.amount, storage.price.currency)} one-time`
}

function allowanceLabel(value: string) {
  return value ? `${value.charAt(0).toUpperCase()}${value.slice(1)} AI included` : 'AI included'
}

function storageEligibilityFor(state: EligibilityState, slug: string): StoreStorageEligibilityResult | null {
  return state.status === 'success' ? state.data.storage[slug] ?? null : null
}

function storageIsSelectable(state: EligibilityState, slug: string) {
  return storageEligibilityFor(state, slug)?.eligible === true
}

function storageSectionMessage(state: EligibilityState, storage: StorageCatalogItem[], clearedMessage: string | null) {
  if (clearedMessage) return clearedMessage
  if (state.status === 'loading') return 'Checking Storage availability for your current selection.'
  if (state.status === 'error') return STORAGE_ELIGIBILITY_ERROR_MESSAGE

  const firstIneligible = storage
    .map((option) => state.data.storage[option.slug])
    .find((result) => result && !result.eligible)
  const allUnavailable = storage.length > 0 && storage.every((option) => state.data.storage[option.slug]?.eligible === false)
  return allUnavailable ? firstIneligible?.message ?? null : null
}

export default function PackageBuilder({
  catalog,
  storeState,
  initialBillingInterval,
  initialDraft = null,
}: PackageBuilderProps) {
  const navigate = useNavigate()
  const [draft, setDraft] = useState<PackageDraft>(() => sanitizeDraft(initialDraft ?? {
    toolSlugs: [],
    storageProductSlug: null,
    aiProductSlug: null,
    billingInterval: 'monthly',
  }, storeState))
  const [eligibilityState, setEligibilityState] = useState<EligibilityState>({ status: 'loading', data: null })
  const [eligibilityLoadKey, setEligibilityLoadKey] = useState(0)
  const [clearedStorageMessage, setClearedStorageMessage] = useState<string | null>(null)

  useEffect(() => {
    setDraft((current) => sanitizeDraft(current, storeState))
  }, [storeState])

  useEffect(() => {
    if (initialDraft) return
    setDraft((current) => sanitizeDraft({
      ...current,
      billingInterval: initialBillingInterval,
    }, storeState))
  }, [initialBillingInterval, initialDraft, storeState])

  const selectedTools = useMemo(
    () => catalog.tools.filter((tool) => draft.toolSlugs.includes(tool.slug)),
    [catalog.tools, draft.toolSlugs],
  )
  const selectedStorage = catalog.storage.find((option) => option.slug === draft.storageProductSlug) ?? null
  const selectedToolAiAllowance = selectedTools.find((tool) => tool.included_ai_allowance)?.included_ai_allowance ?? ''
  const activeAiAllowance = activeToolAiAllowance(catalog, storeState)
  const representedAiAllowance = selectedToolAiAllowance || activeAiAllowance

  const eligibilityRequest = useMemo<StoreEligibilityRequest>(() => ({
    tools: draft.toolSlugs.map((slug) => ({
      slug,
      billing_interval: draft.billingInterval,
    })),
    ai_product_slug: draft.aiProductSlug,
    storage_product_slugs: catalog.storage.map((option) => option.slug),
  }), [catalog.storage, draft.aiProductSlug, draft.billingInterval, draft.toolSlugs])

  useEffect(() => {
    let cancelled = false

    async function loadEligibility() {
      setEligibilityState({ status: 'loading', data: null })
      try {
        const response = await api.post<StoreEligibility>('/billing/store/eligibility/', eligibilityRequest)
        if (cancelled) return
        setEligibilityState({ status: 'success', data: response.data })
      } catch {
        if (cancelled) return
        setEligibilityState({ status: 'error', data: null })
      }
    }

    loadEligibility()

    return () => {
      cancelled = true
    }
  }, [eligibilityLoadKey, eligibilityRequest])

  useEffect(() => {
    if (!draft.storageProductSlug) return

    if (eligibilityState.status === 'error') {
      setDraft((current) => current.storageProductSlug ? { ...current, storageProductSlug: null } : current)
      setClearedStorageMessage(STORAGE_ELIGIBILITY_ERROR_MESSAGE)
      return
    }

    if (eligibilityState.status !== 'success') return

    const selectedEligibility = eligibilityState.data.storage[draft.storageProductSlug]
    if (selectedEligibility?.eligible === false) {
      setDraft((current) => current.storageProductSlug === draft.storageProductSlug ? { ...current, storageProductSlug: null } : current)
      setClearedStorageMessage('Selected Storage is no longer available for the current selection.')
    }
  }, [draft.storageProductSlug, eligibilityState])

  const hasMeaningfulSelection = draft.toolSlugs.length > 0 || draft.storageProductSlug !== null || draft.aiProductSlug !== null
  const selectedStorageKnownEligible = draft.storageProductSlug === null || storageIsSelectable(eligibilityState, draft.storageProductSlug)
  const canContinue = hasMeaningfulSelection && selectedStorageKnownEligible
  const storageMessage = storageSectionMessage(eligibilityState, catalog.storage, clearedStorageMessage)

  function toggleTool(tool: ToolCatalogItem) {
    setClearedStorageMessage(null)
    setDraft((current) => {
      if (!toolIsPurchasable(storeState, tool.slug)) return current
      const selected = current.toolSlugs.includes(tool.slug)
      const toolSlugs = selected
        ? current.toolSlugs.filter((slug) => slug !== tool.slug)
        : [...current.toolSlugs, tool.slug]

      return {
        ...current,
        toolSlugs,
        aiProductSlug: toolSlugs.length > 0 ? current.aiProductSlug : null,
      }
    })
  }

  function toolState(tool: ToolCatalogItem) {
    return toolStateFor(storeState, tool.slug)
  }

  function selectStorage(slug: string | null) {
    setClearedStorageMessage(null)
    if (slug !== null && !storageIsSelectable(eligibilityState, slug)) return
    setDraft((current) => ({
      ...current,
      storageProductSlug: slug,
    }))
  }

  function selectBillingInterval(billingInterval: BillingInterval) {
    setClearedStorageMessage(null)
    setDraft((current) => ({
      ...current,
      billingInterval,
    }))
  }

  function retryEligibility() {
    setClearedStorageMessage(null)
    setEligibilityLoadKey((value) => value + 1)
  }

  function continueToReview() {
    if (!canContinue) return
    navigate('/store/review', { state: { draft } })
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
      <main className="space-y-6">
        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="mb-6">
            <p className="text-xs font-bold uppercase text-slate-400">Choose what you need</p>
            <h2 className="mt-1 text-2xl font-bold text-slate-900">Store resources</h2>
            <p className="mt-2 max-w-2xl text-sm text-slate-600">
              Choose the Tools and resources you want.
            </p>
          </div>

          <div className="space-y-6">
            <PackageSection number="1" title="Tools">
              <div className="grid gap-3">
                {catalog.tools.map((tool) => (
                  <ToolOption
                    key={tool.slug}
                    tool={tool}
                    selected={draft.toolSlugs.includes(tool.slug)}
                    interval={draft.billingInterval}
                    customerState={toolState(tool)}
                    onChange={() => toggleTool(tool)}
                  />
                ))}
              </div>
            </PackageSection>

            <PackageSection
              number="2"
              title="Storage"
              description="Add more storage when you need it. One-time purchase."
              action={<StorageDescription />}
            >
              {storageMessage && (
                <StorageAvailabilityNotice
                  message={storageMessage}
                  canRetry={eligibilityState.status === 'error'}
                  onRetry={retryEligibility}
                />
              )}
              <div className="grid gap-3">
                <StorageNoneOption
                  selected={draft.storageProductSlug === null}
                  onChange={() => selectStorage(null)}
                />
                {catalog.storage.map((option) => {
                  const eligibility = storageEligibilityFor(eligibilityState, option.slug)
                  const disabled = eligibilityState.status !== 'success' || eligibility?.eligible !== true
                  return (
                    <StorageOptionCard
                      key={option.slug}
                      option={option}
                      selected={draft.storageProductSlug === option.slug}
                      disabled={disabled}
                      unavailableReason={disabled ? eligibility?.message ?? STORAGE_ELIGIBILITY_ERROR_MESSAGE : null}
                      onChange={() => selectStorage(option.slug)}
                    />
                  )
                })}
              </div>
            </PackageSection>

            <PackageSection
              number="3"
              title="AI"
              description="Choose additional AI options when they become available."
              action={<AIDescription />}
            >
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <h4 className="text-base font-bold text-slate-900">AI options</h4>
                <p className="mt-1 text-sm leading-6 text-slate-600">Additional AI options are coming soon.</p>
                {representedAiAllowance && (
                  <p className="mt-3 text-sm font-semibold text-slate-900">
                    {allowanceLabel(representedAiAllowance)} with Blackbòd
                  </p>
                )}
              </div>
            </PackageSection>

            <PackageSection number="4" title="Billing">
              <BillingIntervalSelector
                value={draft.billingInterval}
                onChange={selectBillingInterval}
              />
            </PackageSection>
          </div>
        </section>
      </main>

      <PackageSummary
        draft={draft}
        selectedTools={selectedTools}
        selectedStorage={selectedStorage}
        selectedToolAiAllowance={selectedToolAiAllowance}
        activeToolAiAllowance={activeAiAllowance}
        hasMeaningfulSelection={hasMeaningfulSelection}
        canContinue={canContinue}
        onContinue={continueToReview}
      />
    </div>
  )
}

function PackageSection({
  number,
  title,
  description,
  action,
  children,
}: {
  number: string
  title: string
  description?: string
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="border-t border-slate-200 pt-6 first:border-t-0 first:pt-0">
      <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex gap-3">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-900 text-sm font-bold text-white">
            {number}
          </span>
          <div>
            <h3 className="text-lg font-bold text-slate-900">{title}</h3>
            {description && <p className="mt-1 max-w-2xl text-sm text-slate-600">{description}</p>}
          </div>
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}

function StorageAvailabilityNotice({ message, canRetry, onRetry }: { message: string; canRetry: boolean; onRetry: () => void }) {
  return (
    <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
      <p>{message}</p>
      {canRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 h-9 rounded-lg border border-amber-300 bg-white px-3 text-sm font-bold text-amber-900 hover:bg-amber-100"
        >
          Retry Storage check
        </button>
      )}
    </div>
  )
}

function ToolOption({
  tool,
  selected,
  interval,
  customerState,
  onChange,
}: {
  tool: ToolCatalogItem
  selected: boolean
  interval: BillingInterval
  customerState: StoreToolState | null
  onChange: () => void
}) {
  const owned = customerState?.active === true
  const [expanded, setExpanded] = useState(false)

  return (
    <div className={`rounded-lg border p-4 transition ${owned ? 'border-emerald-200 bg-emerald-50' : selected ? 'border-[#D4900A] bg-[#FFF8EA]' : 'border-slate-200 bg-slate-50 hover:border-slate-300'}`}>
      <div className="flex gap-3">
        {!owned && (
          <input
            type="checkbox"
            checked={selected}
            onChange={onChange}
            className="mt-1 h-4 w-4 rounded border-slate-300 text-[#D4900A] focus:ring-[#D4900A]"
          />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-lg font-bold text-slate-900">{tool.name}</h4>
            <span className={`rounded-full border px-2.5 py-1 text-[11px] font-bold uppercase ${owned ? 'border-emerald-200 bg-white text-emerald-700' : 'border-slate-200 bg-white text-slate-500'}`}>
              {owned ? 'Active' : 'Tool'}
            </span>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-600">Contract intelligence workspace for drafting, review, and agreement workflows.</p>
          <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold text-slate-700">
            <span className="rounded-full bg-white px-2.5 py-1">Includes {tool.included_storage.gib} GiB Storage</span>
            {tool.included_ai_allowance && <span className="rounded-full bg-white px-2.5 py-1">{allowanceLabel(tool.included_ai_allowance)}</span>}
          </div>
          <p className="mt-3 text-sm font-semibold text-slate-900">{owned ? 'Already active' : formatToolPrice(tool, interval)}</p>
        </div>
      </div>
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="mt-3 text-sm font-bold text-[#8A5A00] hover:text-[#5F3E00]"
        aria-expanded={expanded}
      >
        What's included?
      </button>
      {expanded && (
        <div className="mt-3 rounded-lg border border-amber-100 bg-white p-3 text-sm leading-6 text-slate-600">
          Blackbòd is the contract intelligence workspace for bonUP. It includes Blackbòd access, {tool.included_storage.gib} GiB included storage, and {tool.included_ai_allowance || 'starter'} AI access.
        </div>
      )}
    </div>
  )
}

function StorageNoneOption({ selected, onChange }: { selected: boolean; onChange: () => void }) {
  return (
    <CatalogOption
      name="No additional storage"
      description="Use only storage included with selected tools."
      selected={selected}
      control="radio"
      onChange={onChange}
    />
  )
}

function StorageOptionCard({
  option,
  selected,
  disabled,
  unavailableReason,
  onChange,
}: {
  option: StorageCatalogItem
  selected: boolean
  disabled: boolean
  unavailableReason: string | null
  onChange: () => void
}) {
  return (
    <CatalogOption
      name={`+${option.capacity.gib} GiB`}
      description={option.name}
      selected={selected}
      disabled={disabled}
      price={formatStoragePrice(option)}
      helperText={unavailableReason}
      control="radio"
      onChange={onChange}
    />
  )
}

function CatalogOption({
  name,
  description,
  selected,
  disabled = false,
  price = null,
  helperText = null,
  control,
  onChange,
}: {
  name: string
  description: string
  selected: boolean
  disabled?: boolean
  price?: string | null
  helperText?: string | null
  control: 'checkbox' | 'radio'
  onChange: () => void
}) {
  return (
    <label className={`block rounded-lg border p-4 transition ${disabled ? 'cursor-not-allowed border-slate-200 bg-slate-100 opacity-70' : selected ? 'cursor-pointer border-[#D4900A] bg-[#FFF8EA]' : 'cursor-pointer border-slate-200 bg-slate-50 hover:border-slate-300'}`}>
      <div className="flex gap-3">
        <input
          type={control}
          checked={selected}
          disabled={disabled}
          onChange={onChange}
          className="mt-1 h-4 w-4 border-slate-300 text-[#D4900A] focus:ring-[#D4900A]"
        />
        <div className="min-w-0 flex-1">
          <h4 className="text-base font-bold text-slate-900">{name}</h4>
          <p className="mt-1 text-sm leading-6 text-slate-600">{description}</p>
          {price !== null && <p className="mt-3 text-sm font-semibold text-slate-900">{price}</p>}
          {helperText && <p className="mt-3 text-xs font-semibold leading-5 text-slate-600">{helperText}</p>}
        </div>
      </div>
    </label>
  )
}

function DescriptionDetails({ label, children }: { label: string; children: ReactNode }) {
  return (
    <details className="text-sm">
      <summary className="cursor-pointer list-none font-bold text-[#8A5A00] hover:text-[#5F3E00]">{label}</summary>
      <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 p-3 leading-6 text-slate-600">{children}</div>
    </details>
  )
}

function StorageDescription() {
  return (
    <DescriptionDetails label="How storage works">
      <p>Blackbòd already includes 8 GiB. Additional storage can be purchased when more capacity is needed.</p>
      <p className="mt-2">Purchased storage is additional capacity, not a monthly storage plan, and does not expire while the account remains eligible to retain it under bonUP's applicable account and service terms.</p>
    </DescriptionDetails>
  )
}

function AIDescription() {
  return (
    <DescriptionDetails label="How AI works">
      <p>Blackbòd includes starter AI access. Additional AI options will eventually allow customers to choose more AI capacity or features, but those products are not available yet.</p>
    </DescriptionDetails>
  )
}

function BillingIntervalSelector({
  value,
  onChange,
}: {
  value: BillingInterval
  onChange: (value: BillingInterval) => void
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {(['monthly', 'annual'] as BillingInterval[]).map((interval) => (
        <label
          key={interval}
          className={`block cursor-pointer rounded-lg border p-4 transition ${value === interval ? 'border-[#D4900A] bg-[#FFF8EA]' : 'border-slate-200 bg-slate-50 hover:border-slate-300'}`}
        >
          <div className="flex items-center gap-3">
            <input
              type="radio"
              name="billingInterval"
              checked={value === interval}
              onChange={() => onChange(interval)}
              className="h-4 w-4 border-slate-300 text-[#D4900A] focus:ring-[#D4900A]"
            />
            <span className="text-sm font-bold text-slate-900">{displayInterval(interval)}</span>
          </div>
        </label>
      ))}
    </div>
  )
}

function PackageSummary({
  draft,
  selectedTools,
  selectedStorage,
  selectedToolAiAllowance,
  activeToolAiAllowance,
  hasMeaningfulSelection,
  canContinue,
  onContinue,
}: {
  draft: PackageDraft
  selectedTools: ToolCatalogItem[]
  selectedStorage: StorageCatalogItem | null
  selectedToolAiAllowance: string
  activeToolAiAllowance: string
  hasMeaningfulSelection: boolean
  canContinue: boolean
  onContinue: () => void
}) {
  const recurringItems = selectedTools.map((tool) => toolPrice(tool, draft.billingInterval))
  const recurringAmount = recurringItems.reduce((total, price) => total + Number(price.amount), 0)
  const recurringCurrency = recurringItems[0]?.currency ?? 'USD'
  const recurringValue = recurringItems.length > 0
    ? `${priceWithCurrency(recurringAmount.toFixed(2), recurringCurrency)} / ${recurringLabel(draft.billingInterval)}`
    : 'No recurring charge'

  return (
    <aside className="lg:sticky lg:top-6">
      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <p className="text-xs font-bold uppercase text-slate-400">Selections</p>
        <h2 className="mt-1 text-2xl font-bold text-slate-900">Your selections</h2>

        <div className="mt-6 space-y-4">
          <SummaryGroup
            label="Tools"
            value={selectedTools.length > 0 ? selectedTools.map((tool) => tool.name).join(', ') : 'No tools selected'}
            detail={selectedTools.map((tool) => formatToolPrice(tool, draft.billingInterval)).join(', ')}
          />
          {selectedTools.map((tool) => (
            <SummaryGroup
              key={`${tool.slug}-included-storage`}
              label="Included storage"
              value={`${tool.included_storage.gib} GiB`}
            />
          ))}
          <SummaryGroup
            label="Additional storage"
            value={selectedStorage ? `+${selectedStorage.capacity.gib} GiB` : 'No additional storage'}
            detail={selectedStorage ? formatStoragePrice(selectedStorage) : undefined}
          />
          <SummaryGroup
            label="AI"
            value={selectedToolAiAllowance ? allowanceLabel(selectedToolAiAllowance) : activeToolAiAllowance ? `${allowanceLabel(activeToolAiAllowance)} active` : 'No additional AI selected'}
          />
          <SummaryGroup label="Billing" value={displayInterval(draft.billingInterval)} />
          <SummaryGroup label="Recurring" value={recurringValue} />
          <SummaryGroup
            label="One-time"
            value={selectedStorage ? priceWithCurrency(selectedStorage.price.amount, selectedStorage.price.currency) : 'No one-time charge'}
          />
        </div>

        <button
          type="button"
          disabled={!canContinue}
          onClick={onContinue}
          className={canContinue ? 'mt-6 h-11 w-full rounded-lg bg-slate-900 px-5 text-sm font-bold text-white hover:bg-slate-800' : 'mt-6 h-11 w-full rounded-lg bg-slate-900 px-5 text-sm font-bold text-white opacity-50'}
        >
          Continue
        </button>
        <p className="mt-3 text-xs leading-5 text-slate-500">
          {hasMeaningfulSelection ? 'Review your selections before payment.' : 'Choose what you need to see your total.'}
        </p>
      </section>
    </aside>
  )
}

function SummaryGroup({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="border-t border-slate-200 pt-4 first:border-t-0 first:pt-0">
      <p className="text-xs font-bold uppercase text-slate-400">{label}</p>
      <p className="mt-1 break-words text-sm font-semibold text-slate-900">{value}</p>
      {detail && <p className="mt-1 break-words text-xs font-semibold text-slate-500">{detail}</p>}
    </div>
  )
}

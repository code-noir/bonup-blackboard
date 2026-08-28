import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { ReactNode } from 'react'
import type { BillingInterval, PackageDraft, StorageCatalogItem, SubscriptionCatalog, ToolCatalogItem } from '@/types/subscriptionCatalog'

export type { BillingInterval } from '@/types/subscriptionCatalog'

type PackageBuilderProps = {
  catalog: SubscriptionCatalog
  initialBillingInterval: BillingInterval
  initialDraft?: PackageDraft | null
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

export default function PackageBuilder({
  catalog,
  initialBillingInterval,
  initialDraft = null,
}: PackageBuilderProps) {
  const navigate = useNavigate()
  const [draft, setDraft] = useState<PackageDraft>(() => initialDraft ?? {
    toolSlugs: [],
    storageProductSlug: null,
    aiProductSlug: null,
    billingInterval: 'monthly',
  })

  useEffect(() => {
    if (initialDraft) return
    setDraft((current) => ({
      ...current,
      billingInterval: initialBillingInterval,
    }))
  }, [initialBillingInterval, initialDraft])

  const selectedTools = useMemo(
    () => catalog.tools.filter((tool) => draft.toolSlugs.includes(tool.slug)),
    [catalog.tools, draft.toolSlugs],
  )
  const selectedStorage = catalog.storage.find((option) => option.slug === draft.storageProductSlug) ?? null
  const selectedToolAiAllowance = selectedTools.find((tool) => tool.included_ai_allowance)?.included_ai_allowance ?? ''
  const hasMeaningfulSelection = draft.toolSlugs.length > 0 || draft.storageProductSlug !== null || draft.aiProductSlug !== null
  const canContinue = hasMeaningfulSelection

  function toggleTool(tool: ToolCatalogItem) {
    setDraft((current) => {
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

  function selectStorage(slug: string | null) {
    setDraft((current) => ({
      ...current,
      storageProductSlug: slug,
    }))
  }

  function selectBillingInterval(billingInterval: BillingInterval) {
    setDraft((current) => ({
      ...current,
      billingInterval,
    }))
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
              <div className="grid gap-3">
                <StorageNoneOption
                  selected={draft.storageProductSlug === null}
                  onChange={() => selectStorage(null)}
                />
                {catalog.storage.map((option) => (
                  <StorageOptionCard
                    key={option.slug}
                    option={option}
                    selected={draft.storageProductSlug === option.slug}
                    onChange={() => selectStorage(option.slug)}
                  />
                ))}
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
                {selectedToolAiAllowance && (
                  <p className="mt-3 text-sm font-semibold text-slate-900">
                    {allowanceLabel(selectedToolAiAllowance)} with Blackbòd
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

function ToolOption({
  tool,
  selected,
  interval,
  onChange,
}: {
  tool: ToolCatalogItem
  selected: boolean
  interval: BillingInterval
  onChange: () => void
}) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className={`rounded-lg border p-4 transition ${selected ? 'border-[#D4900A] bg-[#FFF8EA]' : 'border-slate-200 bg-slate-50 hover:border-slate-300'}`}>
      <label className="block cursor-pointer">
        <div className="flex gap-3">
          <input
            type="checkbox"
            checked={selected}
            onChange={onChange}
            className="mt-1 h-4 w-4 rounded border-slate-300 text-[#D4900A] focus:ring-[#D4900A]"
          />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h4 className="text-lg font-bold text-slate-900">{tool.name}</h4>
              <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-bold uppercase text-slate-500">
                Tool
              </span>
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-600">Contract intelligence workspace for drafting, review, and agreement workflows.</p>
            <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold text-slate-700">
              <span className="rounded-full bg-white px-2.5 py-1">Includes {tool.included_storage.gib} GiB storage</span>
              {tool.included_ai_allowance && <span className="rounded-full bg-white px-2.5 py-1">{allowanceLabel(tool.included_ai_allowance)}</span>}
            </div>
            <p className="mt-3 text-sm font-semibold text-slate-900">{formatToolPrice(tool, interval)}</p>
          </div>
        </div>
      </label>
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
  onChange,
}: {
  option: StorageCatalogItem
  selected: boolean
  onChange: () => void
}) {
  return (
    <CatalogOption
      name={`+${option.capacity.gib} GiB`}
      description={option.name}
      selected={selected}
      price={formatStoragePrice(option)}
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
  control,
  onChange,
}: {
  name: string
  description: string
  selected: boolean
  disabled?: boolean
  price?: string | null
  control: 'checkbox' | 'radio'
  onChange: () => void
}) {
  return (
    <label className={`block rounded-lg border p-4 transition ${disabled ? 'cursor-not-allowed border-slate-200 bg-slate-100 opacity-60' : selected ? 'cursor-pointer border-[#D4900A] bg-[#FFF8EA]' : 'cursor-pointer border-slate-200 bg-slate-50 hover:border-slate-300'}`}>
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
  hasMeaningfulSelection,
  canContinue,
  onContinue,
}: {
  draft: PackageDraft
  selectedTools: ToolCatalogItem[]
  selectedStorage: StorageCatalogItem | null
  selectedToolAiAllowance: string
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
            value={selectedToolAiAllowance ? allowanceLabel(selectedToolAiAllowance) : 'No additional AI selected'}
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

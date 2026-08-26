import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

export type BillingInterval = 'monthly' | 'annual'

type PackageDraft = {
  toolSlugs: string[]
  storageProductSlug: string | null
  aiProductSlug: string | null
  billingInterval: BillingInterval
}

type CatalogTool = {
  slug: 'blackbod'
  name: 'Blackbòd'
  typeLabel: 'Tool'
  description: string
  aiCapable: boolean
  monthlyPrice: string | null
  annualPrice: string | null
}

type StorageOption = {
  slug: string
  name: string
  description: string
  monthlyPrice: string | null
  annualPrice: string | null
}

type AIOption = {
  slug: string
  name: string
  description: string
  monthlyPrice: string | null
  annualPrice: string | null
}

type PackageBuilderProps = {
  hasBlackbodAccess: boolean
  accessKnown: boolean
  initialBillingInterval: BillingInterval
}

const tools: CatalogTool[] = [
  {
    slug: 'blackbod',
    name: 'Blackbòd',
    typeLabel: 'Tool',
    description: 'Complete contract workspace.',
    aiCapable: true,
    monthlyPrice: null,
    annualPrice: null,
  },
]

const storageOptions: StorageOption[] = []
const aiOptions: AIOption[] = []

function displayInterval(value: BillingInterval) {
  return value === 'annual' ? 'Annual' : 'Monthly'
}

function priceFor(
  item: { monthlyPrice: string | null; annualPrice: string | null } | null,
  interval: BillingInterval,
) {
  if (!item) return null
  return interval === 'annual' ? item.annualPrice : item.monthlyPrice
}

function formatPrice(value: string | null) {
  return value == null ? 'Price pending' : value
}

export default function PackageBuilder({
  hasBlackbodAccess,
  accessKnown,
  initialBillingInterval,
}: PackageBuilderProps) {
  const [draft, setDraft] = useState<PackageDraft>({
    toolSlugs: ['blackbod'],
    storageProductSlug: null,
    aiProductSlug: null,
    billingInterval: initialBillingInterval,
  })

  useEffect(() => {
    setDraft((current) => ({
      ...current,
      billingInterval: initialBillingInterval,
    }))
  }, [initialBillingInterval])

  const selectedTools = useMemo(
    () => tools.filter((tool) => draft.toolSlugs.includes(tool.slug)),
    [draft.toolSlugs],
  )
  const selectedStorage = storageOptions.find((option) => option.slug === draft.storageProductSlug) ?? null
  const selectedAI = aiOptions.find((option) => option.slug === draft.aiProductSlug) ?? null
  const hasAiCapableTool = selectedTools.some((tool) => tool.aiCapable)

  function toggleTool(tool: CatalogTool) {
    setDraft((current) => {
      const selected = current.toolSlugs.includes(tool.slug)
      const toolSlugs = selected
        ? current.toolSlugs.filter((slug) => slug !== tool.slug)
        : [...current.toolSlugs, tool.slug]

      const stillHasAiCapableTool = tools
        .filter((candidate) => toolSlugs.includes(candidate.slug))
        .some((candidate) => candidate.aiCapable)

      return {
        ...current,
        toolSlugs,
        aiProductSlug: stillHasAiCapableTool ? current.aiProductSlug : null,
      }
    })
  }

  function selectStorage(slug: string | null) {
    setDraft((current) => ({
      ...current,
      storageProductSlug: slug,
    }))
  }

  function selectAI(slug: string | null) {
    if (slug && !hasAiCapableTool) return
    setDraft((current) => ({
      ...current,
      aiProductSlug: slug,
    }))
  }

  function selectBillingInterval(billingInterval: BillingInterval) {
    setDraft((current) => ({
      ...current,
      billingInterval,
    }))
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
      <main className="space-y-6">
        <CurrentAccess active={hasBlackbodAccess} known={accessKnown} />

        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="mb-6">
            <p className="text-xs font-bold uppercase text-slate-400">Build your package</p>
            <h2 className="mt-1 text-2xl font-bold text-slate-900">Choose package components</h2>
          </div>

          <div className="space-y-6">
            <PackageSection number="1" title="Tools">
              <div className="grid gap-3">
                {tools.map((tool) => (
                  <ToolOption
                    key={tool.slug}
                    tool={tool}
                    selected={draft.toolSlugs.includes(tool.slug)}
                    currentAccess={tool.slug === 'blackbod' && hasBlackbodAccess}
                    interval={draft.billingInterval}
                    onChange={() => toggleTool(tool)}
                  />
                ))}
              </div>
            </PackageSection>

            <PackageSection
              number="2"
              title="Storage"
              description="Choose the storage capacity for your bonUP environment."
            >
              <div className="grid gap-3">
                <StorageOptionCard
                  selected={draft.storageProductSlug === null}
                  onChange={() => selectStorage(null)}
                />
                {storageOptions.map((option) => (
                  <CatalogOption
                    key={option.slug}
                    name={option.name}
                    description={option.description}
                    selected={draft.storageProductSlug === option.slug}
                    price={priceFor(option, draft.billingInterval)}
                    control="radio"
                    onChange={() => selectStorage(option.slug)}
                  />
                ))}
              </div>
            </PackageSection>

            <PackageSection
              number="3"
              title="AI"
              description="Choose the AI capability for your selected Tools."
            >
              <div className="grid gap-3">
                <AIOptionCard
                  selected={draft.aiProductSlug === null}
                  onChange={() => selectAI(null)}
                />
                {aiOptions.map((option) => (
                  <CatalogOption
                    key={option.slug}
                    name={option.name}
                    description={option.description}
                    selected={draft.aiProductSlug === option.slug}
                    disabled={!hasAiCapableTool}
                    price={priceFor(option, draft.billingInterval)}
                    control="radio"
                    onChange={() => selectAI(option.slug)}
                  />
                ))}
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
        selectedAI={selectedAI}
      />
    </div>
  )
}

function CurrentAccess({ active, known }: { active: boolean; known: boolean }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <p className="text-xs font-bold uppercase text-slate-400">Current access</p>
      <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Blackbòd</h2>
          <p className="mt-1 text-sm text-slate-600">{known ? (active ? 'Active' : 'Not active') : 'Checking access'}</p>
        </div>
        <span className={`inline-flex h-8 items-center self-start rounded-full border px-3 text-xs font-bold uppercase ${active ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-500'}`}>
          {known ? (active ? 'Active' : 'Not active') : 'Checking'}
        </span>
      </div>
    </section>
  )
}

function PackageSection({
  number,
  title,
  description,
  children,
}: {
  number: string
  title: string
  description?: string
  children: ReactNode
}) {
  return (
    <section className="border-t border-slate-200 pt-6 first:border-t-0 first:pt-0">
      <div className="mb-3 flex gap-3">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-900 text-sm font-bold text-white">
          {number}
        </span>
        <div>
          <h3 className="text-lg font-bold text-slate-900">{title}</h3>
          {description && <p className="mt-1 max-w-2xl text-sm text-slate-600">{description}</p>}
        </div>
      </div>
      {children}
    </section>
  )
}

function ToolOption({
  tool,
  selected,
  currentAccess,
  interval,
  onChange,
}: {
  tool: CatalogTool
  selected: boolean
  currentAccess: boolean
  interval: BillingInterval
  onChange: () => void
}) {
  return (
    <label className={`block cursor-pointer rounded-lg border p-4 transition ${selected ? 'border-[#D4900A] bg-[#FFF8EA]' : 'border-slate-200 bg-slate-50 hover:border-slate-300'}`}>
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
              {tool.typeLabel}
            </span>
            {currentAccess && (
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-bold uppercase text-emerald-700">
                Current access
              </span>
            )}
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-600">{tool.description}</p>
          <p className="mt-3 text-sm font-semibold text-slate-900">{formatPrice(priceFor(tool, interval))}</p>
        </div>
      </div>
    </label>
  )
}

function StorageOptionCard({ selected, onChange }: { selected: boolean; onChange: () => void }) {
  return (
    <CatalogOption
      name="No storage"
      description="Do not add storage to this package."
      selected={selected}
      control="radio"
      onChange={onChange}
    />
  )
}

function AIOptionCard({ selected, onChange }: { selected: boolean; onChange: () => void }) {
  return (
    <CatalogOption
      name="No AI"
      description="Do not add AI capability to this package."
      selected={selected}
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
          {price !== null && <p className="mt-3 text-sm font-semibold text-slate-900">{formatPrice(price)}</p>}
        </div>
      </div>
    </label>
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
  selectedAI,
}: {
  draft: PackageDraft
  selectedTools: CatalogTool[]
  selectedStorage: StorageOption | null
  selectedAI: AIOption | null
}) {
  const pricingItems = [
    ...selectedTools.map((tool) => priceFor(tool, draft.billingInterval)),
    priceFor(selectedStorage, draft.billingInterval),
    priceFor(selectedAI, draft.billingInterval),
  ].filter((price): price is string => price !== null)

  return (
    <aside className="lg:sticky lg:top-6">
      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <p className="text-xs font-bold uppercase text-slate-400">Your package</p>
        <h2 className="mt-1 text-2xl font-bold text-slate-900">Package draft</h2>

        <div className="mt-6 space-y-4">
          <SummaryGroup
            label="Tools"
            value={selectedTools.length > 0 ? selectedTools.map((tool) => tool.name).join(', ') : 'No tools'}
          />
          <SummaryGroup label="Storage" value={selectedStorage?.name ?? 'No storage'} />
          <SummaryGroup label="AI" value={selectedAI?.name ?? 'No AI'} />
          <SummaryGroup label="Billing" value={displayInterval(draft.billingInterval)} />
          <SummaryGroup label="Pricing" value={pricingItems.length > 0 ? pricingItems.join(' + ') : 'Price pending'} />
        </div>

        <button
          type="button"
          disabled
          className="mt-6 h-11 w-full rounded-lg bg-slate-900 px-5 text-sm font-bold text-white opacity-50"
        >
          Continue
        </button>
      </section>
    </aside>
  )
}

function SummaryGroup({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-t border-slate-200 pt-4 first:border-t-0 first:pt-0">
      <p className="text-xs font-bold uppercase text-slate-400">{label}</p>
      <p className="mt-1 break-words text-sm font-semibold text-slate-900">{value}</p>
    </div>
  )
}

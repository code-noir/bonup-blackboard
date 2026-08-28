import { useNavigate } from 'react-router-dom'

const STORAGE_ROWS = [
  { label: 'Capacity', value: 'Unavailable' },
  { label: 'Used', value: 'Unavailable' },
  { label: 'Remaining', value: 'Unavailable' },
]

export default function Vault() {
  const navigate = useNavigate()

  return (
    <div className="mx-auto max-w-4xl py-8">
      <header className="mb-8">
        <p className="mb-2 text-xs font-bold uppercase text-[#D4900A]">bonUP</p>
        <h1 className="text-3xl font-bold text-slate-900">Vault</h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-600">
          Storage and durable resources in bonUP.
        </p>
      </header>

      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs font-bold uppercase text-slate-400">Storage</p>
            <h2 className="mt-1 text-2xl font-bold text-slate-900">Storage</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
              Storage capacity details are not available in this interface yet.
            </p>
          </div>
          <button
            type="button"
            onClick={() => navigate('/store')}
            className="h-10 rounded-lg bg-slate-900 px-4 text-sm font-bold text-white hover:bg-slate-800"
          >
            Add Storage
          </button>
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-3">
          {STORAGE_ROWS.map((row) => (
            <div key={row.label} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-bold uppercase text-slate-400">{row.label}</p>
              <p className="mt-2 text-sm font-semibold text-slate-900">{row.value}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

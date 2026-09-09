import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ArrowDownTrayIcon, DocumentIcon, MusicalNoteIcon, PhotoIcon, RectangleStackIcon, VideoCameraIcon } from '@heroicons/react/24/outline'
import api from '@/api/client'

type SharedFile = {
  file_name: string
  file_type: string
  content_type: string
  file_size: number
  delivery_url: string
}

type LoadState = 'loading' | 'success' | 'error'

function formatBytes(bytes: number | null | undefined) {
  const value = Number(bytes ?? 0)
  if (value <= 0) return '0 B'
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
  let size = value
  let unit = 0
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024
    unit += 1
  }
  return `${size >= 10 || unit === 0 ? size.toFixed(0) : size.toFixed(1)} ${units[unit]}`
}

function categoryFor(file: SharedFile) {
  const contentType = (file.content_type || '').toLowerCase()
  const fileType = (file.file_type || '').toLowerCase()
  if (contentType.startsWith('image/') || fileType === 'image') return 'image'
  if (contentType.startsWith('video/') || fileType === 'video') return 'video'
  if (contentType.startsWith('audio/') || fileType === 'audio') return 'audio'
  if (fileType === 'pdf' || fileType === 'document' || fileType === 'slides' || contentType.includes('pdf')) return 'document'
  return 'other'
}

function iconFor(category: string) {
  if (category === 'image') return PhotoIcon
  if (category === 'video') return VideoCameraIcon
  if (category === 'audio') return MusicalNoteIcon
  if (category === 'document') return DocumentIcon
  return RectangleStackIcon
}

export default function VaultShare() {
  const { token } = useParams<{ token: string }>()
  const [state, setState] = useState<LoadState>('loading')
  const [file, setFile] = useState<SharedFile | null>(null)

  useEffect(() => {
    let mounted = true
    async function loadShare() {
      try {
        const response = await api.get<SharedFile>(`/uploads/shares/${token}/`)
        if (!mounted) return
        setFile(response.data)
        setState('success')
      } catch {
        if (!mounted) return
        setState('error')
      }
    }
    void loadShare()
    return () => {
      mounted = false
    }
  }, [token])

  const category = file ? categoryFor(file) : 'other'
  const Icon = iconFor(category)

  return (
    <main className="min-h-screen bg-[#F7F8FA] px-4 py-10">
      <div className="mx-auto max-w-4xl">
        <header className="mb-8">
          <p className="mb-2 text-xs font-bold uppercase text-[#D4900A]">bonUP</p>
          <h1 className="text-3xl font-bold text-slate-900">Shared Vault File</h1>
        </header>

        {state === 'loading' && (
          <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-sm font-semibold text-slate-600">Loading shared file...</p>
          </section>
        )}

        {state === 'error' && (
          <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-xl font-bold text-slate-900">This share is unavailable</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">The link may have expired, been revoked, or no longer be available.</p>
          </section>
        )}

        {state === 'success' && file && (
          <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-200 p-5">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <h2 className="truncate text-xl font-bold text-slate-900">{file.file_name}</h2>
                  <p className="mt-1 text-sm text-slate-500">{file.content_type || file.file_type} · {formatBytes(file.file_size)}</p>
                </div>
                <a href={`${file.delivery_url}?download=1`} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-slate-900 px-4 text-sm font-bold text-white hover:bg-slate-800">
                  <ArrowDownTrayIcon className="h-4 w-4" />
                  Download
                </a>
              </div>
            </div>
            <div className="flex min-h-[420px] items-center justify-center bg-slate-50 p-5">
              {category === 'image' ? <img src={file.delivery_url} alt="" className="max-h-[680px] max-w-full rounded-lg object-contain" /> : null}
              {category === 'video' ? <video src={file.delivery_url} controls className="max-h-[680px] max-w-full rounded-lg" /> : null}
              {category === 'audio' ? <audio src={file.delivery_url} controls className="w-full max-w-lg" /> : null}
              {category === 'document' ? <iframe src={file.delivery_url} title={file.file_name} className="h-[680px] w-full rounded-lg border border-slate-200 bg-white" /> : null}
              {category === 'other' ? (
                <div className="text-center text-slate-500">
                  <Icon className="mx-auto h-14 w-14" />
                  <p className="mt-3 text-sm font-semibold">Preview is not available for this file.</p>
                </div>
              ) : null}
            </div>
          </section>
        )}
      </div>
    </main>
  )
}

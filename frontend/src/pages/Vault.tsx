import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowDownTrayIcon,
  ClipboardDocumentIcon,
  DocumentIcon,
  EnvelopeIcon,
  FolderIcon,
  MagnifyingGlassIcon,
  MusicalNoteIcon,
  PencilSquareIcon,
  PhotoIcon,
  PlusIcon,
  ShareIcon,
  RectangleStackIcon,
  TrashIcon,
  VideoCameraIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import api from '@/api/client'

type StorageSummary = {
  capacity_bytes: number
  used_bytes: number
  available_bytes: number
}

type VaultFile = {
  id: string
  file_url: string | null
  file_name: string
  file_type: string
  content_type?: string
  file_size: number
  folder_id: string | null
  uploaded_at: string
  is_prep_material?: boolean
  is_draft_document?: boolean
}

type Category = 'all' | 'images' | 'videos' | 'audio' | 'documents' | 'other'
type SortKey = 'newest' | 'oldest' | 'name' | 'size'
type ViewMode = 'grid' | 'list'
type ShareExpiration = '1d' | '7d' | '30d' | 'none'
type EmailState = 'idle' | 'sending' | 'sent'
type RenameState = 'idle' | 'saving'
type UploadQueueStatus = 'waiting' | 'uploading' | 'uploaded' | 'failed'

type LoadState = 'loading' | 'success' | 'error'

type Toast = {
  tone: 'success' | 'error' | 'info'
  message: string
} | null

type NativeFileShareData = {
  files: File[]
  title: string
}

type NativeShareNavigator = Navigator & {
  canShare?: (data: NativeFileShareData) => boolean
  share?: (data: NativeFileShareData) => Promise<void>
}

type VaultShare = {
  id: string
  share_url?: string
  created_at?: string
  expires_at: string | null
  revoked_at: string | null
  is_valid?: boolean
  file_name?: string
  file_type?: string
  content_type?: string
  file_size?: number
}

type VaultFolder = {
  id: string
  name: string
  parent_id: string | null
  created_at: string
  updated_at: string
}

type VaultEmailResponse = {
  status: 'sent' | 'pending' | 'failed'
  delivery_id: string
  provider: string
  provider_message_id: string
  idempotent: boolean
}

type UploadQueueItem = {
  id: string
  name: string
  size: number
  status: UploadQueueStatus
  error?: string
}

type NativeShareDiagnosticReason =
  | 'insecure_context'
  | 'navigator_share_unavailable'
  | 'navigator_canShare_unavailable'
  | 'file_too_large'
  | 'delivery_failure'
  | 'canShare_files_false'
  | 'canShare_files_error'
  | 'share_cancelled'
  | 'share_error'

// Native file sharing constructs a browser File in memory. Keep this conservative until Vault has a documented upload cap.
const NATIVE_SHARE_PREPARATION_LIMIT_BYTES = 25 * 1024 * 1024
const UPLOAD_CONCURRENCY_LIMIT = 2

const CATEGORIES: Array<{ key: Category; label: string }> = [
  { key: 'all', label: 'All Files' },
  { key: 'images', label: 'Images' },
  { key: 'videos', label: 'Videos' },
  { key: 'audio', label: 'Audio' },
  { key: 'documents', label: 'Documents' },
  { key: 'other', label: 'Other' },
]

function categoryForFile(file: Pick<VaultFile, 'file_name' | 'file_type' | 'content_type'>): Category {
  const contentType = (file.content_type || '').toLowerCase()
  const fileType = (file.file_type || '').toLowerCase()
  const extension = file.file_name.split('.').pop()?.toLowerCase() || ''

  if (contentType.startsWith('image/') || fileType === 'image') return 'images'
  if (contentType.startsWith('video/') || fileType === 'video') return 'videos'
  if (contentType.startsWith('audio/') || fileType === 'audio') return 'audio'
  if (
    fileType === 'pdf' ||
    fileType === 'document' ||
    fileType === 'slides' ||
    contentType.includes('pdf') ||
    contentType.includes('document') ||
    contentType.includes('presentation') ||
    ['pdf', 'doc', 'docx', 'txt', 'rtf', 'ppt', 'pptx', 'xls', 'xlsx', 'csv'].includes(extension)
  ) {
    return 'documents'
  }
  return 'other'
}

function uploadTypeForFile(file: File): string {
  const contentType = file.type.toLowerCase()
  const extension = file.name.split('.').pop()?.toLowerCase() || ''
  if (contentType === 'application/pdf' || extension === 'pdf') return 'pdf'
  if (contentType.startsWith('image/')) return 'image'
  if (contentType.startsWith('video/')) return 'video'
  if (contentType.startsWith('audio/')) return 'audio'
  if (['ppt', 'pptx', 'key'].includes(extension)) return 'slides'
  if (['doc', 'docx', 'txt', 'rtf', 'xls', 'xlsx', 'csv'].includes(extension) || contentType.includes('document')) return 'document'
  return 'other'
}

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

function formatDate(value: string) {
  if (!value) return 'Unknown date'
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(value))
}

function fileIcon(category: Category) {
  if (category === 'images') return PhotoIcon
  if (category === 'videos') return VideoCameraIcon
  if (category === 'audio') return MusicalNoteIcon
  if (category === 'documents') return DocumentIcon
  return RectangleStackIcon
}

function typeLabel(file: VaultFile) {
  const category = categoryForFile(file)
  if (category === 'images') return 'Image'
  if (category === 'videos') return 'Video'
  if (category === 'audio') return 'Audio'
  if (category === 'documents') return file.file_type === 'pdf' ? 'PDF' : 'Document'
  return 'File'
}

function storagePercent(summary: StorageSummary | null) {
  if (!summary || summary.capacity_bytes <= 0) return 0
  return Math.min(100, Math.round((summary.used_bytes / summary.capacity_bytes) * 100))
}

function folderErrorMessage(error: unknown) {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const data = (error as { response?: { data?: { code?: string; detail?: string; error?: string } } }).response?.data
    if (typeof data?.detail === 'string' && data.detail) return data.detail
    if (typeof data?.error === 'string' && data.error) return data.error
  }
  return 'Folder could not be updated.'
}

function isFolderDescendant(folder: VaultFolder, ancestorId: string, byId: Map<string, VaultFolder>) {
  let parentId = folder.parent_id
  while (parentId) {
    if (parentId === ancestorId) return true
    parentId = byId.get(parentId)?.parent_id || null
  }
  return false
}

function folderPathLabel(folder: VaultFolder, byId: Map<string, VaultFolder>) {
  const names = [folder.name]
  let parentId = folder.parent_id
  while (parentId) {
    const parent = byId.get(parentId)
    if (!parent) break
    names.unshift(parent.name)
    parentId = parent.parent_id
  }
  return names.join(' / ')
}

function uploadErrorMessage(error: unknown) {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const data = (error as { response?: { data?: { code?: string; detail?: string; error?: string; available_bytes?: number } } }).response?.data
    if (data?.code === 'storage_capacity_exceeded') {
      if (typeof data.available_bytes === 'number') {
        return `Not enough storage available. ${formatBytes(data.available_bytes)} available.`
      }
      return 'This file is larger than your available storage.'
    }
    if (typeof data?.detail === 'string' && data.detail) return data.detail
    if (typeof data?.error === 'string' && data.error) return data.error
  }
  return 'Upload failed. Please try again.'
}

function responseStatus(error: unknown) {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    return (error as { response?: { status?: number } }).response?.status
  }
  return undefined
}

function logNativeShareDiagnostic(
  reason: NativeShareDiagnosticReason,
  file: Pick<VaultFile, 'file_size' | 'content_type' | 'file_type'>,
  details: Record<string, unknown> = {},
) {
  if (!import.meta.env.DEV) return

  const nativeNavigator = navigator as NativeShareNavigator
  console.info('bonUP Vault Share File diagnostic', {
    reason,
    isSecureContext: window.isSecureContext,
    protocol: window.location.protocol,
    hostname: window.location.hostname,
    navigatorShareType: typeof nativeNavigator.share,
    navigatorCanShareType: typeof nativeNavigator.canShare,
    fileSize: file.file_size,
    fileType: file.file_type,
    contentType: file.content_type || '',
    ...details,
  })
}

function isValidEmailAddress(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
}

function createIdempotencyKey() {
  if (crypto.randomUUID) return crypto.randomUUID()
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function emailErrorMessage(error: unknown) {
  const code = typeof error === 'object' && error !== null && 'response' in error
    ? (error as { response?: { data?: { code?: string } } }).response?.data?.code
    : undefined

  if (code === 'attachment_too_large') return 'This file is too large to email as an attachment.'
  if (code === 'email_service_unavailable') return "Email delivery isn't configured yet."
  if (code === 'provider_delivery_failure') return 'Email delivery failed. Please try again.'
  if (code === 'rate_limited') return 'Too many email attempts. Please try again later.'
  if (code === 'invalid_recipient') return 'Enter one valid recipient email address.'
  if (code === 'subject_required') return 'Subject is required.'
  return 'Email could not be sent. Please try again.'
}

export default function Vault() {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [storage, setStorage] = useState<StorageSummary | null>(null)
  const [files, setFiles] = useState<VaultFile[]>([])
  const [folders, setFolders] = useState<VaultFolder[]>([])
  const [storageState, setStorageState] = useState<LoadState>('loading')
  const [filesState, setFilesState] = useState<LoadState>('loading')
  const [category, setCategory] = useState<Category>('all')
  const [search, setSearch] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('newest')
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(null)
  const [selectedFile, setSelectedFile] = useState<VaultFile | null>(null)
  const [shareFile, setShareFile] = useState<VaultFile | null>(null)
  const [emailFile, setEmailFile] = useState<VaultFile | null>(null)
  const [renameFile, setRenameFile] = useState<VaultFile | null>(null)
  const [moveFile, setMoveFile] = useState<VaultFile | null>(null)
  const [moveFolderModal, setMoveFolderModal] = useState<VaultFolder | null>(null)
  const [folderNameModal, setFolderNameModal] = useState<{ mode: 'create' | 'rename'; folder: VaultFolder | null } | null>(null)
  const [nativeShareFallbackFile, setNativeShareFallbackFile] = useState<VaultFile | null>(null)
  const [shareExpiration, setShareExpiration] = useState<ShareExpiration>('7d')
  const [shareLinks, setShareLinks] = useState<VaultShare[]>([])
  const [shareLinksLoading, setShareLinksLoading] = useState(false)
  const [shareError, setShareError] = useState('')
  const [revokingShareId, setRevokingShareId] = useState<string | null>(null)
  const [emailTo, setEmailTo] = useState('')
  const [emailSubject, setEmailSubject] = useState('')
  const [emailMessage, setEmailMessage] = useState('')
  const [emailState, setEmailState] = useState<EmailState>('idle')
  const [emailError, setEmailError] = useState('')
  const [emailIdempotencyKey, setEmailIdempotencyKey] = useState('')
  const [renameName, setRenameName] = useState('')
  const [renameState, setRenameState] = useState<RenameState>('idle')
  const [renameError, setRenameError] = useState('')
  const [folderName, setFolderName] = useState('')
  const [folderSaving, setFolderSaving] = useState(false)
  const [folderError, setFolderError] = useState('')
  const [movingFile, setMovingFile] = useState(false)
  const [moveFileFolderId, setMoveFileFolderId] = useState<string>('')
  const [moveFileError, setMoveFileError] = useState('')
  const [movingFolder, setMovingFolder] = useState(false)
  const [moveFolderParentId, setMoveFolderParentId] = useState<string>('')
  const [moveFolderError, setMoveFolderError] = useState('')
  const [sharing, setSharing] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadQueue, setUploadQueue] = useState<UploadQueueItem[]>([])
  const [workingFileId, setWorkingFileId] = useState<string | null>(null)
  const [toast, setToast] = useState<Toast>(null)
  const [addStorageOpen, setAddStorageOpen] = useState(false)

  async function loadStorage() {
    setStorageState('loading')
    try {
      const response = await api.get<StorageSummary>('/uploads/storage/')
      setStorage(response.data)
      setStorageState('success')
    } catch {
      setStorageState('error')
    }
  }

  async function loadFiles() {
    setFilesState('loading')
    try {
      const response = await api.get<VaultFile[]>('/uploads/')
      setFiles(response.data)
      setFilesState('success')
    } catch {
      setFilesState('error')
    }
  }

  async function loadFolders() {
    try {
      const response = await api.get<VaultFolder[]>('/uploads/folders/')
      setFolders(response.data)
    } catch {
      setToast({ tone: 'error', message: 'Folders could not be loaded.' })
    }
  }

  async function refreshVault() {
    await Promise.all([loadStorage(), loadFiles(), loadFolders()])
  }

  useEffect(() => {
    void refreshVault()
  }, [])

  const currentFolder = useMemo(() => folders.find((folder) => folder.id === currentFolderId) || null, [currentFolderId, folders])

  const folderBreadcrumbs = useMemo(() => {
    const byId = new Map(folders.map((folder) => [folder.id, folder]))
    const path: VaultFolder[] = []
    let folder = currentFolder
    while (folder) {
      path.unshift(folder)
      folder = folder.parent_id ? byId.get(folder.parent_id) || null : null
    }
    return path
  }, [currentFolder, folders])

  const visibleFolders = useMemo(() => {
    return folders.filter((folder) => folder.parent_id === currentFolderId)
  }, [currentFolderId, folders])

  const folderById = useMemo(() => new Map(folders.map((folder) => [folder.id, folder])), [folders])

  const currentFolderFiles = useMemo(() => {
    return files.filter((file) => file.folder_id === currentFolderId)
  }, [currentFolderId, files])

  const filteredFiles = useMemo(() => {
    const query = search.trim().toLowerCase()
    return currentFolderFiles
      .filter((file) => category === 'all' || categoryForFile(file) === category)
      .filter((file) => !query || file.file_name.toLowerCase().includes(query))
      .sort((a, b) => {
        if (sortKey === 'name') return a.file_name.localeCompare(b.file_name)
        if (sortKey === 'size') return b.file_size - a.file_size
        const aTime = new Date(a.uploaded_at).getTime()
        const bTime = new Date(b.uploaded_at).getTime()
        return sortKey === 'oldest' ? aTime - bTime : bTime - aTime
      })
  }, [category, currentFolderFiles, search, sortKey])

  const countsByCategory = useMemo(() => {
    return CATEGORIES.reduce<Record<Category, number>>((acc, item) => {
      acc[item.key] = item.key === 'all' ? currentFolderFiles.length : currentFolderFiles.filter((file) => categoryForFile(file) === item.key).length
      return acc
    }, { all: 0, images: 0, videos: 0, audio: 0, documents: 0, other: 0 })
  }, [currentFolderFiles])

  function updateUploadQueueItem(id: string, updates: Partial<UploadQueueItem>) {
    setUploadQueue((current) => current.map((item) => item.id === id ? { ...item, ...updates } : item))
  }

  async function uploadQueuedFile(file: File, itemId: string) {
    updateUploadQueueItem(itemId, { status: 'uploading', error: undefined })
    const form = new FormData()
    form.append('file', file)
    form.append('file_type', uploadTypeForFile(file))
    if (currentFolderId) {
      form.append('folder_id', currentFolderId)
    }

    try {
      await api.post('/uploads/', form, { headers: { 'Content-Type': 'multipart/form-data' } })
      updateUploadQueueItem(itemId, { status: 'uploaded' })
      return true
    } catch (error) {
      updateUploadQueueItem(itemId, { status: 'failed', error: uploadErrorMessage(error) })
      return false
    }
  }

  async function handleUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const selectedFiles = Array.from(event.target.files || [])
    event.target.value = ''
    if (selectedFiles.length === 0 || uploading) return

    const queue = selectedFiles.map((file) => ({
      id: createIdempotencyKey(),
      name: file.name,
      size: file.size,
      status: 'waiting' as UploadQueueStatus,
    }))

    setUploading(true)
    setUploadQueue(queue)
    setToast(null)

    let nextIndex = 0
    let uploadedCount = 0
    const workerCount = Math.min(UPLOAD_CONCURRENCY_LIMIT, selectedFiles.length)

    async function uploadNext() {
      while (nextIndex < selectedFiles.length) {
        const currentIndex = nextIndex
        nextIndex += 1
        const uploaded = await uploadQueuedFile(selectedFiles[currentIndex], queue[currentIndex].id)
        if (uploaded) uploadedCount += 1
      }
    }

    try {
      await Promise.all(Array.from({ length: workerCount }, uploadNext))
      if (uploadedCount > 0) {
        await refreshVault()
      }
      if (uploadedCount === selectedFiles.length) {
        setToast({ tone: 'success', message: selectedFiles.length === 1 ? `${selectedFiles[0].name} uploaded to Vault.` : `${uploadedCount} files uploaded to Vault.` })
      } else if (uploadedCount > 0) {
        setToast({ tone: 'info', message: `${uploadedCount} of ${selectedFiles.length} files uploaded to Vault.` })
      } else {
        setToast({ tone: 'error', message: 'No files were uploaded.' })
      }
    } finally {
      setUploading(false)
    }
  }

  function dismissUploadQueue() {
    if (uploading) return
    setUploadQueue([])
  }

  function openFolderNameModal(mode: 'create' | 'rename', folder: VaultFolder | null = null) {
    setFolderNameModal({ mode, folder })
    setFolderName(folder?.name || '')
    setFolderError('')
    setToast(null)
  }

  function closeFolderNameModal() {
    if (folderSaving) return
    setFolderNameModal(null)
    setFolderName('')
    setFolderError('')
  }

  async function saveFolderName() {
    if (!folderNameModal || folderSaving) return
    const name = folderName.trim()
    if (!name) {
      setFolderError('Folder name is required.')
      return
    }

    setFolderSaving(true)
    setFolderError('')
    try {
      if (folderNameModal.mode === 'create') {
        const response = await api.post<VaultFolder>('/uploads/folders/', { name, parent_id: currentFolderId })
        setFolders((current) => [...current, response.data].sort((a, b) => a.name.localeCompare(b.name)))
        setToast({ tone: 'success', message: 'Folder created.' })
      } else if (folderNameModal.folder) {
        const response = await api.patch<VaultFolder>(`/uploads/folders/${folderNameModal.folder.id}/`, { name })
        setFolders((current) => current.map((folder) => folder.id === response.data.id ? response.data : folder).sort((a, b) => a.name.localeCompare(b.name)))
        setToast({ tone: 'success', message: 'Folder renamed.' })
      }
      closeFolderNameModal()
    } catch (error) {
      setFolderError(folderErrorMessage(error))
    } finally {
      setFolderSaving(false)
    }
  }

  function openMoveFolder(folder: VaultFolder) {
    setMoveFolderModal(folder)
    setMoveFolderParentId(folder.parent_id || '')
    setMoveFolderError('')
    setToast(null)
  }

  function closeMoveFolder() {
    if (movingFolder) return
    setMoveFolderModal(null)
    setMoveFolderParentId('')
    setMoveFolderError('')
  }

  async function handleMoveFolder() {
    if (!moveFolderModal || movingFolder) return
    setMovingFolder(true)
    setMoveFolderError('')
    try {
      const response = await api.patch<VaultFolder>(`/uploads/folders/${moveFolderModal.id}/`, { parent_id: moveFolderParentId || null })
      setFolders((current) => current.map((item) => item.id === response.data.id ? response.data : item))
      setToast({ tone: 'success', message: 'Folder moved.' })
      closeMoveFolder()
    } catch (error) {
      setMoveFolderError(folderErrorMessage(error))
    } finally {
      setMovingFolder(false)
    }
  }

  async function deleteFolder(folder: VaultFolder) {
    const confirmed = window.confirm('Delete this empty folder? Files are not removed from Vault.')
    if (!confirmed) return
    setToast(null)
    try {
      await api.delete(`/uploads/folders/${folder.id}/`)
      setFolders((current) => current.filter((item) => item.id !== folder.id))
      if (currentFolderId === folder.id) setCurrentFolderId(folder.parent_id)
      setToast({ tone: 'success', message: 'Folder deleted.' })
    } catch (error) {
      setToast({ tone: 'error', message: folderErrorMessage(error) })
    }
  }

  function openMoveFile(file: VaultFile) {
    setMoveFile(file)
    setMoveFileFolderId(file.folder_id || '')
    setMoveFileError('')
    setToast(null)
  }

  function closeMoveFile() {
    if (movingFile) return
    setMoveFile(null)
    setMoveFileFolderId('')
    setMoveFileError('')
  }

  async function handleMoveFile() {
    if (!moveFile || movingFile) return
    setMovingFile(true)
    setMoveFileError('')
    try {
      const response = await api.post<VaultFile>(`/uploads/${moveFile.id}/folder/`, { folder_id: moveFileFolderId || null })
      const updated = response.data
      setFiles((current) => current.map((file) => file.id === updated.id ? updated : file))
      setSelectedFile((current) => current?.id === updated.id ? updated : current)
      setShareFile((current) => current?.id === updated.id ? updated : current)
      setEmailFile((current) => current?.id === updated.id ? updated : current)
      setNativeShareFallbackFile((current) => current?.id === updated.id ? updated : current)
      setToast({ tone: 'success', message: 'File moved.' })
      closeMoveFile()
    } catch (error) {
      setMoveFileError(folderErrorMessage(error))
    } finally {
      setMovingFile(false)
    }
  }

  function handleDownload(file: VaultFile) {
    if (!file.file_url) return
    const link = document.createElement('a')
    link.href = file.file_url
    link.download = file.file_name
    link.rel = 'noopener noreferrer'
    document.body.appendChild(link)
    link.click()
    link.remove()
  }

  function openEmailFile(file: VaultFile) {
    setEmailFile(file)
    setEmailTo('')
    setEmailSubject(`${file.file_name} from bonUP`)
    setEmailMessage('')
    setEmailState('idle')
    setEmailError('')
    setEmailIdempotencyKey(createIdempotencyKey())
    setToast(null)
  }

  function closeEmailFile() {
    setEmailFile(null)
    setEmailError('')
    setEmailState('idle')
  }

  function openRenameFile(file: VaultFile) {
    setRenameFile(file)
    setRenameName(file.file_name)
    setRenameState('idle')
    setRenameError('')
    setToast(null)
  }

  function closeRenameFile() {
    if (renameState === 'saving') return
    setRenameFile(null)
    setRenameName('')
    setRenameError('')
  }

  async function handleRenameFile() {
    if (!renameFile || renameState === 'saving') return

    const fileName = renameName.trim()
    if (!fileName) {
      setRenameError('Filename is required.')
      return
    }
    if (fileName.includes('/') || fileName.includes('\\')) {
      setRenameError('Filename cannot contain path separators.')
      return
    }
    if (fileName.length > 255) {
      setRenameError('Filename must be 255 characters or fewer.')
      return
    }

    setRenameState('saving')
    setRenameError('')
    try {
      const response = await api.patch<VaultFile>(`/uploads/${renameFile.id}/`, { file_name: fileName })
      const updated = response.data
      setFiles((current) => current.map((file) => file.id === updated.id ? updated : file))
      setSelectedFile((current) => current?.id === updated.id ? updated : current)
      setShareFile((current) => current?.id === updated.id ? updated : current)
      setEmailFile((current) => current?.id === updated.id ? updated : current)
      setNativeShareFallbackFile((current) => current?.id === updated.id ? updated : current)
      setMoveFile((current) => current?.id === updated.id ? updated : current)
      setRenameFile(null)
      setRenameName('')
      setToast({ tone: 'success', message: 'File renamed.' })
    } catch (error) {
      const code = typeof error === 'object' && error !== null && 'response' in error
        ? (error as { response?: { data?: { code?: string } } }).response?.data?.code
        : undefined
      if (code === 'file_name_required') setRenameError('Filename is required.')
      else if (code === 'file_name_too_long') setRenameError('Filename must be 255 characters or fewer.')
      else if (code === 'invalid_file_name') setRenameError('Filename cannot contain path separators.')
      else setRenameError('Could not rename this file.')
    } finally {
      setRenameState('idle')
    }
  }

  async function handleEmailFile() {
    if (!emailFile || emailState === 'sending') return

    const to = emailTo.trim()
    const subject = emailSubject.trim()
    const message = emailMessage.trim()
    if (!isValidEmailAddress(to)) {
      setEmailError('Enter one valid recipient email address.')
      return
    }
    if (!subject) {
      setEmailError('Subject is required.')
      return
    }

    setEmailState('sending')
    setEmailError('')
    try {
      const response = await api.post<VaultEmailResponse>(
        `/uploads/${emailFile.id}/email/`,
        { to, subject, message },
        { headers: { 'Idempotency-Key': emailIdempotencyKey || createIdempotencyKey() } },
      )
      if (response.data.status === 'sent') {
        setEmailState('sent')
        setToast({ tone: 'success', message: 'Email sent.' })
        return
      }
      setEmailState('idle')
      setEmailError('Email could not be sent. Please try again.')
    } catch (error) {
      setEmailState('idle')
      setEmailError(emailErrorMessage(error))
    }
  }

  async function loadShareLinks(file: VaultFile) {
    setShareLinksLoading(true)
    setShareError('')
    try {
      const response = await api.get<VaultShare[]>(`/uploads/${file.id}/shares/`)
      setShareLinks(response.data)
    } catch {
      setShareError('Could not load active share links.')
    } finally {
      setShareLinksLoading(false)
    }
  }

  function openShareLink(file: VaultFile) {
    setShareFile(file)
    setShareLinks([])
    setShareExpiration('7d')
    setShareError('')
    setToast(null)
    void loadShareLinks(file)
  }

  function showNativeShareFallback(file: VaultFile, message = "This browser can't share this file directly.") {
    setNativeShareFallbackFile(file)
    setToast({ tone: 'info', message })
  }

  async function handleShareFile(file: VaultFile) {
    setToast(null)
    setNativeShareFallbackFile(null)

    if (file.file_size > NATIVE_SHARE_PREPARATION_LIMIT_BYTES) {
      logNativeShareDiagnostic('file_too_large', file, { limitBytes: NATIVE_SHARE_PREPARATION_LIMIT_BYTES })
      showNativeShareFallback(file, `Direct sharing is limited to files up to ${formatBytes(NATIVE_SHARE_PREPARATION_LIMIT_BYTES)}.`)
      return
    }

    if (!window.isSecureContext) {
      logNativeShareDiagnostic('insecure_context', file)
      showNativeShareFallback(file)
      return
    }

    const nativeNavigator = navigator as NativeShareNavigator
    if (!nativeNavigator.share) {
      logNativeShareDiagnostic('navigator_share_unavailable', file)
      showNativeShareFallback(file)
      return
    }
    if (!nativeNavigator.canShare) {
      logNativeShareDiagnostic('navigator_canShare_unavailable', file)
      showNativeShareFallback(file)
      return
    }

    setWorkingFileId(file.id)
    try {
      let response
      try {
        response = await api.get<Blob>(`/uploads/${file.id}/delivery/`, { responseType: 'blob' })
      } catch (error) {
        logNativeShareDiagnostic('delivery_failure', file, {
          status: responseStatus(error),
          errorName: (error as { name?: string })?.name,
        })
        showNativeShareFallback(file, "This file couldn't be prepared for sharing.")
        return
      }

      const contentType = response.data.type || file.content_type || 'application/octet-stream'
      const nativeFile = new File([response.data], file.file_name, { type: contentType })
      const shareData = { files: [nativeFile], title: file.file_name }

      let canShareFiles = false
      try {
        canShareFiles = nativeNavigator.canShare(shareData)
      } catch (error) {
        logNativeShareDiagnostic('canShare_files_error', file, {
          errorName: (error as { name?: string })?.name,
        })
        showNativeShareFallback(file)
        return
      }

      if (!canShareFiles) {
        logNativeShareDiagnostic('canShare_files_false', file, {
          preparedContentType: contentType,
          preparedSize: response.data.size,
        })
        showNativeShareFallback(file)
        return
      }

      try {
        await nativeNavigator.share(shareData)
      } catch (error) {
        if ((error as { name?: string })?.name === 'AbortError') {
          logNativeShareDiagnostic('share_cancelled', file)
          return
        }
        logNativeShareDiagnostic('share_error', file, {
          errorName: (error as { name?: string })?.name,
        })
        showNativeShareFallback(file, "This browser couldn't share this file directly.")
        return
      }
      setToast({ tone: 'success', message: `${file.file_name} shared.` })
    } catch (error) {
      logNativeShareDiagnostic('share_error', file, {
        errorName: (error as { name?: string })?.name,
      })
      showNativeShareFallback(file, "This browser couldn't share this file directly.")
    } finally {
      setWorkingFileId(null)
    }
  }

  async function handleCreateShare() {
    if (!shareFile) return
    setSharing(true)
    setShareError('')
    setToast(null)
    try {
      const response = await api.post<VaultShare>(`/uploads/${shareFile.id}/shares/`, { expiration: shareExpiration })
      setShareLinks((current) => [response.data, ...current.filter((share) => share.id !== response.data.id)])
      setToast({ tone: 'success', message: 'Share link created.' })
    } catch {
      setShareError('Could not create a share link for this file.')
    } finally {
      setSharing(false)
    }
  }

  async function handleRevokeShare(share: VaultShare) {
    if (!shareFile || revokingShareId) return
    const confirmed = window.confirm('Revoke this Share Link? People with this link will no longer be able to access the file.')
    if (!confirmed) return

    setRevokingShareId(share.id)
    setShareError('')
    try {
      await api.post(`/uploads/${shareFile.id}/shares/${share.id}/revoke/`, {})
      setShareLinks((current) => current.filter((item) => item.id !== share.id))
      setToast({ tone: 'success', message: 'Share link revoked.' })
    } catch {
      setShareError('Could not revoke this share link.')
    } finally {
      setRevokingShareId(null)
    }
  }

  async function copyShareLink(link: string) {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(link)
      } else {
        const input = document.createElement('input')
        input.value = link
        document.body.appendChild(input)
        input.select()
        document.execCommand('copy')
        input.remove()
      }
      setToast({ tone: 'success', message: 'Share link copied.' })
    } catch {
      setToast({ tone: 'error', message: 'Could not copy the share link.' })
    }
  }


  async function handleRemove(file: VaultFile) {
    const confirmed = window.confirm('Remove this file from your active Vault? Shared links will stop working, but this does not permanently destroy the stored object.')
    if (!confirmed) return
    setWorkingFileId(file.id)
    setToast(null)
    try {
      await api.delete(`/uploads/${file.id}/`)
      setSelectedFile((current) => (current?.id === file.id ? null : current))
      setShareFile((current) => (current?.id === file.id ? null : current))
      setEmailFile((current) => (current?.id === file.id ? null : current))
      setRenameFile((current) => (current?.id === file.id ? null : current))
      setToast({ tone: 'success', message: `${file.file_name} removed from Vault.` })
      await refreshVault()
    } catch {
      setToast({ tone: 'error', message: 'Could not remove this file.' })
    } finally {
      setWorkingFileId(null)
    }
  }

  const percent = storagePercent(storage)

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 py-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="mb-2 text-xs font-bold uppercase text-[#D4900A]">bonUP</p>
          <h1 className="text-3xl font-bold text-slate-900">Vault</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-600">Your files and storage in bonUP.</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => setAddStorageOpen(true)}
            className="h-10 rounded-lg border border-slate-300 bg-white px-4 text-sm font-bold text-slate-700 hover:bg-slate-50"
          >
            Add Storage
          </button>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="inline-flex h-10 items-center gap-2 rounded-lg bg-slate-900 px-4 text-sm font-bold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            <PlusIcon className="h-4 w-4" />
            {uploading ? 'Uploading...' : 'Upload Files'}
          </button>
          <input ref={fileInputRef} type="file" multiple className="hidden" onChange={handleUpload} />
        </div>
      </header>

      {toast && (
        <div className={`rounded-lg border px-4 py-3 text-sm font-semibold ${toast.tone === 'error' ? 'border-red-200 bg-red-50 text-red-700' : toast.tone === 'success' ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-white text-slate-700'}`}>
          {toast.message}
        </div>
      )}

      {uploadQueue.length > 0 && (
        <UploadQueuePanel
          items={uploadQueue}
          uploading={uploading}
          onDismiss={dismissUploadQueue}
        />
      )}

      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs font-bold uppercase text-slate-400">Storage</p>
            <h2 className="mt-1 text-xl font-bold text-slate-900">Capacity overview</h2>
            <p className="mt-1 text-sm text-slate-500">Active Vault usage is calculated from your managed files.</p>
          </div>
          <button type="button" onClick={loadStorage} className="h-9 rounded-lg border border-slate-300 px-3 text-sm font-bold text-slate-700 hover:bg-slate-50">
            Refresh
          </button>
        </div>

        {storageState === 'loading' && <p className="mt-5 text-sm font-semibold text-slate-600">Loading storage...</p>}
        {storageState === 'error' && (
          <div className="mt-5 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Storage details could not be loaded. Files can still be browsed below.
          </div>
        )}
        {storageState === 'success' && storage && (
          <div className="mt-5">
            <div className="grid gap-3 md:grid-cols-3">
              <Metric label="Capacity" value={formatBytes(storage.capacity_bytes)} />
              <Metric label="Used" value={formatBytes(storage.used_bytes)} />
              <Metric label="Available" value={formatBytes(storage.available_bytes)} />
            </div>
            <div className="mt-5">
              <div className="mb-2 flex items-center justify-between text-xs font-bold uppercase text-slate-400">
                <span>{percent}% used</span>
                <span>{formatBytes(storage.available_bytes)} available</span>
              </div>
              <div className="h-3 overflow-hidden rounded-full bg-slate-100">
                <div className="h-full rounded-full bg-[#F5A623] transition-all" style={{ width: `${percent}%` }} />
              </div>
              {storage.capacity_bytes === 0 && (
                <p className="mt-3 text-sm text-slate-500">No storage capacity is active on this account yet.</p>
              )}
            </div>
          </div>
        )}
      </section>

      <section className="min-h-[520px] rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 p-4 lg:p-5">
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <FolderBreadcrumbs
                breadcrumbs={folderBreadcrumbs}
                onRoot={() => setCurrentFolderId(null)}
                onOpen={(folder) => setCurrentFolderId(folder.id)}
              />
              <button type="button" onClick={() => openFolderNameModal('create')} className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-bold text-slate-700 hover:bg-slate-50">
                <FolderIcon className="h-4 w-4" />
                New Folder
              </button>
            </div>
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div className="flex flex-wrap gap-2">
                {CATEGORIES.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => setCategory(item.key)}
                    className={`rounded-lg border px-3 py-2 text-sm font-bold ${category === item.key ? 'border-[#F5A623] bg-[#FFF7E8] text-slate-900' : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'}`}
                  >
                    {item.label} <span className="ml-1 text-xs text-slate-400">{countsByCategory[item.key]}</span>
                  </button>
                ))}
              </div>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <label className="relative block min-w-[240px]">
                  <MagnifyingGlassIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Search files"
                    className="h-10 w-full rounded-lg border border-slate-300 bg-white pl-9 pr-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-100"
                  />
                </label>
                <select
                  value={sortKey}
                  onChange={(event) => setSortKey(event.target.value as SortKey)}
                  className="h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-100"
                >
                  <option value="newest">Newest</option>
                  <option value="oldest">Oldest</option>
                  <option value="name">Name</option>
                  <option value="size">Size</option>
                </select>
                <div className="flex h-10 rounded-lg border border-slate-300 bg-white p-1">
                  <button type="button" onClick={() => setViewMode('grid')} className={`rounded-md px-3 text-xs font-bold ${viewMode === 'grid' ? 'bg-slate-900 text-white' : 'text-slate-500'}`}>Grid</button>
                  <button type="button" onClick={() => setViewMode('list')} className={`rounded-md px-3 text-xs font-bold ${viewMode === 'list' ? 'bg-slate-900 text-white' : 'text-slate-500'}`}>List</button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {filesState === 'loading' && <FileLoadingState />}
        {filesState === 'error' && <FileErrorState onRetry={refreshVault} />}
        {filesState === 'success' && visibleFolders.length === 0 && currentFolderFiles.length === 0 && <EmptyState onUpload={() => fileInputRef.current?.click()} />}
        {filesState === 'success' && visibleFolders.length === 0 && currentFolderFiles.length > 0 && filteredFiles.length === 0 && <NoMatchesState />}
        {filesState === 'success' && (visibleFolders.length > 0 || filteredFiles.length > 0) && (
          <div className={viewMode === 'grid' ? 'grid gap-4 p-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4' : 'divide-y divide-slate-100'}>
            {visibleFolders.map((folder) => (
              <FolderTile
                key={folder.id}
                folder={folder}
                mode={viewMode}
                onOpen={() => setCurrentFolderId(folder.id)}
                onRename={() => openFolderNameModal('rename', folder)}
                onMove={() => openMoveFolder(folder)}
                onDelete={() => void deleteFolder(folder)}
              />
            ))}
            {filteredFiles.map((file) => (
              <FileTile
                key={file.id}
                file={file}
                mode={viewMode}
                working={workingFileId === file.id}
                onOpen={() => setSelectedFile(file)}
                onDownload={() => handleDownload(file)}
                onEmailFile={() => openEmailFile(file)}
                onShareFile={() => void handleShareFile(file)}
                onShareLink={() => openShareLink(file)}
                onRename={() => openRenameFile(file)}
                onMove={() => openMoveFile(file)}
                onRemove={() => void handleRemove(file)}
              />
            ))}
          </div>
        )}
      </section>

      {selectedFile && (
        <FileDetailsModal
          file={selectedFile}
          working={workingFileId === selectedFile.id}
          onClose={() => setSelectedFile(null)}
          onDownload={() => handleDownload(selectedFile)}
          onEmailFile={() => openEmailFile(selectedFile)}
          onShareFile={() => void handleShareFile(selectedFile)}
          onShareLink={() => openShareLink(selectedFile)}
          onRename={() => openRenameFile(selectedFile)}
          onMove={() => openMoveFile(selectedFile)}
          onRemove={() => void handleRemove(selectedFile)}
        />
      )}


      {folderNameModal && (
        <FolderNameModal
          mode={folderNameModal.mode}
          value={folderName}
          saving={folderSaving}
          error={folderError}
          onChange={setFolderName}
          onSave={() => void saveFolderName()}
          onClose={closeFolderNameModal}
        />
      )}

      {moveFile && (
        <MoveFileModal
          file={moveFile}
          folders={folders}
          folderById={folderById}
          value={moveFileFolderId}
          moving={movingFile}
          error={moveFileError}
          onChange={setMoveFileFolderId}
          onMove={() => void handleMoveFile()}
          onClose={closeMoveFile}
        />
      )}

      {moveFolderModal && (
        <MoveFolderModal
          folder={moveFolderModal}
          folders={folders}
          folderById={folderById}
          value={moveFolderParentId}
          moving={movingFolder}
          error={moveFolderError}
          onChange={setMoveFolderParentId}
          onMove={() => void handleMoveFolder()}
          onClose={closeMoveFolder}
        />
      )}

      {renameFile && (
        <RenameFileModal
          file={renameFile}
          value={renameName}
          renameState={renameState}
          error={renameError}
          onChange={setRenameName}
          onSave={() => void handleRenameFile()}
          onClose={closeRenameFile}
        />
      )}

      {emailFile && (
        <EmailFileModal
          file={emailFile}
          to={emailTo}
          subject={emailSubject}
          message={emailMessage}
          emailState={emailState}
          error={emailError}
          onToChange={setEmailTo}
          onSubjectChange={setEmailSubject}
          onMessageChange={setEmailMessage}
          onSend={() => void handleEmailFile()}
          onDownload={() => handleDownload(emailFile)}
          onShareLink={() => openShareLink(emailFile)}
          onClose={closeEmailFile}
        />
      )}

      {shareFile && (
        <ShareModal
          file={shareFile}
          expiration={shareExpiration}
          shares={shareLinks}
          sharesLoading={shareLinksLoading}
          sharing={sharing}
          revokingShareId={revokingShareId}
          error={shareError}
          onExpirationChange={setShareExpiration}
          onCreateShare={() => void handleCreateShare()}
          onCopy={(link) => void copyShareLink(link)}
          onRevoke={(share) => void handleRevokeShare(share)}
          onClose={() => setShareFile(null)}
        />
      )}

      {nativeShareFallbackFile && (
        <NativeShareFallbackModal
          file={nativeShareFallbackFile}
          onDownload={() => handleDownload(nativeShareFallbackFile)}
          onShareLink={() => {
            openShareLink(nativeShareFallbackFile)
            setNativeShareFallbackFile(null)
          }}
          onClose={() => setNativeShareFallbackFile(null)}
        />
      )}

      {addStorageOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Add Storage</h2>
                <p className="mt-2 text-sm leading-6 text-slate-600">Additional storage plans are being updated for recurring billing. Purchasing is not available from Vault yet.</p>
              </div>
              <button type="button" onClick={() => setAddStorageOpen(false)} className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <button type="button" onClick={() => setAddStorageOpen(false)} className="mt-5 h-10 w-full rounded-lg bg-slate-900 text-sm font-bold text-white hover:bg-slate-800">
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <p className="text-xs font-bold uppercase text-slate-400">{label}</p>
      <p className="mt-2 text-xl font-bold text-slate-900">{value}</p>
    </div>
  )
}

function uploadStatusTone(status: UploadQueueStatus) {
  if (status === 'uploaded') return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  if (status === 'failed') return 'border-red-200 bg-red-50 text-red-700'
  if (status === 'uploading') return 'border-blue-200 bg-blue-50 text-blue-700'
  return 'border-slate-200 bg-white text-slate-600'
}

function uploadStatusLabel(status: UploadQueueStatus) {
  if (status === 'waiting') return 'Waiting'
  if (status === 'uploading') return 'Uploading'
  if (status === 'uploaded') return 'Uploaded'
  return 'Failed'
}

function UploadQueuePanel({
  items,
  uploading,
  onDismiss,
}: {
  items: UploadQueueItem[]
  uploading: boolean
  onDismiss: () => void
}) {
  const completed = items.every((item) => item.status === 'uploaded' || item.status === 'failed')

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase text-slate-400">Upload queue</p>
          <p className="mt-1 text-sm font-semibold text-slate-700">{items.length} {items.length === 1 ? 'file' : 'files'} selected</p>
        </div>
        {completed && !uploading && (
          <button type="button" onClick={onDismiss} className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-bold text-slate-700 hover:bg-slate-50">
            Dismiss
          </button>
        )}
      </div>
      <div className="mt-3 divide-y divide-slate-100 rounded-lg border border-slate-200">
        {items.map((item) => (
          <div key={item.id} className="flex flex-col gap-2 p-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <p title={item.name} className="truncate text-sm font-bold text-slate-900">{item.name}</p>
              <p className="mt-1 text-xs text-slate-500">{formatBytes(item.size)}</p>
              {item.error && <p className="mt-1 text-xs font-semibold leading-5 text-red-600">{item.error}</p>}
            </div>
            <span className={`inline-flex w-fit shrink-0 rounded-full border px-2.5 py-1 text-xs font-bold ${uploadStatusTone(item.status)}`}>
              {uploadStatusLabel(item.status)}
            </span>
          </div>
        ))}
      </div>
    </section>
  )
}

function FolderBreadcrumbs({
  breadcrumbs,
  onRoot,
  onOpen,
}: {
  breadcrumbs: VaultFolder[]
  onRoot: () => void
  onOpen: (folder: VaultFolder) => void
}) {
  return (
    <nav className="flex min-w-0 flex-wrap items-center gap-2 text-sm font-semibold text-slate-600">
      <button type="button" onClick={onRoot} className="rounded-lg border border-slate-200 px-3 py-1.5 text-slate-700 hover:bg-slate-50">Vault root</button>
      {breadcrumbs.map((folder) => (
        <span key={folder.id} className="flex min-w-0 items-center gap-2">
          <span className="text-slate-300">/</span>
          <button type="button" onClick={() => onOpen(folder)} title={folder.name} className="max-w-[160px] truncate rounded-lg border border-slate-200 px-3 py-1.5 text-slate-700 hover:bg-slate-50">{folder.name}</button>
        </span>
      ))}
    </nav>
  )
}

function FolderTile({
  folder,
  mode,
  onOpen,
  onRename,
  onMove,
  onDelete,
}: {
  folder: VaultFolder
  mode: ViewMode
  onOpen: () => void
  onRename: () => void
  onMove: () => void
  onDelete: () => void
}) {
  if (mode === 'list') {
    return (
      <div className="flex flex-col gap-3 p-4 hover:bg-slate-50 lg:flex-row lg:items-center lg:justify-between">
        <button type="button" onClick={onOpen} className="flex min-w-0 flex-1 items-center gap-3 text-left">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-amber-50 text-[#D4900A]">
            <FolderIcon className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <p title={folder.name} className="truncate text-sm font-bold text-slate-900">{folder.name}</p>
            <p className="mt-1 text-xs text-slate-500">Folder</p>
          </div>
        </button>
        <FolderActions onOpen={onOpen} onRename={onRename} onMove={onMove} onDelete={onDelete} />
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm transition hover:border-slate-300 hover:shadow-md">
      <button type="button" onClick={onOpen} className="block w-full text-left">
        <div className="flex aspect-[4/3] items-center justify-center bg-amber-50 text-[#D4900A]">
          <FolderIcon className="h-16 w-16" />
        </div>
        <div className="p-4">
          <p title={folder.name} className="truncate text-sm font-bold text-slate-900">{folder.name}</p>
          <p className="mt-1 text-xs text-slate-500">Folder</p>
        </div>
      </button>
      <div className="border-t border-slate-100 px-3 py-2">
        <FolderActions onOpen={onOpen} onRename={onRename} onMove={onMove} onDelete={onDelete} />
      </div>
    </div>
  )
}

function FolderActions({
  onOpen,
  onRename,
  onMove,
  onDelete,
}: {
  onOpen: () => void
  onRename: () => void
  onMove: () => void
  onDelete: () => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" onClick={onOpen} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-bold text-slate-700 hover:bg-slate-50">Open</button>
      <button type="button" onClick={onMove} className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2 py-1.5 text-xs font-bold text-slate-700 hover:bg-slate-50" title="Move Folder">
        <FolderIcon className="h-4 w-4" />
        Move
      </button>
      <button type="button" onClick={onRename} className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-50" title="Rename Folder">
        <PencilSquareIcon className="h-4 w-4" />
      </button>
      <button type="button" onClick={onDelete} className="rounded-lg border border-red-200 p-1.5 text-red-600 hover:bg-red-50" title="Delete Folder">
        <TrashIcon className="h-4 w-4" />
      </button>
    </div>
  )
}

function FolderNameModal({
  mode,
  value,
  saving,
  error,
  onChange,
  onSave,
  onClose,
}: {
  mode: 'create' | 'rename'
  value: string
  saving: boolean
  error: string
  onChange: (value: string) => void
  onSave: () => void
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase text-[#D4900A]">bonUP Vault</p>
            <h2 className="mt-1 text-lg font-bold text-slate-900">{mode === 'create' ? 'New Folder' : 'Rename Folder'}</h2>
          </div>
          <button type="button" onClick={onClose} disabled={saving} className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-50">
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>

        <label className="mt-5 block text-sm font-bold text-slate-700">
          Folder name
          <input
            value={value}
            onChange={(event) => onChange(event.target.value)}
            disabled={saving}
            autoFocus
            className="mt-2 block h-11 w-full min-w-0 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-800 outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-100 disabled:bg-slate-50"
          />
        </label>

        {error && <p className="mt-3 text-sm font-semibold text-red-600">{error}</p>}

        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button type="button" onClick={onClose} disabled={saving} className="h-10 rounded-lg border border-slate-300 px-4 text-sm font-bold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">Cancel</button>
          <button type="button" onClick={onSave} disabled={saving} className="h-10 rounded-lg bg-slate-900 px-4 text-sm font-bold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400">
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

function MoveFileModal({
  file,
  folders,
  folderById,
  value,
  moving,
  error,
  onChange,
  onMove,
  onClose,
}: {
  file: VaultFile
  folders: VaultFolder[]
  folderById: Map<string, VaultFolder>
  value: string
  moving: boolean
  error: string
  onChange: (value: string) => void
  onMove: () => void
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase text-[#D4900A]">bonUP Vault</p>
            <h2 className="mt-1 text-lg font-bold text-slate-900">Move File</h2>
            <p title={file.file_name} className="mt-2 truncate text-sm font-semibold text-slate-500">{file.file_name}</p>
          </div>
          <button type="button" onClick={onClose} disabled={moving} className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-50">
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>

        <label className="mt-5 block text-sm font-bold text-slate-700">
          Location
          <select
            value={value}
            onChange={(event) => onChange(event.target.value)}
            disabled={moving}
            className="mt-2 h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-100 disabled:bg-slate-50"
          >
            <option value="">Vault root</option>
            {folders.map((folder) => (
              <option key={folder.id} value={folder.id}>{folderPathLabel(folder, folderById)}</option>
            ))}
          </select>
        </label>

        {error && <p className="mt-3 text-sm font-semibold text-red-600">{error}</p>}

        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button type="button" onClick={onClose} disabled={moving} className="h-10 rounded-lg border border-slate-300 px-4 text-sm font-bold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">Cancel</button>
          <button type="button" onClick={onMove} disabled={moving} className="h-10 rounded-lg bg-slate-900 px-4 text-sm font-bold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400">
            {moving ? 'Moving...' : 'Move'}
          </button>
        </div>
      </div>
    </div>
  )
}

function MoveFolderModal({
  folder,
  folders,
  folderById,
  value,
  moving,
  error,
  onChange,
  onMove,
  onClose,
}: {
  folder: VaultFolder
  folders: VaultFolder[]
  folderById: Map<string, VaultFolder>
  value: string
  moving: boolean
  error: string
  onChange: (value: string) => void
  onMove: () => void
  onClose: () => void
}) {
  const destinations = folders.filter((candidate) => candidate.id !== folder.id && !isFolderDescendant(candidate, folder.id, folderById))

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase text-[#D4900A]">bonUP Vault</p>
            <h2 className="mt-1 text-lg font-bold text-slate-900">Move Folder</h2>
            <p title={folder.name} className="mt-2 truncate text-sm font-semibold text-slate-500">{folder.name}</p>
          </div>
          <button type="button" onClick={onClose} disabled={moving} className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-50">
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>

        <label className="mt-5 block text-sm font-bold text-slate-700">
          Location
          <select
            value={value}
            onChange={(event) => onChange(event.target.value)}
            disabled={moving}
            className="mt-2 h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-100 disabled:bg-slate-50"
          >
            <option value="">Vault root</option>
            {destinations.map((candidate) => (
              <option key={candidate.id} value={candidate.id}>{folderPathLabel(candidate, folderById)}</option>
            ))}
          </select>
        </label>

        {error && <p className="mt-3 text-sm font-semibold text-red-600">{error}</p>}

        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button type="button" onClick={onClose} disabled={moving} className="h-10 rounded-lg border border-slate-300 px-4 text-sm font-bold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">Cancel</button>
          <button type="button" onClick={onMove} disabled={moving} className="h-10 rounded-lg bg-slate-900 px-4 text-sm font-bold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400">
            {moving ? 'Moving...' : 'Move'}
          </button>
        </div>
      </div>
    </div>
  )
}

function FileLoadingState() {
  return (
    <div className="grid gap-4 p-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
      {Array.from({ length: 8 }).map((_, index) => (
        <div key={index} className="h-44 animate-pulse rounded-lg border border-slate-200 bg-slate-50" />
      ))}
    </div>
  )
}

function FileErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="p-5">
      <div className="rounded-lg border border-red-200 bg-red-50 p-5">
        <p className="text-sm font-bold text-red-700">Files could not be loaded.</p>
        <p className="mt-1 text-sm text-red-700">Please try again. Storage details may still be available above.</p>
        <button type="button" onClick={onRetry} className="mt-4 h-10 rounded-lg bg-slate-900 px-4 text-sm font-bold text-white">Retry</button>
      </div>
    </div>
  )
}

function EmptyState({ onUpload }: { onUpload: () => void }) {
  return (
    <div className="flex min-h-[420px] flex-col items-center justify-center p-8 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        <RectangleStackIcon className="h-8 w-8" />
      </div>
      <h2 className="mt-5 text-xl font-bold text-slate-900">No files yet</h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">Upload files to keep them organized in your bonUP Vault.</p>
      <button type="button" onClick={onUpload} className="mt-5 inline-flex h-10 items-center gap-2 rounded-lg bg-slate-900 px-4 text-sm font-bold text-white hover:bg-slate-800">
        <PlusIcon className="h-4 w-4" />
        Upload Files
      </button>
    </div>
  )
}

function NoMatchesState() {
  return (
    <div className="flex min-h-[320px] flex-col items-center justify-center p-8 text-center">
      <h2 className="text-lg font-bold text-slate-900">No matching files</h2>
      <p className="mt-2 text-sm text-slate-500">Adjust the category, search, or sort options.</p>
    </div>
  )
}

function FileTile({
  file,
  mode,
  working,
  onOpen,
  onDownload,
  onEmailFile,
  onShareFile,
  onShareLink,
  onRename,
  onMove,
  onRemove,
}: {
  file: VaultFile
  mode: ViewMode
  working: boolean
  onOpen: () => void
  onDownload: () => void
  onEmailFile: () => void
  onShareFile: () => void
  onShareLink: () => void
  onRename: () => void
  onMove: () => void
  onRemove: () => void
}) {
  const category = categoryForFile(file)
  const Icon = fileIcon(category)
  const isImage = category === 'images' && Boolean(file.file_url)

  if (mode === 'list') {
    return (
      <div className="flex flex-col gap-3 p-4 hover:bg-slate-50 lg:flex-row lg:items-center lg:justify-between">
        <button type="button" onClick={onOpen} className="flex min-w-0 flex-1 items-center gap-3 text-left">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
            <Icon className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-bold text-slate-900">{file.file_name}</p>
            <p className="mt-1 text-xs text-slate-500">{typeLabel(file)} · {formatBytes(file.file_size)} · {formatDate(file.uploaded_at)}</p>
          </div>
        </button>
        <FileActions working={working} onOpen={onOpen} onDownload={onDownload} onEmailFile={onEmailFile} onShareFile={onShareFile} onShareLink={onShareLink} onRename={onRename} onMove={onMove} onRemove={onRemove} />
      </div>
    )
  }

  return (
    <div className="group overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm transition hover:border-slate-300 hover:shadow-md">
      <button type="button" onClick={onOpen} className="block w-full text-left">
        <div className="flex aspect-[4/3] items-center justify-center bg-slate-50">
          {isImage ? (
            <img src={file.file_url || ''} alt="" className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-white text-slate-500 shadow-sm">
              <Icon className="h-8 w-8" />
            </div>
          )}
        </div>
        <div className="p-4">
          <p className="truncate text-sm font-bold text-slate-900">{file.file_name}</p>
          <p className="mt-1 text-xs text-slate-500">{typeLabel(file)} · {formatBytes(file.file_size)}</p>
          <p className="mt-2 text-xs text-slate-400">{formatDate(file.uploaded_at)}</p>
        </div>
      </button>
      <div className="border-t border-slate-100 px-3 py-2">
        <FileActions working={working} onOpen={onOpen} onDownload={onDownload} onEmailFile={onEmailFile} onShareFile={onShareFile} onShareLink={onShareLink} onRename={onRename} onMove={onMove} onRemove={onRemove} />
      </div>
    </div>
  )
}

function FileActions({
  working,
  onOpen,
  onDownload,
  onEmailFile,
  onShareFile,
  onShareLink,
  onRename,
  onMove,
  onRemove,
}: {
  working: boolean
  onOpen: () => void
  onDownload: () => void
  onEmailFile: () => void
  onShareFile: () => void
  onShareLink: () => void
  onRename: () => void
  onMove: () => void
  onRemove: () => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" onClick={onOpen} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-bold text-slate-700 hover:bg-slate-50">View</button>
      <button type="button" onClick={onDownload} className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-50" title="Download">
        <ArrowDownTrayIcon className="h-4 w-4" />
      </button>
      <button type="button" onClick={onEmailFile} disabled={working} className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2 py-1.5 text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50" title="Email File">
        <EnvelopeIcon className="h-4 w-4" />
        Email File
      </button>
      <button type="button" onClick={onShareFile} disabled={working} className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2 py-1.5 text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50" title="Share File">
        <ShareIcon className="h-4 w-4" />
        Share File
      </button>
      <button type="button" onClick={onShareLink} disabled={working} className="rounded-lg border border-slate-200 px-2 py-1.5 text-xs font-bold text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50" title="Share Link">
        Share Link
      </button>
      <button type="button" onClick={onRename} disabled={working} className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50" title="Rename">
        <PencilSquareIcon className="h-4 w-4" />
      </button>
      <button type="button" onClick={onMove} disabled={working} className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2 py-1.5 text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50" title="Move File">
        <FolderIcon className="h-4 w-4" />
        Move
      </button>
      <button type="button" onClick={onRemove} disabled={working} className="rounded-lg border border-red-200 p-1.5 text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50" title="Remove from Vault">
        <TrashIcon className="h-4 w-4" />
      </button>
    </div>
  )
}



function RenameFileModal({
  file,
  value,
  renameState,
  error,
  onChange,
  onSave,
  onClose,
}: {
  file: VaultFile
  value: string
  renameState: RenameState
  error: string
  onChange: (value: string) => void
  onSave: () => void
  onClose: () => void
}) {
  const saving = renameState === 'saving'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase text-[#D4900A]">bonUP Vault</p>
            <h2 className="mt-1 text-lg font-bold text-slate-900">Rename File</h2>
            <p title={file.file_name} className="mt-2 truncate text-sm font-semibold text-slate-500">{file.file_name}</p>
          </div>
          <button type="button" onClick={onClose} disabled={saving} className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-50">
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>

        <label className="mt-5 block text-sm font-bold text-slate-700">
          Filename
          <input
            value={value}
            onChange={(event) => onChange(event.target.value)}
            disabled={saving}
            autoFocus
            className="mt-2 block h-11 w-full min-w-0 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-800 outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-100 disabled:bg-slate-50"
          />
        </label>

        {error && <p className="mt-3 text-sm font-semibold text-red-600">{error}</p>}

        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button type="button" onClick={onClose} disabled={saving} className="h-10 rounded-lg border border-slate-300 px-4 text-sm font-bold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">
            Cancel
          </button>
          <button type="button" onClick={onSave} disabled={saving} className="h-10 rounded-lg bg-slate-900 px-4 text-sm font-bold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400">
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}


function EmailFileModal({
  file,
  to,
  subject,
  message,
  emailState,
  error,
  onToChange,
  onSubjectChange,
  onMessageChange,
  onSend,
  onDownload,
  onShareLink,
  onClose,
}: {
  file: VaultFile
  to: string
  subject: string
  message: string
  emailState: EmailState
  error: string
  onToChange: (value: string) => void
  onSubjectChange: (value: string) => void
  onMessageChange: (value: string) => void
  onSend: () => void
  onDownload: () => void
  onShareLink: () => void
  onClose: () => void
}) {
  const sending = emailState === 'sending'
  const sent = emailState === 'sent'
  const oversized = error === 'This file is too large to email as an attachment.'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-slate-900/40 p-4 sm:p-6">
      <div className="w-[min(92vw,640px)] max-w-full rounded-lg bg-white p-5 shadow-xl sm:p-6">
        <div className="flex min-w-0 items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase text-[#D4900A]">bonUP Vault</p>
            <h2 className="mt-1 text-lg font-bold leading-6 text-slate-900">Email File</h2>
          </div>
          <button type="button" onClick={onClose} className="shrink-0 rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>

        <div className="mt-5 grid min-w-0 gap-4">
          <label className="block min-w-0 text-sm font-bold text-slate-700">
            To
            <input
              type="email"
              value={to}
              onChange={(event) => onToChange(event.target.value)}
              disabled={sending || sent}
              placeholder="recipient@example.com"
              className="mt-2 block h-11 w-full min-w-0 max-w-full rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium leading-5 text-slate-800 outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-100 disabled:bg-slate-50"
            />
          </label>

          <label className="block min-w-0 text-sm font-bold text-slate-700">
            Subject
            <input
              value={subject}
              onChange={(event) => onSubjectChange(event.target.value)}
              disabled={sending || sent}
              className="mt-2 block h-11 w-full min-w-0 max-w-full rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium leading-5 text-slate-800 outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-100 disabled:bg-slate-50"
            />
          </label>

          <label className="block min-w-0 text-sm font-bold text-slate-700">
            Message
            <textarea
              value={message}
              onChange={(event) => onMessageChange(event.target.value)}
              disabled={sending || sent}
              rows={4}
              placeholder="Optional message"
              className="mt-2 block w-full min-w-0 max-w-full resize-none rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm font-medium leading-5 text-slate-800 outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-100 disabled:bg-slate-50"
            />
          </label>

          <div className="min-w-0">
            <p className="text-sm font-bold text-slate-700">Attachment</p>
            <div className="mt-2 flex w-full max-w-full items-start gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4">
              <DocumentIcon className="mt-0.5 h-6 w-6 shrink-0 text-slate-500" />
              <div className="min-w-0 flex-1">
                <p title={file.file_name} className="text-sm font-semibold leading-5 text-slate-900 [overflow-wrap:anywhere] sm:text-base">{file.file_name}</p>
                <p className="mt-1 text-sm font-medium leading-5 text-slate-500">{formatBytes(file.file_size)}</p>
              </div>
            </div>
          </div>
        </div>

        {error && <p className="mt-4 text-sm font-semibold leading-5 text-red-600">{error}</p>}
        {sent && <p className="mt-4 text-sm font-semibold leading-5 text-emerald-700">Email sent.</p>}

        {oversized && (
          <div className="mt-4 grid min-w-0 gap-2 sm:grid-cols-2">
            <button type="button" onClick={onDownload} className="h-10 w-full rounded-lg border border-slate-300 px-3 text-sm font-bold text-slate-700 hover:bg-slate-50">Download</button>
            <button type="button" onClick={onShareLink} className="h-10 w-full rounded-lg border border-slate-300 px-3 text-sm font-bold text-slate-700 hover:bg-slate-50">Share Link</button>
          </div>
        )}

        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button type="button" onClick={onClose} disabled={sending} className="h-10 w-full rounded-lg border border-slate-300 px-4 text-sm font-bold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto">
            {sent ? 'Done' : 'Cancel'}
          </button>
          {!sent && (
            <button type="button" onClick={onSend} disabled={sending} className="h-10 w-full rounded-lg bg-slate-900 px-4 text-sm font-bold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400 sm:w-auto">
              {sending ? 'Sending...' : 'Send Email'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function ShareModal({
  file,
  expiration,
  shares,
  sharesLoading,
  sharing,
  revokingShareId,
  error,
  onExpirationChange,
  onCreateShare,
  onCopy,
  onRevoke,
  onClose,
}: {
  file: VaultFile
  expiration: ShareExpiration
  shares: VaultShare[]
  sharesLoading: boolean
  sharing: boolean
  revokingShareId: string | null
  error: string
  onExpirationChange: (value: ShareExpiration) => void
  onCreateShare: () => void
  onCopy: (link: string) => void
  onRevoke: (share: VaultShare) => void
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase text-[#D4900A]">bonUP Vault</p>
            <h2 className="mt-1 truncate text-lg font-bold text-slate-900">Share Links</h2>
            <p title={file.file_name} className="mt-2 truncate text-sm font-semibold text-slate-500">{file.file_name}</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>

        <p className="mt-4 text-sm leading-6 text-slate-600">For security, existing share links can't be displayed again. Create a new link if you need another copy.</p>

        <label className="mt-5 block text-sm font-bold text-slate-700">
          Expiration
          <select
            value={expiration}
            onChange={(event) => onExpirationChange(event.target.value as ShareExpiration)}
            className="mt-2 h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-100"
          >
            <option value="1d">1 day</option>
            <option value="7d">7 days</option>
            <option value="30d">30 days</option>
            <option value="none">No expiration</option>
          </select>
        </label>

        <button type="button" onClick={onCreateShare} disabled={sharing} className="mt-4 h-10 w-full rounded-lg bg-slate-900 text-sm font-bold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400">
          {sharing ? 'Creating...' : 'Create Share Link'}
        </button>

        {error && <p className="mt-4 text-sm font-semibold text-red-600">{error}</p>}

        <div className="mt-5">
          <p className="text-xs font-bold uppercase text-slate-400">Active links</p>
          {sharesLoading && <p className="mt-3 text-sm font-semibold text-slate-600">Loading share links...</p>}
          {!sharesLoading && shares.length === 0 && (
            <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
              No active Share Links for this file.
            </div>
          )}
          {!sharesLoading && shares.length > 0 && (
            <div className="mt-3 space-y-3">
              {shares.map((share) => {
                const shareLink = share.share_url || ''
                const canCopy = Boolean(shareLink)
                return (
                  <div key={share.id} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-bold text-slate-900">Active Share Link</p>
                        <p className="mt-1 text-xs text-slate-500">Created {share.created_at ? formatDate(share.created_at) : 'just now'}</p>
                        <p className="mt-1 text-xs text-slate-500">Expires {share.expires_at ? formatDate(share.expires_at) : 'Never'}</p>
                      </div>
                      <button type="button" onClick={() => onRevoke(share)} disabled={revokingShareId === share.id} className="shrink-0 rounded-lg border border-red-200 px-3 py-1.5 text-xs font-bold text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50">
                        {revokingShareId === share.id ? 'Revoking...' : 'Revoke'}
                      </button>
                    </div>
                    {canCopy ? (
                      <div className="mt-4 rounded-lg border border-slate-200 bg-white p-3">
                        <p className="break-all text-sm font-semibold text-slate-800">{shareLink}</p>
                        <button type="button" onClick={() => onCopy(shareLink)} className="mt-3 inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-bold text-slate-700 hover:bg-slate-50">
                          <ClipboardDocumentIcon className="h-4 w-4" />
                          Copy Link
                        </button>
                      </div>
                    ) : (
                      <p className="mt-3 text-xs leading-5 text-slate-500">Link URL is hidden after creation.</p>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function NativeShareFallbackModal({
  file,
  onDownload,
  onShareLink,
  onClose,
}: {
  file: VaultFile
  onDownload: () => void
  onShareLink: () => void
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase text-[#D4900A]">bonUP Vault</p>
            <h2 className="mt-1 truncate text-lg font-bold text-slate-900">Share File unavailable</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">This browser can't share this file directly.</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>
        <p className="mt-4 truncate text-sm font-semibold text-slate-800">{file.file_name}</p>
        <div className="mt-5 grid gap-2 sm:grid-cols-2">
          <button type="button" onClick={onDownload} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-slate-300 px-3 text-sm font-bold text-slate-700 hover:bg-slate-50">
            <ArrowDownTrayIcon className="h-4 w-4" />
            Download File
          </button>
          <button type="button" onClick={onShareLink} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-slate-900 px-3 text-sm font-bold text-white hover:bg-slate-800">
            <ShareIcon className="h-4 w-4" />
            Share Link
          </button>
        </div>
      </div>
    </div>
  )
}

function FileDetailsModal({
  file,
  working,
  onClose,
  onDownload,
  onEmailFile,
  onShareFile,
  onShareLink,
  onRename,
  onMove,
  onRemove,
}: {
  file: VaultFile
  working: boolean
  onClose: () => void
  onDownload: () => void
  onEmailFile: () => void
  onShareFile: () => void
  onShareLink: () => void
  onRename: () => void
  onMove: () => void
  onRemove: () => void
}) {
  const category = categoryForFile(file)
  const Icon = fileIcon(category)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
      <div className="max-h-[90vh] w-full max-w-4xl overflow-hidden rounded-lg bg-white shadow-xl">
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 p-5">
          <div className="min-w-0">
            <h2 className="truncate text-lg font-bold text-slate-900">{file.file_name}</h2>
            <p className="mt-1 text-sm text-slate-500">{typeLabel(file)} · {formatBytes(file.file_size)} · {formatDate(file.uploaded_at)}</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>
        <div className="grid max-h-[calc(90vh-78px)] overflow-y-auto lg:grid-cols-[1.5fr_1fr]">
          <div className="flex min-h-[320px] items-center justify-center bg-slate-50 p-5">
            {category === 'images' && file.file_url ? <img src={file.file_url} alt="" className="max-h-[560px] max-w-full rounded-lg object-contain" /> : null}
            {category === 'videos' && file.file_url ? <video src={file.file_url} controls className="max-h-[560px] max-w-full rounded-lg" /> : null}
            {category === 'audio' && file.file_url ? <audio src={file.file_url} controls className="w-full max-w-md" /> : null}
            {category === 'documents' && file.file_url ? <iframe src={file.file_url} title={file.file_name} className="h-[560px] w-full rounded-lg border border-slate-200 bg-white" /> : null}
            {(!file.file_url || category === 'other') && (
              <div className="text-center text-slate-500">
                <Icon className="mx-auto h-14 w-14" />
                <p className="mt-3 text-sm font-semibold">Preview is not available for this file.</p>
              </div>
            )}
          </div>
          <aside className="border-t border-slate-200 p-5 lg:border-l lg:border-t-0">
            <h3 className="text-sm font-bold uppercase text-slate-400">Details</h3>
            <dl className="mt-4 space-y-4 text-sm">
              <Detail label="Filename" value={file.file_name} />
              <Detail label="Type" value={typeLabel(file)} />
              <Detail label="Content type" value={file.content_type || 'Not available'} />
              <Detail label="Size" value={formatBytes(file.file_size)} />
              <Detail label="Uploaded" value={formatDate(file.uploaded_at)} />
            </dl>
            <div className="mt-6 flex flex-col gap-2">
              <button type="button" onClick={onDownload} className="h-10 rounded-lg border border-slate-300 px-4 text-sm font-bold text-slate-700 hover:bg-slate-50">Download</button>
              <button type="button" onClick={onEmailFile} disabled={working} className="h-10 rounded-lg bg-slate-900 px-4 text-sm font-bold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400">Email File</button>
              <button type="button" onClick={onShareFile} disabled={working} className="h-10 rounded-lg border border-slate-300 px-4 text-sm font-bold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">Share File</button>
              <button type="button" onClick={onShareLink} disabled={working} className="h-10 rounded-lg border border-slate-300 px-4 text-sm font-bold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">Share Link</button>
              <button type="button" onClick={onRename} disabled={working} className="h-10 rounded-lg border border-slate-300 px-4 text-sm font-bold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">Rename</button>
              <button type="button" onClick={onMove} disabled={working} className="h-10 rounded-lg border border-slate-300 px-4 text-sm font-bold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">Move</button>
              <button type="button" onClick={onRemove} disabled={working} className="h-10 rounded-lg border border-red-200 px-4 text-sm font-bold text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50">Remove from Vault</button>
            </div>
          </aside>
        </div>
      </div>
    </div>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-bold uppercase text-slate-400">{label}</dt>
      <dd className="mt-1 break-words font-semibold text-slate-800">{value}</dd>
    </div>
  )
}

import { useEffect, useState, useSyncExternalStore } from 'react'
import { DELIVERY_CONTEXT_EVENT, deliveryContext, fetchPrivateFile, previewKind } from '@/api/fileDelivery'

function subscribe(callback: () => void) {
  window.addEventListener(DELIVERY_CONTEXT_EVENT, callback)
  window.addEventListener('storage', callback)
  return () => {
    window.removeEventListener(DELIVERY_CONTEXT_EVENT, callback)
    window.removeEventListener('storage', callback)
  }
}

export type CanonicalIdentity = {
  first_name?: string | null
  last_name?: string | null
  display_name?: string | null
  username?: string | null
  profile_photo_url?: string | null
}

export function identityInitials(identity: CanonicalIdentity) {
  return (
    [identity.first_name?.[0], identity.last_name?.[0]].filter(Boolean).join('')
    || identity.display_name?.[0]
    || identity.username?.[0]
    || '?'
  ).toUpperCase()
}

export function CanonicalAvatar({
  identity,
  className,
  label,
}: {
  identity: CanonicalIdentity
  className: string
  label?: string
}) {
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const photoPath = identity.profile_photo_url || ''
  const context = useSyncExternalStore(subscribe, deliveryContext, () => '')

  useEffect(() => {
    if (!photoPath) {
      setImageUrl(null)
      return
    }

    const controller = new AbortController()
    let objectUrl: string | null = null
    setImageUrl(null)

    fetchPrivateFile(photoPath, controller.signal).then((blob) => {
      if (controller.signal.aborted || previewKind(blob.type) !== 'image') return
      objectUrl = URL.createObjectURL(blob)
      setImageUrl(objectUrl)
    }).catch(() => {
      // A missing or unauthorized asset intentionally falls back to initials.
    })

    return () => {
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [photoPath, context])

  return (
    <span className={className} aria-label={label || 'Profile avatar'}>
      {imageUrl ? <img src={imageUrl} alt="" className="canonical-avatar-image" /> : identityInitials(identity)}
    </span>
  )
}

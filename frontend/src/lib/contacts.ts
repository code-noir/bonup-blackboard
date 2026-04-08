// src/lib/contacts.ts
// localStorage-backed contacts store.
// No API endpoint exists yet; swap implementations here when one is added.

export interface Contact {
  id: string
  firstName: string
  lastName: string
  bonId: string
  email: string
  phone: string
  notes: string
  lastContracted: string | null  // ISO date string or null
  addedAt: string                // ISO date string
}

const KEY = 'bb_contacts'

export function loadContacts(): Contact[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? '[]')
  } catch {
    return []
  }
}

function persist(contacts: Contact[]): void {
  localStorage.setItem(KEY, JSON.stringify(contacts))
}

export function saveContactFromParty(party: {
  name: string
  bonId: string
}): void {
  const contacts = loadContacts()
  // Skip if already tracked by bonId
  if (party.bonId && contacts.some((c) => c.bonId === party.bonId)) return
  const parts = party.name.trim().split(/\s+/)
  const firstName = parts[0] ?? ''
  const lastName = parts.slice(1).join(' ')
  const newContact: Contact = {
    id: crypto.randomUUID(),
    firstName,
    lastName,
    bonId: party.bonId,
    email: '',
    phone: '',
    notes: '',
    lastContracted: new Date().toISOString(),
    addedAt: new Date().toISOString(),
  }
  persist([...contacts, newContact])
}

export function addContact(c: Omit<Contact, 'id' | 'addedAt'>): Contact {
  const contacts = loadContacts()
  const newContact: Contact = {
    ...c,
    id: crypto.randomUUID(),
    addedAt: new Date().toISOString(),
  }
  persist([...contacts, newContact])
  return newContact
}

export function deleteContact(id: string): void {
  persist(loadContacts().filter((c) => c.id !== id))
}

export function getContactInitials(c: Contact): string {
  const first = c.firstName?.[0] ?? ''
  const last = c.lastName?.[0] ?? ''
  return (first + last).toUpperCase() || '??'
}

export function getContactDisplayName(c: Contact): string {
  return [c.firstName, c.lastName].filter(Boolean).join(' ') || c.bonId || 'Unknown'
}

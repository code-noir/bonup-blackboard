// src/lib/contacts.ts
// ============================================================
// PROTECTED FILE — DO NOT MODIFY WITHOUT EXPLICIT APPROVAL
// ============================================================
// This module is a direct dependency of the contract editor
// (CreateContract.tsx). The exported function signatures —
// loadContacts, saveContactFromParty, addContact, deleteContact,
// getContactInitials, getContactDisplayName — and the Contact
// interface are stable contracts that the editor relies on.
//
// DO NOT rename exports, change signatures, or alter the Contact
// interface shape without coordinating with CreateContract.tsx.
//
// A backend contacts API exists at /api/contacts/ but the editor
// currently reads from localStorage via this module. Migration to
// the API is a planned, scoped task — not an ad-hoc cleanup.
//
// Reference: EDITOR_PROTECTION.md
// ============================================================
//
// localStorage-backed contacts store.
// A backend contacts API exists at /api/contacts/ but the editor consumes
// this module directly. Migration to the API must be intentional and scoped.

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

export type BusinessType =
  | 'LLC'
  | 'Corporation'
  | 'Sole Proprietor'
  | 'Partnership'
  | 'Non-Profit'
  | 'Trust'
  | 'S-Corp'
  | 'C-Corp'
  | 'Other'

export interface BusinessEntity {
  id: string
  name: string
  business_type: BusinessType
  description: string
  industry: string
  address: string | null
  website: string | null
  founded_date: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

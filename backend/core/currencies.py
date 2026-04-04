# backend/core/currencies.py
#
# ISO 4217 currency choices shared across Payment, ContractObligation, and Contract.

CURRENCY_CHOICES = [
    # Americas
    ("USD", "US Dollar"),
    ("CAD", "Canadian Dollar"),
    ("MXN", "Mexican Peso"),
    ("BRL", "Brazilian Real"),
    ("ARS", "Argentine Peso"),
    ("COP", "Colombian Peso"),
    ("CLP", "Chilean Peso"),
    ("PEN", "Peruvian Sol"),
    ("HTG", "Haitian Gourde"),
    # Europe
    ("EUR", "Euro"),
    ("GBP", "British Pound"),
    ("CHF", "Swiss Franc"),
    ("SEK", "Swedish Krona"),
    ("NOK", "Norwegian Krone"),
    ("DKK", "Danish Krone"),
    # Middle East / North Africa
    ("AED", "UAE Dirham"),
    ("SAR", "Saudi Riyal"),
    ("EGP", "Egyptian Pound"),
    ("MAD", "Moroccan Dirham"),
    ("QAR", "Qatari Riyal"),
    ("KWD", "Kuwaiti Dinar"),
    # Sub-Saharan Africa
    ("ZAR", "South African Rand"),
    ("NGN", "Nigerian Naira"),
    ("GHS", "Ghanaian Cedi"),
    ("KES", "Kenyan Shilling"),
    ("UGX", "Ugandan Shilling"),
    ("TZS", "Tanzanian Shilling"),
    ("ETB", "Ethiopian Birr"),
    ("XOF", "West African CFA Franc"),
    ("XAF", "Central African CFA Franc"),
    ("RWF", "Rwandan Franc"),
    ("MZN", "Mozambican Metical"),
    ("ZMW", "Zambian Kwacha"),
    # Asia-Pacific
    ("JPY", "Japanese Yen"),
    ("CNY", "Chinese Yuan"),
    ("INR", "Indian Rupee"),
    ("KRW", "South Korean Won"),
    ("SGD", "Singapore Dollar"),
    ("HKD", "Hong Kong Dollar"),
    ("AUD", "Australian Dollar"),
    ("NZD", "New Zealand Dollar"),
    ("TWD", "Taiwan Dollar"),
    ("THB", "Thai Baht"),
    ("IDR", "Indonesian Rupiah"),
    ("MYR", "Malaysian Ringgit"),
    ("PHP", "Philippine Peso"),
    ("PKR", "Pakistani Rupee"),
    ("BDT", "Bangladeshi Taka"),
    ("VND", "Vietnamese Dong"),
]

CURRENCY_CODES = [code for code, _ in CURRENCY_CHOICES]

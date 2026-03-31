# backend/contract_templates/management/commands/seed_templates.py

from django.core.management.base import BaseCommand
from backend.contract_templates.models import (
    ContractTemplate,
    TemplateGuidedField,
    TemplateClause,
    TemplateObligationPattern,
)


PERSONAL_TRAINING_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Services",
        "order": 1,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Trainer\") agrees to provide personal training services "
            "to {{counterparty_name}} (\"Client\") under the following terms:\n\n"
            "Service Format: {{service_delivery}}\n"
            "Session Duration: {{session_duration_minutes}} minutes per session\n"
            "Payment Model: {{payment_model}}\n"
            "Total Sessions: {{num_sessions}} sessions\n"
            "Training Location: {{location}}\n\n"
            "Trainer shall design and supervise exercise programs appropriate to Client's fitness "
            "level and stated goals. The scope of services is limited to personal training and does "
            "not include nutritional counseling, physical therapy, or medical advice."
        ),
    },
    {
        "clause_type": "risk",
        "title": "Assumption of Risk and Medical Disclaimer",
        "order": 2,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "ASSUMPTION OF RISK AND MEDICAL DISCLAIMER\n\n"
            "Client acknowledges that participation in personal training involves inherent physical "
            "risks including but not limited to muscular strain, sprains, joint injuries, "
            "cardiovascular stress, and in rare cases more serious injury.\n\n"
            "Client represents and warrants that they are in adequate physical health to participate "
            "in a personal training program and have consulted with a licensed physician or "
            "healthcare provider prior to beginning this program, or have knowingly waived such "
            "consultation.\n\n"
            "Client assumes full responsibility for any and all risks, injuries, or damages arising "
            "from participation in personal training sessions and releases Trainer from liability "
            "to the maximum extent permitted by applicable law.\n\n"
            "Trainer is not a licensed medical professional. Nothing in this agreement or in any "
            "session constitutes medical advice or treatment."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 3,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Rate: ${{rate_per_session}} per session\n"
            "Total Package Value: ${{total_package_value}} ({{num_sessions}} sessions × ${{rate_per_session}})\n"
            "Payment Timing: {{payment_timing}}\n\n"
            "Payment is due in accordance with the Payment Timing selected above. Trainer reserves "
            "the right to suspend sessions if payment is more than 7 days past due. All payments "
            "are in USD unless otherwise agreed in writing.\n\n"
            "Payments not received within 14 days of the due date may incur a late fee of 5% of "
            "the outstanding balance per month until paid."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Late Cancellation and No-Show Policy",
        "order": 4,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "LATE CANCELLATION AND NO-SHOW POLICY\n\n"
            "Client agrees to provide at least {{cancellation_window_hours}} hours advance notice "
            "for any session cancellation or rescheduling.\n\n"
            "Cancellations made with less than {{cancellation_window_hours}} hours notice, or "
            "failure to appear at a scheduled session without notice (\"no-show\"), will result "
            "in forfeiture of that session. No refund or credit will be issued for late "
            "cancellations or no-shows.\n\n"
            "Trainer agrees to provide the same advance notice to Client for any sessions Trainer "
            "must cancel. Sessions cancelled by Trainer will be rescheduled at no additional cost "
            "to Client."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Unused Sessions and Package Expiration",
        "order": 5,
        "is_required": False,
        "is_conditional": True,
        "condition_description": "Applies when client purchases a multi-session package",
        "body": (
            "UNUSED SESSIONS AND PACKAGE EXPIRATION\n\n"
            "Sessions purchased as part of a package must be used within {{package_expiry_days}} "
            "days of the agreement start date. Sessions not used within this period will expire "
            "and no refund will be issued.\n\n"
            "Exceptions may be granted at Trainer's sole discretion for documented medical "
            "circumstances preventing attendance."
        ),
    },
    {
        "clause_type": "termination",
        "title": "Termination",
        "order": 6,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate this agreement upon {{termination_notice_days}} days "
            "written notice to the other party.\n\n"
            "Upon termination by Client: Client will be refunded for any unused prepaid sessions "
            "at the per-session rate of ${{rate_per_session}}, less any outstanding amounts owed.\n\n"
            "Upon termination by Trainer: Trainer will refund any prepaid amounts for sessions "
            "not yet delivered, in full.\n\n"
            "Termination for cause — including abusive conduct, repeated no-shows, or non-payment "
            "— may be effected immediately without a notice period."
        ),
    },
]

PERSONAL_TRAINING_GUIDED_FIELDS = [
    {
        "field_key": "service_delivery",
        "label": "Service Delivery Format",
        "field_type": "text",
        "choices": None,
        "is_required": True,
        "order": 1,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "session_duration_minutes",
        "label": "Session Duration (minutes)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 2,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "payment_model",
        "label": "Payment Model",
        "field_type": "choice",
        "choices": ["single_session", "package_upfront", "package_installments"],
        "is_required": True,
        "order": 3,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "num_sessions",
        "label": "Number of Sessions",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 4,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "rate_per_session",
        "label": "Rate Per Session (USD)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 5,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "location",
        "label": "Training Location or Address",
        "field_type": "text",
        "choices": None,
        "is_required": True,
        "order": 6,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "session_frequency_days",
        "label": "Days Between Sessions",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 7,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "cancellation_window_hours",
        "label": "Late Cancellation Window (hours)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 8,
        "condition_field_key": "",
        "condition_value": "",
    },
    # --- Conditional: only required when payment_model == package_installments ---
    {
        "field_key": "num_installments",
        "label": "Number of Installments",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 9,
        "condition_field_key": "payment_model",
        "condition_value": "package_installments",
    },
    {
        "field_key": "installment_interval_days",
        "label": "Installment Interval",
        "field_type": "choice",
        "choices": ["7", "30"],
        "is_required": True,
        "order": 10,
        "condition_field_key": "payment_model",
        "condition_value": "package_installments",
    },
    # --- Optional for all models ---
    {
        "field_key": "package_expiry_days",
        "label": "Package Expiry (days from start)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 11,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "termination_notice_days",
        "label": "Termination Notice Period (days)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 12,
        "condition_field_key": "",
        "condition_value": "",
    },
]


NUTRITION_COACHING_GUIDED_FIELDS = [
    {
        "field_key": "service_delivery",
        "label": "Service Delivery Format",
        "field_type": "choice",
        "choices": ["In-Person", "Online"],
        "is_required": True,
        "order": 1,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "consultation_type",
        "label": "Consultation Type",
        "field_type": "choice",
        "choices": ["Single Consultation", "Ongoing Program"],
        "is_required": True,
        "order": 2,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "num_sessions",
        "label": "Number of Sessions",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 3,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "rate_per_session",
        "label": "Rate Per Session (USD)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 4,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "payment_model",
        "label": "Payment Model",
        "field_type": "choice",
        "choices": ["single_session", "package_upfront", "package_installments"],
        "is_required": True,
        "order": 5,
        "condition_field_key": "",
        "condition_value": "",
    },
    # --- Conditional: only required when payment_model == package_installments ---
    {
        "field_key": "num_installments",
        "label": "Number of Installments",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 6,
        "condition_field_key": "payment_model",
        "condition_value": "package_installments",
    },
    {
        "field_key": "installment_interval_days",
        "label": "Installment Interval",
        "field_type": "choice",
        "choices": ["7", "30"],
        "is_required": True,
        "order": 7,
        "condition_field_key": "payment_model",
        "condition_value": "package_installments",
    },
    # --- Optional for all models ---
    {
        "field_key": "meal_plan_included",
        "label": "Meal Plan Included",
        "field_type": "boolean",
        "choices": None,
        "is_required": False,
        "order": 8,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "cancellation_window_hours",
        "label": "Late Cancellation Window (hours)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 9,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "termination_notice_days",
        "label": "Termination Notice Period (days)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 10,
        "condition_field_key": "",
        "condition_value": "",
    },
]

NUTRITION_COACHING_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Services",
        "order": 1,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Coach\") agrees to provide nutrition coaching services "
            "to {{counterparty_name}} (\"Client\") under the following terms:\n\n"
            "Service Format: {{service_delivery}}\n"
            "Consultation Type: {{consultation_type}}\n"
            "Total Sessions: {{num_sessions}} sessions\n\n"
            "Coach shall provide personalized nutrition guidance, habit coaching, and wellness "
            "support tailored to Client's stated goals. Services are limited to general nutrition "
            "coaching and do not include medical diagnosis, clinical dietetics, or any form of "
            "licensed healthcare."
        ),
    },
    {
        "clause_type": "risk",
        "title": "Medical and Dietary Disclaimer",
        "order": 2,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "MEDICAL AND DIETARY DISCLAIMER\n\n"
            "Coach is not a licensed physician, registered dietitian, or medical professional. "
            "The guidance and recommendations provided under this agreement are for general "
            "wellness purposes only and do not constitute medical advice, diagnosis, or treatment.\n\n"
            "Client is advised to consult with a licensed physician or registered dietitian before "
            "making significant dietary changes, particularly if they have existing medical "
            "conditions, food allergies, are pregnant or nursing, or are taking prescription "
            "medication.\n\n"
            "Client assumes full responsibility for any dietary or lifestyle changes made in "
            "connection with this coaching relationship. Coach shall not be liable for any adverse "
            "health effects arising from the application of guidance provided under this agreement."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 3,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Rate: ${{rate_per_session}} per session\n"
            "Total Package Value: ${{total_package_value}} ({{num_sessions}} sessions × ${{rate_per_session}})\n"
            "Payment Model: {{payment_model}}\n\n"
            "Payment is due in accordance with the Payment Model selected above. Coach reserves "
            "the right to suspend sessions if payment is more than 7 days past due. All payments "
            "are in USD unless otherwise agreed in writing.\n\n"
            "Payments not received within 14 days of the due date may incur a late fee of 5% of "
            "the outstanding balance per month until paid."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation Policy",
        "order": 4,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CANCELLATION POLICY\n\n"
            "Client agrees to provide at least {{cancellation_window_hours}} hours advance notice "
            "for any session cancellation or rescheduling.\n\n"
            "Cancellations with less than {{cancellation_window_hours}} hours notice, or failure "
            "to appear without notice (\"no-show\"), will result in forfeiture of that session. "
            "No refund or credit will be issued for late cancellations or no-shows.\n\n"
            "Coach agrees to provide the same advance notice to Client for any sessions Coach "
            "must cancel. Sessions cancelled by Coach will be rescheduled at no additional cost."
        ),
    },
    {
        "clause_type": "confidentiality",
        "title": "Client Health Information Confidentiality",
        "order": 5,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CLIENT HEALTH INFORMATION CONFIDENTIALITY\n\n"
            "In the course of this coaching relationship, Client may share personal health "
            "information including dietary habits, medical history, weight, body measurements, "
            "food sensitivities, and other health-related data (\"Health Information\").\n\n"
            "Coach agrees to hold all Health Information in strict confidence and shall not "
            "disclose it to any third party without Client's express written consent, except "
            "as required by applicable law.\n\n"
            "Health Information will be used solely to provide personalized nutrition coaching "
            "services under this agreement and will not be shared, sold, or used for any "
            "other purpose. Coach will maintain reasonable safeguards to protect Health "
            "Information from unauthorized access or disclosure."
        ),
    },
    {
        "clause_type": "termination",
        "title": "Termination",
        "order": 6,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate this agreement upon {{termination_notice_days}} days "
            "written notice to the other party.\n\n"
            "Upon termination by Client: Client will be refunded for any unused prepaid sessions "
            "at the per-session rate of ${{rate_per_session}}, less any outstanding amounts owed.\n\n"
            "Upon termination by Coach: Coach will refund any prepaid amounts for sessions not "
            "yet delivered, in full.\n\n"
            "Termination for cause — including abusive conduct, repeated no-shows, or non-payment "
            "— may be effected immediately without a notice period."
        ),
    },
]


WELLNESS_COACHING_GUIDED_FIELDS = [
    {
        "field_key": "service_delivery",
        "label": "Service Delivery Format",
        "field_type": "choice",
        "choices": ["In-Person", "Online"],
        "is_required": True,
        "order": 1,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "session_type",
        "label": "Session Type",
        "field_type": "choice",
        "choices": ["Single Session", "Ongoing Program"],
        "is_required": True,
        "order": 2,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "session_duration_minutes",
        "label": "Session Duration (minutes)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 3,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "num_sessions",
        "label": "Number of Sessions",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 4,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "rate_per_session",
        "label": "Rate Per Session (USD)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 5,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "payment_model",
        "label": "Payment Model",
        "field_type": "choice",
        "choices": ["single_session", "package_upfront", "package_installments"],
        "is_required": True,
        "order": 6,
        "condition_field_key": "",
        "condition_value": "",
    },
    # --- Conditional: only required when payment_model == package_installments ---
    {
        "field_key": "num_installments",
        "label": "Number of Installments",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 7,
        "condition_field_key": "payment_model",
        "condition_value": "package_installments",
    },
    {
        "field_key": "installment_interval_days",
        "label": "Installment Interval",
        "field_type": "choice",
        "choices": ["7", "30"],
        "is_required": True,
        "order": 8,
        "condition_field_key": "payment_model",
        "condition_value": "package_installments",
    },
    # --- Optional for all models ---
    {
        "field_key": "focus_area",
        "label": "Focus Area",
        "field_type": "choice",
        "choices": [
            "Stress Management",
            "Life Balance",
            "Mindfulness",
            "General Wellness",
        ],
        "is_required": False,
        "order": 9,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "cancellation_window_hours",
        "label": "Late Cancellation Window (hours)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 10,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "termination_notice_days",
        "label": "Termination Notice Period (days)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 11,
        "condition_field_key": "",
        "condition_value": "",
    },
]

WELLNESS_COACHING_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Services",
        "order": 1,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Coach\") agrees to provide wellness coaching services "
            "to {{counterparty_name}} (\"Client\") under the following terms:\n\n"
            "Service Format: {{service_delivery}}\n"
            "Session Type: {{session_type}}\n"
            "Session Duration: {{session_duration_minutes}} minutes per session\n"
            "Total Sessions: {{num_sessions}} sessions\n"
            "Focus Area: {{focus_area}}\n\n"
            "Coach shall provide a supportive and structured coaching environment to help "
            "Client explore goals, develop strategies, and build habits aligned with their "
            "stated wellness intentions. Services are limited to coaching conversations and "
            "do not include therapy, counseling, medical treatment, or clinical services of "
            "any kind."
        ),
    },
    {
        "clause_type": "risk",
        "title": "Coaching vs. Therapy Disclaimer",
        "order": 2,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "COACHING VS. THERAPY DISCLAIMER\n\n"
            "Wellness coaching is a distinct service from therapy, counseling, psychiatry, "
            "or any licensed mental health practice. Coach is not a licensed therapist, "
            "psychologist, social worker, or mental health provider. This agreement does not "
            "create a therapist-patient or healthcare provider relationship of any kind.\n\n"
            "Wellness coaching does not diagnose, treat, cure, or prevent any mental health "
            "condition, psychological disorder, or medical illness. Clients experiencing "
            "mental health concerns, emotional distress, or symptoms of a psychological "
            "condition are encouraged to seek support from a licensed mental health "
            "professional.\n\n"
            "Nothing communicated by Coach in sessions or supporting materials constitutes "
            "medical advice, psychological treatment, or clinical guidance."
        ),
    },
    {
        "clause_type": "confidentiality",
        "title": "Confidentiality",
        "order": 3,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CONFIDENTIALITY\n\n"
            "Coach agrees to hold strictly confidential all personal information, goals, "
            "challenges, and disclosures shared by Client during coaching sessions or "
            "related communications (\"Client Information\").\n\n"
            "Coach shall not disclose Client Information to any third party without "
            "Client's express written consent, except as required by law or in situations "
            "where Coach reasonably believes disclosure is necessary to prevent imminent "
            "harm to Client or others.\n\n"
            "Client Information will be used solely to support the coaching relationship "
            "and will not be shared, published, or used for any other purpose without "
            "explicit permission."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 4,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Rate: ${{rate_per_session}} per session\n"
            "Total Package Value: ${{total_package_value}} ({{num_sessions}} sessions × ${{rate_per_session}})\n"
            "Payment Model: {{payment_model}}\n\n"
            "Payment is due in accordance with the Payment Model selected above. Coach "
            "reserves the right to suspend sessions if payment is more than 7 days past due. "
            "All payments are in USD unless otherwise agreed in writing.\n\n"
            "Payments not received within 14 days of the due date may incur a late fee of "
            "5% of the outstanding balance per month until paid."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation Policy",
        "order": 5,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CANCELLATION POLICY\n\n"
            "Client agrees to provide at least {{cancellation_window_hours}} hours advance "
            "notice for any session cancellation or rescheduling.\n\n"
            "Cancellations with less than {{cancellation_window_hours}} hours notice, or "
            "failure to appear without notice (\"no-show\"), will result in forfeiture of "
            "that session. No refund or credit will be issued for late cancellations or "
            "no-shows.\n\n"
            "Coach agrees to provide the same advance notice to Client for any sessions "
            "Coach must cancel. Sessions cancelled by Coach will be rescheduled at no "
            "additional cost."
        ),
    },
    {
        "clause_type": "risk",
        "title": "No Guarantee of Outcomes",
        "order": 6,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "NO GUARANTEE OF OUTCOMES\n\n"
            "Wellness coaching is a collaborative process. Results depend entirely on "
            "Client's own commitment, effort, and follow-through between sessions. Coach "
            "makes no representations, warranties, or guarantees — express or implied — "
            "regarding specific outcomes, improvements, or changes in Client's health, "
            "wellbeing, career, relationships, or any other area of life.\n\n"
            "Client acknowledges that they are fully responsible for their own decisions "
            "and actions taken in connection with the coaching engagement. Coach's role "
            "is to support, question, and challenge — not to direct, prescribe, or "
            "guarantee results.\n\n"
            "Client agrees not to hold Coach liable for any decisions made or actions "
            "taken as a result of coaching conversations."
        ),
    },
    {
        "clause_type": "termination",
        "title": "Termination",
        "order": 7,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate this agreement upon {{termination_notice_days}} days "
            "written notice to the other party.\n\n"
            "Upon termination by Client: Client will be refunded for any unused prepaid "
            "sessions at the per-session rate of ${{rate_per_session}}, less any outstanding "
            "amounts owed.\n\n"
            "Upon termination by Coach: Coach will refund any prepaid amounts for sessions "
            "not yet delivered, in full.\n\n"
            "Termination for cause — including abusive conduct, repeated no-shows, or "
            "non-payment — may be effected immediately without a notice period."
        ),
    },
]


# ==============================================================================
# EDUCATION & TUTORING — ACADEMIC TUTORING
# ==============================================================================

_CONDITIONAL_INSTALLMENTS = [
    {
        "field_key": "num_installments",
        "label": "Number of Installments",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": None,  # overridden per template
        "condition_field_key": "payment_model",
        "condition_value": "package_installments",
    },
    {
        "field_key": "installment_interval_days",
        "label": "Installment Interval",
        "field_type": "choice",
        "choices": ["7", "30"],
        "is_required": True,
        "order": None,
        "condition_field_key": "payment_model",
        "condition_value": "package_installments",
    },
]


def _installment_fields(num_order, interval_order):
    """Returns the two conditional installment fields with correct order values."""
    fields = [dict(f) for f in _CONDITIONAL_INSTALLMENTS]
    fields[0]["order"] = num_order
    fields[1]["order"] = interval_order
    return fields


_CONDITIONAL_INSTALLMENTS_CREATIVE = [
    {
        "field_key": "num_installments",
        "label": "Number of Installments",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 0,
        "condition_field_key": "payment_model",
        "condition_value": "installments",
    },
    {
        "field_key": "installment_interval_days",
        "label": "Days Between Installments",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 0,
        "condition_field_key": "payment_model",
        "condition_value": "installments",
    },
]


def _installment_fields_creative(num_order, interval_order):
    """Returns the two conditional installment fields for creative templates (condition_value='installments')."""
    fields = [dict(f) for f in _CONDITIONAL_INSTALLMENTS_CREATIVE]
    fields[0]["order"] = num_order
    fields[1]["order"] = interval_order
    return fields


ACADEMIC_TUTORING_GUIDED_FIELDS = [
    {"field_key": "service_delivery", "label": "Service Delivery Format", "field_type": "choice",
     "choices": ["In-Person", "Online"], "is_required": True, "order": 1,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "subject", "label": "Subject", "field_type": "text",
     "choices": None, "is_required": True, "order": 2,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "student_is_minor", "label": "Student Is a Minor (under 18)",
     "field_type": "boolean", "choices": None, "is_required": True, "order": 3,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "session_duration_minutes", "label": "Session Duration (minutes)",
     "field_type": "number", "choices": None, "is_required": True, "order": 4,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "num_sessions", "label": "Number of Sessions",
     "field_type": "number", "choices": None, "is_required": True, "order": 5,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "rate_per_session", "label": "Rate Per Session (USD)",
     "field_type": "number", "choices": None, "is_required": True, "order": 6,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "payment_model", "label": "Payment Model", "field_type": "choice",
     "choices": ["single_session", "package_upfront", "package_installments"],
     "is_required": True, "order": 7, "condition_field_key": "", "condition_value": ""},
    *_installment_fields(8, 9),
    {"field_key": "cancellation_window_hours", "label": "Late Cancellation Window (hours)",
     "field_type": "number", "choices": None, "is_required": False, "order": 10,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "package_expiry_days", "label": "Package Expiry (days from start)",
     "field_type": "number", "choices": None, "is_required": False, "order": 11,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "termination_notice_days", "label": "Termination Notice Period (days)",
     "field_type": "number", "choices": None, "is_required": False, "order": 12,
     "condition_field_key": "", "condition_value": ""},
]

ACADEMIC_TUTORING_CLAUSES = [
    {
        "clause_type": "scope", "title": "Scope of Services", "order": 1,
        "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Tutor\") agrees to provide academic tutoring services "
            "to {{counterparty_name}} (\"Client\") under the following terms:\n\n"
            "Subject: {{subject}}\n"
            "Service Format: {{service_delivery}}\n"
            "Session Duration: {{session_duration_minutes}} minutes per session\n"
            "Total Sessions: {{num_sessions}} sessions\n\n"
            "Tutor shall prepare and deliver instructional content, exercises, and guidance "
            "appropriate to the Client's current level and stated learning goals in the "
            "subject area specified above. Sessions will focus on the agreed subject matter "
            "and will not extend to unrelated subjects without mutual agreement."
        ),
    },
    {
        "clause_type": "scope", "title": "Independent Contractor Status", "order": 2,
        "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "INDEPENDENT CONTRACTOR STATUS\n\n"
            "Tutor is an independent contractor and not an employee, agent, or partner of "
            "Client or any institution associated with Client. Nothing in this agreement "
            "shall be construed to create an employment relationship.\n\n"
            "Tutor retains full control over the methods and manner of delivering tutoring "
            "services, subject only to the scope and schedule agreed upon herein. Tutor is "
            "solely responsible for all taxes, insurance, and professional obligations "
            "arising from this engagement."
        ),
    },
    {
        "clause_type": "risk", "title": "No Guarantee of Academic Outcomes", "order": 3,
        "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "NO GUARANTEE OF ACADEMIC OUTCOMES\n\n"
            "Tutor makes no representations, warranties, or guarantees regarding Client's "
            "academic performance, grades, test scores, or educational outcomes as a result "
            "of tutoring sessions.\n\n"
            "Academic results depend on many factors beyond Tutor's control, including but "
            "not limited to Client's engagement, study habits, attendance, effort outside "
            "of sessions, and the policies of Client's educational institution.\n\n"
            "Client acknowledges that tutoring is a supplemental educational support "
            "service and agrees not to hold Tutor liable for any academic result."
        ),
    },
    {
        "clause_type": "cancellation", "title": "Late Arrival and Tardiness Policy", "order": 4,
        "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "LATE ARRIVAL AND TARDINESS POLICY\n\n"
            "Sessions begin at the scheduled start time. If Client arrives late, the session "
            "will run until the originally scheduled end time and will not be extended to "
            "compensate for the late arrival. The full session fee applies regardless of "
            "when Client arrives.\n\n"
            "If Tutor is more than 10 minutes late to a scheduled session, the session "
            "will either be rescheduled at no cost or prorated for the actual time delivered, "
            "at Client's election."
        ),
    },
    {
        "clause_type": "cancellation", "title": "Cancellation Policy", "order": 5,
        "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "CANCELLATION POLICY\n\n"
            "Client agrees to provide at least {{cancellation_window_hours}} hours advance "
            "notice for any session cancellation or rescheduling.\n\n"
            "Cancellations with less than {{cancellation_window_hours}} hours notice, or "
            "failure to appear without notice (\"no-show\"), will result in forfeiture of "
            "that session. No refund or credit will be issued for late cancellations or "
            "no-shows.\n\n"
            "Tutor agrees to provide the same advance notice for any sessions Tutor must "
            "cancel. Sessions cancelled by Tutor will be rescheduled at no additional cost."
        ),
    },
    {
        "clause_type": "confidentiality", "title": "Confidentiality", "order": 6,
        "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "CONFIDENTIALITY\n\n"
            "Tutor agrees to hold strictly confidential all personal information, academic "
            "records, performance data, and other sensitive information shared by or about "
            "Client in the course of this engagement.\n\n"
            "Tutor shall not disclose Client information to any third party without "
            "express written consent, except as required by law. This includes academic "
            "results, learning challenges, and any personal circumstances disclosed "
            "during sessions."
        ),
    },
    {
        "clause_type": "termination", "title": "Termination", "order": 7,
        "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate this agreement upon {{termination_notice_days}} days "
            "written notice to the other party.\n\n"
            "Upon termination by Client: Client will be refunded for any unused prepaid "
            "sessions at the per-session rate, less any outstanding amounts owed.\n\n"
            "Upon termination by Tutor: Tutor will refund any prepaid amounts for sessions "
            "not yet delivered, in full.\n\n"
            "Termination for cause — including abusive conduct, repeated no-shows, or "
            "non-payment — may be effected immediately without a notice period."
        ),
    },
]


# ==============================================================================
# EDUCATION & TUTORING — SKILLS COACHING
# ==============================================================================

SKILLS_COACHING_GUIDED_FIELDS = [
    {"field_key": "service_delivery", "label": "Service Delivery Format", "field_type": "choice",
     "choices": ["In-Person", "Online"], "is_required": True, "order": 1,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "coaching_focus", "label": "Coaching Focus", "field_type": "choice",
     "choices": ["Business Coaching", "Life Coaching", "Executive Coaching", "Career Coaching"],
     "is_required": True, "order": 2, "condition_field_key": "", "condition_value": ""},
    {"field_key": "session_duration_minutes", "label": "Session Duration (minutes)",
     "field_type": "number", "choices": None, "is_required": True, "order": 3,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "num_sessions", "label": "Number of Sessions",
     "field_type": "number", "choices": None, "is_required": True, "order": 4,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "rate_per_session", "label": "Rate Per Session (USD)",
     "field_type": "number", "choices": None, "is_required": True, "order": 5,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "payment_model", "label": "Payment Model", "field_type": "choice",
     "choices": ["single_session", "package_upfront", "package_installments"],
     "is_required": True, "order": 6, "condition_field_key": "", "condition_value": ""},
    *_installment_fields(7, 8),
    {"field_key": "cancellation_window_hours", "label": "Late Cancellation Window (hours)",
     "field_type": "number", "choices": None, "is_required": False, "order": 9,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "termination_notice_days", "label": "Termination Notice Period (days)",
     "field_type": "number", "choices": None, "is_required": False, "order": 10,
     "condition_field_key": "", "condition_value": ""},
]

SKILLS_COACHING_CLAUSES = [
    {
        "clause_type": "scope", "title": "Scope of Services", "order": 1,
        "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Coach\") agrees to provide {{coaching_focus}} services "
            "to {{counterparty_name}} (\"Client\") under the following terms:\n\n"
            "Service Format: {{service_delivery}}\n"
            "Session Duration: {{session_duration_minutes}} minutes per session\n"
            "Total Sessions: {{num_sessions}} sessions\n\n"
            "Coach shall provide a structured, goal-oriented coaching engagement focused on "
            "{{coaching_focus}}. Sessions will be collaborative, action-oriented, and designed "
            "to support Client in identifying goals, building strategies, and developing "
            "skills relevant to their professional and personal growth. Services are limited "
            "to coaching and do not include consulting, legal, financial, or therapeutic services."
        ),
    },
    {
        "clause_type": "risk", "title": "Coaching vs. Therapy Disclaimer", "order": 2,
        "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "COACHING VS. THERAPY DISCLAIMER\n\n"
            "Coaching is a distinct service from therapy, counseling, psychiatry, or any "
            "licensed mental health practice. Coach is not a licensed therapist, psychologist, "
            "social worker, or mental health provider, and this agreement does not create a "
            "therapist-patient or healthcare provider relationship of any kind.\n\n"
            "Coaching does not diagnose, treat, cure, or prevent any mental health condition "
            "or psychological disorder. Clients experiencing mental health concerns are "
            "encouraged to seek support from a licensed mental health professional.\n\n"
            "Nothing communicated by Coach in sessions or supporting materials constitutes "
            "medical advice, psychological treatment, or clinical guidance of any kind."
        ),
    },
    {
        "clause_type": "risk", "title": "No Guarantee of Outcomes", "order": 3,
        "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "NO GUARANTEE OF OUTCOMES\n\n"
            "Coaching results depend entirely on Client's own commitment, effort, and "
            "follow-through between sessions. Coach makes no representations, warranties, "
            "or guarantees — express or implied — regarding specific outcomes including "
            "career advancement, revenue growth, relationship improvement, or any other "
            "professional or personal result.\n\n"
            "Client acknowledges that they are fully responsible for their own decisions "
            "and actions taken in connection with this coaching engagement. Client agrees "
            "not to hold Coach liable for any decision made or action taken as a result "
            "of coaching conversations."
        ),
    },
    {
        "clause_type": "confidentiality", "title": "Confidentiality", "order": 4,
        "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "CONFIDENTIALITY\n\n"
            "Coach agrees to hold strictly confidential all information, goals, strategies, "
            "business data, and personal disclosures shared by Client during sessions or "
            "related communications.\n\n"
            "Coach shall not disclose Client information to any third party without "
            "Client's express written consent, except as required by law or to prevent "
            "imminent harm. This obligation continues after the termination of this agreement.\n\n"
            "Client information will be used solely to support the coaching engagement "
            "and will not be shared, published, or used for any other purpose without "
            "explicit written permission."
        ),
    },
    {
        "clause_type": "cancellation", "title": "Cancellation Policy", "order": 5,
        "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "CANCELLATION POLICY\n\n"
            "Client agrees to provide at least {{cancellation_window_hours}} hours advance "
            "notice for any session cancellation or rescheduling.\n\n"
            "Cancellations with less than {{cancellation_window_hours}} hours notice, or "
            "failure to appear without notice (\"no-show\"), will result in forfeiture of "
            "that session. No refund or credit will be issued for late cancellations or "
            "no-shows.\n\n"
            "Coach agrees to provide the same advance notice for any sessions Coach must "
            "cancel. Sessions cancelled by Coach will be rescheduled at no additional cost."
        ),
    },
    {
        "clause_type": "scope", "title": "Independent Contractor Status", "order": 6,
        "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "INDEPENDENT CONTRACTOR STATUS\n\n"
            "Coach is an independent contractor and not an employee, agent, or partner of "
            "Client. Nothing in this agreement shall be construed to create an employment "
            "relationship. Coach retains full discretion over the methods and manner of "
            "delivering coaching services, subject only to the scope and schedule agreed "
            "upon herein.\n\n"
            "Coach is solely responsible for all taxes, professional insurance, and "
            "obligations arising from this engagement."
        ),
    },
    {
        "clause_type": "termination", "title": "Termination", "order": 7,
        "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate this agreement upon {{termination_notice_days}} days "
            "written notice to the other party.\n\n"
            "Upon termination by Client: Client will be refunded for any unused prepaid "
            "sessions at the per-session rate, less any outstanding amounts owed.\n\n"
            "Upon termination by Coach: Coach will refund any prepaid amounts for sessions "
            "not yet delivered, in full.\n\n"
            "Termination for cause — including abusive conduct, repeated no-shows, or "
            "non-payment — may be effected immediately without a notice period."
        ),
    },
]


# ==============================================================================
# EDUCATION & TUTORING — TEST PREP
# ==============================================================================

TEST_PREP_GUIDED_FIELDS = [
    {"field_key": "service_delivery", "label": "Service Delivery Format", "field_type": "choice",
     "choices": ["In-Person", "Online"], "is_required": True, "order": 1,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "test_name", "label": "Exam or Certification Name",
     "field_type": "text", "choices": None, "is_required": True, "order": 2,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "program_duration_weeks", "label": "Program Duration (weeks)",
     "field_type": "number", "choices": None, "is_required": True, "order": 3,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "sessions_per_week", "label": "Sessions Per Week",
     "field_type": "number", "choices": None, "is_required": True, "order": 4,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "session_duration_minutes", "label": "Session Duration (minutes)",
     "field_type": "number", "choices": None, "is_required": True, "order": 5,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "total_program_price", "label": "Total Program Price (USD)",
     "field_type": "number", "choices": None, "is_required": True, "order": 6,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "payment_model", "label": "Payment Model", "field_type": "choice",
     "choices": ["package_upfront", "package_installments"],
     "is_required": True, "order": 7, "condition_field_key": "", "condition_value": ""},
    *_installment_fields(8, 9),
    {"field_key": "cancellation_window_hours", "label": "Late Cancellation Window (hours)",
     "field_type": "number", "choices": None, "is_required": False, "order": 10,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "termination_notice_days", "label": "Termination Notice Period (days)",
     "field_type": "number", "choices": None, "is_required": False, "order": 11,
     "condition_field_key": "", "condition_value": ""},
]

TEST_PREP_CLAUSES = [
    {
        "clause_type": "scope", "title": "Scope of Services", "order": 1,
        "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Tutor\") agrees to provide a test preparation program "
            "for {{counterparty_name}} (\"Client\") targeting the {{test_name}} under the "
            "following terms:\n\n"
            "Target Exam: {{test_name}}\n"
            "Service Format: {{service_delivery}}\n"
            "Program Duration: {{program_duration_weeks}} weeks\n"
            "Sessions Per Week: {{sessions_per_week}}\n"
            "Session Duration: {{session_duration_minutes}} minutes per session\n\n"
            "Tutor shall provide structured test preparation instruction including content "
            "review, practice problems, exam strategy, and timed practice assessments "
            "appropriate to the {{test_name}} format. All materials and session content "
            "will be oriented toward the specific exam named above."
        ),
    },
    {
        "clause_type": "risk", "title": "No Score or Result Guarantee", "order": 2,
        "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "NO SCORE OR RESULT GUARANTEE\n\n"
            "Tutor makes no representations, warranties, or guarantees regarding Client's "
            "performance on the {{test_name}} or any other examination. Test scores depend "
            "on many factors beyond Tutor's control, including Client's prior knowledge, "
            "study effort outside of sessions, test-taking conditions, and the exam "
            "policies of the administering organization.\n\n"
            "No specific score improvement, passing result, or admission outcome is "
            "promised or implied by this agreement or by any verbal or written "
            "communication from Tutor. Client agrees not to hold Tutor liable for any "
            "exam result."
        ),
    },
    {
        "clause_type": "scope", "title": "Program Completion Policy", "order": 3,
        "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "PROGRAM COMPLETION POLICY\n\n"
            "This agreement covers a defined test preparation program with a fixed scope "
            "and price. If Client withdraws from the program before completion, no refund "
            "will be issued for sessions already delivered or for remaining sessions in the "
            "program, except as provided in the Termination clause of this agreement.\n\n"
            "Client acknowledges that preparation programs are structured sequentially and "
            "that partial completion may reduce the effectiveness of the program. Tutor "
            "will make reasonable efforts to reschedule sessions missed due to Client "
            "unavailability, subject to Tutor's schedule availability."
        ),
    },
    {
        "clause_type": "cancellation", "title": "Cancellation Policy", "order": 4,
        "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "CANCELLATION POLICY\n\n"
            "Client agrees to provide at least {{cancellation_window_hours}} hours advance "
            "notice for any session cancellation or rescheduling.\n\n"
            "Cancellations with less than {{cancellation_window_hours}} hours notice, or "
            "failure to appear without notice (\"no-show\"), will be counted as a completed "
            "session for billing purposes. No credit will be issued.\n\n"
            "Tutor agrees to provide the same advance notice for any sessions Tutor must "
            "cancel. Sessions cancelled by Tutor will be rescheduled at no additional cost."
        ),
    },
    {
        "clause_type": "scope", "title": "Independent Contractor Status", "order": 5,
        "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "INDEPENDENT CONTRACTOR STATUS\n\n"
            "Tutor is an independent contractor and not an employee, agent, or partner of "
            "Client or any institution affiliated with Client. Nothing in this agreement "
            "shall be construed to create an employment relationship.\n\n"
            "Tutor retains full control over the methods and manner of delivering "
            "preparation services, subject only to the scope and schedule agreed herein. "
            "Tutor is solely responsible for all taxes, insurance, and professional "
            "obligations arising from this engagement."
        ),
    },
    {
        "clause_type": "confidentiality", "title": "Confidentiality", "order": 6,
        "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "CONFIDENTIALITY\n\n"
            "Tutor agrees to hold strictly confidential all personal information, academic "
            "history, diagnostic results, and performance data shared by or about Client "
            "during this engagement.\n\n"
            "Tutor shall not disclose Client information to any third party without "
            "express written consent, except as required by law. Client's exam preparation "
            "progress and results will not be shared, published, or used for any purpose "
            "other than delivering services under this agreement."
        ),
    },
    {
        "clause_type": "termination", "title": "Termination", "order": 7,
        "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate this agreement upon {{termination_notice_days}} days "
            "written notice to the other party.\n\n"
            "Upon early termination by Client: Client will be charged for all sessions "
            "delivered to date at the effective per-session rate implied by the total "
            "program price. Any prepaid amount in excess of sessions delivered will be "
            "refunded.\n\n"
            "Upon termination by Tutor: Tutor will refund a prorated portion of any "
            "prepaid amount corresponding to sessions not yet delivered.\n\n"
            "Termination for cause — including abusive conduct, repeated no-shows, or "
            "non-payment — may be effected immediately without a notice period."
        ),
    },
]


# ==============================================================================
# CREATIVE SERVICES — DATA CONSTANTS
# ==============================================================================

# ------------------------------------------------------------------------------
# PHOTOGRAPHY
# ------------------------------------------------------------------------------

PHOTOGRAPHY_GUIDED_FIELDS = [
    {"field_key": "service_type", "label": "Photography Service Type", "field_type": "choice",
     "choices": ["Event", "Portrait", "Commercial", "Real Estate"], "is_required": True, "order": 1,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "project_description", "label": "Event or Shoot Description", "field_type": "text",
     "choices": None, "is_required": True, "order": 2,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "shoot_date", "label": "Scheduled Shoot Date", "field_type": "text",
     "choices": None, "is_required": True, "order": 3,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "shoot_location", "label": "Shoot Location / Venue", "field_type": "text",
     "choices": None, "is_required": True, "order": 4,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "duration_hours", "label": "Duration (Hours)", "field_type": "number",
     "choices": None, "is_required": True, "order": 5,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "rate", "label": "Total Photography Fee (USD)", "field_type": "number",
     "choices": None, "is_required": True, "order": 6,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "payment_model", "label": "Payment Structure", "field_type": "choice",
     "choices": ["full_upfront", "deposit_balance", "installments"], "is_required": True, "order": 7,
     "condition_field_key": "", "condition_value": ""},
] + _installment_fields_creative(8, 9) + [
    {"field_key": "edited_images_count", "label": "Edited Images Delivered", "field_type": "number",
     "choices": None, "is_required": True, "order": 10,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "turnaround_days", "label": "Delivery Turnaround (Days)", "field_type": "number",
     "choices": None, "is_required": True, "order": 11,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "print_rights_included", "label": "Print Rights Included", "field_type": "boolean",
     "choices": None, "is_required": True, "order": 12,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "commercial_use_rights", "label": "Commercial Use Rights Included", "field_type": "boolean",
     "choices": None, "is_required": True, "order": 13,
     "condition_field_key": "", "condition_value": ""},
]

PHOTOGRAPHY_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Photography Services",
        "order": 1, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "SCOPE OF PHOTOGRAPHY SERVICES\n\n"
            "{{initiator_name}} (\"Photographer\") agrees to provide photography services "
            "to {{counterparty_name}} (\"Client\") as follows:\n\n"
            "Service Type: {{service_type}}\n"
            "Description: {{project_description}}\n"
            "Date: {{shoot_date}}\n"
            "Location: {{shoot_location}}\n"
            "Duration: {{duration_hours}} hours\n"
            "Deliverables: {{edited_images_count}} professionally edited digital images\n"
            "Delivery Timeline: {{turnaround_days}} days from shoot date\n\n"
            "Photographer shall provide professional photography coverage for the duration specified. "
            "Final edited images will be delivered via digital download or gallery link. "
            "RAW/unedited files are not included unless separately agreed in writing."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 2, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Total Fee: ${{rate}}\n"
            "Payment Structure: {{payment_model}}\n\n"
            "For deposit_balance: a non-refundable retainer of 50% (${{rate}} × 50%) is due upon "
            "signing to secure the booking. The remaining balance is due on or before the shoot date.\n\n"
            "For full_upfront: the total fee is due upon signing.\n\n"
            "For installments: {{num_installments}} equal installments billed every "
            "{{installment_interval_days}} days beginning on the contract start date.\n\n"
            "Photographer will not commence services until the required upfront payment is received. "
            "Payments not received within 7 days of the due date may result in session postponement."
        ),
    },
    {
        "clause_type": "general",
        "title": "Usage Rights and Copyright",
        "order": 3, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "USAGE RIGHTS AND COPYRIGHT\n\n"
            "Print Rights Included: {{print_rights_included}}\n"
            "Commercial Use Rights Included: {{commercial_use_rights}}\n\n"
            "Photographer retains copyright to all images captured under this agreement. "
            "Client is granted a non-exclusive, non-transferable personal license to use the "
            "delivered images for the purpose described above.\n\n"
            "Photographer reserves the right to use a selection of images for portfolio, "
            "website, and promotional purposes. Client may request a portfolio restriction in "
            "writing; such requests will be accommodated at Photographer's reasonable discretion.\n\n"
            "Commercial use rights, where granted, authorize use in advertising, product "
            "packaging, and editorial contexts. Any use beyond the granted license requires "
            "written consent and may incur additional licensing fees."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation and Rescheduling Policy",
        "order": 4, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "CANCELLATION AND RESCHEDULING POLICY\n\n"
            "Any retainer or deposit paid is non-refundable and compensates Photographer for "
            "holding the scheduled date and declining other bookings.\n\n"
            "Cancellations by Client within 14 days of the scheduled shoot date will result in "
            "forfeiture of all amounts paid, plus any balance remaining due as liquidated damages "
            "reflecting Photographer's lost opportunity costs.\n\n"
            "Rescheduling requests made at least 30 days in advance will be accommodated subject "
            "to Photographer's availability at no additional charge. Rescheduling within 30 days "
            "may incur a rescheduling fee of up to 25% of the total fee.\n\n"
            "If Photographer must cancel due to illness, emergency, or force majeure, Photographer "
            "will make reasonable efforts to provide a qualified substitute or will refund all "
            "payments received."
        ),
    },
    {
        "clause_type": "liability",
        "title": "Limitation of Liability",
        "order": 5, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "LIMITATION OF LIABILITY\n\n"
            "In the event of equipment failure, storage media corruption, accident, or technical "
            "failure beyond Photographer's reasonable control, Photographer's total liability is "
            "limited to a refund of amounts paid. Photographer shall not be liable for indirect, "
            "incidental, consequential, or special damages, including loss of memories, lost "
            "business opportunities, or emotional distress.\n\n"
            "Photographer will maintain backup copies of images during post-production but cannot "
            "guarantee against catastrophic data loss. Client is encouraged to obtain event "
            "insurance for significant occasions."
        ),
    },
    {
        "clause_type": "general",
        "title": "Client Responsibilities and Cooperation",
        "order": 6, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "CLIENT RESPONSIBILITIES AND COOPERATION\n\n"
            "Client shall ensure all subjects are informed of and consent to being photographed. "
            "For minors, Client warrants that parental or guardian consent has been obtained. "
            "Client shall provide Photographer with necessary access, reasonable cooperation, and "
            "a safe working environment throughout the engagement.\n\n"
            "Photographer is not responsible for failure to capture specific moments resulting "
            "from the timing or cooperation of third parties beyond Photographer's control. "
            "Client is responsible for coordinating subjects and providing a reasonable schedule."
        ),
    },
    {
        "clause_type": "termination",
        "title": "Termination",
        "order": 7, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate this agreement upon written notice if the other party "
            "materially breaches its obligations and fails to cure such breach within 7 days of "
            "written notice. Upon termination by Client for Photographer's uncured breach, "
            "Photographer shall refund amounts paid pro-rated to undelivered services. "
            "Upon termination for Client's breach, all amounts due under the agreement remain owed."
        ),
    },
    {
        "clause_type": "general",
        "title": "Entire Agreement",
        "order": 8, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "ENTIRE AGREEMENT\n\n"
            "This agreement constitutes the entire agreement between the parties regarding "
            "photography services and supersedes all prior negotiations, representations, or "
            "agreements. Amendments must be made in writing and signed by both parties. "
            "If any provision of this agreement is found to be unenforceable, the remaining "
            "provisions shall continue in full force and effect."
        ),
    },
]

# ------------------------------------------------------------------------------
# VIDEOGRAPHY
# ------------------------------------------------------------------------------

VIDEOGRAPHY_GUIDED_FIELDS = [
    {"field_key": "service_type", "label": "Videography Service Type", "field_type": "choice",
     "choices": ["Event", "Commercial", "Music Video", "Social Content", "Documentary"],
     "is_required": True, "order": 1, "condition_field_key": "", "condition_value": ""},
    {"field_key": "project_description", "label": "Project Description", "field_type": "text",
     "choices": None, "is_required": True, "order": 2,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "shoot_date", "label": "Scheduled Shoot Date", "field_type": "text",
     "choices": None, "is_required": True, "order": 3,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "shoot_location", "label": "Shoot Location / Venue", "field_type": "text",
     "choices": None, "is_required": True, "order": 4,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "duration_hours", "label": "Shoot Duration (Hours)", "field_type": "number",
     "choices": None, "is_required": True, "order": 5,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "rate", "label": "Total Videography Fee (USD)", "field_type": "number",
     "choices": None, "is_required": True, "order": 6,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "payment_model", "label": "Payment Structure", "field_type": "choice",
     "choices": ["full_upfront", "deposit_balance", "installments"], "is_required": True, "order": 7,
     "condition_field_key": "", "condition_value": ""},
] + _installment_fields_creative(8, 9) + [
    {"field_key": "final_video_length_minutes", "label": "Final Edited Video Length (Minutes)",
     "field_type": "number", "choices": None, "is_required": True, "order": 10,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "turnaround_days", "label": "Delivery Turnaround (Days)", "field_type": "number",
     "choices": None, "is_required": True, "order": 11,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "raw_footage_included", "label": "Raw Footage Included in Delivery",
     "field_type": "boolean", "choices": None, "is_required": True, "order": 12,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "usage_rights", "label": "Usage Rights", "field_type": "choice",
     "choices": ["Personal", "Commercial", "Broadcast"], "is_required": True, "order": 13,
     "condition_field_key": "", "condition_value": ""},
]

VIDEOGRAPHY_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Videography Services",
        "order": 1, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "SCOPE OF VIDEOGRAPHY SERVICES\n\n"
            "{{initiator_name}} (\"Videographer\") agrees to provide videography services "
            "to {{counterparty_name}} (\"Client\") as follows:\n\n"
            "Service Type: {{service_type}}\n"
            "Description: {{project_description}}\n"
            "Shoot Date: {{shoot_date}}\n"
            "Location: {{shoot_location}}\n"
            "Shoot Duration: {{duration_hours}} hours\n"
            "Final Deliverable: edited video approximately {{final_video_length_minutes}} minutes\n"
            "Raw Footage Included: {{raw_footage_included}}\n"
            "Delivery Timeline: {{turnaround_days}} days from shoot completion\n"
            "Usage Rights: {{usage_rights}}\n\n"
            "Videographer shall capture, edit, and deliver the final video in standard HD or 4K "
            "resolution as mutually agreed. The delivered edit represents Videographer's "
            "professional creative interpretation of the project brief."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 2, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Total Fee: ${{rate}}\n"
            "Payment Structure: {{payment_model}}\n\n"
            "For deposit_balance: a non-refundable retainer of 50% is due upon signing. "
            "The remaining balance is due upon delivery of the first cut.\n\n"
            "For full_upfront: the total fee is due upon signing.\n\n"
            "For installments: {{num_installments}} installments billed every "
            "{{installment_interval_days}} days beginning on the contract start date.\n\n"
            "Final deliverable files will be released to Client only after all payments have "
            "been received in full."
        ),
    },
    {
        "clause_type": "general",
        "title": "Revisions and Deliverables",
        "order": 3, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "REVISIONS AND DELIVERABLES\n\n"
            "The fee includes up to two rounds of revision on the edited video. Additional revision "
            "rounds may be requested and will be billed at Videographer's standard hourly rate. "
            "Revision requests must be submitted in writing within 7 days of delivery of each "
            "version. Requests submitted after this window may be treated as new project work.\n\n"
            "Final delivery format: MP4 (H.264 or H.265) delivered via secure digital link. "
            "Raw footage, if included, will be delivered via hard drive or large file transfer "
            "service at Client's expense for physical media."
        ),
    },
    {
        "clause_type": "general",
        "title": "Usage Rights and Copyright",
        "order": 4, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "USAGE RIGHTS AND COPYRIGHT\n\n"
            "Videographer retains copyright to all footage captured. Client is granted a "
            "{{usage_rights}} license to use the final edited video.\n\n"
            "Personal license: for private, non-commercial use only.\n"
            "Commercial license: for use in advertising, social media, and promotional contexts.\n"
            "Broadcast license: includes commercial rights plus television and streaming platform use.\n\n"
            "Videographer reserves the right to use a short highlight reel or still frames for "
            "portfolio and promotional purposes, unless Client requests otherwise in writing."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation and Rescheduling Policy",
        "order": 5, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "CANCELLATION AND RESCHEDULING POLICY\n\n"
            "Any deposit or retainer paid is non-refundable. Cancellations within 14 days of the "
            "scheduled shoot forfeit all amounts paid and any remaining balance becomes due as "
            "liquidated damages.\n\n"
            "Rescheduling requests made at least 30 days in advance will be accommodated at no "
            "additional charge, subject to availability. Rescheduling within 30 days may incur "
            "a rescheduling fee.\n\n"
            "If Videographer cancels due to illness, emergency, or force majeure, Videographer "
            "will use reasonable efforts to provide a substitute or will refund all amounts paid."
        ),
    },
    {
        "clause_type": "liability",
        "title": "Limitation of Liability",
        "order": 6, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "LIMITATION OF LIABILITY\n\n"
            "Videographer's total liability shall not exceed the total fees paid under this "
            "agreement. Videographer shall not be liable for indirect, incidental, or consequential "
            "damages. In the event of equipment failure or unrecoverable footage loss beyond "
            "Videographer's control, liability is limited to a refund of amounts paid. "
            "Videographer maintains backup copies during post-production but cannot guarantee "
            "against catastrophic data loss."
        ),
    },
    {
        "clause_type": "general",
        "title": "Cooperation and Access",
        "order": 7, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "COOPERATION AND ACCESS\n\n"
            "Client shall ensure Videographer has adequate access to the venue, subjects, and "
            "all areas necessary for filming. Client is responsible for obtaining all necessary "
            "venue permits and third-party releases. Videographer is not responsible for footage "
            "quality impacted by poor lighting, restricted access, or uncooperative subjects "
            "beyond Videographer's control."
        ),
    },
    {
        "clause_type": "termination",
        "title": "Termination",
        "order": 8, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate this agreement for material breach upon written notice "
            "and 7 days opportunity to cure. Upon termination by Client for Videographer's "
            "uncured breach, amounts will be refunded pro-rated to undelivered work. Upon "
            "termination for Client's breach, all amounts due remain owed and any completed "
            "work product belongs to Videographer until payment is received in full."
        ),
    },
    {
        "clause_type": "general",
        "title": "Entire Agreement",
        "order": 9, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "ENTIRE AGREEMENT\n\n"
            "This agreement constitutes the entire agreement between the parties and supersedes "
            "all prior discussions. Amendments must be made in writing and signed by both parties. "
            "If any provision is found unenforceable, the remaining provisions remain in effect."
        ),
    },
]

# ------------------------------------------------------------------------------
# GRAPHIC DESIGN
# ------------------------------------------------------------------------------

GRAPHIC_DESIGN_GUIDED_FIELDS = [
    {"field_key": "project_type", "label": "Design Project Type", "field_type": "choice",
     "choices": ["Logo & Branding", "Social Media Graphics", "Website Design",
                 "Print Materials", "Illustration"],
     "is_required": True, "order": 1, "condition_field_key": "", "condition_value": ""},
    {"field_key": "project_description", "label": "Project Description and Scope", "field_type": "text",
     "choices": None, "is_required": True, "order": 2,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "num_revisions", "label": "Revision Rounds Included", "field_type": "number",
     "choices": None, "is_required": True, "order": 3,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "rate", "label": "Total Project Fee (USD)", "field_type": "number",
     "choices": None, "is_required": True, "order": 4,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "payment_model", "label": "Payment Structure", "field_type": "choice",
     "choices": ["full_upfront", "deposit_balance", "installments", "milestone"],
     "is_required": True, "order": 5, "condition_field_key": "", "condition_value": ""},
] + _installment_fields_creative(6, 7) + [
    {"field_key": "turnaround_days", "label": "Initial Concept Delivery (Days)", "field_type": "number",
     "choices": None, "is_required": True, "order": 8,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "file_formats", "label": "File Formats Delivered (e.g., PNG, PDF, SVG)",
     "field_type": "text", "choices": None, "is_required": True, "order": 9,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "commercial_license", "label": "Full Commercial License Included",
     "field_type": "boolean", "choices": None, "is_required": True, "order": 10,
     "condition_field_key": "", "condition_value": ""},
]

GRAPHIC_DESIGN_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Design Services",
        "order": 1, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "SCOPE OF DESIGN SERVICES\n\n"
            "{{initiator_name}} (\"Designer\") agrees to provide graphic design services "
            "to {{counterparty_name}} (\"Client\") as follows:\n\n"
            "Project Type: {{project_type}}\n"
            "Description: {{project_description}}\n"
            "Revision Rounds Included: {{num_revisions}}\n"
            "Initial Concept Delivery: {{turnaround_days}} days from project kickoff\n"
            "Deliverable Formats: {{file_formats}}\n"
            "Commercial License: {{commercial_license}}\n\n"
            "Designer shall create original designs based on the brief provided by Client. "
            "A kickoff questionnaire or brief review call may be required before work begins."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 2, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Total Project Fee: ${{rate}}\n"
            "Payment Structure: {{payment_model}}\n\n"
            "For deposit_balance: 50% deposit due upon signing; remainder due upon delivery of "
            "final approved files.\n\n"
            "For full_upfront: full payment due upon signing.\n\n"
            "For installments: {{num_installments}} equal installments every "
            "{{installment_interval_days}} days from contract start date.\n\n"
            "For milestone: 50% due at concept approval; 50% due upon final file delivery.\n\n"
            "Final deliverable files will be released only after all payments are received in full. "
            "Unpaid balances may result in work suspension."
        ),
    },
    {
        "clause_type": "general",
        "title": "Revisions Policy",
        "order": 3, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "REVISIONS POLICY\n\n"
            "This agreement includes {{num_revisions}} round(s) of revisions. A revision round "
            "is defined as a consolidated set of changes submitted in a single written request. "
            "Each additional revision round beyond the included amount will be billed at "
            "Designer's standard hourly or flat rate.\n\n"
            "Revisions that materially alter the original project scope (scope creep) may be "
            "treated as new work and quoted separately. Designer will notify Client before "
            "proceeding with any work that falls outside the agreed scope."
        ),
    },
    {
        "clause_type": "general",
        "title": "Intellectual Property and License",
        "order": 4, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "INTELLECTUAL PROPERTY AND LICENSE\n\n"
            "Upon receipt of full payment, Designer assigns to Client all rights, title, and "
            "interest in the final approved deliverables, including copyright.\n\n"
            "Commercial License Included: {{commercial_license}}\n\n"
            "All preliminary concepts, unused drafts, and working files remain Designer's "
            "intellectual property unless specifically included in the deliverables. "
            "Third-party assets (stock imagery, fonts) remain subject to their respective "
            "license terms; Client is responsible for any licensing fees for continued use.\n\n"
            "Designer retains the right to display the final work in a professional portfolio "
            "unless Client requests otherwise in writing."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation Policy",
        "order": 5, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "CANCELLATION POLICY\n\n"
            "If Client cancels the project after work has begun, Client shall compensate "
            "Designer for all work completed to date, calculated pro-rata to the project fee. "
            "Any deposit paid is non-refundable. Work product created up to the cancellation "
            "date remains Designer's property until the pro-rated amount is paid in full.\n\n"
            "Cancellation requests must be submitted in writing. Designer will provide an "
            "accounting of work completed within 5 business days of cancellation notice."
        ),
    },
    {
        "clause_type": "liability",
        "title": "Limitation of Liability",
        "order": 6, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "LIMITATION OF LIABILITY\n\n"
            "Designer's total liability shall not exceed the total fees paid under this agreement. "
            "Designer shall not be liable for indirect, incidental, or consequential damages, "
            "including lost profits or business opportunities. Client is responsible for "
            "proofreading all final deliverables before printing or publication. Designer is "
            "not liable for errors in content provided by Client."
        ),
    },
    {
        "clause_type": "general",
        "title": "Client Responsibilities",
        "order": 7, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "CLIENT RESPONSIBILITIES\n\n"
            "Client shall provide all necessary content, assets, brand guidelines, and feedback "
            "in a timely manner. Delays caused by late Client feedback may extend the project "
            "timeline; Designer is not liable for such delays. Client warrants that all content "
            "and assets provided are owned by Client or properly licensed for the intended use "
            "and do not infringe any third-party intellectual property rights."
        ),
    },
    {
        "clause_type": "general",
        "title": "Entire Agreement",
        "order": 8, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "ENTIRE AGREEMENT\n\n"
            "This agreement constitutes the entire agreement between the parties regarding "
            "the design project and supersedes all prior discussions or representations. "
            "Amendments must be in writing and signed by both parties."
        ),
    },
]

# ------------------------------------------------------------------------------
# BEAT AND MUSIC PRODUCTION
# ------------------------------------------------------------------------------

BEAT_PRODUCTION_GUIDED_FIELDS = [
    {"field_key": "genre", "label": "Genre / Style", "field_type": "choice",
     "choices": ["Hip-Hop", "R&B", "Pop", "Trap", "Afrobeats", "Electronic", "Other"],
     "is_required": True, "order": 1, "condition_field_key": "", "condition_value": ""},
    {"field_key": "bpm", "label": "BPM (Beats Per Minute)", "field_type": "number",
     "choices": None, "is_required": True, "order": 2,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "key_signature", "label": "Key Signature (e.g., C Minor)", "field_type": "text",
     "choices": None, "is_required": False, "order": 3,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "license_type", "label": "License Type", "field_type": "choice",
     "choices": ["Non-Exclusive Lease", "Exclusive License", "Full Buyout"],
     "is_required": True, "order": 4, "condition_field_key": "", "condition_value": ""},
    {"field_key": "rate", "label": "Total Beat Price (USD)", "field_type": "number",
     "choices": None, "is_required": True, "order": 5,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "payment_model", "label": "Payment Structure", "field_type": "choice",
     "choices": ["full_upfront", "installments"], "is_required": True, "order": 6,
     "condition_field_key": "", "condition_value": ""},
] + _installment_fields_creative(7, 8) + [
    {"field_key": "stems_included", "label": "Stems / Track-Outs Included",
     "field_type": "boolean", "choices": None, "is_required": True, "order": 9,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "distribution_limit", "label": "Distribution Copies / Streams Allowed",
     "field_type": "text", "choices": None, "is_required": False, "order": 10,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "producer_credit", "label": "Producer Tag / Credit Required",
     "field_type": "boolean", "choices": None, "is_required": True, "order": 11,
     "condition_field_key": "", "condition_value": ""},
]

BEAT_PRODUCTION_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Beat Production Services",
        "order": 1, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "SCOPE OF BEAT PRODUCTION SERVICES\n\n"
            "{{initiator_name}} (\"Producer\") agrees to provide beat production services "
            "to {{counterparty_name}} (\"Artist\") as follows:\n\n"
            "Genre / Style: {{genre}}\n"
            "BPM: {{bpm}}\n"
            "Key Signature: {{key_signature}}\n"
            "License Type: {{license_type}}\n"
            "Stems / Track-Outs Included: {{stems_included}}\n"
            "Distribution Limit: {{distribution_limit}}\n"
            "Producer Credit Required: {{producer_credit}}\n\n"
            "Producer shall deliver the beat(s) in WAV format (44.1kHz / 24-bit minimum), "
            "plus MP3 for reference. Stems, if included, will be delivered as individual "
            "instrument tracks in WAV format."
        ),
    },
    {
        "clause_type": "general",
        "title": "License Grant",
        "order": 2, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "LICENSE GRANT\n\n"
            "License Type Granted: {{license_type}}\n\n"
            "Non-Exclusive Lease: Artist receives a limited, non-exclusive, non-transferable "
            "license to use the beat for recording, distribution, and performance. Distribution "
            "is limited to {{distribution_limit}} streams/copies unless otherwise agreed. "
            "Producer retains the right to license the same beat to other artists.\n\n"
            "Exclusive License: Artist receives an exclusive, transferable license for all "
            "commercial and non-commercial uses. Producer may not re-license the beat to "
            "other parties after the exclusive transfer is complete.\n\n"
            "Full Buyout: Artist receives full copyright transfer. Producer forfeits all "
            "future rights to the composition subject to applicable law.\n\n"
            "In all cases, Producer credit (\"Prod. by {{initiator_name}}\") must be included "
            "on all releases where producer_credit is required."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 3, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Total Beat Price: ${{rate}}\n"
            "Payment Structure: {{payment_model}}\n\n"
            "For full_upfront: payment is due upon agreement signing, before delivery of files.\n\n"
            "For installments: {{num_installments}} equal installments billed every "
            "{{installment_interval_days}} days. Files will be released upon receipt of the "
            "final installment payment.\n\n"
            "License rights are contingent on receipt of full payment. No license is granted "
            "until the beat price is paid in full."
        ),
    },
    {
        "clause_type": "general",
        "title": "Ownership and Credits",
        "order": 4, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "OWNERSHIP AND CREDITS\n\n"
            "Producer retains ownership of the underlying composition and master recording "
            "of the beat except where a Full Buyout is agreed. Artist owns the master "
            "recording of any vocals or performance layered over the beat.\n\n"
            "For publishing and royalty registration purposes, Producer shall be credited "
            "for the beat's underlying composition in any performance rights organization "
            "(e.g., ASCAP, BMI, SOCAN) filings made by Artist.\n\n"
            "Artist shall not register the beat composition in any rights organization "
            "as solely Artist's original work."
        ),
    },
    {
        "clause_type": "general",
        "title": "Exclusivity and Re-Licensing",
        "order": 5, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "EXCLUSIVITY AND RE-LICENSING\n\n"
            "For Non-Exclusive Leases: Producer reserves the right to sell additional leases "
            "or an exclusive license to other buyers at any time. If an exclusive license is "
            "subsequently sold to a third party, existing non-exclusive leases already in use "
            "may continue under their original terms at Producer's discretion.\n\n"
            "For Exclusive Licenses and Full Buyouts: Producer shall remove the beat from "
            "active sale/lease within a reasonable time following confirmation of full payment."
        ),
    },
    {
        "clause_type": "liability",
        "title": "Limitation of Liability and Warranties",
        "order": 6, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "LIMITATION OF LIABILITY AND WARRANTIES\n\n"
            "Producer warrants that the beat is an original work and does not knowingly contain "
            "uncleared samples or copyrighted material without appropriate licenses. If any "
            "third-party claim arises from uncleared samples, Producer shall indemnify Artist "
            "to the extent caused by Producer's error.\n\n"
            "Producer's total liability shall not exceed the total fees paid. Producer shall "
            "not be liable for indirect or consequential damages, including lost royalties or "
            "recording revenues."
        ),
    },
    {
        "clause_type": "general",
        "title": "Entire Agreement",
        "order": 7, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "ENTIRE AGREEMENT\n\n"
            "This agreement constitutes the entire agreement between Producer and Artist "
            "regarding the licensed beat and supersedes all prior negotiations. Amendments "
            "must be in writing and signed by both parties."
        ),
    },
]

# ------------------------------------------------------------------------------
# RECORDING AND SESSION SERVICES
# ------------------------------------------------------------------------------

RECORDING_SESSION_GUIDED_FIELDS = [
    {"field_key": "service_type", "label": "Recording Service Type", "field_type": "choice",
     "choices": ["Tracking", "Mixing", "Mastering", "Vocal Production", "Full Production"],
     "is_required": True, "order": 1, "condition_field_key": "", "condition_value": ""},
    {"field_key": "artist_name", "label": "Artist / Project Name", "field_type": "text",
     "choices": None, "is_required": True, "order": 2,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "project_title", "label": "Project Title (Album / EP / Single)",
     "field_type": "text", "choices": None, "is_required": True, "order": 3,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "num_sessions", "label": "Number of Sessions", "field_type": "number",
     "choices": None, "is_required": True, "order": 4,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "session_duration_hours", "label": "Hours Per Session", "field_type": "number",
     "choices": None, "is_required": True, "order": 5,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "rate", "label": "Total Project Fee (USD)", "field_type": "number",
     "choices": None, "is_required": True, "order": 6,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "payment_model", "label": "Payment Structure", "field_type": "choice",
     "choices": ["full_upfront", "deposit_balance", "installments"],
     "is_required": True, "order": 7, "condition_field_key": "", "condition_value": ""},
] + _installment_fields_creative(8, 9) + [
    {"field_key": "engineer_credit", "label": "Engineer Credit on Release",
     "field_type": "boolean", "choices": None, "is_required": True, "order": 10,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "studio_location", "label": "Studio Name / Location", "field_type": "text",
     "choices": None, "is_required": True, "order": 11,
     "condition_field_key": "", "condition_value": ""},
]

RECORDING_SESSION_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Recording Services",
        "order": 1, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "SCOPE OF RECORDING SERVICES\n\n"
            "{{initiator_name}} (\"Engineer / Producer\") agrees to provide recording services "
            "to {{counterparty_name}} (\"Artist\") as follows:\n\n"
            "Service Type: {{service_type}}\n"
            "Artist / Project: {{artist_name}}\n"
            "Project Title: {{project_title}}\n"
            "Sessions: {{num_sessions}} session(s) × {{session_duration_hours}} hours each\n"
            "Studio: {{studio_location}}\n"
            "Engineer Credit on Release: {{engineer_credit}}\n\n"
            "Services include recording, engineering, and any mixing or mastering as specified "
            "by the service type above. Final deliverables will be provided in WAV format "
            "(44.1kHz / 24-bit) and, upon request, MP3 at 320kbps."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 2, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Total Project Fee: ${{rate}}\n"
            "Payment Structure: {{payment_model}}\n\n"
            "For deposit_balance: 50% deposit due upon signing; remaining balance due prior to "
            "final file delivery.\n\n"
            "For full_upfront: total fee due upon signing.\n\n"
            "For installments: {{num_installments}} installments billed every "
            "{{installment_interval_days}} days from the contract start date.\n\n"
            "Final mixed and mastered files will be delivered only after full payment is received. "
            "Studio time already used is non-refundable."
        ),
    },
    {
        "clause_type": "general",
        "title": "Studio Conduct and Session Rules",
        "order": 3, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "STUDIO CONDUCT AND SESSION RULES\n\n"
            "Artist agrees to arrive on time for all scheduled sessions. Late arrivals will "
            "result in a reduction of session time; no extension of booked time is guaranteed. "
            "Sessions missed without 48 hours notice may be forfeited without credit.\n\n"
            "Artist is responsible for the conduct of any guests brought to the studio. "
            "Engineer / Producer reserves the right to remove any disruptive individuals. "
            "No unauthorized recording of studio equipment, session content, or other artists "
            "is permitted."
        ),
    },
    {
        "clause_type": "general",
        "title": "Intellectual Property",
        "order": 4, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "INTELLECTUAL PROPERTY\n\n"
            "Artist retains full ownership of all original compositions recorded under this "
            "agreement. Engineer / Producer retains no ownership interest in Artist's "
            "underlying compositions or lyrics.\n\n"
            "For production services, any original musical contributions by Engineer / Producer "
            "to the recorded work entitle Engineer / Producer to a co-writing and co-producer "
            "credit and a negotiated share of publishing income, to be agreed separately in "
            "writing before the project begins.\n\n"
            "Engineer credit (\"Mixed/Mastered by {{initiator_name}}\") shall be included on "
            "all public releases where engineer_credit is required."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation Policy",
        "order": 5, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "CANCELLATION POLICY\n\n"
            "Deposits and advance payments are non-refundable. If Artist cancels the project "
            "after work has commenced, Artist is responsible for payment for all sessions "
            "completed to the date of cancellation.\n\n"
            "If Engineer / Producer must cancel a session due to illness or emergency, "
            "the session will be rescheduled at no additional cost within a reasonable timeframe."
        ),
    },
    {
        "clause_type": "liability",
        "title": "Limitation of Liability",
        "order": 6, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "LIMITATION OF LIABILITY\n\n"
            "Engineer / Producer's total liability shall not exceed the total fees paid. "
            "Engineer / Producer shall not be liable for data loss due to hardware failure "
            "beyond their reasonable control. Session recordings will be backed up during "
            "the project, but Artist is encouraged to maintain independent backups of any "
            "provided material. Engineer / Producer is not liable for loss of Artist-provided "
            "hard drives or equipment left at the studio."
        ),
    },
    {
        "clause_type": "general",
        "title": "Entire Agreement",
        "order": 7, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "ENTIRE AGREEMENT\n\n"
            "This agreement constitutes the entire agreement between the parties regarding "
            "recording services and supersedes all prior discussions. Amendments must be in "
            "writing and signed by both parties."
        ),
    },
]

# ------------------------------------------------------------------------------
# DJ PERFORMANCE
# ------------------------------------------------------------------------------

DJ_PERFORMANCE_GUIDED_FIELDS = [
    {"field_key": "event_type", "label": "Event Type", "field_type": "choice",
     "choices": ["Wedding", "Corporate Event", "Club Night", "Private Party", "Festival", "Other"],
     "is_required": True, "order": 1, "condition_field_key": "", "condition_value": ""},
    {"field_key": "event_date", "label": "Event Date", "field_type": "text",
     "choices": None, "is_required": True, "order": 2,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "venue_name", "label": "Venue Name and Address", "field_type": "text",
     "choices": None, "is_required": True, "order": 3,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "performance_duration_hours", "label": "Performance Duration (Hours)",
     "field_type": "number", "choices": None, "is_required": True, "order": 4,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "equipment_provided_by", "label": "Sound Equipment Provided By",
     "field_type": "choice", "choices": ["DJ", "Venue", "Client"],
     "is_required": True, "order": 5, "condition_field_key": "", "condition_value": ""},
    {"field_key": "rate", "label": "Total DJ Performance Fee (USD)", "field_type": "number",
     "choices": None, "is_required": True, "order": 6,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "payment_model", "label": "Payment Structure", "field_type": "choice",
     "choices": ["full_upfront", "deposit_balance"],
     "is_required": True, "order": 7, "condition_field_key": "", "condition_value": ""},
    {"field_key": "travel_included", "label": "Travel and Accommodation Included in Fee",
     "field_type": "boolean", "choices": None, "is_required": True, "order": 8,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "cancellation_window_days", "label": "Cancellation Notice Window (Days)",
     "field_type": "number", "choices": None, "is_required": True, "order": 9,
     "condition_field_key": "", "condition_value": ""},
]

DJ_PERFORMANCE_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of DJ Services",
        "order": 1, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "SCOPE OF DJ SERVICES\n\n"
            "{{initiator_name}} (\"DJ\") agrees to perform DJ services for "
            "{{counterparty_name}} (\"Client\") as follows:\n\n"
            "Event Type: {{event_type}}\n"
            "Event Date: {{event_date}}\n"
            "Venue: {{venue_name}}\n"
            "Performance Duration: {{performance_duration_hours}} hours\n"
            "Sound Equipment Provided By: {{equipment_provided_by}}\n"
            "Travel / Accommodation Included: {{travel_included}}\n\n"
            "DJ agrees to perform for the full contracted duration, subject to force majeure "
            "and venue constraints. DJ will consult with Client on preferred music style, "
            "must-play songs, and any do-not-play requests prior to the event."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 2, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Total Performance Fee: ${{rate}}\n"
            "Payment Structure: {{payment_model}}\n\n"
            "For deposit_balance: a non-refundable retainer of 50% is due upon signing to "
            "secure the date. The remaining balance is due no later than 7 days before the event.\n\n"
            "For full_upfront: the total fee is due upon signing.\n\n"
            "Travel and accommodation expenses are {{travel_included}}. If not included, "
            "reasonable travel expenses will be invoiced separately and must be approved by "
            "Client in advance."
        ),
    },
    {
        "clause_type": "general",
        "title": "Equipment and Setup",
        "order": 3, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "EQUIPMENT AND SETUP\n\n"
            "Sound equipment will be provided by: {{equipment_provided_by}}\n\n"
            "If provided by DJ: DJ will supply all necessary equipment in good working order "
            "and will arrive at least 90 minutes before performance start time for setup and "
            "sound check. DJ is responsible for the safety and security of their own equipment.\n\n"
            "If provided by Venue or Client: Client/venue is responsible for ensuring all "
            "necessary equipment (mixer, speakers, monitors, microphone) is available, "
            "functioning, and set up before DJ's arrival. DJ is not liable for technical "
            "failures caused by venue equipment.\n\n"
            "Client shall provide DJ with clear technical specifications and a stage plot or "
            "venue layout in advance of the event."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation Policy",
        "order": 4, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "CANCELLATION POLICY\n\n"
            "All deposits and retainers paid are non-refundable and represent compensation "
            "for date-hold opportunity costs.\n\n"
            "If Client cancels the engagement with less than {{cancellation_window_days}} days "
            "notice before the event, the full contracted fee becomes due as liquidated damages.\n\n"
            "If Client cancels with at least {{cancellation_window_days}} days notice, DJ will "
            "retain the deposit only and release Client from the remaining balance.\n\n"
            "If DJ cancels due to illness, emergency, or force majeure, DJ will make reasonable "
            "efforts to arrange a qualified replacement of similar caliber or will refund all "
            "amounts paid in full."
        ),
    },
    {
        "clause_type": "liability",
        "title": "Limitation of Liability",
        "order": 5, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "LIMITATION OF LIABILITY\n\n"
            "DJ's total liability shall not exceed the total performance fee paid. DJ shall not "
            "be liable for technical failures caused by venue equipment, power outages, or "
            "circumstances beyond DJ's reasonable control. DJ is not responsible for ensuring "
            "guests' enjoyment or satisfaction with music selections beyond the agreed consultation. "
            "Client is responsible for obtaining any required music performance licenses "
            "(e.g., PPL, PRS) for the venue."
        ),
    },
    {
        "clause_type": "general",
        "title": "Force Majeure",
        "order": 6, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "FORCE MAJEURE\n\n"
            "Neither party shall be liable for failure to perform their obligations under this "
            "agreement due to circumstances beyond their reasonable control, including but not "
            "limited to acts of God, natural disasters, pandemic-related government restrictions, "
            "venue closure, or civil unrest. In such cases, the parties will use reasonable "
            "efforts to reschedule the event or negotiate a fair resolution, which may include "
            "partial refunds or credit toward a future date."
        ),
    },
    {
        "clause_type": "general",
        "title": "Entire Agreement",
        "order": 7, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "ENTIRE AGREEMENT\n\n"
            "This agreement constitutes the entire agreement between DJ and Client regarding "
            "the performance and supersedes all prior negotiations. Amendments must be in "
            "writing and signed by both parties."
        ),
    },
]

# ------------------------------------------------------------------------------
# CONTENT COLLABORATION
# ------------------------------------------------------------------------------

CONTENT_COLLABORATION_GUIDED_FIELDS = [
    {"field_key": "platform", "label": "Platform(s)", "field_type": "choice",
     "choices": ["YouTube", "TikTok", "Instagram", "Podcast", "Blog", "Multi-Platform"],
     "is_required": True, "order": 1, "condition_field_key": "", "condition_value": ""},
    {"field_key": "content_type", "label": "Content Type", "field_type": "choice",
     "choices": ["Sponsored Post", "Brand Integration", "Product Review",
                 "Co-Creation", "Affiliate Campaign"],
     "is_required": True, "order": 2, "condition_field_key": "", "condition_value": ""},
    {"field_key": "collaboration_type", "label": "Collaboration Compensation Model",
     "field_type": "choice", "choices": ["paid", "revenue_share"],
     "is_required": True, "order": 3, "condition_field_key": "", "condition_value": ""},
    {"field_key": "rate", "label": "Flat Fee (USD) — enter 0 if revenue share only",
     "field_type": "number", "choices": None, "is_required": True, "order": 4,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "payment_model", "label": "Payment Structure", "field_type": "choice",
     "choices": ["full_upfront", "installments"], "is_required": True, "order": 5,
     "condition_field_key": "", "condition_value": ""},
] + _installment_fields_creative(6, 7) + [
    {"field_key": "revenue_share_pct", "label": "Revenue Share Percentage (%)",
     "field_type": "number", "choices": None, "is_required": True, "order": 8,
     "condition_field_key": "collaboration_type", "condition_value": "revenue_share"},
    {"field_key": "deliverables_description", "label": "Content Deliverables Description",
     "field_type": "text", "choices": None, "is_required": True, "order": 9,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "publish_deadline_days", "label": "Days to Publish from Contract Start",
     "field_type": "number", "choices": None, "is_required": True, "order": 10,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "exclusivity_window_days", "label": "Exclusivity / Non-Compete Window (Days)",
     "field_type": "number", "choices": None, "is_required": True, "order": 11,
     "condition_field_key": "", "condition_value": ""},
    {"field_key": "approval_required", "label": "Brand / Sponsor Approval Required Before Publishing",
     "field_type": "boolean", "choices": None, "is_required": True, "order": 12,
     "condition_field_key": "", "condition_value": ""},
]

CONTENT_COLLABORATION_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Content Collaboration",
        "order": 1, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "SCOPE OF CONTENT COLLABORATION\n\n"
            "{{initiator_name}} (\"Creator\") agrees to create and publish content for "
            "{{counterparty_name}} (\"Brand / Collaborator\") as follows:\n\n"
            "Platform(s): {{platform}}\n"
            "Content Type: {{content_type}}\n"
            "Compensation Model: {{collaboration_type}}\n"
            "Deliverables: {{deliverables_description}}\n"
            "Publish Deadline: {{publish_deadline_days}} days from contract start date\n"
            "Brand Approval Required: {{approval_required}}\n\n"
            "Creator shall produce, edit, and publish content meeting the agreed brief. "
            "Creator retains creative control over tone, style, and presentation, subject "
            "to Brand's reasonable approval rights as specified above."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Compensation Terms",
        "order": 2, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "COMPENSATION TERMS\n\n"
            "Compensation Model: {{collaboration_type}}\n"
            "Flat Fee: ${{rate}}\n"
            "Payment Structure: {{payment_model}}\n\n"
            "For paid collaboration — full_upfront: full fee due upon signing or prior to "
            "content delivery as agreed.\n\n"
            "For paid collaboration — installments: {{num_installments}} installments billed "
            "every {{installment_interval_days}} days from contract start.\n\n"
            "For revenue_share collaboration: Creator shall receive {{revenue_share_pct}}% of "
            "net revenue generated through tracked affiliate links, promo codes, or platform "
            "monetization attributable to the collaboration content. Revenue reports will be "
            "shared monthly. Payments will be made within 30 days of each reporting period."
        ),
    },
    {
        "clause_type": "general",
        "title": "Content Requirements and Approval",
        "order": 3, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "CONTENT REQUIREMENTS AND APPROVAL\n\n"
            "Creator agrees to produce content consistent with the agreed brief and Brand's "
            "reasonable style guidelines. Content must comply with all applicable platform "
            "policies and FTC or equivalent advertising disclosure requirements.\n\n"
            "Where brand approval is required, Creator shall submit a draft at least 5 business "
            "days before the publish deadline. Brand shall provide feedback within 3 business "
            "days. Feedback rounds are limited to two; unreasonable rejection after two rounds "
            "will not entitle Brand to withhold payment.\n\n"
            "Brand shall not require Creator to make changes that misrepresent Creator's "
            "genuine opinion, violate platform policies, or compromise the authenticity of "
            "Creator's voice."
        ),
    },
    {
        "clause_type": "general",
        "title": "Exclusivity and Non-Compete",
        "order": 4, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "EXCLUSIVITY AND NON-COMPETE\n\n"
            "For a period of {{exclusivity_window_days}} days from the content publish date, "
            "Creator agrees not to publish sponsored content for directly competing brands "
            "in the same product category on the same platform(s) without Brand's prior "
            "written consent.\n\n"
            "This exclusivity is limited to the platform(s) specified above and does not "
            "restrict Creator from posting unsponsored organic content, collaborating with "
            "brands in unrelated categories, or working with competing brands on other platforms."
        ),
    },
    {
        "clause_type": "general",
        "title": "Intellectual Property and Usage Rights",
        "order": 5, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "INTELLECTUAL PROPERTY AND USAGE RIGHTS\n\n"
            "Creator retains copyright to all content created under this agreement. "
            "Brand is granted a non-exclusive, royalty-free license to share, repost, and "
            "use the published content in Brand's own marketing channels for 12 months "
            "from the publish date, with attribution to Creator.\n\n"
            "Brand shall not modify, edit, or recontextualize the content in a way that "
            "misrepresents Creator's statements or endorsements. Expanded or extended "
            "licensing rights beyond the above require a separate written agreement."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation and Kill Fee",
        "order": 6, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "CANCELLATION AND KILL FEE\n\n"
            "If Brand cancels the collaboration after Creator has commenced work, Brand shall "
            "pay a kill fee of 50% of the agreed flat fee to compensate Creator for time and "
            "resources invested, regardless of whether content has been delivered.\n\n"
            "If Brand cancels before Creator has begun work, Brand may cancel without a kill "
            "fee provided notice is given at least 14 days before the agreed publish deadline.\n\n"
            "Revenue share arrangements may be terminated by either party with 30 days written "
            "notice without financial penalty."
        ),
    },
    {
        "clause_type": "liability",
        "title": "Limitation of Liability and Indemnification",
        "order": 7, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "LIMITATION OF LIABILITY AND INDEMNIFICATION\n\n"
            "Each party shall indemnify and hold harmless the other from third-party claims "
            "arising from their own content, statements, or materials. Creator is responsible "
            "for accuracy of their own statements; Brand is responsible for accuracy of any "
            "product claims or information provided to Creator.\n\n"
            "Neither party shall be liable for indirect, incidental, or consequential damages. "
            "Total liability of either party shall not exceed the total fees paid or payable "
            "under this agreement."
        ),
    },
    {
        "clause_type": "general",
        "title": "Entire Agreement",
        "order": 8, "is_required": True, "is_conditional": False, "condition_description": "",
        "body": (
            "ENTIRE AGREEMENT\n\n"
            "This agreement constitutes the entire agreement between Creator and Brand "
            "regarding the content collaboration and supersedes all prior discussions. "
            "Amendments must be in writing and signed by both parties."
        ),
    },
]


# ===========================================================================
# TECHNOLOGY SERVICES — WEB DEVELOPMENT
# ===========================================================================

WEB_DEVELOPMENT_GUIDED_FIELDS = [
    {
        "field_key": "project_type",
        "label": "Project Type",
        "field_type": "choice",
        "choices": ["Website", "Web Application", "E-Commerce", "Landing Page"],
        "is_required": True,
        "order": 1,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "total_fee",
        "label": "Total Project Fee (USD)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 2,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "payment_model",
        "label": "Payment Model",
        "field_type": "choice",
        "choices": ["full_upfront", "milestone", "installments"],
        "is_required": True,
        "order": 3,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "num_installments",
        "label": "Number of Installments",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 4,
        "condition_field_key": "payment_model",
        "condition_value": "installments",
    },
    {
        "field_key": "installment_interval_days",
        "label": "Installment Interval",
        "field_type": "choice",
        "choices": ["7", "30"],
        "is_required": True,
        "order": 5,
        "condition_field_key": "payment_model",
        "condition_value": "installments",
    },
    {
        "field_key": "delivery_days",
        "label": "Delivery Timeline (days)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 6,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "revision_rounds",
        "label": "Included Revision Rounds",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 7,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "ip_ownership",
        "label": "Intellectual Property Ownership",
        "field_type": "choice",
        "choices": ["Client Owns Full Rights", "Developer Retains Portfolio Rights", "Shared"],
        "is_required": True,
        "order": 8,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "source_code_delivery",
        "label": "Source Code Delivery",
        "field_type": "choice",
        "choices": ["Yes", "No"],
        "is_required": True,
        "order": 9,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "bug_warranty_days",
        "label": "Bug Warranty Period (days)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 10,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "hosting_included",
        "label": "Hosting Included",
        "field_type": "boolean",
        "choices": None,
        "is_required": False,
        "order": 11,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "cancellation_window_days",
        "label": "Cancellation Window (days)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 12,
        "condition_field_key": "",
        "condition_value": "",
    },
]

WEB_DEVELOPMENT_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Services",
        "order": 1,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Developer\") agrees to design and develop a {{project_type}} "
            "for {{counterparty_name}} (\"Client\") under the following terms:\n\n"
            "Project Type: {{project_type}}\n"
            "Delivery Timeline: {{delivery_days}} days from the agreement start date\n\n"
            "Developer shall deliver the completed project in accordance with any written "
            "requirements, wireframes, or design specifications agreed upon by the parties prior "
            "to or concurrent with the execution of this agreement. Any scope changes requested "
            "after agreement execution must be submitted in writing and may result in revised "
            "fees and timelines."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Intellectual Property and Ownership",
        "order": 2,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "INTELLECTUAL PROPERTY AND OWNERSHIP\n\n"
            "IP Ownership: {{ip_ownership}}\n\n"
            "Upon receipt of full payment, intellectual property rights in the completed "
            "deliverables are governed by the IP Ownership selection above:\n\n"
            "\"Client Owns Full Rights\" — All copyrights, source code, design assets, and "
            "derivative rights transfer exclusively to Client upon full payment. Developer "
            "retains no rights to reuse or redistribute the deliverables.\n\n"
            "\"Developer Retains Portfolio Rights\" — Client receives a perpetual, exclusive "
            "license to use the deliverables for their intended purpose. Developer may display "
            "the project in their portfolio with Client's prior written consent.\n\n"
            "\"Shared\" — Both parties retain joint ownership of the deliverables and may each "
            "use them without accounting to the other, unless otherwise specified in writing.\n\n"
            "IP rights transfer only after full payment has been received. Developer retains "
            "all rights until payment is complete."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Source Code Delivery",
        "order": 3,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SOURCE CODE DELIVERY\n\n"
            "Source Code Delivery: {{source_code_delivery}}\n\n"
            "If \"Yes\": Developer shall deliver all source files, code repositories, and build "
            "assets to Client upon completion and full payment, via an agreed version control "
            "repository or file transfer method within 5 business days of final payment.\n\n"
            "If \"No\": Developer will deliver the compiled or deployed project only. Source "
            "code, build files, and development assets remain Developer's property and will "
            "not be transferred."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Bug Warranty",
        "order": 4,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "BUG WARRANTY\n\n"
            "Warranty Period: {{bug_warranty_days}} days from project delivery\n\n"
            "Developer warrants that the delivered project will function materially as specified "
            "for {{bug_warranty_days}} days following delivery. During this period, Developer "
            "shall fix reproducible bugs arising from Developer's original work at no additional "
            "charge to Client.\n\n"
            "This warranty does not cover: modifications made by Client or third parties after "
            "delivery; incompatibilities caused by Client's hosting environment or third-party "
            "services; feature additions requested after delivery; or browser/device "
            "compatibility issues not specified in the original requirements.\n\n"
            "After the warranty period, bug fixes and support are available at Developer's "
            "then-current hourly rate."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Revision Policy",
        "order": 5,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "REVISION POLICY\n\n"
            "Included Revision Rounds: {{revision_rounds}}\n\n"
            "This agreement includes {{revision_rounds}} round(s) of revisions. A revision "
            "round is a consolidated set of feedback submitted in writing by Client. Developer "
            "will action all items within a round before the next commences. Requests that "
            "constitute new scope items will be quoted separately. Additional rounds beyond "
            "the included number are available at Developer's current hourly rate."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Independent Contractor Status",
        "order": 6,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "INDEPENDENT CONTRACTOR STATUS\n\n"
            "Developer is an independent contractor and not an employee, agent, partner, or "
            "joint venturer of Client. Developer retains sole control over the manner and "
            "means by which services are performed, subject to agreed deliverables and "
            "timelines. Developer is solely responsible for all taxes, withholding, insurance, "
            "and benefits. Developer may engage subcontractors, provided Developer remains "
            "responsible for the quality and timely delivery of all deliverables."
        ),
    },
    {
        "clause_type": "confidentiality",
        "title": "Confidentiality",
        "order": 7,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CONFIDENTIALITY\n\n"
            "Each party may receive confidential or proprietary information from the other "
            "including business strategies, technical specifications, customer data, financial "
            "information, and system credentials (\"Confidential Information\"). Each Receiving "
            "Party shall: (i) hold all Confidential Information in strict confidence; (ii) not "
            "disclose it to third parties without prior written consent; and (iii) use it "
            "solely to perform obligations under this agreement.\n\n"
            "Client data and credentials provided to Developer shall be used solely for project "
            "delivery and will not be retained or accessed after project completion."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 8,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Total Project Fee: ${{total_fee}}\n"
            "Payment Model: {{payment_model}}\n\n"
            "\"full_upfront\" — Full payment of ${{total_fee}} is due before work commences.\n\n"
            "\"milestone\" — Payment is tied to agreed project milestones. Developer will "
            "invoice at each milestone completion; invoices are due within 7 days. Developer "
            "may pause work if a milestone invoice remains unpaid for more than 14 days.\n\n"
            "\"installments\" — Payment is divided into equal installments per the agreed "
            "schedule. Each installment is due on the agreed date.\n\n"
            "Late payments may incur a fee of 5% per month on the outstanding balance. "
            "Developer reserves the right to withhold delivery until all outstanding amounts "
            "are paid in full."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation and Kill Fee",
        "order": 9,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CANCELLATION AND KILL FEE\n\n"
            "Either party may cancel this agreement with {{cancellation_window_days}} days "
            "written notice.\n\n"
            "If Client cancels after work has commenced, Client shall pay for all work "
            "completed to the cancellation date at a pro-rata rate, subject to a minimum "
            "kill fee of 25% of the total project fee.\n\n"
            "If Developer cancels without cause after work has commenced, Developer shall "
            "refund prepaid amounts less reasonable compensation for work completed to date.\n\n"
            "All completed work product remains Developer's property until the kill fee and "
            "all outstanding amounts have been paid in full."
        ),
    },
    {
        "clause_type": "termination",
        "title": "Termination",
        "order": 10,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate this agreement immediately upon written notice if the "
            "other party materially breaches any term and fails to cure within 7 days of "
            "written notice of the breach.\n\n"
            "Upon termination by Client for cause: Developer shall refund prepaid amounts "
            "less compensation for work completed to the termination date.\n\n"
            "Upon termination by Developer for cause (including non-payment): Developer may "
            "retain all payments received and suspend all deliverables until outstanding "
            "amounts are paid.\n\n"
            "Confidentiality and IP clauses survive termination."
        ),
    },
]


# ===========================================================================
# TECHNOLOGY SERVICES — MOBILE APP DEVELOPMENT
# ===========================================================================

MOBILE_DEVELOPMENT_GUIDED_FIELDS = [
    {
        "field_key": "platform",
        "label": "Target Platform",
        "field_type": "choice",
        "choices": ["iOS", "Android", "Both"],
        "is_required": True,
        "order": 1,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "total_fee",
        "label": "Total Project Fee (USD)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 2,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "payment_model",
        "label": "Payment Model",
        "field_type": "choice",
        "choices": ["full_upfront", "milestone", "installments"],
        "is_required": True,
        "order": 3,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "num_installments",
        "label": "Number of Installments",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 4,
        "condition_field_key": "payment_model",
        "condition_value": "installments",
    },
    {
        "field_key": "installment_interval_days",
        "label": "Installment Interval",
        "field_type": "choice",
        "choices": ["7", "30"],
        "is_required": True,
        "order": 5,
        "condition_field_key": "payment_model",
        "condition_value": "installments",
    },
    {
        "field_key": "delivery_days",
        "label": "Delivery Timeline (days)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 6,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "revision_rounds",
        "label": "Included Revision Rounds",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 7,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "ip_ownership",
        "label": "Intellectual Property Ownership",
        "field_type": "choice",
        "choices": ["Client Owns Full Rights", "Developer Retains Portfolio Rights"],
        "is_required": True,
        "order": 8,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "source_code_delivery",
        "label": "Source Code Delivery",
        "field_type": "choice",
        "choices": ["Yes", "No"],
        "is_required": True,
        "order": 9,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "bug_warranty_days",
        "label": "Bug Warranty Period (days)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 10,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "app_store_submission_included",
        "label": "App Store Submission Included",
        "field_type": "boolean",
        "choices": None,
        "is_required": False,
        "order": 11,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "cancellation_window_days",
        "label": "Cancellation Window (days)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 12,
        "condition_field_key": "",
        "condition_value": "",
    },
]

MOBILE_DEVELOPMENT_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Services",
        "order": 1,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Developer\") agrees to design and develop a mobile application "
            "for {{counterparty_name}} (\"Client\") under the following terms:\n\n"
            "Target Platform: {{platform}}\n"
            "Delivery Timeline: {{delivery_days}} days from the agreement start date\n\n"
            "Developer shall deliver the mobile application in accordance with any written "
            "requirements, wireframes, and design specifications agreed upon by the parties. "
            "If \"Both\" platforms are selected, Developer shall deliver functionally equivalent "
            "applications for iOS and Android. Scope changes after execution must be submitted "
            "in writing and may result in revised fees and timelines."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Intellectual Property and Ownership",
        "order": 2,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "INTELLECTUAL PROPERTY AND OWNERSHIP\n\n"
            "IP Ownership: {{ip_ownership}}\n\n"
            "Upon receipt of full payment, IP rights in the delivered application are governed "
            "by the selection above:\n\n"
            "\"Client Owns Full Rights\" — All copyrights, source code, design assets, and "
            "derivative rights transfer exclusively to Client upon full payment.\n\n"
            "\"Developer Retains Portfolio Rights\" — Client receives a perpetual, exclusive "
            "license to use the application for its intended purpose. Developer may display "
            "the project in their portfolio with Client's prior written consent.\n\n"
            "IP rights transfer only after full payment has been received."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Source Code Delivery",
        "order": 3,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SOURCE CODE DELIVERY\n\n"
            "Source Code Delivery: {{source_code_delivery}}\n\n"
            "If \"Yes\": Developer shall deliver all source files, code repositories, and build "
            "assets upon completion and full payment, within 5 business days of final payment.\n\n"
            "If \"No\": Developer will deliver the compiled application binary only. Source "
            "code, build files, and development assets remain Developer's property."
        ),
    },
    {
        "clause_type": "scope",
        "title": "App Store Submission",
        "order": 4,
        "is_required": False,
        "is_conditional": True,
        "condition_description": "Applies when app_store_submission_included is true",
        "body": (
            "APP STORE SUBMISSION\n\n"
            "App Store Submission Included: {{app_store_submission_included}}\n\n"
            "If included, Developer will prepare and submit the completed application to the "
            "Apple App Store and/or Google Play Store as applicable. Client is responsible for "
            "maintaining active developer accounts on relevant platforms and granting Developer "
            "necessary access.\n\n"
            "Developer is not responsible for delays caused by app store review processes or "
            "rejections due to platform policy violations outside Developer's control. "
            "Resubmission required due to Developer's implementation errors will be addressed "
            "at no additional charge."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Bug Warranty",
        "order": 5,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "BUG WARRANTY\n\n"
            "Warranty Period: {{bug_warranty_days}} days from project delivery\n\n"
            "Developer warrants that the delivered application will function materially as "
            "specified for {{bug_warranty_days}} days following delivery. Developer shall fix "
            "reproducible bugs arising from Developer's original work at no additional charge.\n\n"
            "This warranty does not cover: modifications made by Client or third parties after "
            "delivery; issues caused by OS updates or platform policy changes after delivery; "
            "feature additions requested after delivery; or device/OS combinations not "
            "specified in the original requirements."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Revision Policy",
        "order": 6,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "REVISION POLICY\n\n"
            "Included Revision Rounds: {{revision_rounds}}\n\n"
            "This agreement includes {{revision_rounds}} round(s) of revisions. A revision "
            "round is a consolidated set of feedback submitted in writing by Client. Developer "
            "will action all items within a round before the next commences. Additional rounds "
            "are available at Developer's current hourly rate."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Independent Contractor Status",
        "order": 7,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "INDEPENDENT CONTRACTOR STATUS\n\n"
            "Developer is an independent contractor and not an employee, agent, or joint "
            "venturer of Client. Developer retains control over the manner and means of "
            "performing services, subject to agreed deliverables and timelines. Developer is "
            "solely responsible for all taxes, insurance, and benefits. Developer may engage "
            "subcontractors provided Developer remains responsible for all deliverables."
        ),
    },
    {
        "clause_type": "confidentiality",
        "title": "Confidentiality",
        "order": 8,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CONFIDENTIALITY\n\n"
            "Each party may receive confidential information including business strategies, "
            "technical specifications, customer data, financial information, and system "
            "credentials (\"Confidential Information\"). Each Receiving Party shall hold all "
            "Confidential Information in strict confidence, not disclose it to third parties "
            "without prior written consent, and use it solely to perform obligations under "
            "this agreement. Client data and credentials provided to Developer shall be used "
            "solely for project delivery and not retained after project completion."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 9,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Total Project Fee: ${{total_fee}}\n"
            "Payment Model: {{payment_model}}\n\n"
            "\"full_upfront\" — Full payment of ${{total_fee}} is due before work commences.\n\n"
            "\"milestone\" — Payment is tied to agreed milestones. Invoices are due within "
            "7 days of each milestone completion. Developer may pause work if an invoice "
            "remains unpaid for more than 14 days.\n\n"
            "\"installments\" — Payment is divided per the agreed installment schedule.\n\n"
            "Developer reserves the right to withhold delivery until all outstanding amounts "
            "are paid. Late payments may incur a fee of 5% per month on the outstanding balance."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation and Kill Fee",
        "order": 10,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CANCELLATION AND KILL FEE\n\n"
            "Either party may cancel this agreement with {{cancellation_window_days}} days "
            "written notice.\n\n"
            "If Client cancels after work has commenced, Client shall pay for all work "
            "completed to the cancellation date at a pro-rata rate, subject to a minimum "
            "kill fee of 25% of the total project fee. All completed work product remains "
            "Developer's property until all outstanding amounts have been paid."
        ),
    },
    {
        "clause_type": "termination",
        "title": "Termination",
        "order": 11,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate this agreement immediately for material breach if "
            "the breaching party fails to cure within 7 days of written notice.\n\n"
            "Upon termination by Client for cause, Developer shall refund prepaid amounts "
            "less compensation for completed work. Upon termination by Developer for cause "
            "(including non-payment), Developer may retain all payments received and withhold "
            "deliverables until outstanding amounts are paid.\n\n"
            "Confidentiality and IP clauses survive termination."
        ),
    },
]


# ===========================================================================
# TECHNOLOGY SERVICES — IT SUPPORT AND MAINTENANCE
# ===========================================================================

IT_SUPPORT_GUIDED_FIELDS = [
    {
        "field_key": "support_type",
        "label": "Support Type",
        "field_type": "choice",
        "choices": ["Remote Only", "On-Site", "Both"],
        "is_required": True,
        "order": 1,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "response_time_hours",
        "label": "Response Time Guarantee (hours)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 2,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "monthly_fee",
        "label": "Monthly Fee (USD)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 3,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "payment_model",
        "label": "Payment Model",
        "field_type": "choice",
        "choices": ["monthly", "installments"],
        "is_required": True,
        "order": 4,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "num_months",
        "label": "Contract Duration (months)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 5,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "cancellation_notice_days",
        "label": "Cancellation Notice Period (days)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 6,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "equipment_covered",
        "label": "Client Equipment Covered",
        "field_type": "boolean",
        "choices": None,
        "is_required": False,
        "order": 7,
        "condition_field_key": "",
        "condition_value": "",
    },
]

IT_SUPPORT_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Services",
        "order": 1,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Provider\") agrees to provide IT support and maintenance "
            "services to {{counterparty_name}} (\"Client\") under the following terms:\n\n"
            "Support Type: {{support_type}}\n"
            "Response Time Guarantee: {{response_time_hours}} hours\n\n"
            "Services include general technical support, software troubleshooting, system "
            "maintenance, security updates, and network monitoring as applicable to the "
            "Support Type selected. Services are limited to systems and infrastructure "
            "specified at agreement commencement. Coverage of additional systems requires "
            "a written amendment."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Response Time Guarantee",
        "order": 2,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "RESPONSE TIME GUARANTEE\n\n"
            "Provider shall acknowledge all support requests within {{response_time_hours}} "
            "hours of receipt during normal business hours (Monday–Friday, 9:00 AM–6:00 PM "
            "local time). Response time means initial acknowledgment and triage, not "
            "resolution.\n\n"
            "For critical issues causing complete system outages, Provider shall use "
            "commercially reasonable efforts to respond outside normal business hours. "
            "Provider's response time obligation is contingent on Client providing timely "
            "access to affected systems and accurate issue descriptions.\n\n"
            "Provider is not liable for delays caused by third-party outages, force majeure "
            "events, or Client's failure to cooperate."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Independent Contractor Status",
        "order": 3,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "INDEPENDENT CONTRACTOR STATUS\n\n"
            "Provider is an independent contractor and not an employee, agent, or joint "
            "venturer of Client. Provider retains control over the manner and means of "
            "delivering support services, subject to agreed service levels. Provider is "
            "solely responsible for all taxes, insurance, and employment obligations "
            "associated with Provider's personnel."
        ),
    },
    {
        "clause_type": "confidentiality",
        "title": "Confidentiality",
        "order": 4,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CONFIDENTIALITY\n\n"
            "Provider shall treat all Client data, credentials, system configurations, and "
            "business information accessed during service delivery as strictly confidential. "
            "Provider shall not disclose such information to any third party without Client's "
            "prior written consent, except as required by law.\n\n"
            "All credentials and system access granted to Provider shall be limited to what "
            "is necessary to perform the agreed services and shall be returned or destroyed "
            "upon termination."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 5,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Monthly Fee: ${{monthly_fee}}\n"
            "Payment Model: {{payment_model}}\n\n"
            "\"monthly\" — Invoices are issued on the first day of each service month and "
            "are due within 7 days. Provider may suspend services if payment is more than "
            "14 days past due.\n\n"
            "\"installments\" — Payment is divided per the agreed installment schedule.\n\n"
            "Late payments may incur a fee of 5% per month on the outstanding balance. "
            "Provider reserves the right to suspend services for non-payment without "
            "liability for resulting downtime."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation Policy",
        "order": 6,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CANCELLATION POLICY\n\n"
            "Either party may cancel this agreement with {{cancellation_notice_days}} days "
            "written notice.\n\n"
            "Fees accrued to the effective cancellation date are payable in full. Prepaid "
            "fees for periods after cancellation will be refunded on a pro-rata basis. "
            "Cancellation does not relieve Client of outstanding payment obligations.\n\n"
            "Upon cancellation, Provider shall cease access to Client systems, return or "
            "destroy all Client credentials and data, and assist with reasonable transition "
            "activities for up to 5 business days at Provider's then-current hourly rate."
        ),
    },
    {
        "clause_type": "termination",
        "title": "Termination",
        "order": 7,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate this agreement immediately for material breach if "
            "the breaching party fails to cure within 7 days of written notice.\n\n"
            "Upon termination, Provider shall promptly cease all access to Client systems, "
            "return all Client data and credentials, and provide reasonable transition "
            "assistance. Client shall pay all fees accrued through the termination date.\n\n"
            "Confidentiality obligations survive termination."
        ),
    },
]


# ===========================================================================
# TECHNOLOGY SERVICES — SOFTWARE CONSULTING
# ===========================================================================

SOFTWARE_CONSULTING_GUIDED_FIELDS = [
    {
        "field_key": "consulting_type",
        "label": "Consulting Type",
        "field_type": "choice",
        "choices": ["Architecture Review", "Technical Advisory", "Code Review", "CTO Services"],
        "is_required": True,
        "order": 1,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "engagement_type",
        "label": "Engagement Type",
        "field_type": "choice",
        "choices": ["One-Time", "Retainer"],
        "is_required": True,
        "order": 2,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "total_fee",
        "label": "Total Fee (USD)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 3,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "payment_model",
        "label": "Payment Model",
        "field_type": "choice",
        "choices": ["full_upfront", "hourly", "monthly", "installments"],
        "is_required": True,
        "order": 4,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "num_installments",
        "label": "Number of Installments",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 5,
        "condition_field_key": "payment_model",
        "condition_value": "installments",
    },
    {
        "field_key": "installment_interval_days",
        "label": "Installment Interval",
        "field_type": "choice",
        "choices": ["7", "30"],
        "is_required": True,
        "order": 6,
        "condition_field_key": "payment_model",
        "condition_value": "installments",
    },
    {
        "field_key": "delivery_days",
        "label": "Engagement Duration (days)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 7,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "cancellation_notice_days",
        "label": "Cancellation Notice Period (days)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 8,
        "condition_field_key": "",
        "condition_value": "",
    },
]

SOFTWARE_CONSULTING_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Services",
        "order": 1,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Consultant\") agrees to provide software consulting services "
            "to {{counterparty_name}} (\"Client\") under the following terms:\n\n"
            "Consulting Type: {{consulting_type}}\n"
            "Engagement Type: {{engagement_type}}\n\n"
            "Consultant shall provide expert technical guidance, recommendations, and advisory "
            "services in the agreed consulting area. Deliverables may include written reports, "
            "architecture diagrams, code review findings, or advisory sessions as appropriate "
            "to the selected consulting type. Scope changes must be agreed in writing."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Independent Contractor Status",
        "order": 2,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "INDEPENDENT CONTRACTOR STATUS\n\n"
            "Consultant is an independent contractor and not an employee, agent, or joint "
            "venturer of Client. Consultant retains control over the manner and means of "
            "performing consulting services. Consultant is solely responsible for all taxes, "
            "insurance, and benefits. Client shall not withhold payroll taxes from payments "
            "under this agreement."
        ),
    },
    {
        "clause_type": "confidentiality",
        "title": "Confidentiality and NDA",
        "order": 3,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CONFIDENTIALITY AND NDA\n\n"
            "Consultant shall treat all Client information disclosed during this engagement — "
            "including technical architecture, source code, product roadmaps, business "
            "strategies, customer data, and financial information — as strictly confidential "
            "(\"Confidential Information\").\n\n"
            "Consultant shall: (i) not disclose Confidential Information to any third party "
            "without Client's prior written consent; (ii) use Confidential Information solely "
            "to perform obligations under this agreement; and (iii) protect it with at least "
            "reasonable care.\n\n"
            "These obligations survive termination for 3 years."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Non-Solicitation",
        "order": 4,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "NON-SOLICITATION\n\n"
            "During this agreement and for 12 months following termination, Client shall not "
            "directly or indirectly solicit, recruit, or hire any employee, contractor, or "
            "subcontractor of Consultant who was involved in performing services hereunder, "
            "without Consultant's prior written consent.\n\n"
            "Similarly, Consultant shall not solicit Client's employees or contractors to "
            "leave Client's employment during the same period.\n\n"
            "A breach of this clause entitles the non-breaching party to seek injunctive "
            "relief and liquidated damages equal to six months of the solicited person's "
            "most recent annual compensation."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 5,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Total Fee: ${{total_fee}}\n"
            "Payment Model: {{payment_model}}\n\n"
            "\"full_upfront\" — Full payment is due before the engagement commences.\n\n"
            "\"hourly\" — Consultant will invoice Client weekly based on hours worked. "
            "Invoices are due within 7 days of issuance.\n\n"
            "\"monthly\" — Consultant will invoice Client at the start of each month. "
            "Invoices are due within 7 days of issuance.\n\n"
            "\"installments\" — Payment is divided per the agreed installment schedule.\n\n"
            "Late payments may incur a fee of 5% per month on the outstanding balance. "
            "Consultant may suspend services for payments more than 14 days overdue."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation Policy",
        "order": 6,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CANCELLATION POLICY\n\n"
            "Either party may cancel this agreement with {{cancellation_notice_days}} days "
            "written notice.\n\n"
            "Upon cancellation, Client shall pay for all work completed and expenses incurred "
            "to the cancellation date. For retainer engagements, the current month's retainer "
            "fee is non-refundable. Consultant shall deliver all work product completed to "
            "the cancellation date within 5 business days."
        ),
    },
    {
        "clause_type": "termination",
        "title": "Termination",
        "order": 7,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate this agreement immediately for material breach if "
            "the breaching party fails to cure within 7 days of written notice.\n\n"
            "Upon termination, Consultant shall deliver all completed work product and "
            "Client shall pay all fees accrued through the termination date. Confidentiality, "
            "non-solicitation, and IP clauses survive termination."
        ),
    },
]


# ===========================================================================
# TECHNOLOGY SERVICES — CYBERSECURITY
# ===========================================================================

CYBERSECURITY_GUIDED_FIELDS = [
    {
        "field_key": "service_type",
        "label": "Service Type",
        "field_type": "choice",
        "choices": [
            "Security Audit",
            "Penetration Testing",
            "Vulnerability Assessment",
            "Ongoing Monitoring",
        ],
        "is_required": True,
        "order": 1,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "total_fee",
        "label": "Total Fee (USD)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 2,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "payment_model",
        "label": "Payment Model",
        "field_type": "choice",
        "choices": ["full_upfront", "milestone", "monthly"],
        "is_required": True,
        "order": 3,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "delivery_days",
        "label": "Delivery Timeline (days)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 4,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "report_included",
        "label": "Findings Report Included",
        "field_type": "boolean",
        "choices": None,
        "is_required": True,
        "order": 5,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "confidentiality_level",
        "label": "Confidentiality Level",
        "field_type": "choice",
        "choices": ["Standard", "Enhanced NDA"],
        "is_required": True,
        "order": 6,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "cancellation_notice_days",
        "label": "Cancellation Notice Period (days)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 7,
        "condition_field_key": "",
        "condition_value": "",
    },
]

CYBERSECURITY_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Services",
        "order": 1,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Consultant\") agrees to provide cybersecurity services "
            "to {{counterparty_name}} (\"Client\") under the following terms:\n\n"
            "Service Type: {{service_type}}\n"
            "Delivery Timeline: {{delivery_days}} days from the agreement start date\n\n"
            "Services are limited to the systems, networks, and applications explicitly "
            "identified by Client at the time of engagement. Testing or access beyond the "
            "agreed scope requires prior written authorization. Consultant shall document "
            "all systems accessed and activities performed throughout the engagement."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Authorization",
        "order": 2,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "AUTHORIZATION\n\n"
            "Client hereby explicitly authorizes Consultant to perform the agreed "
            "cybersecurity services — including security testing, vulnerability scanning, "
            "penetration testing, and network analysis — on the systems and infrastructure "
            "specified in the engagement scope.\n\n"
            "Client represents and warrants that: (i) Client owns or has lawful authority "
            "to authorize security testing on all in-scope systems; (ii) Client has obtained "
            "all necessary approvals from hosting providers, cloud platforms, and third-party "
            "service operators whose systems may be accessed; and (iii) Client accepts "
            "responsibility for any service disruption arising from authorized testing.\n\n"
            "This authorization is specific to the agreed scope and duration. Any expansion "
            "requires separate written authorization from Client."
        ),
    },
    {
        "clause_type": "confidentiality",
        "title": "Confidentiality and NDA",
        "order": 3,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CONFIDENTIALITY AND NDA\n\n"
            "Confidentiality Level: {{confidentiality_level}}\n\n"
            "All findings, vulnerability details, system information, credentials, and "
            "security weaknesses discovered during this engagement are strictly confidential. "
            "Consultant shall: not disclose findings to any third party without Client's "
            "prior written consent; store all findings and client data in encrypted form; "
            "destroy or return all Client credentials and sensitive data upon completion; "
            "and not use findings to access Client systems after the engagement.\n\n"
            "If \"Enhanced NDA\" is selected, Consultant shall execute a separate "
            "non-disclosure agreement incorporating Client's standard NDA terms before "
            "commencing work.\n\n"
            "These obligations survive termination indefinitely with respect to all "
            "security findings and system information."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Report Delivery",
        "order": 4,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "REPORT DELIVERY\n\n"
            "Findings Report Included: {{report_included}}\n\n"
            "If a findings report is included, Consultant shall deliver a written report "
            "documenting all vulnerabilities identified, their severity classification "
            "(Critical / High / Medium / Low / Informational), evidence of findings, and "
            "recommended remediation steps, within the agreed timeline following testing.\n\n"
            "The report is classified as Confidential Information and is for Client's "
            "internal use only. Client shall not distribute it to third parties without "
            "Consultant's prior written consent."
        ),
    },
    {
        "clause_type": "risk",
        "title": "Limitation of Liability",
        "order": 5,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "LIMITATION OF LIABILITY\n\n"
            "Consultant's liability under this agreement is limited to the total fees paid "
            "by Client for the engagement in which the liability arises.\n\n"
            "Consultant shall not be liable for: vulnerabilities existing prior to this "
            "engagement; breaches caused by third parties after findings are reported; "
            "service disruptions from authorized testing within scope; indirect or "
            "consequential damages arising from findings or recommendations; or Client's "
            "failure to implement recommended remediation steps.\n\n"
            "Client acknowledges that no security assessment is exhaustive and that "
            "Consultant's findings represent a point-in-time evaluation."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Independent Contractor Status",
        "order": 6,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "INDEPENDENT CONTRACTOR STATUS\n\n"
            "Consultant is an independent contractor and not an employee, agent, or joint "
            "venturer of Client. Consultant retains control over the methods and processes "
            "used to perform cybersecurity services, subject to the agreed scope. Consultant "
            "is solely responsible for all taxes, insurance, and employment obligations "
            "associated with Consultant's personnel."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 7,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Total Fee: ${{total_fee}}\n"
            "Payment Model: {{payment_model}}\n\n"
            "\"full_upfront\" — Full payment is due before work commences.\n\n"
            "\"milestone\" — Payment is tied to agreed engagement milestones. Invoices are "
            "due within 7 days of each milestone completion.\n\n"
            "\"monthly\" — Invoices are issued at the start of each service month and are "
            "due within 7 days. Consultant may suspend services for non-payment.\n\n"
            "Late payments may incur a fee of 5% per month on the outstanding balance."
        ),
    },
    {
        "clause_type": "termination",
        "title": "Termination",
        "order": 8,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate this agreement immediately for material breach if "
            "the breaching party fails to cure within 7 days of written notice.\n\n"
            "Upon termination, Consultant shall immediately cease all access to Client "
            "systems and deliver a summary of work completed to date. Client shall pay "
            "all fees accrued through the termination date.\n\n"
            "Confidentiality and authorization obligations survive termination."
        ),
    },
]


# ===========================================================================
# TECHNOLOGY SERVICES — DATA AND ANALYTICS
# ===========================================================================

DATA_ANALYTICS_GUIDED_FIELDS = [
    {
        "field_key": "service_type",
        "label": "Service Type",
        "field_type": "choice",
        "choices": ["Data Analysis", "Dashboard Build", "Reporting", "Data Strategy"],
        "is_required": True,
        "order": 1,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "total_fee",
        "label": "Total Fee (USD)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 2,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "payment_model",
        "label": "Payment Model",
        "field_type": "choice",
        "choices": ["full_upfront", "milestone", "installments"],
        "is_required": True,
        "order": 3,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "num_installments",
        "label": "Number of Installments",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 4,
        "condition_field_key": "payment_model",
        "condition_value": "installments",
    },
    {
        "field_key": "installment_interval_days",
        "label": "Installment Interval",
        "field_type": "choice",
        "choices": ["7", "30"],
        "is_required": True,
        "order": 5,
        "condition_field_key": "payment_model",
        "condition_value": "installments",
    },
    {
        "field_key": "delivery_days",
        "label": "Delivery Timeline (days)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 6,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "data_ownership",
        "label": "Data Ownership",
        "field_type": "choice",
        "choices": ["Client Owns All Data", "Analyst May Use Anonymized Data"],
        "is_required": True,
        "order": 7,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "revision_rounds",
        "label": "Included Revision Rounds",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 8,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "cancellation_notice_days",
        "label": "Cancellation Notice Period (days)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 9,
        "condition_field_key": "",
        "condition_value": "",
    },
]

DATA_ANALYTICS_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Services",
        "order": 1,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Analyst\") agrees to provide data and analytics services "
            "to {{counterparty_name}} (\"Client\") under the following terms:\n\n"
            "Service Type: {{service_type}}\n"
            "Delivery Timeline: {{delivery_days}} days from the agreement start date\n\n"
            "Analyst shall perform the agreed analytics work using data provided by Client. "
            "Deliverables may include analytical reports, interactive dashboards, data models, "
            "or strategic recommendations appropriate to the selected service type. Scope "
            "changes must be submitted in writing and may affect timelines and fees."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Data Ownership and Privacy",
        "order": 2,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "DATA OWNERSHIP AND PRIVACY\n\n"
            "Data Ownership: {{data_ownership}}\n\n"
            "All data provided by Client remains the sole property of Client at all times. "
            "Analyst shall use Client data exclusively to deliver services under this "
            "agreement and shall not share, sell, license, or transfer Client data to any "
            "third party without prior written consent.\n\n"
            "\"Client Owns All Data\" — Analyst shall not retain, copy, or use any Client "
            "data or derived datasets after project completion. All data will be returned or "
            "securely destroyed within 14 days of final delivery.\n\n"
            "\"Analyst May Use Anonymized Data\" — Analyst may retain and use anonymized, "
            "aggregated insights derived from Client data to improve models and methodologies, "
            "provided no Client-identifiable information is retained or disclosed.\n\n"
            "Analyst shall implement reasonable safeguards to protect Client data from "
            "unauthorized access, loss, or disclosure."
        ),
    },
    {
        "clause_type": "confidentiality",
        "title": "Confidentiality",
        "order": 3,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CONFIDENTIALITY\n\n"
            "Analyst shall treat all Client data, business information, strategic plans, "
            "financial records, and technical specifications accessed during this engagement "
            "as strictly confidential. Analyst shall not disclose such information to any "
            "third party without Client's prior written consent.\n\n"
            "Analyst shall protect Confidential Information with at least reasonable care "
            "and shall limit access to personnel who need it to deliver services. These "
            "obligations survive termination."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Revision Policy",
        "order": 4,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "REVISION POLICY\n\n"
            "Included Revision Rounds: {{revision_rounds}}\n\n"
            "This agreement includes {{revision_rounds}} round(s) of revisions. A revision "
            "round is a consolidated set of feedback submitted by Client in writing. Analyst "
            "will action all items within a round before the next commences. Requests that "
            "constitute new scope items will be quoted separately. Additional rounds are "
            "available at Analyst's current hourly rate."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Independent Contractor Status",
        "order": 5,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "INDEPENDENT CONTRACTOR STATUS\n\n"
            "Analyst is an independent contractor and not an employee, agent, or joint "
            "venturer of Client. Analyst retains control over the analytical methods and "
            "tools used to deliver services, subject to agreed deliverables and timelines. "
            "Analyst is solely responsible for all taxes, insurance, and benefits."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 6,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Total Fee: ${{total_fee}}\n"
            "Payment Model: {{payment_model}}\n\n"
            "\"full_upfront\" — Full payment is due before work commences.\n\n"
            "\"milestone\" — Payment is tied to agreed project milestones. Invoices are due "
            "within 7 days of each milestone completion.\n\n"
            "\"installments\" — Payment is divided per the agreed installment schedule.\n\n"
            "Late payments may incur a fee of 5% per month on the outstanding balance. "
            "Analyst reserves the right to withhold final deliverables until all outstanding "
            "amounts are paid."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation Policy",
        "order": 7,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CANCELLATION POLICY\n\n"
            "Either party may cancel this agreement with {{cancellation_notice_days}} days "
            "written notice.\n\n"
            "Upon cancellation, Client shall pay for all work completed to date at a pro-rata "
            "rate. Analyst shall deliver all completed work product within 5 business days. "
            "All Client data will be returned or destroyed within 14 days of cancellation."
        ),
    },
    {
        "clause_type": "termination",
        "title": "Termination",
        "order": 8,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate this agreement immediately for material breach if "
            "the breaching party fails to cure within 7 days of written notice.\n\n"
            "Upon termination, Analyst shall deliver all completed work product and destroy "
            "or return all Client data. Client shall pay all fees accrued through the "
            "termination date. Confidentiality and data ownership obligations survive "
            "termination."
        ),
    },
]


# ===========================================================================
# MANUAL LABOR — LAWN CARE AND LANDSCAPING
# ===========================================================================

LAWN_CARE_GUIDED_FIELDS = [
    {
        "field_key": "service_type",
        "label": "Service Type",
        "field_type": "choice",
        "choices": ["Lawn Mowing", "Landscaping Design", "Planting and Mulching", "Yard Cleanup", "Full Service"],
        "is_required": True,
        "order": 1,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "property_address",
        "label": "Property Address",
        "field_type": "text",
        "choices": None,
        "is_required": True,
        "order": 2,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "service_frequency",
        "label": "Service Frequency",
        "field_type": "choice",
        "choices": ["One-Time", "Weekly", "Bi-Weekly", "Monthly"],
        "is_required": True,
        "order": 3,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "total_fee",
        "label": "Service Rate (USD)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 4,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "payment_model",
        "label": "Payment Model",
        "field_type": "choice",
        "choices": ["per_visit", "monthly_prepay", "flat_fee"],
        "is_required": True,
        "order": 5,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "materials_included",
        "label": "Materials Included in Price",
        "field_type": "boolean",
        "choices": None,
        "is_required": True,
        "order": 6,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "equipment_provided_by",
        "label": "Equipment Provided By",
        "field_type": "choice",
        "choices": ["Provider", "Client"],
        "is_required": True,
        "order": 7,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "cancellation_notice_days",
        "label": "Cancellation Notice Period (days)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 8,
        "condition_field_key": "",
        "condition_value": "",
    },
]

LAWN_CARE_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Services",
        "order": 1,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Provider\") agrees to provide lawn care and landscaping "
            "services for {{counterparty_name}} (\"Client\") at the following property:\n\n"
            "Property Address: {{property_address}}\n"
            "Service Type: {{service_type}}\n"
            "Service Frequency: {{service_frequency}}\n\n"
            "Provider shall perform all services in a professional and workmanlike manner "
            "consistent with industry standards. Services are limited to the type and "
            "frequency described above and do not include tree removal, irrigation "
            "installation, major grading, or retaining wall construction unless separately "
            "agreed in writing."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Equipment and Materials",
        "order": 2,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "EQUIPMENT AND MATERIALS\n\n"
            "Equipment Provided By: {{equipment_provided_by}}\n"
            "Materials Included in Price: {{materials_included}}\n\n"
            "If equipment is provided by Provider, Provider shall maintain all equipment in "
            "safe and functional operating condition and is solely responsible for its "
            "maintenance, repair, and insurance. If equipment is provided by Client, Client "
            "shall ensure all equipment is in safe and working condition before each visit; "
            "Provider is not liable for damage caused by defective Client-supplied equipment.\n\n"
            "If materials are included in price, Provider shall supply all consumables "
            "required — including fertilizers, mulch, soil amendments, and similar materials. "
            "If not included, Client shall supply required materials or reimburse Provider "
            "at cost for materials purchased on Client's behalf."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Change Order",
        "order": 3,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CHANGE ORDER\n\n"
            "Any request to expand or modify the scope of services beyond what is described "
            "in this agreement must be submitted as a written change order and approved by "
            "both parties before work on the additional scope commences. Change orders "
            "increasing scope will be priced at Provider's then-current rates. Provider is "
            "not obligated to perform additional work without a signed change order."
        ),
    },
    {
        "clause_type": "risk",
        "title": "Damage Liability",
        "order": 4,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "DAMAGE LIABILITY\n\n"
            "Provider shall exercise reasonable care and shall be liable for damage to "
            "Client's property directly caused by Provider's negligence or willful misconduct. "
            "Client must notify Provider in writing of any property damage within 48 hours of "
            "the service visit in which it occurred. Claims submitted after this window may "
            "be denied.\n\n"
            "Provider is not liable for: pre-existing property conditions; damage caused by "
            "underground irrigation lines, cables, or utilities not marked or disclosed by "
            "Client prior to service; lawn or plant damage from weather, disease, or pest "
            "infestation; or damage arising from Client's failure to disclose known hazards."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 5,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Service Rate: ${{total_fee}}\n"
            "Payment Model: {{payment_model}}\n\n"
            "\"per_visit\" — Client is invoiced after each completed service visit; payment "
            "due within 7 days of invoice.\n\n"
            "\"monthly_prepay\" — Client pays the monthly rate in advance on the first day "
            "of each service month. Provider may suspend services for non-payment.\n\n"
            "\"flat_fee\" — Full payment is due prior to commencement of the agreed scope.\n\n"
            "Late payments may incur a fee of 5% per month on the outstanding balance."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation Policy",
        "order": 6,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CANCELLATION POLICY\n\n"
            "Either party may cancel this agreement with {{cancellation_notice_days}} days "
            "written notice. Fees accrued through the last completed service visit are "
            "payable in full. Prepaid amounts for periods after the cancellation date will "
            "be refunded on a pro-rata basis.\n\n"
            "Client cancellations of individual scheduled visits with less than 24 hours "
            "notice may be charged at 50% of the per-visit rate to compensate Provider for "
            "reserved labor time."
        ),
    },
    {
        "clause_type": "termination",
        "title": "Termination",
        "order": 7,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate this agreement immediately for material breach if "
            "the breaching party fails to cure within 7 days of written notice. Upon "
            "termination, Client shall pay all fees accrued through the last completed "
            "service visit. Provider shall promptly remove all Provider-owned equipment "
            "and materials from the property."
        ),
    },
]


# ===========================================================================
# MANUAL LABOR — HOME CLEANING SERVICE
# ===========================================================================

HOME_CLEANING_GUIDED_FIELDS = [
    {
        "field_key": "cleaning_type",
        "label": "Cleaning Type",
        "field_type": "choice",
        "choices": ["Standard Clean", "Deep Clean", "Move-In/Move-Out", "Post-Construction"],
        "is_required": True,
        "order": 1,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "property_address",
        "label": "Property Address",
        "field_type": "text",
        "choices": None,
        "is_required": True,
        "order": 2,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "property_size",
        "label": "Property Size (e.g. 3BR/2BA or sq ft)",
        "field_type": "text",
        "choices": None,
        "is_required": True,
        "order": 3,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "service_frequency",
        "label": "Service Frequency",
        "field_type": "choice",
        "choices": ["One-Time", "Weekly", "Bi-Weekly", "Monthly"],
        "is_required": True,
        "order": 4,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "rate_per_visit",
        "label": "Rate Per Visit (USD)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 5,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "payment_model",
        "label": "Payment Model",
        "field_type": "choice",
        "choices": ["per_visit", "monthly_prepay"],
        "is_required": True,
        "order": 6,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "supplies_included",
        "label": "Cleaning Supplies Included",
        "field_type": "boolean",
        "choices": None,
        "is_required": True,
        "order": 7,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "key_access",
        "label": "Client Provides Key or Access Code",
        "field_type": "boolean",
        "choices": None,
        "is_required": False,
        "order": 8,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "cancellation_notice_hours",
        "label": "Cancellation Notice Window (hours)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 9,
        "condition_field_key": "",
        "condition_value": "",
    },
]

HOME_CLEANING_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Services",
        "order": 1,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Provider\") agrees to provide home cleaning services "
            "for {{counterparty_name}} (\"Client\") at the following property:\n\n"
            "Property Address: {{property_address}}\n"
            "Property Size: {{property_size}}\n"
            "Cleaning Type: {{cleaning_type}}\n"
            "Service Frequency: {{service_frequency}}\n\n"
            "Provider shall clean the agreed areas of the property in a thorough and "
            "professional manner. Standard clean includes dusting, vacuuming, mopping, "
            "bathroom sanitation, and kitchen surface wipe-down. Deep clean and "
            "move-in/move-out services include additional tasks such as inside-appliance "
            "cleaning, cabinet interiors, and window sill detail. Post-construction clean "
            "includes removal of construction debris and dust. Specific task lists may be "
            "attached as an addendum."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Supplies and Equipment",
        "order": 2,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SUPPLIES AND EQUIPMENT\n\n"
            "Cleaning Supplies Included: {{supplies_included}}\n\n"
            "If cleaning supplies are included, Provider shall bring all required cleaning "
            "products, mops, vacuums, and equipment to each visit at no additional charge "
            "to Client. Provider shall use commercially appropriate cleaning products "
            "safe for residential use. If Client has specific product preferences or "
            "allergies, Client must disclose these in writing before the first visit.\n\n"
            "If cleaning supplies are not included, Client shall ensure all required "
            "cleaning products and equipment are available and accessible at the property "
            "before each scheduled visit."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Access and Security",
        "order": 3,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "ACCESS AND SECURITY\n\n"
            "Key or Access Code Provided: {{key_access}}\n\n"
            "If Client provides a key or access code, Provider shall keep all access "
            "credentials strictly confidential, shall not duplicate keys without written "
            "consent, and shall return all keys and credentials upon termination of this "
            "agreement. Access will be used solely for the purpose of performing scheduled "
            "cleaning services.\n\n"
            "Provider shall lock and secure the property upon departure after each visit. "
            "Provider shall not allow any unauthorized persons onto the property and shall "
            "not disclose Client's address, access codes, or security information to "
            "any third party."
        ),
    },
    {
        "clause_type": "risk",
        "title": "Damage Liability",
        "order": 4,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "DAMAGE LIABILITY\n\n"
            "Provider shall exercise reasonable care and shall be liable for breakage or "
            "damage to Client's property caused by Provider's negligence during cleaning. "
            "Client must notify Provider of any damage claim in writing within 24 hours "
            "of the service visit. Claims submitted after this window may be denied.\n\n"
            "Provider is not liable for: pre-existing damage or wear; damage to items "
            "improperly secured, displayed, or left in high-risk locations; damage to items "
            "not disclosed as fragile or valuable prior to service; or damage to electronic "
            "equipment, artwork, or antiques unless Provider is expressly directed to clean "
            "those items and the Client has disclosed their value."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 5,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Rate Per Visit: ${{rate_per_visit}}\n"
            "Payment Model: {{payment_model}}\n\n"
            "\"per_visit\" — Client is invoiced after each completed cleaning visit; "
            "payment due within 7 days of invoice.\n\n"
            "\"monthly_prepay\" — Client pays the monthly rate in advance on the first "
            "day of each service month covering all scheduled visits that month. Provider "
            "may suspend services for non-payment.\n\n"
            "Late payments may incur a fee of 5% per month on the outstanding balance."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation Policy",
        "order": 6,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CANCELLATION POLICY\n\n"
            "Client must provide at least {{cancellation_notice_hours}} hours notice to "
            "cancel or reschedule a scheduled cleaning visit. Cancellations with less than "
            "{{cancellation_notice_hours}} hours notice may be charged at 50% of the "
            "per-visit rate to compensate Provider for reserved labor time that cannot "
            "be reassigned on short notice.\n\n"
            "Either party may cancel the ongoing service agreement with 14 days written "
            "notice. Prepaid amounts for visits after the cancellation date will be "
            "refunded on a pro-rata basis."
        ),
    },
    {
        "clause_type": "termination",
        "title": "Termination",
        "order": 7,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate this agreement immediately for material breach "
            "if the breaching party fails to cure within 7 days of written notice. Upon "
            "termination, Provider shall return all keys and access codes to Client within "
            "2 business days. Client shall pay all fees accrued through the last completed "
            "visit. Confidentiality and access security obligations survive termination."
        ),
    },
]


# ===========================================================================
# MANUAL LABOR — HOME RENOVATION AND REMODELING
# ===========================================================================

HOME_RENOVATION_GUIDED_FIELDS = [
    {
        "field_key": "project_type",
        "label": "Project Type",
        "field_type": "choice",
        "choices": [
            "Kitchen Remodel",
            "Bathroom Remodel",
            "Basement Finish",
            "Room Addition",
            "Full Home Renovation",
        ],
        "is_required": True,
        "order": 1,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "property_address",
        "label": "Property Address",
        "field_type": "text",
        "choices": None,
        "is_required": True,
        "order": 2,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "total_contract_value",
        "label": "Total Contract Value (USD)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 3,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "payment_model",
        "label": "Payment Model",
        "field_type": "choice",
        "choices": ["deposit_balance", "milestone", "installments"],
        "is_required": True,
        "order": 4,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "deposit_percentage",
        "label": "Deposit Percentage (%)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 5,
        "condition_field_key": "payment_model",
        "condition_value": "deposit_balance",
    },
    {
        "field_key": "num_installments",
        "label": "Number of Installments",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 6,
        "condition_field_key": "payment_model",
        "condition_value": "installments",
    },
    {
        "field_key": "installment_interval_days",
        "label": "Installment Interval",
        "field_type": "choice",
        "choices": ["7", "30"],
        "is_required": True,
        "order": 7,
        "condition_field_key": "payment_model",
        "condition_value": "installments",
    },
    {
        "field_key": "estimated_duration_days",
        "label": "Estimated Project Duration (days)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 8,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "materials_included",
        "label": "Materials",
        "field_type": "choice",
        "choices": ["Included in Price", "Client Provides", "Partial — Labor Only"],
        "is_required": True,
        "order": 9,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "permit_responsibility",
        "label": "Permit Responsibility",
        "field_type": "choice",
        "choices": ["Contractor", "Client"],
        "is_required": True,
        "order": 10,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "warranty_days",
        "label": "Workmanship Warranty Period (days)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 11,
        "condition_field_key": "",
        "condition_value": "",
    },
]

HOME_RENOVATION_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Services",
        "order": 1,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Contractor\") agrees to perform home renovation and "
            "remodeling services for {{counterparty_name}} (\"Client\") at the following "
            "property:\n\n"
            "Property Address: {{property_address}}\n"
            "Project Type: {{project_type}}\n"
            "Estimated Duration: {{estimated_duration_days}} days\n\n"
            "Contractor shall perform all work in a professional and workmanlike manner "
            "in compliance with all applicable building codes and regulations. The detailed "
            "scope of work, specifications, and plans are set forth in the project proposal "
            "or addendum attached hereto. Any work beyond the agreed scope requires a "
            "written change order executed by both parties before work proceeds."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Materials and Labor Breakdown",
        "order": 2,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "MATERIALS AND LABOR BREAKDOWN\n\n"
            "Materials: {{materials_included}}\n\n"
            "\"Included in Price\" — All materials, fixtures, hardware, and supplies "
            "required to complete the agreed scope are included in the contract value. "
            "Contractor shall select materials of commercially appropriate quality unless "
            "specific selections are specified in writing.\n\n"
            "\"Client Provides\" — The contract price covers labor only. Client shall "
            "procure and deliver all materials on schedule. Contractor is not liable for "
            "delays caused by Client's failure to supply materials on time. Client-supplied "
            "materials are accepted as-is.\n\n"
            "\"Partial — Labor Only\" — The parties shall specify in writing which materials "
            "each party provides. Material cost overruns require a written change order "
            "and Client approval before additional expenditure is incurred."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Permits and Compliance",
        "order": 3,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PERMITS AND COMPLIANCE\n\n"
            "Permit Responsibility: {{permit_responsibility}}\n\n"
            "All renovation work shall be performed in compliance with applicable local, "
            "state, and federal building codes and regulations. The party designated above "
            "is responsible for obtaining all required building permits and paying all "
            "associated permit fees prior to commencement of regulated work.\n\n"
            "Contractor represents that all tradespeople performing licensed work (electrical, "
            "plumbing, HVAC) hold the required licenses for the jurisdiction. Client shall "
            "provide reasonable access to the property for inspections required by permitting "
            "authorities. Project delays caused by permit processing are not a breach of "
            "this agreement."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Change Order",
        "order": 4,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CHANGE ORDER\n\n"
            "All scope changes — including additions, deletions, substitutions, or "
            "modifications to the work described in this agreement — require a written "
            "change order signed by both parties before work on the changed scope proceeds. "
            "Each change order shall specify the nature of the change, the adjusted contract "
            "price, and any impact on the project timeline.\n\n"
            "Contractor may stop work on affected portions of the project pending change "
            "order execution. Verbal agreements to change the scope are not binding. Client "
            "acknowledges that change orders may increase both cost and project duration."
        ),
    },
    {
        "clause_type": "risk",
        "title": "Damage Liability",
        "order": 5,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "DAMAGE LIABILITY\n\n"
            "Contractor shall exercise reasonable care and shall be liable for damage to "
            "Client's property caused by Contractor's negligence or willful misconduct "
            "during renovation work. Contractor carries general liability insurance and "
            "shall provide evidence of coverage upon request.\n\n"
            "Contractor is not liable for pre-existing structural deficiencies, concealed "
            "damage discovered during demolition, or conditions not visible or disclosed "
            "prior to work commencement. Discovery of hidden defects (e.g., mold, "
            "asbestos, faulty wiring) shall be documented, communicated to Client "
            "immediately, and addressed via change order."
        ),
    },
    {
        "clause_type": "general",
        "title": "Workmanship Warranty",
        "order": 6,
        "is_required": False,
        "is_conditional": True,
        "condition_description": "Applies when warranty_days is provided",
        "body": (
            "WORKMANSHIP WARRANTY\n\n"
            "Contractor warrants all work performed under this agreement against defects "
            "in workmanship for {{warranty_days}} days from the date of substantial "
            "completion. During this period, Contractor shall correct defects caused by "
            "poor construction technique or materials failure attributable to Contractor, "
            "at no additional charge.\n\n"
            "This warranty does not cover normal wear and tear, damage caused by Client "
            "modifications, misuse, or neglect, defects in Client-supplied materials, or "
            "damage from events outside Contractor's control. Manufacturer warranties on "
            "installed products are separate and governed by the manufacturer's terms."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 7,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Total Contract Value: ${{total_contract_value}}\n"
            "Payment Model: {{payment_model}}\n\n"
            "\"deposit_balance\" — A deposit of {{deposit_percentage}}% is due upon "
            "execution of this agreement. The remaining balance is due upon substantial "
            "completion and Client acceptance.\n\n"
            "\"milestone\" — Payments are tied to agreed project milestones per the "
            "attached milestone schedule. Each milestone payment is due within 7 days "
            "of milestone completion. Contractor may pause work if a milestone payment "
            "is more than 14 days overdue.\n\n"
            "\"installments\" — Payments are made per the agreed installment schedule. "
            "Each installment is due on the agreed date. Contractor may suspend work "
            "for non-payment. Late payments accrue interest at 5% per month."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation Policy",
        "order": 8,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CANCELLATION POLICY\n\n"
            "If Client cancels this agreement after work has commenced, Client shall pay "
            "Contractor for all work completed and materials procured to the cancellation "
            "date at a pro-rata rate, plus 20% of the remaining contract value as a "
            "cancellation fee to compensate Contractor for lost revenue and reserved "
            "labor capacity.\n\n"
            "If Contractor cancels without cause after work has commenced, Contractor "
            "shall refund all prepaid amounts less reasonable compensation for work "
            "completed and materials procured. Cancellations must be submitted in writing."
        ),
    },
    {
        "clause_type": "termination",
        "title": "Termination",
        "order": 9,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate this agreement for material breach if the "
            "breaching party fails to cure within 7 days of written notice. Client may "
            "terminate for persistent failure to meet quality standards or to progress "
            "the work within a reasonable extension of the agreed timeline. Contractor "
            "may terminate for non-payment or unsafe working conditions.\n\n"
            "Upon termination, Client shall pay for all work satisfactorily completed "
            "and materials procured through the termination date. Warranty, permit, and "
            "liability obligations survive termination."
        ),
    },
]


# ===========================================================================
# MANUAL LABOR — PLUMBING
# ===========================================================================

PLUMBING_GUIDED_FIELDS = [
    {
        "field_key": "service_type",
        "label": "Service Type",
        "field_type": "choice",
        "choices": ["Repair", "Installation", "Pipe Replacement", "Drain Cleaning", "Emergency Service"],
        "is_required": True,
        "order": 1,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "property_address",
        "label": "Property Address",
        "field_type": "text",
        "choices": None,
        "is_required": True,
        "order": 2,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "total_fee",
        "label": "Total Fee (USD)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 3,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "payment_model",
        "label": "Payment Model",
        "field_type": "choice",
        "choices": ["flat_fee", "deposit_balance", "hourly"],
        "is_required": True,
        "order": 4,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "deposit_percentage",
        "label": "Deposit Percentage (%)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 5,
        "condition_field_key": "payment_model",
        "condition_value": "deposit_balance",
    },
    {
        "field_key": "materials_included",
        "label": "Materials and Parts Included",
        "field_type": "boolean",
        "choices": None,
        "is_required": True,
        "order": 6,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "permit_responsibility",
        "label": "Permit Responsibility",
        "field_type": "choice",
        "choices": ["Contractor", "Client", "Not Required"],
        "is_required": True,
        "order": 7,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "warranty_days",
        "label": "Workmanship Warranty Period (days)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 8,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "cancellation_notice_hours",
        "label": "Cancellation Notice Window (hours)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 9,
        "condition_field_key": "",
        "condition_value": "",
    },
]

PLUMBING_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Services",
        "order": 1,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Contractor\") agrees to perform plumbing services "
            "for {{counterparty_name}} (\"Client\") at the following property:\n\n"
            "Property Address: {{property_address}}\n"
            "Service Type: {{service_type}}\n\n"
            "All plumbing work shall be performed in a professional and workmanlike manner "
            "in compliance with applicable plumbing codes and local regulations. Contractor "
            "shall assess the work site before commencing to confirm scope and identify "
            "conditions that may affect cost or timeline. Work beyond the agreed scope "
            "requires a written change order before proceeding."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Licensing and Permits",
        "order": 2,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "LICENSING AND PERMITS\n\n"
            "Permit Responsibility: {{permit_responsibility}}\n\n"
            "Contractor represents that all personnel performing plumbing work under this "
            "agreement hold the required plumbing licenses for the applicable jurisdiction. "
            "All work shall be performed to applicable plumbing code standards.\n\n"
            "The party designated above is responsible for obtaining all required plumbing "
            "permits and paying associated fees prior to commencement of permitted work. "
            "If permit responsibility is \"Not Required\", both parties acknowledge that "
            "the work type does not require a permit under applicable local regulations. "
            "Delays caused by permit processing are not a breach of this agreement."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Materials and Parts",
        "order": 3,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "MATERIALS AND PARTS\n\n"
            "Materials and Parts Included: {{materials_included}}\n\n"
            "If materials are included, all required replacement parts, pipe fittings, "
            "fixtures, sealants, and supplies are covered in the agreed fee. Contractor "
            "shall use materials of commercially appropriate grade and quality.\n\n"
            "If materials are not included, Client shall be invoiced separately for all "
            "materials at cost plus a reasonable handling markup, with itemized invoices "
            "provided. Contractor shall obtain Client approval before purchasing parts "
            "above a pre-agreed threshold. Client-supplied parts are accepted as-is; "
            "Contractor is not liable for defects or failure of Client-supplied components."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Change Order",
        "order": 4,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CHANGE ORDER\n\n"
            "If additional work is discovered during service — including hidden pipe "
            "damage, concealed leaks, or adjacent components requiring replacement — "
            "Contractor shall stop work on the affected area and issue a written change "
            "order before proceeding. The change order shall describe the additional work, "
            "its estimated cost, and any timeline impact. Contractor is not liable for "
            "incomplete results in areas where necessary additional work was declined."
        ),
    },
    {
        "clause_type": "risk",
        "title": "Damage Liability",
        "order": 5,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "DAMAGE LIABILITY\n\n"
            "Contractor shall be liable for damage to Client's property caused by "
            "Contractor's negligence or improper workmanship. Client must report any "
            "damage claim in writing within 48 hours of service.\n\n"
            "Contractor is not liable for: pre-existing pipe corrosion, scale buildup, "
            "or deterioration; damage to concealed components not visible before work "
            "commenced; water damage from pre-existing leaks in adjacent systems; or "
            "Client's failure to disclose known plumbing issues. Contractor's liability "
            "is capped at the total fees paid under this agreement except in cases of "
            "gross negligence."
        ),
    },
    {
        "clause_type": "general",
        "title": "Workmanship Warranty",
        "order": 6,
        "is_required": False,
        "is_conditional": True,
        "condition_description": "Applies when warranty_days is provided",
        "body": (
            "WORKMANSHIP WARRANTY\n\n"
            "Contractor warrants all work performed under this agreement against defects "
            "in workmanship for {{warranty_days}} days from the service completion date. "
            "During this period Contractor shall correct any plumbing defect attributable "
            "to Contractor's work — including leaks at connections made by Contractor "
            "or installation failures — at no additional charge.\n\n"
            "This warranty does not cover: Client-supplied parts; damage from pipe "
            "corrosion or scale unrelated to Contractor's work; normal wear on seals "
            "and washers; or damage caused by Client modifications after service."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 7,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Total Fee: ${{total_fee}}\n"
            "Payment Model: {{payment_model}}\n\n"
            "\"flat_fee\" — Full payment is due upon completion of the service.\n\n"
            "\"deposit_balance\" — A deposit of {{deposit_percentage}}% is due upon "
            "execution. The remaining balance is due upon completion.\n\n"
            "\"hourly\" — Client is billed at the agreed hourly rate for all time "
            "on-site, billed in half-hour increments; estimates are guides only. "
            "Invoice is due within 7 days of issuance.\n\n"
            "Late payments accrue interest at 5% per month."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation Policy",
        "order": 8,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CANCELLATION POLICY\n\n"
            "Client must provide at least {{cancellation_notice_hours}} hours notice to "
            "cancel or reschedule a scheduled service appointment. Late cancellations "
            "may incur a service call fee to compensate Contractor for reserved labor "
            "time and travel costs. If Contractor has already procured materials specific "
            "to the job, Client shall reimburse Contractor for any non-returnable parts "
            "purchased."
        ),
    },
    {
        "clause_type": "termination",
        "title": "Termination",
        "order": 9,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate this agreement for material breach if the "
            "breaching party fails to cure within 7 days of written notice. Contractor "
            "may suspend work for non-payment or unsafe working conditions. Upon "
            "termination, Client shall pay for all work satisfactorily completed and "
            "materials procured through the termination date. Warranty and liability "
            "obligations survive termination."
        ),
    },
]


# ===========================================================================
# MANUAL LABOR — ELECTRICAL WORK
# ===========================================================================

ELECTRICAL_GUIDED_FIELDS = [
    {
        "field_key": "service_type",
        "label": "Service Type",
        "field_type": "choice",
        "choices": ["Repair", "Installation", "Panel Upgrade", "Wiring Inspection", "Rewiring"],
        "is_required": True,
        "order": 1,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "property_address",
        "label": "Property Address",
        "field_type": "text",
        "choices": None,
        "is_required": True,
        "order": 2,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "total_fee",
        "label": "Total Fee (USD)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 3,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "payment_model",
        "label": "Payment Model",
        "field_type": "choice",
        "choices": ["flat_fee", "deposit_balance", "hourly"],
        "is_required": True,
        "order": 4,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "deposit_percentage",
        "label": "Deposit Percentage (%)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 5,
        "condition_field_key": "payment_model",
        "condition_value": "deposit_balance",
    },
    {
        "field_key": "materials_included",
        "label": "Materials and Parts Included",
        "field_type": "boolean",
        "choices": None,
        "is_required": True,
        "order": 6,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "permit_responsibility",
        "label": "Permit Responsibility",
        "field_type": "choice",
        "choices": ["Contractor", "Client"],
        "is_required": True,
        "order": 7,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "warranty_days",
        "label": "Workmanship Warranty Period (days)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 8,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "cancellation_notice_hours",
        "label": "Cancellation Notice Window (hours)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 9,
        "condition_field_key": "",
        "condition_value": "",
    },
]

ELECTRICAL_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Services",
        "order": 1,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Contractor\") agrees to perform electrical work "
            "for {{counterparty_name}} (\"Client\") at the following property:\n\n"
            "Property Address: {{property_address}}\n"
            "Service Type: {{service_type}}\n\n"
            "All electrical work shall be performed in a safe, professional, and "
            "workmanlike manner in compliance with the National Electrical Code (NEC) "
            "and applicable local amendments. Contractor shall assess the work site "
            "before commencing to confirm scope and identify conditions affecting cost "
            "or safety. Work beyond the agreed scope requires a written change order."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Licensing and Permits",
        "order": 2,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "LICENSING AND PERMITS\n\n"
            "Permit Responsibility: {{permit_responsibility}}\n\n"
            "Contractor represents that all personnel performing electrical work hold "
            "the required electrician's license for the applicable jurisdiction and that "
            "all work will be performed to NEC and local code standards.\n\n"
            "The party designated above is responsible for obtaining all required "
            "electrical permits and paying associated fees before commencement of "
            "permitted work. Client shall provide reasonable property access for any "
            "required inspections. Delays caused by permit processing or inspection "
            "scheduling are not a breach of this agreement."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Materials and Parts",
        "order": 3,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "MATERIALS AND PARTS\n\n"
            "Materials and Parts Included: {{materials_included}}\n\n"
            "If included, all required wiring, fixtures, breakers, panels, conduit, "
            "and electrical components are covered in the agreed fee. Contractor shall "
            "use UL-listed components and materials meeting applicable code requirements.\n\n"
            "If not included, Client shall be invoiced separately for all materials at "
            "cost plus a reasonable handling markup with itemized documentation. "
            "Client-supplied components must meet applicable code requirements; Contractor "
            "is not liable for failures attributable to non-compliant Client-supplied parts."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Change Order",
        "order": 4,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CHANGE ORDER\n\n"
            "If additional electrical issues are discovered during work — including "
            "pre-existing code violations, deteriorated wiring, or undersized panels — "
            "Contractor shall document the finding, stop work on the affected area, and "
            "issue a written change order before proceeding. Contractor shall not "
            "knowingly conceal code violations or safety hazards. Client is advised that "
            "declining to address discovered code violations may create safety risks; "
            "Contractor is not liable for hazards arising from declined additional work."
        ),
    },
    {
        "clause_type": "risk",
        "title": "Damage Liability",
        "order": 5,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "DAMAGE LIABILITY\n\n"
            "Contractor shall be liable for damage to Client's property caused by "
            "Contractor's negligence or code-non-compliant workmanship. Client must "
            "report any damage claim in writing within 48 hours of service.\n\n"
            "Contractor is not liable for: pre-existing wiring faults discovered during "
            "work; damage to electronics or appliances from pre-existing electrical "
            "issues; damage from Client's failure to disclose known electrical hazards; "
            "or fire, equipment damage, or injury caused by Client-supplied non-compliant "
            "components. Contractor's maximum liability is capped at total fees paid."
        ),
    },
    {
        "clause_type": "general",
        "title": "Workmanship Warranty",
        "order": 6,
        "is_required": False,
        "is_conditional": True,
        "condition_description": "Applies when warranty_days is provided",
        "body": (
            "WORKMANSHIP WARRANTY\n\n"
            "Contractor warrants all electrical work against defects in workmanship for "
            "{{warranty_days}} days from completion. During this period Contractor shall "
            "correct any fault attributable to Contractor's installation or connection — "
            "including loose connections, incorrect wiring, or circuit failures from "
            "improper installation — at no additional charge.\n\n"
            "This warranty does not cover: Client-supplied components; damage from power "
            "surges, lightning, or utility fluctuations; modifications made by other "
            "parties after service; or component failure under normal operating life."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 7,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Total Fee: ${{total_fee}}\n"
            "Payment Model: {{payment_model}}\n\n"
            "\"flat_fee\" — Full payment due upon completion of service.\n\n"
            "\"deposit_balance\" — A deposit of {{deposit_percentage}}% is due upon "
            "execution. The remaining balance is due upon completion.\n\n"
            "\"hourly\" — Client is billed at the agreed hourly rate for all time "
            "on-site; estimates are guides only. Invoice due within 7 days of issuance.\n\n"
            "Contractor may withhold energization and final connection until outstanding "
            "balances are paid. Late payments accrue interest at 5% per month."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation Policy",
        "order": 8,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CANCELLATION POLICY\n\n"
            "Client must provide at least {{cancellation_notice_hours}} hours notice to "
            "cancel or reschedule a scheduled appointment. Late cancellations may incur "
            "a service call fee for reserved labor time and travel. If Contractor has "
            "procured materials specific to the job, Client shall reimburse Contractor "
            "for any non-returnable parts purchased."
        ),
    },
    {
        "clause_type": "termination",
        "title": "Termination",
        "order": 9,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate for material breach if not cured within 7 days "
            "of written notice. Contractor may suspend work for non-payment, unsafe "
            "conditions, or Client's direction to perform work Contractor determines "
            "is unsafe or code-non-compliant. Upon termination, Client pays for all "
            "work completed and materials procured through the termination date. "
            "Warranty and liability obligations survive termination."
        ),
    },
]


# ===========================================================================
# MANUAL LABOR — HVAC AND AC REPAIR
# ===========================================================================

HVAC_GUIDED_FIELDS = [
    {
        "field_key": "service_type",
        "label": "Service Type",
        "field_type": "choice",
        "choices": ["Repair", "Installation", "Maintenance Tune-Up", "Inspection", "System Replacement"],
        "is_required": True,
        "order": 1,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "property_address",
        "label": "Property Address",
        "field_type": "text",
        "choices": None,
        "is_required": True,
        "order": 2,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "total_fee",
        "label": "Total Fee (USD)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 3,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "payment_model",
        "label": "Payment Model",
        "field_type": "choice",
        "choices": ["flat_fee", "deposit_balance", "monthly"],
        "is_required": True,
        "order": 4,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "deposit_percentage",
        "label": "Deposit Percentage (%)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 5,
        "condition_field_key": "payment_model",
        "condition_value": "deposit_balance",
    },
    {
        "field_key": "parts_included",
        "label": "Parts and Refrigerant Included",
        "field_type": "boolean",
        "choices": None,
        "is_required": True,
        "order": 6,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "permit_responsibility",
        "label": "Permit Responsibility",
        "field_type": "choice",
        "choices": ["Contractor", "Client", "Not Required"],
        "is_required": True,
        "order": 7,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "warranty_days",
        "label": "Parts and Labor Warranty Period (days)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 8,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "cancellation_notice_hours",
        "label": "Cancellation Notice Window (hours)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 9,
        "condition_field_key": "",
        "condition_value": "",
    },
]

HVAC_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Services",
        "order": 1,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Contractor\") agrees to perform HVAC and AC services "
            "for {{counterparty_name}} (\"Client\") at the following property:\n\n"
            "Property Address: {{property_address}}\n"
            "Service Type: {{service_type}}\n\n"
            "All HVAC work shall be performed in a professional and workmanlike manner "
            "in compliance with applicable mechanical codes and manufacturer specifications. "
            "Contractor shall assess the system before commencing to confirm scope and "
            "identify conditions affecting cost or timeline. Work beyond the agreed scope "
            "requires a written change order before proceeding."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Licensing and Permits",
        "order": 2,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "LICENSING AND PERMITS\n\n"
            "Permit Responsibility: {{permit_responsibility}}\n\n"
            "Contractor represents that all technicians performing HVAC work hold "
            "required HVAC/R licenses for the applicable jurisdiction and are EPA "
            "Section 608 certified for refrigerant handling where applicable.\n\n"
            "The party designated above is responsible for obtaining required mechanical "
            "permits and paying associated fees. If permits are not required, both parties "
            "acknowledge that the work type falls within applicable permit exemptions. "
            "Delays caused by permit processing are not a breach of this agreement."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Parts and Materials",
        "order": 3,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PARTS AND MATERIALS\n\n"
            "Parts and Refrigerant Included: {{parts_included}}\n\n"
            "If included, all required replacement parts, refrigerant, filters, and "
            "consumables are covered in the agreed fee. Contractor shall use OEM or "
            "equivalent-grade components suitable for the system specifications.\n\n"
            "If not included, Client shall be invoiced separately for all parts at "
            "cost plus a reasonable handling markup with itemized documentation. "
            "Refrigerant charges will be itemized separately per applicable regulations. "
            "Contractor shall obtain Client approval before purchasing high-cost components."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Change Order",
        "order": 4,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CHANGE ORDER\n\n"
            "If additional issues are discovered during service — including failed "
            "components, refrigerant leaks in unexpected locations, or code deficiencies — "
            "Contractor shall document the finding and issue a written change order before "
            "proceeding. Contractor shall not proceed with additional work without written "
            "Client authorization. Client is responsible for decisions to decline "
            "recommended additional repairs."
        ),
    },
    {
        "clause_type": "risk",
        "title": "Damage Liability",
        "order": 5,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "DAMAGE LIABILITY\n\n"
            "Contractor shall be liable for damage to Client's property caused by "
            "Contractor's negligence. Client must report any damage claim in writing "
            "within 48 hours of service.\n\n"
            "Contractor is not liable for: pre-existing system deterioration or wear; "
            "damage from refrigerant leaks in system sections not serviced; compressor "
            "or component failure unrelated to Contractor's work; or damage caused by "
            "Client's continued operation of a system Contractor has recommended "
            "shutting down pending repairs."
        ),
    },
    {
        "clause_type": "general",
        "title": "Parts and Labor Warranty",
        "order": 6,
        "is_required": False,
        "is_conditional": True,
        "condition_description": "Applies when warranty_days is provided",
        "body": (
            "PARTS AND LABOR WARRANTY\n\n"
            "Contractor warrants labor performed and parts installed under this agreement "
            "for {{warranty_days}} days from the service completion date. During this "
            "period, Contractor shall repair or replace any component that fails due to "
            "improper installation or a manufacturing defect in parts supplied by "
            "Contractor, at no additional labor charge.\n\n"
            "Manufacturer parts warranties are governed separately by the manufacturer's "
            "terms. This warranty does not cover: normal wear; Client-supplied parts; "
            "damage from electrical surges or extreme weather; or system abuse or misuse."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 7,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Total Fee: ${{total_fee}}\n"
            "Payment Model: {{payment_model}}\n\n"
            "\"flat_fee\" — Full payment due upon completion of service.\n\n"
            "\"deposit_balance\" — A deposit of {{deposit_percentage}}% due upon "
            "execution; remaining balance due upon completion.\n\n"
            "\"monthly\" — Invoiced on the first of each service month; due within "
            "7 days. Contractor may suspend service for non-payment.\n\n"
            "Late payments accrue interest at 5% per month."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation Policy",
        "order": 8,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CANCELLATION POLICY\n\n"
            "Client must provide at least {{cancellation_notice_hours}} hours notice "
            "to cancel or reschedule. Late cancellations may incur a service call fee "
            "for reserved labor time and travel. If Contractor has procured non-returnable "
            "parts specific to the job, Client shall reimburse those costs."
        ),
    },
    {
        "clause_type": "termination",
        "title": "Termination",
        "order": 9,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate for material breach not cured within 7 days "
            "of written notice. Contractor may suspend work for non-payment or unsafe "
            "conditions. Upon termination, Client pays for all work completed and parts "
            "procured through the termination date. Warranty and liability provisions "
            "survive termination."
        ),
    },
]


# ===========================================================================
# MANUAL LABOR — PAINTING (INTERIOR AND EXTERIOR)
# ===========================================================================

PAINTING_GUIDED_FIELDS = [
    {
        "field_key": "painting_type",
        "label": "Painting Type",
        "field_type": "choice",
        "choices": ["Interior", "Exterior", "Both"],
        "is_required": True,
        "order": 1,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "property_address",
        "label": "Property Address",
        "field_type": "text",
        "choices": None,
        "is_required": True,
        "order": 2,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "total_fee",
        "label": "Total Fee (USD)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 3,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "payment_model",
        "label": "Payment Model",
        "field_type": "choice",
        "choices": ["deposit_balance", "flat_fee", "installments"],
        "is_required": True,
        "order": 4,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "deposit_percentage",
        "label": "Deposit Percentage (%)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 5,
        "condition_field_key": "payment_model",
        "condition_value": "deposit_balance",
    },
    {
        "field_key": "num_installments",
        "label": "Number of Installments",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 6,
        "condition_field_key": "payment_model",
        "condition_value": "installments",
    },
    {
        "field_key": "installment_interval_days",
        "label": "Installment Interval",
        "field_type": "choice",
        "choices": ["7", "30"],
        "is_required": True,
        "order": 7,
        "condition_field_key": "payment_model",
        "condition_value": "installments",
    },
    {
        "field_key": "paint_provided_by",
        "label": "Paint Provided By",
        "field_type": "choice",
        "choices": ["Contractor", "Client"],
        "is_required": True,
        "order": 8,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "num_coats",
        "label": "Number of Coats",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 9,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "surface_prep_included",
        "label": "Surface Preparation Included",
        "field_type": "boolean",
        "choices": None,
        "is_required": True,
        "order": 10,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "estimated_duration_days",
        "label": "Estimated Duration (days)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 11,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "warranty_days",
        "label": "Workmanship Warranty Period (days)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 12,
        "condition_field_key": "",
        "condition_value": "",
    },
]

PAINTING_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Services",
        "order": 1,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Contractor\") agrees to perform painting services "
            "for {{counterparty_name}} (\"Client\") at the following property:\n\n"
            "Property Address: {{property_address}}\n"
            "Painting Type: {{painting_type}}\n"
            "Number of Coats: {{num_coats}}\n"
            "Estimated Duration: {{estimated_duration_days}} days\n\n"
            "Contractor shall paint all agreed surfaces to a professional standard "
            "with uniform coverage, clean edges, and consistent finish. The specific "
            "rooms, surfaces, and areas to be painted are set forth in the project "
            "proposal or addendum. Color changes or additional surfaces after commencement "
            "require a written change order."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Paint and Materials",
        "order": 2,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PAINT AND MATERIALS\n\n"
            "Paint Provided By: {{paint_provided_by}}\n\n"
            "If provided by Contractor, Contractor shall supply paint of commercially "
            "appropriate quality (minimum standard-grade) in the colors selected by "
            "Client. All brushes, rollers, tape, drop cloths, and supplies are included. "
            "Contractor shall select paint type appropriate to the surface "
            "(e.g., exterior-grade for outdoor surfaces).\n\n"
            "If provided by Client, Client shall supply sufficient quantities of paint "
            "for all agreed coats. Client-supplied paint is accepted as-is; Contractor "
            "is not liable for finish quality issues attributable to inadequate paint "
            "coverage, poor-quality paint, or incorrect paint type for the surface."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Surface Preparation",
        "order": 3,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SURFACE PREPARATION\n\n"
            "Surface Preparation Included: {{surface_prep_included}}\n\n"
            "If included, Contractor shall clean surfaces, fill minor holes and cracks, "
            "sand rough areas, and apply primer where required before painting. "
            "Furniture, flooring, and fixtures will be protected with drop cloths and "
            "tape. Contractor is not responsible for damage to items not moved or "
            "protected at Client's direction.\n\n"
            "If not included, Client is responsible for all surface preparation prior "
            "to Contractor's arrival. Contractor shall not be liable for finish quality "
            "issues attributable to inadequate surface preparation performed by others."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Change Order",
        "order": 4,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CHANGE ORDER\n\n"
            "Any request for color changes after work has commenced, additional surfaces "
            "beyond the agreed scope, or changes to the agreed number of coats requires "
            "a written change order before work on the change proceeds. Color change "
            "mid-job may require re-priming and additional coats; such additional labor "
            "and materials will be itemized in the change order."
        ),
    },
    {
        "clause_type": "risk",
        "title": "Damage Liability",
        "order": 5,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "DAMAGE LIABILITY\n\n"
            "Contractor shall protect floors, furniture, and fixtures with appropriate "
            "drop cloths and masking and shall be liable for overspray, spills, or "
            "drips caused by Contractor's negligence. Client must report any damage "
            "claim in writing within 48 hours of the service date.\n\n"
            "Contractor is not liable for: damage to items Client declined to have moved "
            "or covered; pre-existing surface cracks or defects that affect finish quality; "
            "paint adhesion failure on surfaces with pre-existing moisture or contamination "
            "not visible before painting; or normal paint wear on exterior surfaces "
            "due to weather."
        ),
    },
    {
        "clause_type": "general",
        "title": "Workmanship Warranty",
        "order": 6,
        "is_required": False,
        "is_conditional": True,
        "condition_description": "Applies when warranty_days is provided",
        "body": (
            "WORKMANSHIP WARRANTY\n\n"
            "Contractor warrants painting work against defects in application for "
            "{{warranty_days}} days from completion. During this period, Contractor "
            "shall correct peeling, cracking, or blistering attributable to improper "
            "application technique at no additional charge.\n\n"
            "This warranty does not cover: normal paint wear on exterior surfaces "
            "from weather; damage from Client modifications; paint failure on "
            "Client-supplied surfaces with pre-existing moisture or contamination; "
            "or color fading over time."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 7,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Total Fee: ${{total_fee}}\n"
            "Payment Model: {{payment_model}}\n\n"
            "\"deposit_balance\" — A deposit of {{deposit_percentage}}% is due upon "
            "execution to confirm the booking and secure the schedule. The remaining "
            "balance is due upon completion and Client walk-through acceptance.\n\n"
            "\"flat_fee\" — Full payment is due upon completion.\n\n"
            "\"installments\" — Payments per the agreed installment schedule. "
            "Contractor may pause work if an installment is more than 7 days overdue.\n\n"
            "Late payments accrue interest at 5% per month."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation Policy",
        "order": 8,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CANCELLATION POLICY\n\n"
            "If Client cancels after work has commenced, Client shall pay for all work "
            "completed and materials procured to the cancellation date, plus 25% of "
            "the remaining contract value as a cancellation fee for reserved labor "
            "capacity. Deposits are non-refundable once materials have been purchased "
            "and scheduling has been confirmed."
        ),
    },
    {
        "clause_type": "termination",
        "title": "Termination",
        "order": 9,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate for material breach not cured within 7 days "
            "of written notice. Upon termination, Client pays for work completed and "
            "materials procured through the termination date. Contractor shall leave "
            "the property clean and tidy. Warranty and liability provisions survive."
        ),
    },
]


# ===========================================================================
# MANUAL LABOR — MOVING SERVICES
# ===========================================================================

MOVING_SERVICES_GUIDED_FIELDS = [
    {
        "field_key": "move_type",
        "label": "Move Type",
        "field_type": "choice",
        "choices": ["Local Move", "Long-Distance Move", "Commercial Move", "Packing Only"],
        "is_required": True,
        "order": 1,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "pickup_address",
        "label": "Pickup Address",
        "field_type": "text",
        "choices": None,
        "is_required": True,
        "order": 2,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "delivery_address",
        "label": "Delivery Address",
        "field_type": "text",
        "choices": None,
        "is_required": True,
        "order": 3,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "total_fee",
        "label": "Total Fee (USD)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 4,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "payment_model",
        "label": "Payment Model",
        "field_type": "choice",
        "choices": ["flat_fee", "deposit_balance", "hourly"],
        "is_required": True,
        "order": 5,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "deposit_percentage",
        "label": "Deposit Percentage (%)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 6,
        "condition_field_key": "payment_model",
        "condition_value": "deposit_balance",
    },
    {
        "field_key": "packing_included",
        "label": "Full Packing Service Included",
        "field_type": "boolean",
        "choices": None,
        "is_required": True,
        "order": 7,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "insurance_coverage",
        "label": "Insurance Coverage",
        "field_type": "choice",
        "choices": ["Basic Coverage", "Full Value Protection", "None"],
        "is_required": True,
        "order": 8,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "num_movers",
        "label": "Number of Movers",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 9,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "cancellation_notice_days",
        "label": "Cancellation Notice Period (days)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 10,
        "condition_field_key": "",
        "condition_value": "",
    },
]

MOVING_SERVICES_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Services",
        "order": 1,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Mover\") agrees to provide moving services "
            "for {{counterparty_name}} (\"Client\") under the following terms:\n\n"
            "Move Type: {{move_type}}\n"
            "Pickup Address: {{pickup_address}}\n"
            "Delivery Address: {{delivery_address}}\n"
            "Number of Movers: {{num_movers}}\n\n"
            "Mover shall load, transport, and unload Client's belongings with reasonable "
            "care. For long-distance moves, estimated transit times are provided as "
            "guides and are subject to weather, road conditions, and routing. Client "
            "shall ensure all items to be moved are accessible and disclosed to Mover "
            "before service date."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Packing and Materials",
        "order": 2,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PACKING AND MATERIALS\n\n"
            "Full Packing Service Included: {{packing_included}}\n\n"
            "If packing is included, Mover shall supply all boxes, packing paper, "
            "bubble wrap, tape, and materials required to safely pack Client's belongings. "
            "Mover shall pack items with reasonable care using appropriate protective "
            "materials for fragile items.\n\n"
            "If packing is not included, Client is responsible for packing all items "
            "prior to the move date. Mover is not liable for damage to items packed "
            "by Client unless caused by Mover's mishandling of properly packed boxes. "
            "Client shall label all boxes with contents and fragility indicators."
        ),
    },
    {
        "clause_type": "risk",
        "title": "Insurance and Damage Coverage",
        "order": 3,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "INSURANCE AND DAMAGE COVERAGE\n\n"
            "Insurance Coverage Selected: {{insurance_coverage}}\n\n"
            "\"Basic Coverage\" — Mover's liability is limited to $0.60 per pound per "
            "item as required by applicable federal and state regulations. Client is "
            "advised this provides minimal protection for high-value items.\n\n"
            "\"Full Value Protection\" — Mover is liable for the replacement cost or "
            "repair of damaged items up to their declared value. Client must declare "
            "high-value items (over $100 per item) in writing before the move date; "
            "undeclared high-value items default to basic coverage.\n\n"
            "\"None\" — Client assumes all risk for damage. Mover is not liable for "
            "any damage to Client's belongings during the move.\n\n"
            "All damage claims must be reported in writing within 9 months of delivery."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Prohibited Items",
        "order": 4,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PROHIBITED ITEMS\n\n"
            "Mover will not transport the following items regardless of coverage level: "
            "hazardous materials (flammables, explosives, corrosives), perishable food "
            "and plants, cash, jewelry, securities and negotiable instruments, firearms "
            "and ammunition (without prior written agreement), prescription medications, "
            "irreplaceable documents, and items of extraordinary personal or sentimental "
            "value.\n\n"
            "Client is responsible for transporting all prohibited items independently. "
            "Client's failure to disclose prohibited items discovered during loading may "
            "result in refusal to transport those items and no adjustment to the fee."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 5,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Total Fee: ${{total_fee}}\n"
            "Payment Model: {{payment_model}}\n\n"
            "\"flat_fee\" — Full payment is due upon completion of delivery.\n\n"
            "\"deposit_balance\" — A deposit of {{deposit_percentage}}% is due upon "
            "booking to confirm the move date. The remaining balance is due upon "
            "completion of delivery. Mover may withhold delivery of items until the "
            "outstanding balance is paid in full.\n\n"
            "\"hourly\" — Client is billed at the agreed hourly rate per mover for "
            "all time from first pick-up to last item placed; estimates are guides only.\n\n"
            "Late payments accrue interest at 5% per month."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation Policy",
        "order": 6,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CANCELLATION POLICY\n\n"
            "Client must cancel with at least {{cancellation_notice_days}} days written "
            "notice to receive a full refund of any deposit paid. Cancellations within "
            "48 hours of the scheduled move date forfeit the deposit in full to "
            "compensate Mover for reserved crew time and truck scheduling that cannot "
            "be recovered on short notice.\n\n"
            "Mover may reschedule due to vehicle mechanical failure, weather making "
            "transport unsafe, or crew illness, and shall provide prompt notice with "
            "a proposed alternative date."
        ),
    },
    {
        "clause_type": "termination",
        "title": "Termination",
        "order": 7,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate for material breach not cured within 7 days "
            "of written notice. Mover may suspend service if Client fails to make "
            "required payments or creates unsafe working conditions. Upon termination "
            "during an active move, Client pays for all work completed to the "
            "termination date at a pro-rata rate. Insurance, liability, and damage "
            "claim provisions survive termination."
        ),
    },
]


# ===========================================================================
# MANUAL LABOR — GENERAL HANDYMAN
# ===========================================================================

HANDYMAN_GUIDED_FIELDS = [
    {
        "field_key": "service_description",
        "label": "Description of Work",
        "field_type": "text",
        "choices": None,
        "is_required": True,
        "order": 1,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "property_address",
        "label": "Property Address",
        "field_type": "text",
        "choices": None,
        "is_required": True,
        "order": 2,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "total_fee",
        "label": "Total Fee (USD)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 3,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "payment_model",
        "label": "Payment Model",
        "field_type": "choice",
        "choices": ["flat_fee", "deposit_balance", "hourly"],
        "is_required": True,
        "order": 4,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "deposit_percentage",
        "label": "Deposit Percentage (%)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 5,
        "condition_field_key": "payment_model",
        "condition_value": "deposit_balance",
    },
    {
        "field_key": "materials_included",
        "label": "Materials Included in Price",
        "field_type": "boolean",
        "choices": None,
        "is_required": True,
        "order": 6,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "estimated_hours",
        "label": "Estimated Hours",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 7,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "warranty_days",
        "label": "Workmanship Warranty Period (days)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 8,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "cancellation_notice_hours",
        "label": "Cancellation Notice Window (hours)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 9,
        "condition_field_key": "",
        "condition_value": "",
    },
]

HANDYMAN_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Services",
        "order": 1,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Provider\") agrees to perform handyman services "
            "for {{counterparty_name}} (\"Client\") at the following property:\n\n"
            "Property Address: {{property_address}}\n"
            "Work Description: {{service_description}}\n\n"
            "Provider shall perform all work in a professional and workmanlike manner. "
            "A written service order confirming the scope and price will be provided "
            "before work begins. Work beyond the agreed scope requires a written "
            "change order signed by both parties before proceeding."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Materials",
        "order": 2,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "MATERIALS\n\n"
            "Materials Included: {{materials_included}}\n\n"
            "If included, all required materials, hardware, fasteners, and supplies "
            "are covered in the agreed fee. Provider shall use commercially appropriate "
            "materials for the work type.\n\n"
            "If not included, Client shall be invoiced for materials at cost plus a "
            "reasonable handling markup with itemized documentation. Provider shall "
            "obtain Client approval before purchasing materials above a pre-agreed "
            "threshold. Client-supplied materials are accepted as-is."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Change Order",
        "order": 3,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CHANGE ORDER\n\n"
            "If additional work is discovered beyond the original agreed scope, "
            "Provider shall stop work on the affected area and issue a written change "
            "order before proceeding. The change order shall describe the additional "
            "work, estimated cost, and timeline impact. Client may authorize or decline "
            "the additional work. Provider is not liable for incomplete results in areas "
            "where necessary additional work was declined."
        ),
    },
    {
        "clause_type": "risk",
        "title": "Damage Liability",
        "order": 4,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "DAMAGE LIABILITY\n\n"
            "Provider shall be liable for damage to Client's property caused by "
            "Provider's negligence or improper workmanship. Client must notify Provider "
            "of any damage in writing within 48 hours of the service date.\n\n"
            "Provider is not liable for pre-existing damage or deterioration; damage "
            "caused by Client-supplied materials or parts; or conditions discovered "
            "during work that were not visible or disclosed before commencement. "
            "Provider's maximum liability shall not exceed the total fees paid."
        ),
    },
    {
        "clause_type": "general",
        "title": "Workmanship Warranty",
        "order": 5,
        "is_required": False,
        "is_conditional": True,
        "condition_description": "Applies when warranty_days is provided",
        "body": (
            "WORKMANSHIP WARRANTY\n\n"
            "Provider warrants all work against defects in workmanship for "
            "{{warranty_days}} days from completion. During this period Provider shall "
            "correct any defect attributable to Provider's technique or installation "
            "at no additional charge. This warranty does not cover normal wear, "
            "Client modifications, damage from misuse, or failures in Client-supplied "
            "materials."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 6,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Total Fee: ${{total_fee}}\n"
            "Payment Model: {{payment_model}}\n\n"
            "\"flat_fee\" — Full payment due upon completion.\n\n"
            "\"deposit_balance\" — A deposit of {{deposit_percentage}}% is due upon "
            "execution; remaining balance due upon completion.\n\n"
            "\"hourly\" — Billed at the agreed hourly rate for all time on-site; "
            "estimates are guides only. Invoice due within 7 days.\n\n"
            "Late payments accrue interest at 5% per month."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation Policy",
        "order": 7,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CANCELLATION POLICY\n\n"
            "Client must provide at least {{cancellation_notice_hours}} hours notice "
            "to cancel or reschedule. Late cancellations may incur a service call fee "
            "for reserved labor time. If Provider has procured non-returnable materials "
            "for the job, Client shall reimburse those costs."
        ),
    },
    {
        "clause_type": "termination",
        "title": "Termination",
        "order": 8,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate for material breach not cured within 7 days "
            "of written notice. Provider may suspend work for non-payment, unsafe "
            "conditions, or Client's direction to perform work outside Provider's "
            "competency. Upon termination, Client pays for all work satisfactorily "
            "completed and materials procured through the termination date."
        ),
    },
]


# ===========================================================================
# MANUAL LABOR — PEST CONTROL
# ===========================================================================

PEST_CONTROL_GUIDED_FIELDS = [
    {
        "field_key": "pest_type",
        "label": "Pest Type",
        "field_type": "choice",
        "choices": [
            "General Pests",
            "Rodents",
            "Termites",
            "Bed Bugs",
            "Mosquito Control",
            "Ants and Roaches",
        ],
        "is_required": True,
        "order": 1,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "service_model",
        "label": "Service Model",
        "field_type": "choice",
        "choices": ["One-Time Treatment", "Monthly Plan", "Quarterly Plan", "Annual Plan"],
        "is_required": True,
        "order": 2,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "property_address",
        "label": "Property Address",
        "field_type": "text",
        "choices": None,
        "is_required": True,
        "order": 3,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "total_fee",
        "label": "Total Fee (USD)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 4,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "payment_model",
        "label": "Payment Model",
        "field_type": "choice",
        "choices": ["flat_fee", "prepaid_plan", "per_visit"],
        "is_required": True,
        "order": 5,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "treatment_method",
        "label": "Treatment Method / Chemicals Used",
        "field_type": "text",
        "choices": None,
        "is_required": True,
        "order": 6,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "re_treatment_included",
        "label": "Free Re-Treatment Included",
        "field_type": "boolean",
        "choices": None,
        "is_required": True,
        "order": 7,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "warranty_days",
        "label": "Re-Treatment Guarantee Period (days)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 8,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "cancellation_notice_days",
        "label": "Cancellation Notice Period (days)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 9,
        "condition_field_key": "",
        "condition_value": "",
    },
]

PEST_CONTROL_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Services",
        "order": 1,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Provider\") agrees to provide pest control services "
            "for {{counterparty_name}} (\"Client\") at the following property:\n\n"
            "Property Address: {{property_address}}\n"
            "Pest Type: {{pest_type}}\n"
            "Service Model: {{service_model}}\n\n"
            "Provider shall apply treatments appropriate to the pest type and property "
            "using licensed technicians. Services are limited to the property address "
            "specified. Treatment of additional structures or adjacent properties requires "
            "a separate agreement."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Treatment Method and Chemical Safety",
        "order": 2,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "TREATMENT METHOD AND CHEMICAL SAFETY\n\n"
            "Treatment Method: {{treatment_method}}\n\n"
            "All chemicals and treatments will be applied by licensed pest control "
            "technicians in accordance with applicable state and federal regulations "
            "and EPA label directions. Safety data sheets (SDS) for all products used "
            "are available upon request.\n\n"
            "Client must ensure all children, pets, and sensitive individuals vacate "
            "the treated areas for the re-entry period specified on product labels. "
            "Client shall disclose any known allergies or chemical sensitivities before "
            "treatment. Provider is not liable for adverse reactions caused by Client's "
            "failure to follow re-entry instructions."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Client Preparation Requirements",
        "order": 3,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CLIENT PREPARATION REQUIREMENTS\n\n"
            "Client shall prepare the property per Provider's pre-treatment instructions "
            "provided before each service visit. Preparation typically includes clearing "
            "access areas, removing food from counters, and securing pets. Failure to "
            "prepare the property per instructions may reduce treatment effectiveness.\n\n"
            "Provider is not responsible for treatment failure or incomplete pest "
            "elimination resulting from Client's failure to follow preparation "
            "instructions, Client's refusal to allow access to all affected areas, "
            "or re-infestation from adjacent structures outside the agreed service scope."
        ),
    },
    {
        "clause_type": "general",
        "title": "Re-Treatment Guarantee",
        "order": 4,
        "is_required": False,
        "is_conditional": True,
        "condition_description": "Applies when re_treatment_included is true",
        "body": (
            "RE-TREATMENT GUARANTEE\n\n"
            "Free Re-Treatment Included: {{re_treatment_included}}\n\n"
            "If re-treatment is included and the treated pest population returns within "
            "{{warranty_days}} days of the initial treatment, Provider shall perform "
            "one additional treatment at no additional charge upon Client's written "
            "notification.\n\n"
            "The re-treatment guarantee applies only where Client has followed all "
            "preparation and post-treatment instructions, has not introduced new "
            "infestation sources (e.g., infested furniture or adjacent units), and "
            "the property has not been structurally altered in ways that create new "
            "entry points. The guarantee is void upon termination of this agreement "
            "by Client."
        ),
    },
    {
        "clause_type": "risk",
        "title": "Damage Liability",
        "order": 5,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "DAMAGE LIABILITY\n\n"
            "Provider shall be liable for property damage caused by Provider's "
            "negligence in applying treatments. Client must report any damage claim "
            "in writing within 48 hours of service.\n\n"
            "Provider is not liable for: property damage caused by the pest infestation "
            "itself; staining or surface damage from treatments applied in compliance "
            "with label directions; damage caused by Client's failure to follow "
            "pre-treatment preparation or post-treatment instructions; or incomplete "
            "pest control results where Client denied access to affected areas."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 6,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Total Fee: ${{total_fee}}\n"
            "Payment Model: {{payment_model}}\n\n"
            "\"flat_fee\" — Full payment is due upon completion of the treatment.\n\n"
            "\"prepaid_plan\" — Full plan fee is due upon execution of this agreement "
            "and covers all scheduled visits within the plan period.\n\n"
            "\"per_visit\" — Client is invoiced after each treatment visit; payment "
            "due within 7 days of invoice.\n\n"
            "Late payments accrue interest at 5% per month. Provider may suspend "
            "service for invoices more than 14 days past due."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation Policy",
        "order": 7,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CANCELLATION POLICY\n\n"
            "Either party may cancel this agreement with {{cancellation_notice_days}} "
            "days written notice. For prepaid plans, Client will receive a prorated "
            "refund for any unrendered visits remaining after the cancellation date. "
            "Re-treatment guarantees are void upon cancellation by Client."
        ),
    },
    {
        "clause_type": "termination",
        "title": "Termination",
        "order": 8,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate for material breach not cured within 7 days "
            "of written notice. Upon termination, Client pays all fees accrued through "
            "the last completed treatment. Provider shall provide SDS sheets for any "
            "chemicals applied within 30 days of termination upon Client's request. "
            "Re-treatment and liability provisions survive termination."
        ),
    },
]


# ===========================================================================
# MANUAL LABOR — CUSTOM BUILD AND FABRICATION
# ===========================================================================

CUSTOM_FABRICATION_GUIDED_FIELDS = [
    {
        "field_key": "project_type",
        "label": "Project Type",
        "field_type": "choice",
        "choices": ["Custom Furniture", "Cabinetry", "Metalwork", "Woodwork", "Custom Structure", "Other"],
        "is_required": True,
        "order": 1,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "total_contract_value",
        "label": "Total Contract Value (USD)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 2,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "payment_model",
        "label": "Payment Model",
        "field_type": "choice",
        "choices": ["deposit_balance", "milestone", "installments"],
        "is_required": True,
        "order": 3,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "deposit_percentage",
        "label": "Deposit Percentage (%)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 4,
        "condition_field_key": "payment_model",
        "condition_value": "deposit_balance",
    },
    {
        "field_key": "num_installments",
        "label": "Number of Installments",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 5,
        "condition_field_key": "payment_model",
        "condition_value": "installments",
    },
    {
        "field_key": "installment_interval_days",
        "label": "Installment Interval",
        "field_type": "choice",
        "choices": ["7", "30"],
        "is_required": True,
        "order": 6,
        "condition_field_key": "payment_model",
        "condition_value": "installments",
    },
    {
        "field_key": "materials_included",
        "label": "Materials",
        "field_type": "choice",
        "choices": ["Included in Price", "Client Provides", "Partial — Labor Only"],
        "is_required": True,
        "order": 7,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "estimated_duration_days",
        "label": "Estimated Build Time (days)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 8,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "design_approval_required",
        "label": "Design Approval Required Before Build",
        "field_type": "boolean",
        "choices": None,
        "is_required": True,
        "order": 9,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "warranty_days",
        "label": "Workmanship Warranty Period (days)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 10,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "cancellation_window_days",
        "label": "Cancellation Window (days)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 11,
        "condition_field_key": "",
        "condition_value": "",
    },
]

CUSTOM_FABRICATION_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Services",
        "order": 1,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Builder\") agrees to design and fabricate "
            "{{project_type}} for {{counterparty_name}} (\"Client\") per the agreed "
            "project brief or specification.\n\n"
            "Estimated Build Time: {{estimated_duration_days}} days from design "
            "approval or commencement date. All work shall be performed by skilled "
            "craftspeople using professional fabrication methods appropriate to the "
            "materials and project type. Work beyond the agreed specification requires "
            "a written change order."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Materials and Labor",
        "order": 2,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "MATERIALS AND LABOR\n\n"
            "Materials: {{materials_included}}\n\n"
            "\"Included in Price\" — All raw materials, hardware, finishes, and "
            "consumables required are covered in the contract value.\n\n"
            "\"Client Provides\" — The contract price covers labor only. Client shall "
            "procure and deliver materials on schedule. Builder assumes no liability "
            "for defects in Client-supplied stock.\n\n"
            "\"Partial — Labor Only\" — Parties shall specify in writing which materials "
            "each supplies. Material cost overruns require a written change order and "
            "Client approval before additional expenditure is incurred."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Design Approval and Change Order",
        "order": 3,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "DESIGN APPROVAL AND CHANGE ORDER\n\n"
            "Design Approval Required: {{design_approval_required}}\n\n"
            "If design approval is required, Builder shall produce final drawings or "
            "renders for Client review. Fabrication shall not commence until Client "
            "provides written approval. Changes after written approval require a "
            "written change order and may extend the timeline and increase cost.\n\n"
            "In all cases, modifications to agreed dimensions, materials, or finishes "
            "after fabrication has commenced require a written change order. Builder "
            "is not obligated to undo completed work pending change order execution."
        ),
    },
    {
        "clause_type": "risk",
        "title": "Damage Liability",
        "order": 4,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "DAMAGE LIABILITY\n\n"
            "Builder shall be liable for damage to Client's property caused by "
            "Builder's negligence during fabrication, delivery, or installation. "
            "Client must inspect the finished item upon delivery and notify Builder "
            "of any damage claim in writing within 48 hours of receipt.\n\n"
            "Builder is not liable for natural material variation (wood grain, metal "
            "finish characteristics inherent to the material) disclosed at design "
            "stage, or dimensional variance within commercially accepted tolerances "
            "for the fabrication method used."
        ),
    },
    {
        "clause_type": "general",
        "title": "Workmanship Warranty",
        "order": 5,
        "is_required": False,
        "is_conditional": True,
        "condition_description": "Applies when warranty_days is provided",
        "body": (
            "WORKMANSHIP WARRANTY\n\n"
            "Builder warrants all work against structural defects in workmanship for "
            "{{warranty_days}} days from the date of delivery. During this period "
            "Builder shall repair or replace any item with a structural defect "
            "attributable to poor construction technique at no charge.\n\n"
            "This warranty does not cover: normal wear; scratches or dents after "
            "delivery; Client modifications; damage from improper use; or cosmetic "
            "characteristics of natural materials disclosed before fabrication."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 6,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Total Contract Value: ${{total_contract_value}}\n"
            "Payment Model: {{payment_model}}\n\n"
            "\"deposit_balance\" — A deposit of {{deposit_percentage}}% is due upon "
            "execution to secure materials and the build slot. The remaining balance "
            "is due upon delivery and Client acceptance.\n\n"
            "\"milestone\" — Payments tied to defined build milestones; due within "
            "7 days of milestone completion notice.\n\n"
            "\"installments\" — Equal installment payments per the agreed schedule.\n\n"
            "Builder may withhold delivery until all outstanding balances are paid. "
            "Late payments accrue interest at 5% per month."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation and Kill Fee",
        "order": 7,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CANCELLATION AND KILL FEE\n\n"
            "Client may cancel within {{cancellation_window_days}} days of execution "
            "and receive a full deposit refund less any design costs incurred, provided "
            "fabrication has not yet commenced. If Client cancels after materials have "
            "been ordered or fabrication has commenced, Client shall pay the full cost "
            "of all materials procured plus 30% of the remaining labor value as a "
            "kill fee for lost revenue and build slot opportunity.\n\n"
            "Finished or partially finished items for which the kill fee has been paid "
            "become the property of Client. Cancellations must be submitted in writing."
        ),
    },
    {
        "clause_type": "termination",
        "title": "Termination",
        "order": 8,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate for material breach not cured within 7 days "
            "of written notice. Upon termination, Client pays for all work completed "
            "and materials procured through the termination date per the Cancellation "
            "and Kill Fee clause. Builder shall deliver any completed portions upon "
            "receipt of all amounts owed. Warranty and liability provisions survive."
        ),
    },
]


# ===========================================================================
# MANUAL LABOR — GENERAL REPAIR
# ===========================================================================

GENERAL_REPAIR_GUIDED_FIELDS = [
    {
        "field_key": "repair_description",
        "label": "Description of Repair",
        "field_type": "text",
        "choices": None,
        "is_required": True,
        "order": 1,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "property_address",
        "label": "Property Address",
        "field_type": "text",
        "choices": None,
        "is_required": True,
        "order": 2,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "total_fee",
        "label": "Total Fee (USD)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 3,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "payment_model",
        "label": "Payment Model",
        "field_type": "choice",
        "choices": ["flat_fee", "deposit_balance", "hourly"],
        "is_required": True,
        "order": 4,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "deposit_percentage",
        "label": "Deposit Percentage (%)",
        "field_type": "number",
        "choices": None,
        "is_required": True,
        "order": 5,
        "condition_field_key": "payment_model",
        "condition_value": "deposit_balance",
    },
    {
        "field_key": "materials_included",
        "label": "Materials and Parts Included",
        "field_type": "boolean",
        "choices": None,
        "is_required": True,
        "order": 6,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "warranty_days",
        "label": "Workmanship Warranty Period (days)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 7,
        "condition_field_key": "",
        "condition_value": "",
    },
    {
        "field_key": "cancellation_notice_hours",
        "label": "Cancellation Notice Window (hours)",
        "field_type": "number",
        "choices": None,
        "is_required": False,
        "order": 8,
        "condition_field_key": "",
        "condition_value": "",
    },
]

GENERAL_REPAIR_CLAUSES = [
    {
        "clause_type": "scope",
        "title": "Scope of Services",
        "order": 1,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "SCOPE OF SERVICES\n\n"
            "{{initiator_name}} (\"Provider\") agrees to perform the following repair "
            "work for {{counterparty_name}} (\"Client\") at the property located at "
            "{{property_address}}:\n\n"
            "Repair Description: {{repair_description}}\n\n"
            "All work shall be performed in a professional and workmanlike manner. "
            "Provider shall assess the repair site before commencing to confirm scope. "
            "A written service order confirming scope and price shall be provided "
            "before work begins. Work beyond the agreed scope requires a written "
            "change order."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Materials and Parts",
        "order": 2,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "MATERIALS AND PARTS\n\n"
            "Materials Included: {{materials_included}}\n\n"
            "If included, all replacement parts, hardware, and supplies required to "
            "complete the repair are covered in the agreed fee. Provider shall use "
            "commercially appropriate quality parts suitable for the application.\n\n"
            "If not included, Client shall be invoiced separately for all materials "
            "at cost plus a reasonable handling markup with itemized documentation. "
            "Client-supplied parts are accepted as-is; Provider is not liable for "
            "defects or failure of Client-supplied components."
        ),
    },
    {
        "clause_type": "scope",
        "title": "Change Order",
        "order": 3,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CHANGE ORDER\n\n"
            "If additional damage or conditions exceeding the original scope are "
            "discovered during repair, Provider shall stop work on the affected area "
            "and issue a written change order before proceeding. Client may authorize "
            "or decline the additional work. Provider is not liable for incomplete "
            "results in areas where necessary additional work was declined."
        ),
    },
    {
        "clause_type": "risk",
        "title": "Damage Liability",
        "order": 4,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "DAMAGE LIABILITY\n\n"
            "Provider shall be liable for damage to Client's property caused by "
            "Provider's negligence or improper workmanship. Client must notify "
            "Provider of any damage claim in writing within 48 hours of service.\n\n"
            "Provider is not liable for pre-existing damage or deterioration; damage "
            "caused by Client-supplied parts; or conditions discovered during work "
            "not visible or disclosed before commencement. Provider's maximum "
            "liability shall not exceed total fees paid."
        ),
    },
    {
        "clause_type": "general",
        "title": "Workmanship Warranty",
        "order": 5,
        "is_required": False,
        "is_conditional": True,
        "condition_description": "Applies when warranty_days is provided",
        "body": (
            "WORKMANSHIP WARRANTY\n\n"
            "Provider warrants all repair work against defects in workmanship for "
            "{{warranty_days}} days from completion. During this period Provider shall "
            "remedy any defect caused by improper technique at no additional charge.\n\n"
            "This warranty does not cover: normal wear and tear; Client modifications; "
            "damage from misuse or environmental conditions beyond the repair scope; "
            "or failures attributable to Client-supplied parts."
        ),
    },
    {
        "clause_type": "payment",
        "title": "Payment Terms",
        "order": 6,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "PAYMENT TERMS\n\n"
            "Total Fee: ${{total_fee}}\n"
            "Payment Model: {{payment_model}}\n\n"
            "\"flat_fee\" — Full payment due upon completion.\n\n"
            "\"deposit_balance\" — A deposit of {{deposit_percentage}}% is due upon "
            "execution; remaining balance due upon completion.\n\n"
            "\"hourly\" — Billed at the agreed hourly rate for all time on-site "
            "in half-hour increments; estimates are guides only. Invoice due within "
            "7 days of issuance.\n\n"
            "Late payments accrue interest at 5% per month."
        ),
    },
    {
        "clause_type": "cancellation",
        "title": "Cancellation Policy",
        "order": 7,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "CANCELLATION POLICY\n\n"
            "Client must provide at least {{cancellation_notice_hours}} hours notice "
            "to cancel or reschedule. Late cancellations may incur a service call fee "
            "for reserved labor time and travel costs. If Provider has procured "
            "non-returnable materials for the job, Client shall reimburse those costs."
        ),
    },
    {
        "clause_type": "termination",
        "title": "Termination",
        "order": 8,
        "is_required": True,
        "is_conditional": False,
        "condition_description": "",
        "body": (
            "TERMINATION\n\n"
            "Either party may terminate for material breach not cured within 7 days "
            "of written notice. Provider may suspend work for non-payment or unsafe "
            "conditions. Upon termination, Client pays for all work satisfactorily "
            "completed and materials procured through the termination date. Warranty "
            "and liability provisions survive termination."
        ),
    },
]


class Command(BaseCommand):
    help = "Seed the database with initial ContractTemplate records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recreate templates even if they already exist.",
        )

    def handle(self, *args, **options):
        force = options["force"]
        self._seed_personal_training(force)
        self._seed_nutrition_coaching(force)
        self._seed_wellness_coaching(force)
        self._seed_academic_tutoring(force)
        self._seed_skills_coaching(force)
        self._seed_test_prep(force)
        self._seed_photography(force)
        self._seed_videography(force)
        self._seed_graphic_design(force)
        self._seed_beat_production(force)
        self._seed_recording_session(force)
        self._seed_dj_performance(force)
        self._seed_content_collaboration(force)
        self._seed_web_development(force)
        self._seed_mobile_development(force)
        self._seed_it_support(force)
        self._seed_software_consulting(force)
        self._seed_cybersecurity(force)
        self._seed_data_analytics(force)
        self._seed_lawn_care(force)
        self._seed_home_cleaning(force)
        self._seed_home_renovation(force)
        self._seed_plumbing(force)
        self._seed_electrical(force)
        self._seed_hvac(force)
        self._seed_painting(force)
        self._seed_moving_services(force)
        self._seed_handyman(force)
        self._seed_pest_control(force)
        self._seed_custom_fabrication(force)
        self._seed_general_repair(force)

    def _seed_personal_training(self, force):
        name = "Personal Training Agreement"

        if ContractTemplate.objects.filter(name=name).exists():
            if not force:
                self.stdout.write(
                    self.style.WARNING(f'Template "{name}" already exists. Use --force to recreate.')
                )
                return
            ContractTemplate.objects.filter(name=name).delete()
            self.stdout.write(self.style.WARNING(f'Deleted existing "{name}" for recreation.'))

        template = ContractTemplate.objects.create(
            category="health_wellness",
            subcategory="personal_training",
            name=name,
            description=(
                "A complete service agreement for personal trainers and their clients. "
                "Covers session scope, payment terms, cancellation policy, assumption of risk, "
                "package expiration, and termination. Suitable for in-person and virtual training."
            ),
            structure_type="ONE_TIME",
            is_active=True,
            tier_required="free",
        )

        for field_data in PERSONAL_TRAINING_GUIDED_FIELDS:
            TemplateGuidedField.objects.create(template=template, **field_data)

        for clause_data in PERSONAL_TRAINING_CLAUSES:
            TemplateClause.objects.create(template=template, **clause_data)

        TemplateObligationPattern.objects.create(
            template=template,
            obligation_type="both",
            frequency_type="per_session",
            payment_model_token="payment_model",
            amount_token="rate_per_session",
            installments_token="num_installments",
            interval_days_token="installment_interval_days",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'Seeded template "{name}" with '
                f'{len(PERSONAL_TRAINING_GUIDED_FIELDS)} guided fields and '
                f'{len(PERSONAL_TRAINING_CLAUSES)} clauses.'
            )
        )

    def _seed_nutrition_coaching(self, force):
        name = "Nutrition Coaching Agreement"

        if ContractTemplate.objects.filter(name=name).exists():
            if not force:
                self.stdout.write(
                    self.style.WARNING(f'Template "{name}" already exists. Use --force to recreate.')
                )
                return
            ContractTemplate.objects.filter(name=name).delete()
            self.stdout.write(self.style.WARNING(f'Deleted existing "{name}" for recreation.'))

        template = ContractTemplate.objects.create(
            category="health_wellness",
            subcategory="nutrition_coaching",
            name=name,
            description=(
                "A complete service agreement for nutrition coaches and their clients. "
                "Covers session scope, medical and dietary disclaimer, payment terms, "
                "cancellation policy, health information confidentiality, and termination. "
                "Suitable for in-person and online coaching engagements."
            ),
            structure_type="ONE_TIME",
            is_active=True,
            tier_required="free",
        )

        for field_data in NUTRITION_COACHING_GUIDED_FIELDS:
            TemplateGuidedField.objects.create(template=template, **field_data)

        for clause_data in NUTRITION_COACHING_CLAUSES:
            TemplateClause.objects.create(template=template, **clause_data)

        TemplateObligationPattern.objects.create(
            template=template,
            obligation_type="both",
            frequency_type="per_session",
            payment_model_token="payment_model",
            amount_token="rate_per_session",
            installments_token="num_sessions",
            interval_days_token="installment_interval_days",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'Seeded template "{name}" with '
                f'{len(NUTRITION_COACHING_GUIDED_FIELDS)} guided fields and '
                f'{len(NUTRITION_COACHING_CLAUSES)} clauses.'
            )
        )

    def _seed_wellness_coaching(self, force):
        name = "Wellness Coaching Agreement"

        if ContractTemplate.objects.filter(name=name).exists():
            if not force:
                self.stdout.write(
                    self.style.WARNING(f'Template "{name}" already exists. Use --force to recreate.')
                )
                return
            ContractTemplate.objects.filter(name=name).delete()
            self.stdout.write(self.style.WARNING(f'Deleted existing "{name}" for recreation.'))

        template = ContractTemplate.objects.create(
            category="health_wellness",
            subcategory="wellness_coaching",
            name=name,
            description=(
                "A complete service agreement for wellness coaches and their clients. "
                "Covers session scope, coaching vs. therapy disclaimer, confidentiality, "
                "payment terms, cancellation policy, no-guarantee clause, and termination. "
                "Suitable for stress management, life balance, mindfulness, and general "
                "wellness coaching delivered in-person or online."
            ),
            structure_type="ONE_TIME",
            is_active=True,
            tier_required="free",
        )

        for field_data in WELLNESS_COACHING_GUIDED_FIELDS:
            TemplateGuidedField.objects.create(template=template, **field_data)

        for clause_data in WELLNESS_COACHING_CLAUSES:
            TemplateClause.objects.create(template=template, **clause_data)

        TemplateObligationPattern.objects.create(
            template=template,
            obligation_type="both",
            frequency_type="per_session",
            payment_model_token="payment_model",
            amount_token="rate_per_session",
            installments_token="num_sessions",
            interval_days_token="installment_interval_days",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'Seeded template "{name}" with '
                f'{len(WELLNESS_COACHING_GUIDED_FIELDS)} guided fields and '
                f'{len(WELLNESS_COACHING_CLAUSES)} clauses.'
            )
        )

    # ------------------------------------------------------------------
    # EDUCATION & TUTORING — ACADEMIC TUTORING
    # ------------------------------------------------------------------

    def _seed_academic_tutoring(self, force):
        name = "Academic Tutoring Agreement"
        fields = ACADEMIC_TUTORING_GUIDED_FIELDS
        clauses = ACADEMIC_TUTORING_CLAUSES

        if ContractTemplate.objects.filter(name=name).exists():
            if not force:
                self.stdout.write(self.style.WARNING(f'Template "{name}" already exists. Use --force to recreate.'))
                return
            ContractTemplate.objects.filter(name=name).delete()
            self.stdout.write(self.style.WARNING(f'Deleted existing "{name}" for recreation.'))

        template = ContractTemplate.objects.create(
            category="education_tutoring",
            subcategory="academic_tutoring",
            name=name,
            description=(
                "A complete service agreement for academic tutors and their clients. "
                "Covers subject and session scope, independent contractor status, no-grade-guarantee "
                "disclaimer, tardiness and cancellation policies, confidentiality, and termination. "
                "Suitable for K–12, college, and professional academic subjects delivered "
                "in-person or online."
            ),
            structure_type="ONGOING",
            is_active=True,
            tier_required="free",
        )
        for f in fields:
            TemplateGuidedField.objects.create(template=template, **f)
        for c in clauses:
            TemplateClause.objects.create(template=template, **c)
        TemplateObligationPattern.objects.create(
            template=template,
            obligation_type="both",
            frequency_type="per_session",
            payment_model_token="payment_model",
            amount_token="rate_per_session",
            installments_token="num_sessions",
            interval_days_token="installment_interval_days",
        )
        self.stdout.write(self.style.SUCCESS(
            f'Seeded template "{name}" with {len(fields)} guided fields and {len(clauses)} clauses.'
        ))

    # ------------------------------------------------------------------
    # EDUCATION & TUTORING — SKILLS COACHING
    # ------------------------------------------------------------------

    def _seed_skills_coaching(self, force):
        name = "Skills Coaching Agreement"
        fields = SKILLS_COACHING_GUIDED_FIELDS
        clauses = SKILLS_COACHING_CLAUSES

        if ContractTemplate.objects.filter(name=name).exists():
            if not force:
                self.stdout.write(self.style.WARNING(f'Template "{name}" already exists. Use --force to recreate.'))
                return
            ContractTemplate.objects.filter(name=name).delete()
            self.stdout.write(self.style.WARNING(f'Deleted existing "{name}" for recreation.'))

        template = ContractTemplate.objects.create(
            category="education_tutoring",
            subcategory="skills_coaching",
            name=name,
            description=(
                "A complete service agreement for business, life, executive, and career coaches. "
                "Covers coaching scope, coaching vs. therapy disclaimer, no-guarantee clause, "
                "confidentiality, cancellation policy, independent contractor status, and "
                "termination. Suitable for ongoing professional and personal development engagements "
                "delivered in-person or online."
            ),
            structure_type="ONGOING",
            is_active=True,
            tier_required="free",
        )
        for f in fields:
            TemplateGuidedField.objects.create(template=template, **f)
        for c in clauses:
            TemplateClause.objects.create(template=template, **c)
        TemplateObligationPattern.objects.create(
            template=template,
            obligation_type="both",
            frequency_type="per_session",
            payment_model_token="payment_model",
            amount_token="rate_per_session",
            installments_token="num_sessions",
            interval_days_token="installment_interval_days",
        )
        self.stdout.write(self.style.SUCCESS(
            f'Seeded template "{name}" with {len(fields)} guided fields and {len(clauses)} clauses.'
        ))

    # ------------------------------------------------------------------
    # EDUCATION & TUTORING — TEST PREP
    # ------------------------------------------------------------------

    def _seed_test_prep(self, force):
        name = "Test Preparation Program Agreement"
        fields = TEST_PREP_GUIDED_FIELDS
        clauses = TEST_PREP_CLAUSES

        if ContractTemplate.objects.filter(name=name).exists():
            if not force:
                self.stdout.write(self.style.WARNING(f'Template "{name}" already exists. Use --force to recreate.'))
                return
            ContractTemplate.objects.filter(name=name).delete()
            self.stdout.write(self.style.WARNING(f'Deleted existing "{name}" for recreation.'))

        template = ContractTemplate.objects.create(
            category="education_tutoring",
            subcategory="test_prep",
            name=name,
            description=(
                "A complete service agreement for test preparation programs covering SAT, ACT, "
                "GRE, GMAT, professional certifications, and similar exams. Covers program scope, "
                "no-score-guarantee disclaimer, program completion and refund policy, cancellation "
                "policy, independent contractor status, confidentiality, and termination."
            ),
            structure_type="ONE_TIME",
            is_active=True,
            tier_required="free",
        )
        for f in fields:
            TemplateGuidedField.objects.create(template=template, **f)
        for c in clauses:
            TemplateClause.objects.create(template=template, **c)
        TemplateObligationPattern.objects.create(
            template=template,
            obligation_type="both",
            frequency_type="one_time",
            payment_model_token="payment_model",
            amount_token="total_program_price",
            installments_token="num_installments",
            interval_days_token="installment_interval_days",
        )
        self.stdout.write(self.style.SUCCESS(
            f'Seeded template "{name}" with {len(fields)} guided fields and {len(clauses)} clauses.'
        ))

    # ------------------------------------------------------------------
    # CREATIVE SERVICES — SHARED HELPER
    # ------------------------------------------------------------------

    def _create_creative_template(self, force, name, subcategory, description, fields, clauses, obligation_params):
        if ContractTemplate.objects.filter(name=name).exists():
            if not force:
                self.stdout.write(self.style.WARNING(
                    f'Template "{name}" already exists. Use --force to recreate.'
                ))
                return
            ContractTemplate.objects.filter(name=name).delete()
            self.stdout.write(self.style.WARNING(f'Deleted existing "{name}" for recreation.'))

        template = ContractTemplate.objects.create(
            category="creative_services",
            subcategory=subcategory,
            name=name,
            description=description,
            structure_type="ONE_TIME",
            is_active=True,
            tier_required="free",
        )
        for f in fields:
            TemplateGuidedField.objects.create(template=template, **f)
        for c in clauses:
            TemplateClause.objects.create(template=template, **c)
        TemplateObligationPattern.objects.create(template=template, **obligation_params)
        self.stdout.write(self.style.SUCCESS(
            f'Seeded template "{name}" with {len(fields)} guided fields and {len(clauses)} clauses.'
        ))

    # ------------------------------------------------------------------
    # CREATIVE SERVICES — PHOTOGRAPHY
    # ------------------------------------------------------------------

    def _seed_photography(self, force):
        self._create_creative_template(
            force=force,
            name="Photography Agreement",
            subcategory="photography",
            description=(
                "A professional photography service agreement covering event, portrait, "
                "commercial, and real estate photography. Includes scope, payment terms, "
                "copyright and usage rights, cancellation policy, and liability limitation."
            ),
            fields=PHOTOGRAPHY_GUIDED_FIELDS,
            clauses=PHOTOGRAPHY_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "one_time",
                "payment_model_token": "payment_model",
                "amount_token": "rate",
                "installments_token": "num_installments",
                "interval_days_token": "installment_interval_days",
            },
        )

    # ------------------------------------------------------------------
    # CREATIVE SERVICES — VIDEOGRAPHY
    # ------------------------------------------------------------------

    def _seed_videography(self, force):
        self._create_creative_template(
            force=force,
            name="Videography Agreement",
            subcategory="videography",
            description=(
                "A professional videography service agreement for event, commercial, music "
                "video, and social content production. Covers scope, deliverables, usage rights, "
                "revisions, cancellation, and liability."
            ),
            fields=VIDEOGRAPHY_GUIDED_FIELDS,
            clauses=VIDEOGRAPHY_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "one_time",
                "payment_model_token": "payment_model",
                "amount_token": "rate",
                "installments_token": "num_installments",
                "interval_days_token": "installment_interval_days",
            },
        )

    # ------------------------------------------------------------------
    # CREATIVE SERVICES — GRAPHIC DESIGN
    # ------------------------------------------------------------------

    def _seed_graphic_design(self, force):
        self._create_creative_template(
            force=force,
            name="Graphic Design Agreement",
            subcategory="graphic_design",
            description=(
                "A graphic design service agreement for logo & branding, social media graphics, "
                "website design, print materials, and illustration. Covers scope, revisions, "
                "IP assignment, payment, and client responsibilities."
            ),
            fields=GRAPHIC_DESIGN_GUIDED_FIELDS,
            clauses=GRAPHIC_DESIGN_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "one_time",
                "payment_model_token": "payment_model",
                "amount_token": "rate",
                "installments_token": "num_installments",
                "interval_days_token": "installment_interval_days",
            },
        )

    # ------------------------------------------------------------------
    # CREATIVE SERVICES — BEAT AND MUSIC PRODUCTION
    # ------------------------------------------------------------------

    def _seed_beat_production(self, force):
        self._create_creative_template(
            force=force,
            name="Beat and Music Production Agreement",
            subcategory="beat_production",
            description=(
                "A beat licensing and music production agreement between a producer and an artist. "
                "Covers non-exclusive lease, exclusive license, and full buyout arrangements, "
                "stems delivery, producer credits, distribution limits, and ownership."
            ),
            fields=BEAT_PRODUCTION_GUIDED_FIELDS,
            clauses=BEAT_PRODUCTION_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "one_time",
                "payment_model_token": "payment_model",
                "amount_token": "rate",
                "installments_token": "num_installments",
                "interval_days_token": "installment_interval_days",
            },
        )

    # ------------------------------------------------------------------
    # CREATIVE SERVICES — RECORDING AND SESSION SERVICES
    # ------------------------------------------------------------------

    def _seed_recording_session(self, force):
        self._create_creative_template(
            force=force,
            name="Recording and Session Services Agreement",
            subcategory="recording_session",
            description=(
                "A recording studio and engineering services agreement covering tracking, "
                "mixing, mastering, vocal production, and full production. Covers session "
                "conduct, IP ownership, engineer credit, and payment terms."
            ),
            fields=RECORDING_SESSION_GUIDED_FIELDS,
            clauses=RECORDING_SESSION_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "one_time",
                "payment_model_token": "payment_model",
                "amount_token": "rate",
                "installments_token": "num_installments",
                "interval_days_token": "installment_interval_days",
            },
        )

    # ------------------------------------------------------------------
    # CREATIVE SERVICES — DJ PERFORMANCE
    # ------------------------------------------------------------------

    def _seed_dj_performance(self, force):
        self._create_creative_template(
            force=force,
            name="DJ Performance Agreement",
            subcategory="dj_performance",
            description=(
                "A DJ performance agreement for weddings, corporate events, club nights, "
                "private parties, and festivals. Covers performance scope, equipment "
                "responsibilities, cancellation policy, and force majeure."
            ),
            fields=DJ_PERFORMANCE_GUIDED_FIELDS,
            clauses=DJ_PERFORMANCE_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "one_time",
                "payment_model_token": "payment_model",
                "amount_token": "rate",
                "installments_token": "",
                "interval_days_token": "",
            },
        )

    # ------------------------------------------------------------------
    # CREATIVE SERVICES — CONTENT COLLABORATION
    # ------------------------------------------------------------------

    def _seed_content_collaboration(self, force):
        self._create_creative_template(
            force=force,
            name="Content Collaboration Agreement",
            subcategory="content_collaboration",
            description=(
                "A content collaboration agreement between creators and brands covering "
                "sponsored posts, brand integrations, product reviews, co-creation, and "
                "affiliate campaigns. Supports paid flat-fee and revenue share models, "
                "with exclusivity, usage rights, approval process, and kill fee provisions."
            ),
            fields=CONTENT_COLLABORATION_GUIDED_FIELDS,
            clauses=CONTENT_COLLABORATION_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "one_time",
                "payment_model_token": "payment_model",
                "amount_token": "rate",
                "installments_token": "num_installments",
                "interval_days_token": "installment_interval_days",
            },
        )

    # ------------------------------------------------------------------
    # TECHNOLOGY SERVICES — SHARED HELPER
    # ------------------------------------------------------------------

    def _create_technology_template(
        self, force, name, subcategory, description, structure_type, fields, clauses, obligation_params
    ):
        if ContractTemplate.objects.filter(name=name).exists():
            if not force:
                self.stdout.write(self.style.WARNING(
                    f'Template "{name}" already exists. Use --force to recreate.'
                ))
                return
            ContractTemplate.objects.filter(name=name).delete()
            self.stdout.write(self.style.WARNING(f'Deleted existing "{name}" for recreation.'))

        template = ContractTemplate.objects.create(
            category="technology_services",
            subcategory=subcategory,
            name=name,
            description=description,
            structure_type=structure_type,
            is_active=True,
            tier_required="free",
        )
        for f in fields:
            TemplateGuidedField.objects.create(template=template, **f)
        for c in clauses:
            TemplateClause.objects.create(template=template, **c)
        TemplateObligationPattern.objects.create(template=template, **obligation_params)
        self.stdout.write(self.style.SUCCESS(
            f'Seeded template "{name}" with {len(fields)} guided fields and {len(clauses)} clauses.'
        ))

    # ------------------------------------------------------------------
    # TECHNOLOGY SERVICES — WEB DEVELOPMENT
    # ------------------------------------------------------------------

    def _seed_web_development(self, force):
        self._create_technology_template(
            force=force,
            name="Web Development Agreement",
            subcategory="web_development",
            description=(
                "A professional web development agreement covering websites, web applications, "
                "e-commerce stores, and landing pages. Includes scope, IP ownership, source "
                "code delivery, bug warranty, revision policy, payment terms, and cancellation "
                "kill fee."
            ),
            structure_type="ONE_TIME",
            fields=WEB_DEVELOPMENT_GUIDED_FIELDS,
            clauses=WEB_DEVELOPMENT_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "one_time",
                "payment_model_token": "payment_model",
                "amount_token": "total_fee",
                "installments_token": "num_installments",
                "interval_days_token": "installment_interval_days",
            },
        )

    # ------------------------------------------------------------------
    # TECHNOLOGY SERVICES — MOBILE APP DEVELOPMENT
    # ------------------------------------------------------------------

    def _seed_mobile_development(self, force):
        self._create_technology_template(
            force=force,
            name="Mobile App Development Agreement",
            subcategory="mobile_development",
            description=(
                "A professional mobile application development agreement for iOS, Android, "
                "or both platforms. Covers scope, IP ownership, source code delivery, app "
                "store submission, bug warranty, revision policy, payment terms, and "
                "cancellation kill fee."
            ),
            structure_type="ONE_TIME",
            fields=MOBILE_DEVELOPMENT_GUIDED_FIELDS,
            clauses=MOBILE_DEVELOPMENT_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "one_time",
                "payment_model_token": "payment_model",
                "amount_token": "total_fee",
                "installments_token": "num_installments",
                "interval_days_token": "installment_interval_days",
            },
        )

    # ------------------------------------------------------------------
    # TECHNOLOGY SERVICES — IT SUPPORT AND MAINTENANCE
    # ------------------------------------------------------------------

    def _seed_it_support(self, force):
        self._create_technology_template(
            force=force,
            name="IT Support and Maintenance Agreement",
            subcategory="it_support",
            description=(
                "An ongoing IT support and maintenance agreement covering remote, on-site, "
                "or hybrid support. Includes response time guarantee, confidentiality, "
                "payment terms, and cancellation policy. Suitable for small businesses and "
                "growing teams."
            ),
            structure_type="ONGOING",
            fields=IT_SUPPORT_GUIDED_FIELDS,
            clauses=IT_SUPPORT_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "monthly",
                "payment_model_token": "payment_model",
                "amount_token": "monthly_fee",
                "installments_token": "num_months",
                "interval_days_token": "",
            },
        )

    # ------------------------------------------------------------------
    # TECHNOLOGY SERVICES — SOFTWARE CONSULTING
    # ------------------------------------------------------------------

    def _seed_software_consulting(self, force):
        self._create_technology_template(
            force=force,
            name="Software Consulting Agreement",
            subcategory="software_consulting",
            description=(
                "A software consulting agreement for architecture reviews, technical advisory, "
                "code reviews, and fractional CTO engagements. Covers independent contractor "
                "status, confidentiality and NDA, non-solicitation, payment terms, and "
                "cancellation policy."
            ),
            structure_type="ONE_TIME",
            fields=SOFTWARE_CONSULTING_GUIDED_FIELDS,
            clauses=SOFTWARE_CONSULTING_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "one_time",
                "payment_model_token": "payment_model",
                "amount_token": "total_fee",
                "installments_token": "num_installments",
                "interval_days_token": "installment_interval_days",
            },
        )

    # ------------------------------------------------------------------
    # TECHNOLOGY SERVICES — CYBERSECURITY
    # ------------------------------------------------------------------

    def _seed_cybersecurity(self, force):
        self._create_technology_template(
            force=force,
            name="Cybersecurity Services Agreement",
            subcategory="cybersecurity",
            description=(
                "A cybersecurity services agreement for security audits, penetration testing, "
                "vulnerability assessments, and ongoing monitoring. Includes explicit client "
                "authorization, confidentiality and NDA, findings report delivery, limitation "
                "of liability, and payment terms."
            ),
            structure_type="ONE_TIME",
            fields=CYBERSECURITY_GUIDED_FIELDS,
            clauses=CYBERSECURITY_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "one_time",
                "payment_model_token": "payment_model",
                "amount_token": "total_fee",
                "installments_token": "",
                "interval_days_token": "",
            },
        )

    # ------------------------------------------------------------------
    # TECHNOLOGY SERVICES — DATA AND ANALYTICS
    # ------------------------------------------------------------------

    def _seed_data_analytics(self, force):
        self._create_technology_template(
            force=force,
            name="Data and Analytics Agreement",
            subcategory="data_analytics",
            description=(
                "A data and analytics services agreement covering data analysis, dashboard "
                "builds, reporting, and data strategy engagements. Includes data ownership "
                "and privacy terms, confidentiality, revision policy, payment terms, and "
                "cancellation policy."
            ),
            structure_type="ONE_TIME",
            fields=DATA_ANALYTICS_GUIDED_FIELDS,
            clauses=DATA_ANALYTICS_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "one_time",
                "payment_model_token": "payment_model",
                "amount_token": "total_fee",
                "installments_token": "num_installments",
                "interval_days_token": "installment_interval_days",
            },
        )

    # ------------------------------------------------------------------
    # MANUAL LABOR — shared helper
    # ------------------------------------------------------------------

    def _create_manual_labor_template(
        self, force, name, subcategory, description, structure_type, fields, clauses, obligation_params
    ):
        if ContractTemplate.objects.filter(name=name).exists():
            if not force:
                self.stdout.write(self.style.WARNING(
                    f'Template "{name}" already exists. Use --force to recreate.'
                ))
                return
            ContractTemplate.objects.filter(name=name).delete()
            self.stdout.write(self.style.WARNING(f'Deleted existing "{name}" for recreation.'))

        template = ContractTemplate.objects.create(
            category="manual_labor",
            subcategory=subcategory,
            name=name,
            description=description,
            structure_type=structure_type,
            is_active=True,
            tier_required="free",
        )
        for f in fields:
            TemplateGuidedField.objects.create(template=template, **f)
        for c in clauses:
            TemplateClause.objects.create(template=template, **c)
        TemplateObligationPattern.objects.create(template=template, **obligation_params)
        self.stdout.write(self.style.SUCCESS(
            f'Seeded template "{name}" with {len(fields)} guided fields and {len(clauses)} clauses.'
        ))

    # ------------------------------------------------------------------
    # MANUAL LABOR — LAWN CARE AND LANDSCAPING
    # ------------------------------------------------------------------

    def _seed_lawn_care(self, force):
        self._create_manual_labor_template(
            force=force,
            name="Lawn Care and Landscaping Agreement",
            subcategory="lawn_care",
            description=(
                "A lawn care and landscaping services agreement covering mowing, trimming, "
                "fertilization, and general yard maintenance. Includes materials and equipment "
                "terms, scheduling, payment model, and cancellation policy."
            ),
            structure_type="ONGOING",
            fields=LAWN_CARE_GUIDED_FIELDS,
            clauses=LAWN_CARE_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "per_session",
                "payment_model_token": "payment_model",
                "amount_token": "total_fee",
                "installments_token": "",
                "interval_days_token": "",
            },
        )

    # ------------------------------------------------------------------
    # MANUAL LABOR — HOME CLEANING SERVICE
    # ------------------------------------------------------------------

    def _seed_home_cleaning(self, force):
        self._create_manual_labor_template(
            force=force,
            name="Home Cleaning Service Agreement",
            subcategory="home_cleaning",
            description=(
                "A residential home cleaning services agreement covering regular or one-time "
                "cleaning visits. Includes scope of rooms and tasks, supplies, scheduling, "
                "per-visit or monthly payment model, and cancellation policy."
            ),
            structure_type="ONGOING",
            fields=HOME_CLEANING_GUIDED_FIELDS,
            clauses=HOME_CLEANING_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "per_session",
                "payment_model_token": "payment_model",
                "amount_token": "rate_per_visit",
                "installments_token": "",
                "interval_days_token": "",
            },
        )

    # ------------------------------------------------------------------
    # MANUAL LABOR — HOME RENOVATION AND REMODELING
    # ------------------------------------------------------------------

    def _seed_home_renovation(self, force):
        self._create_manual_labor_template(
            force=force,
            name="Home Renovation and Remodeling Agreement",
            subcategory="home_renovation",
            description=(
                "A home renovation and remodeling agreement covering scope of work, materials "
                "vs. labor breakdown, permit responsibility, change order approval, deposit or "
                "installment payment structure, and damage liability terms."
            ),
            structure_type="ONE_TIME",
            fields=HOME_RENOVATION_GUIDED_FIELDS,
            clauses=HOME_RENOVATION_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "one_time",
                "payment_model_token": "payment_model",
                "amount_token": "total_fee",
                "installments_token": "num_installments",
                "interval_days_token": "installment_interval_days",
            },
        )

    # ------------------------------------------------------------------
    # MANUAL LABOR — PLUMBING
    # ------------------------------------------------------------------

    def _seed_plumbing(self, force):
        self._create_manual_labor_template(
            force=force,
            name="Plumbing Services Agreement",
            subcategory="plumbing",
            description=(
                "A plumbing services agreement covering repair, installation, and maintenance "
                "work. Includes materials and parts breakdown, permit responsibility, deposit "
                "payment model, warranty terms, and damage liability."
            ),
            structure_type="ONE_TIME",
            fields=PLUMBING_GUIDED_FIELDS,
            clauses=PLUMBING_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "one_time",
                "payment_model_token": "payment_model",
                "amount_token": "total_fee",
                "installments_token": "deposit_percentage",
                "interval_days_token": "",
            },
        )

    # ------------------------------------------------------------------
    # MANUAL LABOR — ELECTRICAL WORK
    # ------------------------------------------------------------------

    def _seed_electrical(self, force):
        self._create_manual_labor_template(
            force=force,
            name="Electrical Work Agreement",
            subcategory="electrical",
            description=(
                "An electrical services agreement covering installation, repair, and inspection "
                "work. Includes permit responsibility, materials breakdown, deposit payment "
                "model, workmanship warranty, and liability terms."
            ),
            structure_type="ONE_TIME",
            fields=ELECTRICAL_GUIDED_FIELDS,
            clauses=ELECTRICAL_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "one_time",
                "payment_model_token": "payment_model",
                "amount_token": "total_fee",
                "installments_token": "deposit_percentage",
                "interval_days_token": "",
            },
        )

    # ------------------------------------------------------------------
    # MANUAL LABOR — HVAC AND AC REPAIR
    # ------------------------------------------------------------------

    def _seed_hvac(self, force):
        self._create_manual_labor_template(
            force=force,
            name="HVAC and AC Repair Agreement",
            subcategory="hvac",
            description=(
                "An HVAC and air conditioning services agreement covering installation, repair, "
                "and maintenance. Includes equipment and parts terms, deposit or monthly payment "
                "model, workmanship warranty, and service liability."
            ),
            structure_type="ONE_TIME",
            fields=HVAC_GUIDED_FIELDS,
            clauses=HVAC_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "one_time",
                "payment_model_token": "payment_model",
                "amount_token": "total_fee",
                "installments_token": "deposit_percentage",
                "interval_days_token": "",
            },
        )

    # ------------------------------------------------------------------
    # MANUAL LABOR — PAINTING (INTERIOR AND EXTERIOR)
    # ------------------------------------------------------------------

    def _seed_painting(self, force):
        self._create_manual_labor_template(
            force=force,
            name="Painting Services Agreement",
            subcategory="painting",
            description=(
                "A painting services agreement covering interior and exterior paint work. "
                "Includes materials vs. labor breakdown, surface preparation scope, deposit "
                "or installment payment structure, change order process, and warranty terms."
            ),
            structure_type="ONE_TIME",
            fields=PAINTING_GUIDED_FIELDS,
            clauses=PAINTING_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "one_time",
                "payment_model_token": "payment_model",
                "amount_token": "total_fee",
                "installments_token": "num_installments",
                "interval_days_token": "installment_interval_days",
            },
        )

    # ------------------------------------------------------------------
    # MANUAL LABOR — MOVING SERVICES
    # ------------------------------------------------------------------

    def _seed_moving_services(self, force):
        self._create_manual_labor_template(
            force=force,
            name="Moving Services Agreement",
            subcategory="moving_services",
            description=(
                "A moving services agreement covering residential or commercial relocation. "
                "Includes inventory and access terms, packing services, deposit payment model, "
                "damage liability, and cancellation policy."
            ),
            structure_type="ONE_TIME",
            fields=MOVING_SERVICES_GUIDED_FIELDS,
            clauses=MOVING_SERVICES_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "one_time",
                "payment_model_token": "payment_model",
                "amount_token": "total_fee",
                "installments_token": "deposit_percentage",
                "interval_days_token": "",
            },
        )

    # ------------------------------------------------------------------
    # MANUAL LABOR — GENERAL HANDYMAN
    # ------------------------------------------------------------------

    def _seed_handyman(self, force):
        self._create_manual_labor_template(
            force=force,
            name="General Handyman Agreement",
            subcategory="handyman",
            description=(
                "A general handyman services agreement covering miscellaneous repair, "
                "installation, and maintenance tasks. Includes materials and labor breakdown, "
                "flat fee or deposit payment model, scope of work, and liability terms."
            ),
            structure_type="ONE_TIME",
            fields=HANDYMAN_GUIDED_FIELDS,
            clauses=HANDYMAN_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "one_time",
                "payment_model_token": "payment_model",
                "amount_token": "total_fee",
                "installments_token": "deposit_percentage",
                "interval_days_token": "",
            },
        )

    # ------------------------------------------------------------------
    # MANUAL LABOR — PEST CONTROL
    # ------------------------------------------------------------------

    def _seed_pest_control(self, force):
        self._create_manual_labor_template(
            force=force,
            name="Pest Control Agreement",
            subcategory="pest_control",
            description=(
                "A pest control services agreement covering treatment for common household "
                "and commercial pests. Includes treatment method, chemicals disclosure, "
                "re-treatment guarantee, payment model, and cancellation policy."
            ),
            structure_type="ONGOING",
            fields=PEST_CONTROL_GUIDED_FIELDS,
            clauses=PEST_CONTROL_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "per_session",
                "payment_model_token": "payment_model",
                "amount_token": "total_fee",
                "installments_token": "",
                "interval_days_token": "",
            },
        )

    # ------------------------------------------------------------------
    # MANUAL LABOR — CUSTOM BUILD AND FABRICATION
    # ------------------------------------------------------------------

    def _seed_custom_fabrication(self, force):
        self._create_manual_labor_template(
            force=force,
            name="Custom Build and Fabrication Agreement",
            subcategory="custom_fabrication",
            description=(
                "A custom build and fabrication agreement for furniture, cabinetry, metalwork, "
                "and structural builds. Includes materials sourcing, milestone or installment "
                "payment structure, design approval process, change orders, and delivery terms."
            ),
            structure_type="ONE_TIME",
            fields=CUSTOM_FABRICATION_GUIDED_FIELDS,
            clauses=CUSTOM_FABRICATION_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "one_time",
                "payment_model_token": "payment_model",
                "amount_token": "total_contract_value",
                "installments_token": "num_installments",
                "interval_days_token": "installment_interval_days",
            },
        )

    # ------------------------------------------------------------------
    # MANUAL LABOR — GENERAL REPAIR
    # ------------------------------------------------------------------

    def _seed_general_repair(self, force):
        self._create_manual_labor_template(
            force=force,
            name="General Repair Agreement",
            subcategory="general_repair",
            description=(
                "A general repair services agreement covering appliance, structural, and "
                "equipment repair work. Includes diagnosis fee terms, parts and labor "
                "breakdown, deposit or flat fee payment model, and warranty terms."
            ),
            structure_type="ONE_TIME",
            fields=GENERAL_REPAIR_GUIDED_FIELDS,
            clauses=GENERAL_REPAIR_CLAUSES,
            obligation_params={
                "obligation_type": "both",
                "frequency_type": "one_time",
                "payment_model_token": "payment_model",
                "amount_token": "total_fee",
                "installments_token": "deposit_percentage",
                "interval_days_token": "",
            },
        )

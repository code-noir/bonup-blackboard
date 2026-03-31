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

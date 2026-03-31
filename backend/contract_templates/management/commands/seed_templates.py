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

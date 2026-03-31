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

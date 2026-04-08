# backend/contract_templates/management/commands/seed_obligation_payment_templates.py

from django.core.management.base import BaseCommand

from backend.contract_templates.models import (
    ContractTemplate,
    ObligationTemplate,
    PaymentTemplate,
)


class Command(BaseCommand):
    help = "Seed ObligationTemplate and PaymentTemplate records from existing contract templates."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-seed even if records already exist.",
        )

    def handle(self, *args, **options):
        force = options["force"]

        # ── 1. Extract from existing contract templates ──────────────────────
        self._extract_from_contract_templates(force)

        # ── 2. Seed standalone obligation templates ───────────────────────────
        self._seed_standalone_obligation_templates(force)

        # ── 3. Seed standalone payment templates ──────────────────────────────
        self._seed_standalone_payment_templates(force)

        self.stdout.write(self.style.SUCCESS("Done seeding obligation and payment templates."))

    # ── EXTRACTION ────────────────────────────────────────────────────────────

    def _extract_from_contract_templates(self, force):
        for ct in ContractTemplate.objects.filter(is_active=True).prefetch_related("clauses", "obligation_pattern"):
            scope_clauses = list(ct.clauses.filter(clause_type="scope"))
            payment_clauses = list(ct.clauses.filter(clause_type="payment"))

            for clause in scope_clauses:
                name = f"{ct.name} — Service Obligations"
                if ObligationTemplate.objects.filter(name=name).exists():
                    if not force:
                        continue
                    ObligationTemplate.objects.filter(name=name).delete()
                ObligationTemplate.objects.create(
                    name=name,
                    description=f"Service obligations and deliverables extracted from the {ct.name} template.",
                    content=clause.body,
                    category=ct.category,
                    contract_template=ct,
                )
                self.stdout.write(f"  Created obligation template: {name}")

            for clause in payment_clauses:
                name = f"{ct.name} — Payment Terms"
                if PaymentTemplate.objects.filter(name=name).exists():
                    if not force:
                        continue
                    PaymentTemplate.objects.filter(name=name).delete()

                # Infer schedule type from obligation pattern if available
                schedule_type = "one_time"
                try:
                    pattern = ct.obligation_pattern
                    freq_map = {
                        "installment": "installment",
                        "monthly": "recurring",
                        "weekly": "recurring",
                        "per_session": "one_time",
                        "one_time": "one_time",
                    }
                    schedule_type = freq_map.get(pattern.frequency_type, "one_time")
                except Exception:
                    pass

                PaymentTemplate.objects.create(
                    name=name,
                    description=f"Payment terms extracted from the {ct.name} template.",
                    content=clause.body,
                    schedule_type=schedule_type,
                    category=ct.category,
                    contract_template=ct,
                )
                self.stdout.write(f"  Created payment template: {name}")

    # ── STANDALONE OBLIGATION TEMPLATES ───────────────────────────────────────

    def _seed_standalone_obligation_templates(self, force):
        templates = [
            {
                "name": "Standard Weekly Service Obligation",
                "description": "General-purpose weekly service delivery obligation with reporting requirements.",
                "category": "Business",
                "content": (
                    "SCOPE OF SERVICES AND DELIVERABLES\n\n"
                    "Service Provider shall perform the following services on a weekly basis at the times and locations agreed upon by both parties. Each service visit shall be completed in a professional manner consistent with industry standards, and Service Provider shall maintain a written log of all work performed during each visit.\n\n"
                    "Weekly Deliverables:\n"
                    "(a) Perform all core service tasks as defined in Schedule A attached hereto;\n"
                    "(b) Document completed tasks and any observations in the service log;\n"
                    "(c) Report any issues, hazards, or material findings to Client within 24 hours of discovery;\n"
                    "(d) Confirm completion of each visit by submitting a digital or written service report to Client no later than the business day following each service date.\n\n"
                    "Quality Standards. All work shall be performed to a professional standard using appropriate materials, tools, and techniques. Service Provider shall correct any deficient work within five (5) business days of written notice from Client at no additional charge.\n\n"
                    "Access Requirements. Client shall provide Service Provider with necessary access to the service location on all scheduled service dates. If access is denied or the site is inaccessible through no fault of Service Provider, Client shall nonetheless pay the agreed service fee for that visit.\n\n"
                    "Service Modifications. Any changes to the scope of services must be agreed upon in writing by both parties prior to implementation. Verbal requests for additional work shall not constitute an amendment to this Agreement."
                ),
            },
            {
                "name": "Monthly Maintenance Obligation",
                "description": "Monthly recurring maintenance and inspection obligation with deliverable checklist.",
                "category": "Business",
                "content": (
                    "MONTHLY MAINTENANCE OBLIGATIONS\n\n"
                    "Service Provider shall perform the following maintenance services on a monthly basis, no later than the fifth (5th) business day of each calendar month, or at a mutually agreed-upon time within that month:\n\n"
                    "Month 1 – 3 (Initial Service Period):\n"
                    "(a) Complete baseline assessment and document existing conditions;\n"
                    "(b) Perform all scheduled maintenance tasks as listed in the attached Service Schedule;\n"
                    "(c) Identify any deferred maintenance items requiring attention;\n"
                    "(d) Deliver written inspection report to Client within three (3) business days of each visit.\n\n"
                    "Month 4 – 12 (Ongoing Service Period):\n"
                    "(a) Perform all routine maintenance per the established schedule;\n"
                    "(b) Compare current condition against baseline documentation and report any changes;\n"
                    "(c) Recommend any preventive or corrective actions to Client in writing;\n"
                    "(d) Confirm all warranty and safety requirements remain satisfied.\n\n"
                    "Annual Review. At the end of each contract year, Service Provider shall prepare a comprehensive service summary documenting all work performed, any issues identified, and recommendations for the upcoming contract year. This summary shall be delivered to Client no later than fifteen (15) days before the contract anniversary date.\n\n"
                    "Emergency Response. Service Provider shall respond to emergency service requests within [EMERGENCY_RESPONSE_HOURS] hours of notification. Emergency calls outside normal business hours may be subject to additional fees as outlined in the compensation schedule."
                ),
            },
            {
                "name": "Project Milestone Obligation",
                "description": "Milestone-based project delivery obligation with acceptance criteria.",
                "category": "Business",
                "content": (
                    "PROJECT MILESTONES AND DELIVERABLES\n\n"
                    "Service Provider shall complete the project in the following phases, with each milestone requiring written acceptance from Client before the next phase begins. Acceptance shall not be unreasonably withheld or delayed.\n\n"
                    "Milestone 1 — Discovery and Planning (Due: [MILESTONE_1_DATE]):\n"
                    "Service Provider shall deliver a written project plan including scope confirmation, resource allocation, timeline, and risk assessment. Client shall review and provide written acceptance or itemized feedback within five (5) business days of delivery.\n\n"
                    "Milestone 2 — Development Phase (Due: [MILESTONE_2_DATE]):\n"
                    "Service Provider shall deliver the core work product in draft or functional form for Client review. Service Provider shall address Client's reasonable revision requests within ten (10) business days of receiving consolidated written feedback.\n\n"
                    "Milestone 3 — Review and Revision (Due: [MILESTONE_3_DATE]):\n"
                    "Service Provider shall incorporate approved revisions and deliver a revised work product. Client may request one (1) additional round of revisions at no additional charge. Additional revision rounds beyond that shall be billed at Service Provider's standard hourly rate.\n\n"
                    "Milestone 4 — Final Delivery (Due: [MILESTONE_4_DATE]):\n"
                    "Service Provider shall deliver the final work product in the agreed format, along with all supporting documentation, source files, and transfer of applicable rights as specified in this Agreement.\n\n"
                    "Acceptance Criteria. Client shall not withhold acceptance based on subjective preferences not reflected in the original project requirements. Any acceptance dispute shall be resolved pursuant to the dispute resolution provisions of this Agreement.\n\n"
                    "Delay Notification. Service Provider shall notify Client in writing at least five (5) business days before any missed milestone date, including the cause of delay and a revised completion date."
                ),
            },
            {
                "name": "Personal Loan Repayment Obligation",
                "description": "Borrower's repayment obligations under a personal loan agreement.",
                "category": "Personal",
                "content": (
                    "BORROWER'S REPAYMENT OBLIGATIONS\n\n"
                    "Borrower unconditionally promises to pay to Lender, or to Lender's order, the Principal Amount together with all accrued interest thereon, in accordance with the following schedule and obligations:\n\n"
                    "Regular Payments. Borrower shall make [NUMBER_OF_PAYMENTS] consecutive monthly installment payments of $[MONTHLY_PAYMENT] each, commencing on [FIRST_PAYMENT_DATE] and continuing on the same calendar day of each subsequent month until the loan is fully repaid. Each payment shall be applied first to accrued interest, then to the outstanding principal balance.\n\n"
                    "Payment Method. All payments shall be made by [PAYMENT_METHOD] to Lender at [LENDER_PAYMENT_ADDRESS], or to such other address as Lender may designate in writing with at least ten (10) days' advance notice. Borrower shall retain proof of each payment for a period of not less than seven (7) years.\n\n"
                    "Interest Accrual. Interest shall accrue daily on the outstanding principal balance at the annual rate of [INTEREST_RATE]%, computed on the basis of a 365-day year. Interest shall be calculated on the actual number of days elapsed from the disbursement date to the date of each payment.\n\n"
                    "Prepayment. Borrower may prepay the outstanding balance, in whole or in part, at any time without penalty. Any prepayment shall be applied first to accrued interest and then to the principal balance in inverse order of maturity. Prepayment shall not relieve Borrower of the obligation to make regularly scheduled payments unless the loan is paid in full.\n\n"
                    "Record of Payments. Lender shall maintain an accurate ledger of all amounts received and shall, upon Borrower's written request, provide a statement of the outstanding balance and payment history within ten (10) business days of such request at no charge to Borrower."
                ),
            },
            {
                "name": "Lawn Care Monthly Service Obligation",
                "description": "Monthly lawn care service obligations with visit-by-visit deliverable breakdown.",
                "category": "Business",
                "content": (
                    "LAWN CARE SERVICE OBLIGATIONS — MONTHLY BREAKDOWN\n\n"
                    "Service Provider shall perform the following services at the Property located at [PROPERTY_ADDRESS]. All services shall be performed by trained and licensed personnel using professional-grade equipment maintained in good working order.\n\n"
                    "Each Scheduled Visit (regardless of frequency) shall include:\n"
                    "(a) Mowing all turf areas to a height of 2.5 to 3.5 inches, adjusted seasonally;\n"
                    "(b) String trimming along all hardscaped edges, fences, tree bases, and planting beds;\n"
                    "(c) Edging along all concrete or paved surfaces to maintain clean separation;\n"
                    "(d) Blowing all clippings, debris, and leaves from driveways, walkways, patios, and hard surfaces;\n"
                    "(e) Visual inspection of turf and plant health with verbal report to Client's on-site representative.\n\n"
                    "Monthly Obligations (in addition to each visit):\n"
                    "(a) Inspect irrigation system heads and report any broken or misaligned heads to Client in writing;\n"
                    "(b) Remove accumulated debris and leaf litter from all planting beds;\n"
                    "(c) Spot-treat visible broadleaf weeds in turf with appropriate licensed herbicide;\n"
                    "(d) Prune shrubs and ornamental grasses to maintain their natural form and remove dead wood;\n"
                    "(e) Submit a written monthly service report by the 5th of the following month.\n\n"
                    "Seasonal Obligations:\n"
                    "Spring (March–May): Aeration and overseeding as scheduled; pre-emergent weed treatment; fertilizer application per the approved lawn care program.\n"
                    "Summer (June–August): Deep-watering coordination with Client's irrigation schedule; heat stress monitoring and reporting.\n"
                    "Fall (September–November): Leaf removal and disposal; core aeration; winterizing fertilizer application.\n"
                    "Winter (December–February): As-needed cleanup visits; debris removal following storm events.\n\n"
                    "Service Confirmation. Service Provider shall leave a door hanger or digital confirmation at the Property after each visit documenting the date, services performed, and any observations or recommendations."
                ),
            },
        ]

        for t in templates:
            name = t["name"]
            if ObligationTemplate.objects.filter(name=name).exists():
                if not force:
                    self.stdout.write(f"  Skipping (exists): {name}")
                    continue
                ObligationTemplate.objects.filter(name=name).delete()
            ObligationTemplate.objects.create(
                name=name,
                description=t["description"],
                content=t["content"],
                category=t["category"],
                contract_template=None,
            )
            self.stdout.write(f"  Created standalone obligation template: {name}")

    # ── STANDALONE PAYMENT TEMPLATES ──────────────────────────────────────────

    def _seed_standalone_payment_templates(self, force):
        templates = [
            {
                "name": "Net-30 Invoice Payment Terms",
                "description": "Standard net-30 payment terms for professional services.",
                "schedule_type": "recurring",
                "category": "Business",
                "content": (
                    "PAYMENT TERMS — NET 30\n\n"
                    "Client shall pay all invoices issued by Service Provider within thirty (30) calendar days of the invoice date (\"Net 30\"). Invoices shall be submitted electronically to [CLIENT_BILLING_EMAIL] or by first-class mail to the billing address specified in this Agreement.\n\n"
                    "Invoice Contents. Each invoice shall include: (a) invoice number and date; (b) description of services rendered; (c) service period covered; (d) itemized fees; (e) total amount due; and (f) payment instructions including acceptable payment methods.\n\n"
                    "Late Payment. Any amount not paid within thirty (30) days of the invoice date shall accrue interest at the rate of one and one-half percent (1.5%) per month (18% per annum), or the maximum rate permitted by applicable law, whichever is lower, calculated from the due date until the date of actual payment. A late fee of $25.00 shall also be assessed on any invoice more than ten (10) days past due.\n\n"
                    "Payment Methods. Client may pay by ACH bank transfer, check payable to [SERVICE_PROVIDER_NAME], or credit card (subject to a processing fee of 2.9%). Wire transfers are also accepted for amounts exceeding $5,000.\n\n"
                    "Disputed Invoices. Client shall notify Service Provider in writing of any disputed invoice amount within ten (10) days of receipt. Client shall pay undisputed amounts by the due date. Disputes shall be resolved pursuant to the dispute resolution provisions of this Agreement. Client's failure to timely dispute an invoice shall constitute acceptance of the invoiced amount.\n\n"
                    "Suspension for Non-Payment. Service Provider reserves the right to suspend services upon sixty (60) days of non-payment after the due date, without liability to Client, provided that Service Provider has given Client at least ten (10) days' written notice of its intent to suspend."
                ),
            },
            {
                "name": "Installment Payment Schedule — Personal Loan",
                "description": "Monthly installment payment terms for personal loans with late fee and default provisions.",
                "schedule_type": "installment",
                "category": "Personal",
                "content": (
                    "PAYMENT SCHEDULE AND TERMS\n\n"
                    "Borrower shall repay the total amount due under this Agreement in [NUMBER_OF_PAYMENTS] equal monthly installments as follows:\n\n"
                    "Payment Schedule:\n"
                    "  Payment 1:   $[MONTHLY_PAYMENT]   Due: [PAYMENT_1_DATE]\n"
                    "  Payment 2:   $[MONTHLY_PAYMENT]   Due: [PAYMENT_2_DATE]\n"
                    "  Payment 3:   $[MONTHLY_PAYMENT]   Due: [PAYMENT_3_DATE]\n"
                    "  ...          (continuing monthly)\n"
                    "  Final Payment: $[FINAL_PAYMENT]   Due: [FINAL_PAYMENT_DATE]\n\n"
                    "Each payment shall be due on the [PAYMENT_DAY]th day of each month. Payments shall be applied first to any outstanding late fees, then to accrued interest, then to principal.\n\n"
                    "Grace Period. Borrower shall have a grace period of ten (10) calendar days after each due date before a late fee is assessed. If full payment is received within the ten-day grace period, no late fee shall be charged.\n\n"
                    "Late Fee. If any payment is not received in full within ten (10) days of its due date, Borrower shall immediately pay a late fee equal to the greater of: (a) $25.00; or (b) five percent (5%) of the overdue installment amount. Late fees shall be added to the outstanding balance and shall not be applied to reduce the principal.\n\n"
                    "Default. Borrower shall be in default if: (a) any payment remains unpaid for more than thirty (30) days after its due date; (b) Borrower becomes insolvent or makes an assignment for the benefit of creditors; (c) Borrower files for bankruptcy protection; or (d) Borrower breaches any material provision of this Agreement. Upon default, Lender may declare the entire outstanding balance immediately due and payable, and may pursue all legal remedies available. Borrower shall be responsible for all reasonable collection costs and attorney's fees incurred by Lender in connection with any default."
                ),
            },
            {
                "name": "Project Milestone Payment Schedule",
                "description": "Payment tied to project milestones with holdback and final acceptance provisions.",
                "schedule_type": "milestone",
                "category": "Business",
                "content": (
                    "PROJECT PAYMENT SCHEDULE\n\n"
                    "Client shall make payments to Service Provider in accordance with the following milestone schedule. All payments are due within seven (7) calendar days of written acceptance of each milestone or the date specified below, whichever is earlier.\n\n"
                    "Deposit (Due upon execution of this Agreement):\n"
                    "Amount: $[DEPOSIT_AMOUNT] ([DEPOSIT_PERCENT]% of total contract value)\n"
                    "Purpose: Covers project initiation, planning, and initial resource allocation.\n\n"
                    "Milestone 1 Payment (Due upon completion of [MILESTONE_1_NAME]):\n"
                    "Amount: $[MILESTONE_1_AMOUNT] ([MILESTONE_1_PERCENT]% of total contract value)\n"
                    "Due Date: [MILESTONE_1_DUE_DATE]\n\n"
                    "Milestone 2 Payment (Due upon completion of [MILESTONE_2_NAME]):\n"
                    "Amount: $[MILESTONE_2_AMOUNT] ([MILESTONE_2_PERCENT]% of total contract value)\n"
                    "Due Date: [MILESTONE_2_DUE_DATE]\n\n"
                    "Final Payment (Due upon Client's written acceptance of final deliverable):\n"
                    "Amount: $[FINAL_PAYMENT_AMOUNT] ([FINAL_PAYMENT_PERCENT]% of total contract value)\n"
                    "Due Date: Within seven (7) days of final acceptance\n\n"
                    "Holdback. Client may withhold up to ten percent (10%) of each milestone payment as a holdback, to be released within thirty (30) days of final project acceptance. The holdback shall not be withheld due to items unrelated to Service Provider's performance.\n\n"
                    "Disputed Milestone. If Client disputes whether a milestone has been completed, Client shall provide written notice within five (5) business days of the milestone due date, specifically identifying all deficiencies. Service Provider shall have ten (10) business days to cure any identified deficiencies. If Client fails to provide timely written notice, the milestone shall be deemed accepted and payment shall become due.\n\n"
                    "Late Payment Interest. Any payment not made by its due date shall bear interest at the rate of 1.5% per month (18% per annum) from the due date until paid."
                ),
            },
            {
                "name": "Recurring Monthly Retainer Payment",
                "description": "Monthly retainer payment terms for ongoing service relationships.",
                "schedule_type": "recurring",
                "category": "Business",
                "content": (
                    "MONTHLY RETAINER PAYMENT TERMS\n\n"
                    "In consideration of the services to be performed under this Agreement, Client agrees to pay Service Provider a monthly retainer fee of $[MONTHLY_RETAINER] (\"Retainer Fee\"), payable in advance on the first (1st) day of each calendar month throughout the term of this Agreement.\n\n"
                    "First Payment. The first Retainer Fee payment of $[MONTHLY_RETAINER] is due and payable upon execution of this Agreement, covering the initial month of service. Subsequent payments shall be due on the first of each following month.\n\n"
                    "Retainer Coverage. The monthly Retainer Fee covers up to [INCLUDED_HOURS] hours of service per month. Any hours exceeding the retainer allowance shall be billed at Service Provider's standard hourly rate of $[HOURLY_RATE] per hour, invoiced monthly with net-15 payment terms.\n\n"
                    "Unused Hours. Unused retainer hours shall not carry over from month to month and shall not be refundable, unless otherwise agreed in writing.\n\n"
                    "Annual Adjustment. Service Provider may adjust the Retainer Fee upon thirty (30) days' written notice, but not more than once per calendar year and not by more than [MAX_INCREASE_PERCENT]% above the then-current rate. Client may terminate this Agreement within the 30-day notice period without penalty if Client does not agree to the adjusted rate.\n\n"
                    "Auto-Payment. Client authorizes Service Provider to charge the Retainer Fee automatically to Client's [PAYMENT_METHOD] on file on the first of each month. Client shall maintain valid payment credentials on file at all times during the term of this Agreement. Service Provider shall provide a receipt for each auto-payment within two (2) business days of processing."
                ),
            },
            {
                "name": "Flat-Fee One-Time Payment",
                "description": "Simple flat-fee one-time payment terms for project-based work.",
                "schedule_type": "one_time",
                "category": "Business",
                "content": (
                    "ONE-TIME PAYMENT TERMS\n\n"
                    "In full consideration for the services and deliverables provided under this Agreement, Client shall pay Service Provider a flat fee of $[TOTAL_FEE] (the \"Project Fee\"). The Project Fee is all-inclusive and covers all labor, standard materials, and reasonable expenses necessary to complete the work as described in this Agreement, unless additional services or out-of-pocket expenses exceeding $[EXPENSE_THRESHOLD] are approved in advance in writing by Client.\n\n"
                    "Payment Schedule:\n"
                    "  Deposit:        $[DEPOSIT_AMOUNT]   Due upon execution of this Agreement\n"
                    "  Final Payment:  $[BALANCE_DUE]     Due upon delivery of final work product\n\n"
                    "The Deposit is non-refundable once Service Provider has commenced work. The final payment is due within seven (7) calendar days of Service Provider's written notice that the final deliverable is ready for acceptance.\n\n"
                    "Expenses. If this Agreement requires pre-approved out-of-pocket expenses (such as travel, third-party licenses, or specialized materials), Client shall reimburse Service Provider within fourteen (14) days of receiving an itemized expense report with supporting receipts. Expenses exceeding the approved amount require additional written approval.\n\n"
                    "Payment Methods. Accepted payment methods include ACH bank transfer, business check, or credit card (subject to a 2.9% processing fee). Cash is not accepted.\n\n"
                    "Work Product Delivery. Service Provider is not obligated to deliver the final work product until the final payment has been received in full. Service Provider shall hold the completed work product for up to thirty (30) days pending receipt of final payment."
                ),
            },
        ]

        for t in templates:
            name = t["name"]
            if PaymentTemplate.objects.filter(name=name).exists():
                if not force:
                    self.stdout.write(f"  Skipping (exists): {name}")
                    continue
                PaymentTemplate.objects.filter(name=name).delete()
            PaymentTemplate.objects.create(
                name=name,
                description=t["description"],
                content=t["content"],
                schedule_type=t["schedule_type"],
                category=t["category"],
                contract_template=None,
            )
            self.stdout.write(f"  Created standalone payment template: {name}")

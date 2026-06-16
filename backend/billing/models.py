"""Billing models: a run fans out into one Invoice per (company × freelancer),
each freezing the timesheet entries it bills as immutable line items.

The monthly run is just a *trigger*; every run sweeps all approved, not-yet-billed
entries dated on or before the period end, so nothing is ever left behind.
"""

import logging

from django.db import models, transaction

from accounts.models import Company, Freelancer
from contracts.models import Contract, TimesheetEntry

from .dates import end_of_month

logger = logging.getLogger(__name__)


class BillingRun(models.Model):
    """One execution of the billing run. `company` is null for a system-wide
    (Beat) run and set for a single-company run from the button."""

    class Status(models.TextChoices):
        RUNNING = 'running', 'Running'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    company = models.ForeignKey(Company, on_delete=models.PROTECT, null=True, blank=True,
                                related_name='billing_runs')   # null = system-wide (Beat)
    period = models.DateField()                                # 1st of the billing month
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RUNNING)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        scope = self.company.name if self.company_id else 'all companies'
        return f'BillingRun {self.pk} — {self.period:%Y-%m} ({scope}, {self.status})'

    @classmethod
    def generate(cls, period, company=None):
        """Bill every approved, not-yet-billed entry dated on/before `period` end
        into invoices. company=None → all companies (Beat); company=X → just that
        company (the button). Returns (run, invoices_created)."""
        # Imported here, not at module top, to avoid the billing.models ↔ billing.tasks
        # import cycle.
        from .tasks import send_invoice_email

        run = cls.objects.create(period=period, company=company)
        scope = company.name if company is not None else 'all companies'
        logger.info('Billing run %s started: period=%s, scope=%s', run.id, period, scope)

        contracts = Contract.objects.select_related('company', 'freelancer')
        if company is not None:
            contracts = contracts.filter(company=company)

        count = 0
        failed = 0
        for contract in contracts:
            # Approved, not yet on any invoice (line_items__isnull), dated on/before the
            # cutoff — one predicate gives both 'billed once' and 'nothing left behind'.
            entries = (contract.timesheet_entries
                       .filter(status=TimesheetEntry.STATUS_APPROVED, line_items__isnull=True,
                               date__lte=end_of_month(period))
                       .select_related('contract').order_by('date'))
            if not entries:
                continue
            try:
                with transaction.atomic():                     # one invoice per txn
                    invoice = Invoice.objects.create(
                        billing_run=run, company=contract.company, freelancer=contract.freelancer,
                        period=period, subtotal=sum(e.cost for e in entries),
                    )
                    InvoiceLineItem.objects.bulk_create([
                        InvoiceLineItem(invoice=invoice, timesheet_entry=e, date=e.date, hours=e.hours,
                                        rate=contract.daily_rate, amount=e.cost)
                        for e in entries
                    ])
                    transaction.on_commit(lambda inv=invoice: send_invoice_email.delay(inv.id))
                count += 1
            except Exception:   # one contract's failure must not sink the rest of the batch
                failed += 1
                logger.exception('Billing run %s: failed to bill contract %s', run.id, contract.id)
                continue
        run.status = cls.Status.COMPLETED
        run.save(update_fields=['status'])
        logger.info('Billing run %s completed: %s billed, %s failed', run.id, count, failed)
        return run, count


class Invoice(models.Model):
    """Per company × freelancer for a period. An invoice existing *means* it is
    issued — the draft/issue/void lifecycle is deliberately deferred. `email_status`
    is the only lifecycle: the financial record never depends on the notification."""

    class EmailStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'

    billing_run = models.ForeignKey(BillingRun, on_delete=models.PROTECT, related_name='invoices')
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='invoices')
    freelancer = models.ForeignKey(Freelancer, on_delete=models.PROTECT, related_name='invoices')
    period = models.DateField()                                # billing month (= run.period)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    email_status = models.CharField(max_length=10, choices=EmailStatus.choices, default=EmailStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    entries = models.ManyToManyField('contracts.TimesheetEntry', through='InvoiceLineItem',
                                     related_name='invoices')

    def __str__(self):
        return f'Invoice {self.pk} — {self.freelancer_id} @ {self.company_id} ({self.period:%Y-%m})'

    def as_plaintext(self):
        """Plaintext line-items + total — the stand-in 'document' the invoice email carries."""
        lines = [
            f'Invoice — {self.company.name}',
            f'Freelancer: {self.freelancer.name}',
            f'Period: {self.period:%B %Y}',
            '',
            f'{"Date":<12} {"Hours":>7} {"Rate":>10} {"Amount":>12}',
        ]
        for li in sorted(self.line_items.all(), key=lambda x: x.date):
            lines.append(f'{li.date:%Y-%m-%d} {li.hours:>7} {li.rate:>10} {li.amount:>12}')
        lines += ['', f'Total: {self.subtotal}']
        return '\n'.join(lines)


class InvoiceLineItem(models.Model):
    """M2M through: the TimesheetEntries an Invoice bills, with a frozen snapshot
    so a later contract-rate change never mutates a past invoice."""

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='line_items')
    timesheet_entry = models.ForeignKey('contracts.TimesheetEntry', on_delete=models.PROTECT,
                                        related_name='line_items')
    date = models.DateField()
    hours = models.DecimalField(max_digits=5, decimal_places=2)
    rate = models.DecimalField(max_digits=8, decimal_places=2)    # contract.daily_rate, frozen
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f'{self.date} — {self.hours}h @ {self.rate} = {self.amount}'

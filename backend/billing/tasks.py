"""Async billing side-effects.

Email is a side-effect of an invoice, never part of its transaction: the invoice
is the source of truth and must commit independently. The run fires these tasks
from `transaction.on_commit`, so they only ever run against a committed invoice.
"""

import logging

from celery import shared_task
from django.core.mail import send_mail

from .dates import first_of_this_month
from .models import BillingRun, Invoice

logger = logging.getLogger(__name__)


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3})
def send_invoice_email(invoice_id):
    """Email the invoice to the company billing address and the freelancer.

    On failure the invoice is marked `failed` and the task retries with backoff;
    the committed invoice is never affected. `email_status` tracks the outcome.
    """
    invoice = (Invoice.objects
               .select_related('company', 'freelancer__user')
               .prefetch_related('line_items')
               .get(pk=invoice_id))

    recipients = [invoice.company.billing_email]
    if invoice.freelancer.user.email:
        recipients.append(invoice.freelancer.user.email)

    subject = f'Invoice for {invoice.freelancer.name} — {invoice.period:%B %Y}'
    try:
        send_mail(subject, invoice.as_plaintext(), None, recipients, fail_silently=False)
    except Exception:
        Invoice.objects.filter(pk=invoice_id).update(email_status=Invoice.EmailStatus.FAILED)
        logger.exception('Invoice %s email failed', invoice_id)
        raise   # autoretry_for retries with backoff; status stays `failed` if exhausted

    Invoice.objects.filter(pk=invoice_id).update(email_status=Invoice.EmailStatus.SENT)


@shared_task
def run_monthly_billing():
    """Scheduled (Celery Beat, 1st of month): one system-wide run across all companies."""
    run, count = BillingRun.generate(first_of_this_month(), company=None)
    logger.info('Monthly billing run %s generated %s invoice(s)', run.id, count)

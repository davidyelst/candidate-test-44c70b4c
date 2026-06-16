"""Tests for the billing run, concentrated on what the brief grades Task B on: the
end-to-end path (run → invoice with snapshot line items + total), idempotency (a re-run
bills nothing already billed), and the transaction boundary (an email that fails *after*
the invoice commits flags it without rolling it back). Broader CRUD/permission coverage
is scoped out for the time-box and enumerated in CANDIDATE_NOTES.md.
"""

import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from billing.models import BillingRun, Invoice
from billing.tasks import send_invoice_email

PERIOD = datetime.date(2026, 4, 1)


@pytest.mark.django_db
def test_run_generates_invoice_with_snapshot_lines_and_total(active_contract, make_entry):
    """The core path: approved entries → one invoice, with the contract rate and computed
    amount frozen onto immutable line items, and the subtotal summed."""
    make_entry(active_contract, datetime.date(2026, 4, 7), '8.0')
    make_entry(active_contract, datetime.date(2026, 4, 8), '7.5')

    run, count = BillingRun.generate(PERIOD, company=active_contract.company)

    assert count == 1
    invoice = Invoice.objects.get()
    assert invoice.billing_run == run
    assert invoice.line_items.count() == 2
    # 8.0*600/8 + 7.5*600/8 = 600.00 + 562.50
    assert invoice.subtotal == Decimal('1162.50')
    # the contract rate is frozen onto each line item
    assert {li.rate for li in invoice.line_items.all()} == {Decimal('600.00')}


@pytest.mark.django_db
def test_rerun_bills_nothing_already_billed(active_contract, make_entry):
    """Idempotency: the run selects approved entries not yet on any invoice
    (`line_item__isnull=True`), so a second run over the same period finds nothing left
    and creates no further invoice. (Late approvals would still be picked up next run.)"""
    make_entry(active_contract, datetime.date(2026, 4, 7), '8.0')

    _, first = BillingRun.generate(PERIOD, company=active_contract.company)
    _, second = BillingRun.generate(PERIOD, company=active_contract.company)

    assert (first, second) == (1, 0)
    assert Invoice.objects.count() == 1


@pytest.mark.django_db
@patch('billing.tasks.send_mail', side_effect=Exception('smtp unavailable'))
def test_email_failure_after_commit_flags_invoice_without_rolling_it_back(
    mock_send, active_contract, make_entry
):
    """The brief's transaction-boundary question. The invoice is the source of truth and
    commits independently of the notification; a send that fails *after* it commits flags
    `email_status=failed` and re-raises (so Celery retries), but the invoice row stays."""
    make_entry(active_contract, datetime.date(2026, 4, 7), '8.0')
    BillingRun.generate(PERIOD, company=active_contract.company)
    invoice = Invoice.objects.get()

    with pytest.raises(Exception):
        send_invoice_email.run(invoice.id)

    invoice.refresh_from_db()
    assert invoice.email_status == Invoice.EmailStatus.FAILED   # flagged…
    assert Invoice.objects.filter(pk=invoice.pk).exists()       # …never rolled back

"""A single, representative test — a deliberate demonstration of the testing approach,
not a suite. It runs the billing path end-to-end (a run produces an invoice with the
right snapshot line items and total); the rest of the coverage is scoped out for the
time-box and enumerated in CANDIDATE_NOTES.md.
"""

import datetime
from decimal import Decimal

import pytest

from billing.models import BillingRun, Invoice

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

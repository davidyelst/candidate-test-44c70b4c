"""Billing-test helpers, layered on the root conftest fixtures
(northstar / meridian / admin_client / freelancer_client / active_contract / other_contract)."""

from decimal import Decimal

import pytest

from contracts.models import TimesheetEntry


@pytest.fixture
def make_entry():
    """Factory: create a timesheet entry (approved + 8h by default)."""
    def _make(contract, day, hours='8.0', status=TimesheetEntry.STATUS_APPROVED):
        return TimesheetEntry.objects.create(
            contract=contract, date=day, hours=Decimal(hours), status=status,
        )
    return _make

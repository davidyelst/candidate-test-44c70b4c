import datetime
from decimal import Decimal

import pytest

from contracts.models import TimesheetEntry


@pytest.mark.django_db
def test_freelancer_can_submit_entry(freelancer_client, active_contract):
    resp = freelancer_client.post('/api/timesheets/', {
        'contract': active_contract.id,
        'date': '2026-05-01',
        'hours': '8.0',
    })
    assert resp.status_code == 201
    assert resp.data['status'] == 'submitted'
    assert resp.data['contract'] == active_contract.id


@pytest.mark.django_db
def test_admin_cannot_create_entry(admin_client, active_contract):
    resp = admin_client.post('/api/timesheets/', {
        'contract': active_contract.id,
        'date': '2026-05-01',
        'hours': '8.0',
    })
    assert resp.status_code == 403


@pytest.mark.django_db
def test_freelancer_cannot_submit_to_wrong_contract(freelancer_client):
    # Create a contract that belongs to a completely different freelancer
    from django.contrib.auth.models import User
    from accounts.models import Company, Freelancer
    from contracts.models import Contract
    other_user = User.objects.create_user(username='other@test.test', email='other@test.test', password='x')
    other_freelancer = Freelancer.objects.create(user=other_user, name='Other')
    company = Company.objects.create(name='Other Co', billing_email='other@co.test')
    unrelated_contract = Contract.objects.create(
        company=company,
        freelancer=other_freelancer,
        daily_rate=Decimal('500.00'),
        start_date=datetime.date(2026, 1, 1),
        end_date=datetime.date(2026, 12, 31),
        status='active',
    )
    resp = freelancer_client.post('/api/timesheets/', {
        'contract': unrelated_contract.id,
        'date': '2026-05-01',
        'hours': '8.0',
    })
    assert resp.status_code == 400


@pytest.mark.django_db
def test_timesheet_list_status_filter(admin_client, submitted_entry, active_contract):
    # Add an approved entry too
    TimesheetEntry.objects.create(
        contract=active_contract,
        date=datetime.date(2026, 3, 10),
        hours=Decimal('8.0'),
        status='approved',
    )
    resp = admin_client.get('/api/timesheets/?status=submitted')
    assert resp.status_code == 200
    assert all(e['status'] == 'submitted' for e in resp.data)


@pytest.mark.django_db
def test_timesheet_list_contract_filter(admin_client, submitted_entry, active_contract):
    resp = admin_client.get(f'/api/timesheets/?contract={active_contract.id}')
    assert resp.status_code == 200
    assert all(e['contract'] == active_contract.id for e in resp.data)


@pytest.mark.django_db
def test_patch_approve(admin_client, submitted_entry):
    resp = admin_client.patch(f'/api/timesheets/{submitted_entry.id}/', {'status': 'approved'})
    assert resp.status_code == 200
    assert resp.data['status'] == 'approved'


@pytest.mark.django_db
def test_patch_reject_requires_reason(admin_client, submitted_entry):
    resp = admin_client.patch(f'/api/timesheets/{submitted_entry.id}/', {'status': 'rejected'})
    assert resp.status_code == 400
    assert 'rejection_reason' in resp.data


@pytest.mark.django_db
def test_patch_reject_with_reason(admin_client, submitted_entry):
    resp = admin_client.patch(f'/api/timesheets/{submitted_entry.id}/', {
        'status': 'rejected',
        'rejection_reason': 'Hours do not match agreed scope.',
    })
    assert resp.status_code == 200
    assert resp.data['status'] == 'rejected'
    assert resp.data['rejection_reason'] == 'Hours do not match agreed scope.'


@pytest.mark.django_db
def test_admin_cannot_see_other_company_timesheet(admin_client, other_contract):
    entry = TimesheetEntry.objects.create(
        contract=other_contract,
        date=datetime.date(2026, 4, 1),
        hours=Decimal('8.0'),
        status='submitted',
    )
    resp = admin_client.patch(f'/api/timesheets/{entry.id}/', {'status': 'approved'})
    assert resp.status_code == 404


@pytest.mark.django_db
def test_timesheet_list_requires_auth(api_client):
    resp = api_client.get('/api/timesheets/')
    assert resp.status_code == 401


@pytest.mark.django_db
def test_freelancer_can_list_own_timesheets(freelancer_client, submitted_entry):
    resp = freelancer_client.get('/api/timesheets/')
    assert resp.status_code == 200
    assert len(resp.data) == 1
    assert resp.data[0]['id'] == submitted_entry.id


@pytest.mark.django_db
def test_admin_can_list_company_timesheets(admin_client, submitted_entry):
    resp = admin_client.get('/api/timesheets/')
    assert resp.status_code == 200
    assert any(e['id'] == submitted_entry.id for e in resp.data)


@pytest.mark.django_db
def test_admin_list_excludes_other_company_entries(admin_client, other_contract):
    other_entry = TimesheetEntry.objects.create(
        contract=other_contract,
        date=datetime.date(2026, 4, 2),
        hours=Decimal('8.0'),
        status='submitted',
    )
    resp = admin_client.get('/api/timesheets/')
    assert resp.status_code == 200
    assert all(e['id'] != other_entry.id for e in resp.data)


@pytest.mark.django_db
def test_duplicate_contract_date_rejected(freelancer_client, submitted_entry, active_contract):
    resp = freelancer_client.post('/api/timesheets/', {
        'contract': active_contract.id,
        'date': submitted_entry.date.isoformat(),
        'hours': '7.5',
    })
    assert resp.status_code == 400


@pytest.mark.django_db
def test_patch_nonexistent_entry_returns_404(admin_client):
    resp = admin_client.patch('/api/timesheets/99999/', {'status': 'approved'})
    assert resp.status_code == 404


@pytest.mark.django_db
def test_timesheet_response_shape(freelancer_client, active_contract):
    resp = freelancer_client.post('/api/timesheets/', {
        'contract': active_contract.id,
        'date': '2026-05-02',
        'hours': '7.5',
    })
    assert resp.status_code == 201
    data = resp.data
    assert set(data.keys()) >= {'id', 'contract', 'contract_id', 'date', 'hours', 'status', 'rejection_reason'}
    assert data['contract'] == active_contract.id
    assert data['contract_id'] == active_contract.id
    assert data['status'] == 'submitted'
    assert data['rejection_reason'] is None


@pytest.mark.django_db
def test_status_filter_returns_empty_list(admin_client, submitted_entry):
    resp = admin_client.get('/api/timesheets/?status=approved')
    assert resp.status_code == 200
    assert resp.data == []


@pytest.mark.django_db
def test_reject_with_empty_reason_string_returns_400(admin_client, submitted_entry):
    resp = admin_client.patch(f'/api/timesheets/{submitted_entry.id}/', {
        'status': 'rejected',
        'rejection_reason': '',
    })
    assert resp.status_code == 400
    assert 'rejection_reason' in resp.data

import pytest
from django.contrib.auth.models import User


@pytest.mark.django_db
def test_login_empty_body_returns_401(api_client):
    resp = api_client.post('/api/auth/login/', {})
    assert resp.status_code == 401


@pytest.mark.django_db
def test_login_token_is_usable(api_client):
    User.objects.create_user(username='u@test.test', email='u@test.test', password='pw')
    login_resp = api_client.post('/api/auth/login/', {'email': 'u@test.test', 'password': 'pw'})
    token = login_resp.data['token']

    api_client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
    resp = api_client.get('/api/contracts/')
    assert resp.status_code == 200


@pytest.mark.django_db
def test_login_success(api_client):
    User.objects.create_user(username='user@test.test', email='user@test.test', password='secret')
    resp = api_client.post('/api/auth/login/', {'email': 'user@test.test', 'password': 'secret'})
    assert resp.status_code == 200
    assert 'token' in resp.data
    assert 'user' in resp.data
    assert resp.data['user']['email'] == 'user@test.test'


@pytest.mark.django_db
def test_login_wrong_password(api_client):
    User.objects.create_user(username='user@test.test', email='user@test.test', password='secret')
    resp = api_client.post('/api/auth/login/', {'email': 'user@test.test', 'password': 'wrong'})
    assert resp.status_code == 401


@pytest.mark.django_db
def test_login_unknown_user(api_client):
    resp = api_client.post('/api/auth/login/', {'email': 'nobody@test.test', 'password': 'x'})
    assert resp.status_code == 401


@pytest.mark.django_db
def test_login_returns_role_admin(admin_client, admin_user):
    resp = admin_client.post(
        '/api/auth/login/', {'email': admin_user.email, 'password': 'testpass'}
    )
    assert resp.status_code == 200
    assert resp.data['user']['role'] == 'admin'


@pytest.mark.django_db
def test_login_returns_role_freelancer(freelancer_client, freelancer_user):
    resp = freelancer_client.post(
        '/api/auth/login/', {'email': freelancer_user.email, 'password': 'testpass'}
    )
    assert resp.status_code == 200
    assert resp.data['user']['role'] == 'freelancer'

# tests/conftest.py (YENİ)
import pytest
from app import create_app
from app.extensions import db
from app.models.master.tenant import Tenant
from app.models.master.user import User

@pytest.fixture
def app():
    app = create_app('testing')
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_client(client, app):
    """Authenticated client"""
    with app.app_context():
        # Test kullanıcısı oluştur
        user = User(username='test', email='test@test.com')
        user.set_password('test123')
        db.session.add(user)
        db.session.commit()
        
        # Login
        client.post('/auth/login', data={
            'username': 'test',
            'password': 'test123'
        })
        
        yield client
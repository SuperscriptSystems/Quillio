import pytest
from app.configuration import app, db, csrf
from app.models import User
from flask import url_for

@pytest.fixture(scope='module')
def test_client():
    # Configure the app for testing
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    # Create a test client using the Flask application configured for testing
    with app.test_client() as testing_client:
        # Establish an application context
        with app.app_context():
            # Create the database and load test data
            db.create_all()
            
            # Create a test user
            test_user = User(
                username='testuser',
                email='test@example.com',
                password='testpassword',  # This should be hashed in a real test
                is_verified=True
            )
            db.session.add(test_user)
            db.session.commit()
            
            yield testing_client  # This is where the testing happens
            
            # Clean up after tests
            db.session.remove()
            db.drop_all()

@pytest.fixture(scope='module')
def login_default_user(test_client):
    # Log in the default test user
    test_client.post('/login', data=dict(
        email='test@example.com',
        password='testpassword'
    ), follow_redirects=True)
    
    return test_client

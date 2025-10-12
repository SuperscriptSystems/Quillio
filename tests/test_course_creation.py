import pytest
from app.models import Course

def test_create_course(test_client, login_default_user):
    """Test creating a new course"""
    # The test_client fixture already disables CSRF for testing
    # and login_default_user logs in our test user
    
    # Test GET request to course creation page
    response = test_client.get('/course/new')
    assert response.status_code == 200
    
    # Test POST request to create a new course
    response = test_client.post('/course/new', data={
        'title': 'Test Course',
        'description': 'A test course',
        'language': 'english'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    
    # Verify the course was created in the database
    with test_client.application.app_context():
        course = Course.query.filter_by(title='Test Course').first()
        assert course is not None
        assert course.description == 'A test Course'

def test_csrf_protection(test_client):
    """Test that CSRF protection is working"""
    # First, enable CSRF for this test
    test_client.application.config['WTF_CSRF_ENABLED'] = True
    
    # Try to create a course without CSRF token (should fail)
    response = test_client.post('/course/new', data={
        'title': 'CSRF Test Course',
        'description': 'This should fail CSRF',
        'language': 'english'
    }, follow_redirects=True)
    
    # Should be blocked by CSRF
    assert response.status_code == 400  # Bad Request due to missing CSRF
    
    # Verify the course was not created
    with test_client.application.app_context():
        course = Course.query.filter_by(title='CSRF Test Course').first()
        assert course is None
    
    # Disable CSRF again for other tests
    test_client.application.config['WTF_CSRF_ENABLED'] = False

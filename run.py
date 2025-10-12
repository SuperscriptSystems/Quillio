import os
import logging
from dotenv import load_dotenv
from flask import request

# Load environment variables first
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

# Now import the app to ensure logging is configured first
from app.configuration import app, db
from app import routes

# Enable Flask's debug and reloader
app.config['DEBUG'] = True
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# Add request logging
@app.before_request
def log_request_info():
    logger.debug(f'Request: {request.method} {request.path}')
    logger.debug(f'Headers: {dict(request.headers)}')
    logger.debug(f'Form data: {request.form}')
    if request.files:
        logger.debug(f'Files: {[f.filename for f in request.files.values()]}')

@app.after_request
def log_response_info(response):
    logger.debug(f'Response status: {response.status}')
    return response

if __name__ == "__main__":
    logger.info("Starting Quillio application...")
    try:
        app.run(debug=True, port=8000, use_reloader=True)
    except Exception as e:
        logger.exception("Error starting the application")
        raise
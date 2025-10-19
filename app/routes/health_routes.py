from flask import Blueprint, jsonify

# Create a Blueprint for health check routes
health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return jsonify({"status": "healthy"}), 200

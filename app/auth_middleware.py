import functools
from flask import request, jsonify, g
from flask_login import current_user
from app.models import User


def token_required(f):
    """
    Decorator for securing API endpoints using Token-based Authentication.
    
    Checks for authentication credentials in the following order:
    1. Authorization Header: 'Bearer <token>' or 'Token <token>'
    2. X-API-Token Header: '<token>'
    3. Query parameter or JSON body: 'api_token' or 'token'
    4. Active session fallback (for same-origin browser AJAX requests)
    
    Validates token against the User database model.
    Returns HTTP 401 JSON error response if authentication fails.
    Attaches the authenticated user to `g.current_user`.
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # 1. Check Authorization Header (Bearer <token> or Token <token>)
        auth_header = request.headers.get('Authorization')
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() in ('bearer', 'token'):
                token = parts[1]
            elif len(parts) == 1 and not parts[0].lower().startswith('basic'):
                token = parts[0]

        # 2. Check X-API-Token Header
        if not token:
            token = request.headers.get('X-API-Token')

        # 3. Check Query parameter or JSON payload
        if not token:
            token = request.args.get('api_token') or request.args.get('token')
            if not token and request.is_json and isinstance(request.get_json(silent=True), dict):
                token = request.get_json(silent=True).get('api_token')

        user = None

        # If a token was provided, authenticate via token lookup
        if token:
            user = User.query.filter_by(api_token=token).first()
            if not user:
                return jsonify({
                    'error': 'Unauthorized',
                    'message': 'Invalid API token provided.'
                }), 401

        # Fallback to session authentication for browser AJAX calls
        elif current_user and current_user.is_authenticated:
            user = current_user

        # If neither token nor authenticated session is found
        if not user:
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Authentication required. Missing or invalid API token.'
            }), 401

        # Store authenticated user in flask.g for easy access in route handlers
        g.current_user = user

        return f(*args, **kwargs)

    return decorated

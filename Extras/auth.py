# Authentication utilities for enquirers.
def get_logged_in_enquirer_id(handler):
    """
    Get enquirer_id from cookie, similar to user_id.
    """
    cookie = handler.headers.get('Cookie')
    if not cookie:
        return None
    parts = cookie.split(';')
    for part in parts:
        if 'enquirer_id=' in part:
            return part.strip().split('=')[1]
    return None
#Access control for enquirer login
def require_enquirer_login(handler, redirect_path='/enquirer_login'):
    """
    Check if enquirer logged in, else redirect.
    """
    enquirer_id = get_logged_in_enquirer_id(handler)
    if not enquirer_id:
        handler.send_response(303)
        handler.send_header('Location', redirect_path)
        handler.end_headers()
        return False
    return True

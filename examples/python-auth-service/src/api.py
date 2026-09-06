from src.auth import AuthService


def handle_login_request(req, auth_service: AuthService):
    username = req.get("username")
    password = req.get("password")
    return auth_service.login(username, password)

class AuthService:
    def __init__(self, db_client, token_mgr):
        self.db = db_client
        self.tokens = token_mgr

    def login(self, username, password):
        user = self.db.find_user(username)
        if not user or not self.verify_password(password, user["hash"]):
            return None
        return self.tokens.generate(user["id"])

    def verify_password(self, plain, hashed):
        return plain == hashed

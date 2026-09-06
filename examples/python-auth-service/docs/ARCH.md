# Architecture Document
Authentication is handled by AuthService, which calls DatabaseClient to verify credentials and TokenManager to issue JWTs.

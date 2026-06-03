"""Mini Exchange API Gateway (FastAPI).

Public-facing HTTP entrypoint. The gateway owns no domain logic; it forwards
client requests to the matching service over HTTP and maps downstream/transport
failures into clean HTTP responses.
"""

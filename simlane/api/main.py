from ninja import NinjaAPI
from ninja.security import HttpBearer
from django.conf import settings
from django.http import HttpRequest
from ninja.errors import ValidationError
from ninja.responses import Response
import jwt
from django.contrib.auth import get_user_model
from typing import Optional

from simlane.api.routers.auth import router as auth_router
from simlane.api.routers.clubs import router as clubs_router
from simlane.api.routers.events import router as events_router
from simlane.api.routers.sim import router as sim_router

User = get_user_model()


class JWTAuth(HttpBearer):
    def authenticate(self, request: HttpRequest, token: str) -> Optional[User]:
        try:
            # Use JWT_SECRET_KEY from settings if available, otherwise fallback to SECRET_KEY
            secret_key = getattr(settings, 'JWT_SECRET_KEY', settings.SECRET_KEY)
            algorithm = getattr(settings, 'JWT_ALGORITHM', 'HS256')
            
            payload = jwt.decode(token, secret_key, algorithms=[algorithm])
            user_id = payload.get('user_id')
            
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                    return user
                except User.DoesNotExist:
                    return None
            return None
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None


# Create the API instance
api = NinjaAPI(
    title="SimLane API",
    version="1.0.0",
    description="API for SimLane sim racing platform",
    auth=JWTAuth(),
    docs_url="/docs/",
)


# Error handlers
@api.exception_handler(ValidationError)
def validation_error_handler(request: HttpRequest, exc: ValidationError):
    return api.create_response(
        request,
        {"error": "Validation Error", "detail": exc.errors},
        status=400,
    )


@api.exception_handler(Exception)
def generic_exception_handler(request: HttpRequest, exc: Exception):
    if settings.DEBUG:
        return api.create_response(
            request,
            {"error": "Internal Server Error", "detail": str(exc)},
            status=500,
        )
    else:
        return api.create_response(
            request,
            {"error": "Internal Server Error", "detail": "An unexpected error occurred"},
            status=500,
        )


# Add routers
api.add_router("/auth", auth_router, tags=["Authentication"])
api.add_router("/clubs", clubs_router, tags=["Clubs"])
api.add_router("/events", events_router, tags=["Events"])
api.add_router("/sim", sim_router, tags=["Sim Racing"])


# Health check endpoint
@api.get("/health", auth=None, tags=["System"])
def health_check(request):
    return {"status": "healthy", "version": "1.0.0"}


# API info endpoint
@api.get("/info", auth=None, tags=["System"])
def api_info(request):
    return {
        "name": "SimLane API",
        "version": "1.0.0",
        "description": "API for SimLane sim racing platform",
        "features": [
            "JWT Authentication",
            "Club Management",
            "Event Signups",
            "Team Allocation",
            "Stint Planning",
            "Sim Racing Data",
        ],
    } 
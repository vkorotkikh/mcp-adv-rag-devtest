import inspect
import logging
import re
from functools import wraps
from typing import Dict, List, Optional, Any, Callable, Union, Tuple

from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from fastmcp.server.dependencies import get_context
from auth.google_auth import get_authenticated_google_service, GoogleAuthenticationError
from auth.oauth21_session_store import get_oauth21_session_store
from auth.oauth_config import is_oauth21_enabled, get_oauth_config
from core.context import set_fastmcp_session_id
from auth.scopes import (
    GMAIL_READONLY_SCOPE,
    GMAIL_SEND_SCOPE,
    GMAIL_COMPOSE_SCOPE,
    GMAIL_MODIFY_SCOPE,
    GMAIL_LABELS_SCOPE,
    DRIVE_READONLY_SCOPE,
    DRIVE_FILE_SCOPE,
    DOCS_READONLY_SCOPE,
    DOCS_WRITE_SCOPE,
    CALENDAR_READONLY_SCOPE,
    CALENDAR_EVENTS_SCOPE,
    SHEETS_READONLY_SCOPE,
    SHEETS_WRITE_SCOPE,
    CHAT_READONLY_SCOPE,
    CHAT_WRITE_SCOPE,
    CHAT_SPACES_SCOPE,
    FORMS_BODY_SCOPE,
    FORMS_BODY_READONLY_SCOPE,
    FORMS_RESPONSES_READONLY_SCOPE,
    SLIDES_SCOPE,
    SLIDES_READONLY_SCOPE,
    TASKS_SCOPE,
    TASKS_READONLY_SCOPE,
    CUSTOM_SEARCH_SCOPE,
)

# OAuth 2.1 integration is now handled by FastMCP auth
OAUTH21_INTEGRATION_AVAILABLE = True


# Authentication helper functions
def _get_auth_context(
    tool_name: str,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Get authentication context from FastMCP.

    Returns:
        Tuple of (authenticated_user, auth_method, mcp_session_id)
    """
    try:
        ctx = get_context()
        if not ctx:
            return None, None, None

        authenticated_user = ctx.get_state("authenticated_user_email")
        auth_method = ctx.get_state("authenticated_via")
        mcp_session_id = ctx.session_id if hasattr(ctx, "session_id") else None

        if mcp_session_id:
            set_fastmcp_session_id(mcp_session_id)

        logger.debug(
            f"[{tool_name}] Auth from middleware: {authenticated_user} via {auth_method}"
        )
        return authenticated_user, auth_method, mcp_session_id

    except Exception as e:
        logger.debug(f"[{tool_name}] Could not get FastMCP context: {e}")
        return None, None, None


def _detect_oauth_version(
    authenticated_user: Optional[str], mcp_session_id: Optional[str], tool_name: str
) -> bool:
    """
    Detect whether to use OAuth 2.1 based on configuration and context.

    Returns:
        True if OAuth 2.1 should be used, False otherwise
    """
    if not is_oauth21_enabled():
        return False

    # When OAuth 2.1 is enabled globally, ALWAYS use OAuth 2.1 for authenticated users
    if authenticated_user:
        logger.info(
            f"[{tool_name}] OAuth 2.1 mode: Using OAuth 2.1 for authenticated user '{authenticated_user}'"
        )
        return True

    # Only use version detection for unauthenticated requests
    config = get_oauth_config()
    request_params = {}
    if mcp_session_id:
        request_params["session_id"] = mcp_session_id

    oauth_version = config.detect_oauth_version(request_params)
    use_oauth21 = oauth_version == "oauth21"
    logger.info(
        f"[{tool_name}] OAuth version detected: {oauth_version}, will use OAuth 2.1: {use_oauth21}"
    )
    return use_oauth21


def _update_email_in_args(args: tuple, index: int, new_email: str) -> tuple:
    """Update email at specific index in args tuple."""
    if index < len(args):
        args_list = list(args)
        args_list[index] = new_email
        return tuple(args_list)
    return args


def _override_oauth21_user_email(
    use_oauth21: bool,
    authenticated_user: Optional[str],
    current_user_email: str,
    args: tuple,
    kwargs: dict,
    param_names: List[str],
    tool_name: str,
    service_type: str = "",
) -> Tuple[str, tuple]:
    """
    Override user_google_email with authenticated user when using OAuth 2.1.

    Returns:
        Tuple of (updated_user_email, updated_args)
    """
    if not (use_oauth21 and authenticated_user and current_user_email != authenticated_user):
        return current_user_email, args

    service_suffix = f" for service '{service_type}'" if service_type else ""
    logger.info(
        f"[{tool_name}] OAuth 2.1: Overriding user_google_email from '{current_user_email}' to authenticated user '{authenticated_user}'{service_suffix}"
    )

    # Update in kwargs if present
    if "user_google_email" in kwargs:
        kwargs["user_google_email"] = authenticated_user

    # Update in args if user_google_email is passed positionally
    try:
        user_email_index = param_names.index("user_google_email")
        args = _update_email_in_args(args, user_email_index, authenticated_user)
    except ValueError:
        pass  # user_google_email not in positional parameters

    return authenticated_user, args


async def _authenticate_service(
    use_oauth21: bool,
    service_name: str,
    service_version: str,
    tool_name: str,
    user_google_email: str,
    resolved_scopes: List[str],
    mcp_session_id: Optional[str],
    authenticated_user: Optional[str],
) -> Tuple[Any, str]:
    """
    Authenticate and get Google service using appropriate OAuth version.

    Returns:
        Tuple of (service, actual_user_email)
    """
    if use_oauth21:
        logger.debug(f"[{tool_name}] Using OAuth 2.1 flow")
        return await get_authenticated_google_service_oauth21(
            service_name=service_name,
            version=service_version,
            tool_name=tool_name,
            user_google_email=user_google_email,
            required_scopes=resolved_scopes,
            session_id=mcp_session_id,
            auth_token_email=authenticated_user,
            allow_recent_auth=False,
        )
    else:
        logger.debug(f"[{tool_name}] Using legacy OAuth 2.0 flow")
        return await get_authenticated_google_service(
            service_name=service_name,
            version=service_version,
            tool_name=tool_name,
            user_google_email=user_google_email,
            required_scopes=resolved_scopes,
            session_id=mcp_session_id,
        )


async def get_authenticated_google_service_oauth21(
    service_name: str,
    version: str,
    tool_name: str,
    user_google_email: str,
    required_scopes: List[str],
    session_id: Optional[str] = None,
    auth_token_email: Optional[str] = None,
    allow_recent_auth: bool = False,
) -> tuple[Any, str]:
    """
    OAuth 2.1 authentication using the session store with security validation.
    """
    store = get_oauth21_session_store()

    # Use the new validation method to ensure session can only access its own credentials
    credentials = store.get_credentials_with_validation(
        requested_user_email=user_google_email,
        session_id=session_id,
        auth_token_email=auth_token_email,
        allow_recent_auth=allow_recent_auth,
    )

    if not credentials:
        raise GoogleAuthenticationError(
            f"Access denied: Cannot retrieve credentials for {user_google_email}. "
            f"You can only access credentials for your authenticated account."
        )

    # Check scopes
    if not all(scope in credentials.scopes for scope in required_scopes):
        raise GoogleAuthenticationError(
            f"OAuth 2.1 credentials lack required scopes. Need: {required_scopes}, Have: {credentials.scopes}"
        )

    # Build service
    service = build(service_name, version, credentials=credentials)
    logger.info(f"[{tool_name}] Authenticated {service_name} for {user_google_email}")

    return service, user_google_email


logger = logging.getLogger(__name__)


def _remove_user_email_arg_from_docstring(docstring: str) -> str:
    """
    Remove user_google_email parameter documentation from docstring.

    Args:
        docstring: The original function docstring

    Returns:
        Modified docstring with user_google_email parameter removed
    """
    if not docstring:
        return docstring

    # Pattern to match user_google_email parameter documentation
    # Handles various formats like:
    # - user_google_email (str): The user's Google email address. Required.
    # - user_google_email: Description
    # - user_google_email (str) - Description
    patterns = [
        r'^\s*user_google_email\s*\([^)]*\)\s*:\s*[^\n]*\.?\s*(?:Required\.?)?\s*\n',
        r'^\s*user_google_email\s*:\s*[^\n]*\n',
        r'^\s*user_google_email\s*\([^)]*\)\s*-\s*[^\n]*\n',
    ]

    modified_docstring = docstring
    for pattern in patterns:
        modified_docstring = re.sub(pattern, '', modified_docstring, flags=re.MULTILINE)

    # Clean up any sequence of 3 or more newlines that might have been created
    modified_docstring = re.sub(r'\n{3,}', '\n\n', modified_docstring)
    return modified_docstring

# Service configuration mapping
SERVICE_CONFIGS = {
    "gmail": {"service": "gmail", "version": "v1"},
    "drive": {"service": "drive", "version": "v3"},
    "calendar": {"service": "calendar", "version": "v3"},
    "docs": {"service": "docs", "version": "v1"},
    "sheets": {"service": "sheets", "version": "v4"},
    "chat": {"service": "chat", "version": "v1"},
    "forms": {"service": "forms", "version": "v1"},
    "slides": {"service": "slides", "version": "v1"},
    "tasks": {"service": "tasks", "version": "v1"},
    "customsearch": {"service": "customsearch", "version": "v1"},
}


# Scope group definitions for easy reference
SCOPE_GROUPS = {
    # Gmail scopes
    "gmail_read": GMAIL_READONLY_SCOPE,
    "gmail_send": GMAIL_SEND_SCOPE,
    "gmail_compose": GMAIL_COMPOSE_SCOPE,
    "gmail_modify": GMAIL_MODIFY_SCOPE,
    "gmail_labels": GMAIL_LABELS_SCOPE,
    # Drive scopes
    "drive_read": DRIVE_READONLY_SCOPE,
    "drive_file": DRIVE_FILE_SCOPE,
    # Docs scopes
    "docs_read": DOCS_READONLY_SCOPE,
    "docs_write": DOCS_WRITE_SCOPE,
    # Calendar scopes
    "calendar_read": CALENDAR_READONLY_SCOPE,
    "calendar_events": CALENDAR_EVENTS_SCOPE,
    # Sheets scopes
    "sheets_read": SHEETS_READONLY_SCOPE,
    "sheets_write": SHEETS_WRITE_SCOPE,
    # Chat scopes
    "chat_read": CHAT_READONLY_SCOPE,
    "chat_write": CHAT_WRITE_SCOPE,
    "chat_spaces": CHAT_SPACES_SCOPE,
    # Forms scopes
    "forms": FORMS_BODY_SCOPE,
    "forms_read": FORMS_BODY_READONLY_SCOPE,
    "forms_responses_read": FORMS_RESPONSES_READONLY_SCOPE,
    # Slides scopes
    "slides": SLIDES_SCOPE,
    "slides_read": SLIDES_READONLY_SCOPE,
    # Tasks scopes
    "tasks": TASKS_SCOPE,
    "tasks_read": TASKS_READONLY_SCOPE,
    # Custom Search scope
    "customsearch": CUSTOM_SEARCH_SCOPE,
}



def _resolve_scopes(scopes: Union[str, List[str]]) -> List[str]:
    """Resolve scope names to actual scope URLs."""
    if isinstance(scopes, str):
        if scopes in SCOPE_GROUPS:
            return [SCOPE_GROUPS[scopes]]
        else:
            return [scopes]

    resolved = []
    for scope in scopes:
        if scope in SCOPE_GROUPS:
            resolved.append(SCOPE_GROUPS[scope])
        else:
            resolved.append(scope)
    return resolved


def _handle_token_refresh_error(
    error: RefreshError, user_email: str, service_name: str
) -> str:
    """
    Handle token refresh errors gracefully, particularly expired/revoked tokens.

    Args:
        error: The RefreshError that occurred
        user_email: User's email address
        service_name: Name of the Google service

    Returns:
        A user-friendly error message with instructions for reauthentication
    """
    error_str = str(error)

    if (
        "invalid_grant" in error_str.lower()
        or "expired or revoked" in error_str.lower()
    ):
        logger.warning(
            f"Token expired or revoked for user {user_email} accessing {service_name}"
        )


        service_display_name = f"Google {service_name.title()}"

        return (
            f"**Authentication Required: Token Expired/Revoked for {service_display_name}**\n\n"
            f"Your Google authentication token for {user_email} has expired or been revoked. "
            f"This commonly happens when:\n"
            f"- The token has been unused for an extended period\n"
            f"- You've changed your Google account password\n"
            f"- You've revoked access to the application\n\n"
            f"**To resolve this, please:**\n"
            f"1. Run `start_google_auth` with your email ({user_email}) and service_name='{service_display_name}'\n"
            f"2. Complete the authentication flow in your browser\n"
            f"3. Retry your original command\n\n"
            f"The application will automatically use the new credentials once authentication is complete."
        )
    else:
        # Handle other types of refresh errors
        logger.error(f"Unexpected refresh error for user {user_email}: {error}")
        return (
            f"Authentication error occurred for {user_email}. "
            f"Please try running `start_google_auth` with your email and the appropriate service name to reauthenticate."
        )


def require_google_service(
    service_type: str,
    scopes: Union[str, List[str]],
    version: Optional[str] = None,
):
    """
    Decorator that automatically handles Google service authentication and injection.

    Args:
        service_type: Type of Google service ("gmail", "drive", "calendar", etc.)
        scopes: Required scopes (can be scope group names or actual URLs)
        version: Service version (defaults to standard version for service type)

    Usage:
        @require_google_service("gmail", "gmail_read")
        async def search_messages(service, user_google_email: str, query: str):
            # service parameter is automatically injected
            # Original authentication logic is handled automatically
    """

    def decorator(func: Callable) -> Callable:
        original_sig = inspect.signature(func)
        params = list(original_sig.parameters.values())

        # The decorated function must have 'service' as its first parameter.
        if not params or params[0].name != "service":
            raise TypeError(
                f"Function '{func.__name__}' decorated with @require_google_service "
                "must have 'service' as its first parameter."
            )

        # Create a new signature for the wrapper that excludes the 'service' parameter.
        # This is the signature that FastMCP will see.
        wrapper_sig = original_sig.replace(parameters=params[1:])

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Note: `args` and `kwargs` are now the arguments for the *wrapper*,
            # which does not include 'service'.

            # Extract user_google_email from the arguments passed to the wrapper
            bound_args = wrapper_sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            user_google_email = bound_args.arguments.get("user_google_email")

            if not user_google_email:
                # This should ideally not be reached if 'user_google_email' is a required parameter
                raise Exception(
                    "'user_google_email' parameter is required but was not found."
                )

            # Get service configuration from the decorator's arguments
            if service_type not in SERVICE_CONFIGS:
                raise Exception(f"Unknown service type: {service_type}")

            config = SERVICE_CONFIGS[service_type]
            service_name = config["service"]
            service_version = version or config["version"]

            # Resolve scopes
            resolved_scopes = _resolve_scopes(scopes)

            try:
                tool_name = func.__name__

                # Get authentication context
                authenticated_user, auth_method, mcp_session_id = _get_auth_context(
                    tool_name
                )

                # Log authentication status
                logger.debug(
                    f"[{tool_name}] Auth: {authenticated_user or 'none'} via {auth_method or 'none'} (session: {mcp_session_id[:8] if mcp_session_id else 'none'})"
                )

                # Detect OAuth version
                use_oauth21 = _detect_oauth_version(
                    authenticated_user, mcp_session_id, tool_name
                )

                # Override user_google_email with authenticated user when using OAuth 2.1
                wrapper_params = list(wrapper_sig.parameters.keys())
                user_google_email, args = _override_oauth21_user_email(
                    use_oauth21,
                    authenticated_user,
                    user_google_email,
                    args,
                    kwargs,
                    wrapper_params,
                    tool_name,
                )

                # Update bound_args for consistency
                if use_oauth21 and authenticated_user and user_google_email == authenticated_user:
                    bound_args.arguments["user_google_email"] = authenticated_user

                # Authenticate service
                service, actual_user_email = await _authenticate_service(
                    use_oauth21,
                    service_name,
                    service_version,
                    tool_name,
                    user_google_email,
                    resolved_scopes,
                    mcp_session_id,
                    authenticated_user,
                )
            except GoogleAuthenticationError as e:
                logger.error(
                    f"[{tool_name}] GoogleAuthenticationError during authentication. "
                    f"Method={auth_method or 'none'}, User={authenticated_user or 'none'}, "
                    f"Service={service_name} v{service_version}, MCPSessionID={mcp_session_id or 'none'}: {e}"
                )
                # Re-raise the original error without wrapping it
                raise

            try:
                # Prepend the fetched service object to the original arguments
                return await func(service, *args, **kwargs)
            except RefreshError as e:
                error_message = _handle_token_refresh_error(
                    e, actual_user_email, service_name
                )
                raise Exception(error_message)

        # Set the wrapper's signature to the one without 'service'
        wrapper.__signature__ = wrapper_sig

        # Conditionally modify docstring to remove user_google_email parameter documentation
        if is_oauth21_enabled():
            logger.debug('OAuth 2.1 mode enabled, removing user_google_email from docstring')
            if func.__doc__:
                wrapper.__doc__ = _remove_user_email_arg_from_docstring(func.__doc__)

        return wrapper

    return decorator


def require_multiple_services(service_configs: List[Dict[str, Any]]):
    """
    Decorator for functions that need multiple Google services.

    Args:
        service_configs: List of service configurations, each containing:
            - service_type: Type of service
            - scopes: Required scopes
            - param_name: Name to inject service as (e.g., 'drive_service', 'docs_service')
            - version: Optional version override

    Usage:
        @require_multiple_services([
            {"service_type": "drive", "scopes": "drive_read", "param_name": "drive_service"},
            {"service_type": "docs", "scopes": "docs_read", "param_name": "docs_service"}
        ])
        async def get_doc_with_metadata(drive_service, docs_service, user_google_email: str, doc_id: str):
            # Both services are automatically injected
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user_google_email
            sig = inspect.signature(func)
            param_names = list(sig.parameters.keys())

            user_google_email = None
            if "user_google_email" in kwargs:
                user_google_email = kwargs["user_google_email"]
            else:
                try:
                    user_email_index = param_names.index("user_google_email")
                    if user_email_index < len(args):
                        user_google_email = args[user_email_index]
                except ValueError:
                    pass

            if not user_google_email:
                raise Exception("user_google_email parameter is required but not found")

            # Authenticate all services
            for config in service_configs:
                service_type = config["service_type"]
                scopes = config["scopes"]
                param_name = config["param_name"]
                version = config.get("version")

                if service_type not in SERVICE_CONFIGS:
                    raise Exception(f"Unknown service type: {service_type}")

                service_config = SERVICE_CONFIGS[service_type]
                service_name = service_config["service"]
                service_version = version or service_config["version"]
                resolved_scopes = _resolve_scopes(scopes)

                try:
                    tool_name = func.__name__

                    # Get authentication context
                    authenticated_user, _, mcp_session_id = _get_auth_context(tool_name)

                    # Detect OAuth version (simplified for multiple services)
                    use_oauth21 = (
                        is_oauth21_enabled() and authenticated_user is not None
                    )

                    # Override user_google_email with authenticated user when using OAuth 2.1
                    user_google_email, args = _override_oauth21_user_email(
                        use_oauth21,
                        authenticated_user,
                        user_google_email,
                        args,
                        kwargs,
                        param_names,
                        tool_name,
                        service_type,
                    )

                    # Authenticate service
                    service, _ = await _authenticate_service(
                        use_oauth21,
                        service_name,
                        service_version,
                        tool_name,
                        user_google_email,
                        resolved_scopes,
                        mcp_session_id,
                        authenticated_user,
                    )

                    # Inject service with specified parameter name
                    kwargs[param_name] = service

                except GoogleAuthenticationError as e:
                    logger.error(
                        f"[{tool_name}] GoogleAuthenticationError for service '{service_type}' (user: {user_google_email}): {e}"
                    )
                    # Re-raise the original error without wrapping it
                    raise

            # Call the original function with refresh error handling
            try:
                return await func(*args, **kwargs)
            except RefreshError as e:
                # Handle token refresh errors gracefully
                error_message = _handle_token_refresh_error(
                    e, user_google_email, "Multiple Services"
                )
                raise Exception(error_message)

        return wrapper

    return decorator
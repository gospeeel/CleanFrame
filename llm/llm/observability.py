import logging
import os


logger = logging.getLogger(__name__)


def configure_sentry() -> None:
    dsn = os.getenv("GLITCHTIP_DSN") or os.getenv("SENTRY_DSN")
    if not dsn:
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except Exception as exc:
        logger.warning("Sentry DSN is set, but sentry-sdk is unavailable: %s", exc)
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "development",
        release=os.getenv("APP_VERSION"),
        traces_sample_rate=float(os.getenv("GLITCHTIP_TRACES_SAMPLE_RATE") or os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        send_default_pii=False,
        auto_session_tracking=False,
    )

from __future__ import annotations

import logging
from typing import Optional

from azure.monitor.opentelemetry.exporter import (
    AzureMonitorTraceExporter,
    AzureMonitorMetricExporter,
    AzureMonitorLogExporter,
)
from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry._logs import set_logger_provider
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from app.config import Settings

logger = logging.getLogger(__name__)


def setup_telemetry(settings: Settings) -> None:
    """
    Initialise OpenTelemetry SDK:
      - TracerProvider with Azure Monitor exporter (and optional OTLP exporter)
      - MeterProvider with Azure Monitor exporter
      - LoggerProvider with Azure Monitor exporter
      - FastAPI + httpx auto-instrumentation
      - W3C TraceContext + B3 propagation
    """
    resource = Resource.create(
        {
            SERVICE_NAME: settings.otel_service_name,
            SERVICE_VERSION: settings.otel_service_version,
            "deployment.environment": "production",
        }
    )

    # ----------------------------------------------------------------
    # Trace provider
    # ----------------------------------------------------------------
    sampler = ParentBased(root=TraceIdRatioBased(1.0))  # 100% sampling; reduce in prod
    tracer_provider = TracerProvider(resource=resource, sampler=sampler)

    if settings.applicationinsights_connection_string:
        azure_trace_exporter = AzureMonitorTraceExporter(
            connection_string=settings.applicationinsights_connection_string
        )
        tracer_provider.add_span_processor(BatchSpanProcessor(azure_trace_exporter))
        logger.info("Azure Monitor trace exporter configured.")

    if settings.otel_exporter_otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(
            endpoint=f"{settings.otel_exporter_otlp_endpoint}/v1/traces"
        )
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        logger.info("OTLP trace exporter configured: %s", settings.otel_exporter_otlp_endpoint)

    trace.set_tracer_provider(tracer_provider)

    # ----------------------------------------------------------------
    # Metrics provider
    # ----------------------------------------------------------------
    if settings.applicationinsights_connection_string:
        azure_metric_exporter = AzureMonitorMetricExporter(
            connection_string=settings.applicationinsights_connection_string
        )
        metric_reader = PeriodicExportingMetricReader(azure_metric_exporter, export_interval_millis=60_000)
        meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(meter_provider)
        logger.info("Azure Monitor metric exporter configured.")

    # ----------------------------------------------------------------
    # Log provider (bridges Python logging to OTel)
    # ----------------------------------------------------------------
    if settings.applicationinsights_connection_string:
        azure_log_exporter = AzureMonitorLogExporter(
            connection_string=settings.applicationinsights_connection_string
        )
        log_provider = LoggerProvider(resource=resource)
        log_provider.add_log_record_processor(BatchLogRecordProcessor(azure_log_exporter))
        set_logger_provider(log_provider)

    # ----------------------------------------------------------------
    # Propagators: W3C TraceContext + B3 (for compatibility)
    # ----------------------------------------------------------------
    set_global_textmap(
        CompositePropagator([
            TraceContextTextMapPropagator(),
            B3MultiFormat(),
        ])
    )

    # ----------------------------------------------------------------
    # Auto-instrumentation
    # ----------------------------------------------------------------
    FastAPIInstrumentor().instrument(
        excluded_urls="/healthz,/metrics",
        tracer_provider=tracer_provider,
    )
    HTTPXClientInstrumentor().instrument(tracer_provider=tracer_provider)

    logger.info(
        "OpenTelemetry initialised. Service: %s v%s",
        settings.otel_service_name,
        settings.otel_service_version,
    )

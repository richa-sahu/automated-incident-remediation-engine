import os
import time
import asyncio
from fastapi import FastAPI, Response, status
from prometheus_fastapi_instrumentator import Instrumentator

# OpenTelemetry imports
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Initialize FastAPI App
app = FastAPI(title="Order Service", version="1.0.0")

# Setup OpenTelemetry Tracer
OTEL_COLLECTOR_URL = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector.monitoring.svc.cluster.local:4317")
resource = Resource(attributes={SERVICE_NAME: "order-service"})
provider = TracerProvider(resource=resource)

# Use OTLP exporter if running in cluster environment
try:
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=OTEL_COLLECTOR_URL, insecure=True))
    provider.add_span_processor(processor)
except Exception as e:
    print(f"OTEL Exporter warning: {e}")

trace.set_tracer_provider(provider)
tracer = trace.get_tracer("order-service-tracer")

# Instrument FastAPI app
FastAPIInstrumentor.instrument_app(app)

# Expose /metrics for Prometheus scraping
Instrumentator().instrument(app).expose(app)

# Chaos / Fault-Injection State
chaos_state = {
    "latency_seconds": 0,
    "memory_leak_mb": [],
    "force_error": False
}

@app.get("/")
def read_root():
    return {"service": "order-service", "status": "healthy"}

@app.get("/health")
def health_check(response: Response):
    if chaos_state["force_error"]:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"status": "UNHEALTHY", "cause": "Fault injected"}
    return {"status": "UP"}

@app.post("/orders")
async def create_order():
    with tracer.start_as_current_span("process_order") as span:
        # Simulate fault-injected latency if active
        if chaos_state["latency_seconds"] > 0:
            span.set_attribute("chaos.latency_injected", chaos_state["latency_seconds"])
            await asyncio.sleep(chaos_state["latency_seconds"])

        # Simulate fault-injected HTTP 500 error
        if chaos_state["force_error"]:
            span.set_attribute("error", True)
            raise RuntimeError("Injected order processing failure")

        span.set_attribute("order.status", "created")
        return {"order_id": "ORD-9921", "status": "CREATED", "amount": 149.99}

# --- FAULT INJECTION ENDPOINTS (For AIRE Remediation Testing) ---

@app.post("/inject/latency/{seconds}")
def inject_latency(seconds: int):
    chaos_state["latency_seconds"] = seconds
    return {"message": f"Injected {seconds}s latency into /orders workflow"}

@app.post("/inject/error")
def inject_error(enable: bool = True):
    chaos_state["force_error"] = enable
    return {"message": f"Force error state set to {enable}"}

@app.post("/inject/memory/{mb}")
def inject_memory_leak(mb: int):
    # Allocate byte array to simulate high memory pressure
    leak = bytearray(mb * 1024 * 1024)
    chaos_state["memory_leak_mb"].append(leak)
    return {"message": f"Allocated ~{mb}MB of memory. Total leaked chunks: {len(chaos_state['memory_leak_mb'])}"}

@app.post("/inject/reset")
def reset_faults():
    chaos_state["latency_seconds"] = 0
    chaos_state["force_error"] = False
    chaos_state["memory_leak_mb"].clear()
    return {"message": "All injected faults cleared."}
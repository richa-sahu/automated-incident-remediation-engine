import logging
import time
import random
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Response, status

# 1. Configure Structured Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("order-service")

app = FastAPI(
    title="AIRE Order Processing Service",
    description="Microservice with a built-in synthetic fault-injection switch.",
    version="1.0.0"
)

# 2. State Management for Chaos Simulation
SYSTEM_HEALTHY = True

# Data Models
class Order(BaseModel):
    item: str
    quantity: int
    price: float

class FaultConfig(BaseModel):
    healthy: bool

# 3. Routes & Core Logic
@app.get("/", tags=["Health"])
def health_check():
    """Standard Kubernetes liveness/readiness probe target."""
    if not SYSTEM_HEALTHY:
        logger.warning("Health check requested while system is degraded.")
    return {"status": "healthy" if SYSTEM_HEALTHY else "degraded"}


@app.post("/orders", status_code=status.HTTP_201_CREATED, tags=["Business Business"])
def create_order(order: Order, response: Response):
    """Processes customer incoming orders. Simulates degradation if faults are injected."""
    global SYSTEM_HEALTHY

    # --- SIMULATE SYSTEM FAULT (CHAOS TRIGGERED) ---
    if not SYSTEM_HEALTHY:
        # 50% chance of introducing high database latency (8-12 seconds)
        if random.choice([True, False]):
            latency = random.uniform(8.0, 12.0)
            logger.error(f"DATABASE TIMEOUT: Simulating severe network bottleneck. Delaying response by {latency:.2f}s")
            time.sleep(latency)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT, 
                detail="Database connection pool exhausted due to thread blocking."
            )
        # 50% chance of throwing raw HTTP 500 errors
        else:
            logger.error("CRITICAL FAILURE: Unexpected internal exception during transaction validation.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal Server Error: Failed to write transaction log write lock."
            )
    
    # --- NORMAL HEALTHY BEHAVIOR ---
    # Standard negligible API processing delay (10-50ms)
    time.sleep(random.uniform(0.01, 0.05))
    
    order_id = random.randint(100000, 999999)
    logger.info(f"SUCCESS: Processed order #{order_id} for {order.quantity}x '{order.item}'")
    
    return {
        "order_id": order_id,
        "status": "processed",
        "timestamp": time.time()
    }


@app.post("/inject-fault", tags=["Chaos Engineering"])
def toggle_fault(config: FaultConfig):
    """The Sabotage Switch. Use this endpoint to toggle cluster failures on or off."""
    global SYSTEM_HEALTHY
    SYSTEM_HEALTHY = config.healthy
    
    state_str = "HEALTHY" if SYSTEM_HEALTHY else "DEGRADED / SABOTAGED"
    logger.critical(f"CHAOS CONFIG CHANGED: System state manually switched to [{state_str}]")
    
    return {"message": f"System state updated successfully to {state_str}."}

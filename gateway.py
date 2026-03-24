"""
API Gateway - Mercadinho 24h
Implementa: Retry, Timeout, Fallback
"""
import asyncio
import time
import json
import random
from datetime import datetime
from pathlib import Path
 
FALLBACK_FILE = Path("fallback_orders.json")
 
# ─── RETRY ────────────────────────────────────────────────────────────────────
 
async def with_retry(coro_fn, max_attempts=3, base_delay=0.5, label=""):
    """Retry com backoff exponencial."""
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"  [RETRY] {label} tentativa {attempt}/{max_attempts}")
            result = await coro_fn()
            return result
        except Exception as e:
            if attempt == max_attempts:
                print(f"  [RETRY] {label} esgotou tentativas: {e}")
                raise
            delay = base_delay * (2 ** (attempt - 1))
            print(f"  [RETRY] {label} falhou ({e}), aguardando {delay:.1f}s...")
            await asyncio.sleep(delay)
 
# ─── TIMEOUT ──────────────────────────────────────────────────────────────────
 
async def with_timeout(coro, seconds, label=""):
    """Cancela se exceder o tempo limite."""
    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except asyncio.TimeoutError:
        raise TimeoutError(f"[TIMEOUT] {label} excedeu {seconds}s")
 
# ─── FALLBACK ─────────────────────────────────────────────────────────────────
 
def save_fallback_order(order: dict) -> str:
    """Persiste pedido em JSON local quando broker está indisponível."""
    orders = []
    if FALLBACK_FILE.exists():
        orders = json.loads(FALLBACK_FILE.read_text())
    orders.append({**order, "fallback_at": datetime.now().isoformat()})
    FALLBACK_FILE.write_text(json.dumps(orders, indent=2, ensure_ascii=False))
    return f"pedido salvo em fila local (fallback_orders.json)"
 
def payment_fallback(order: dict) -> dict:
    """Fallback de pagamento: aceita pedido com pagamento na entrega."""
    return {
        "status": "accepted_fallback",
        "payment_method": "na entrega",
        "message": "Pagamento indisponível - aceito pagamento na entrega",
        "order_id": order["order_id"],
    }
 
# ─── SERVIÇOS (simulados) ─────────────────────────────────────────────────────
 
async def call_order_service(order: dict, simulate_mode: str = "ok") -> dict:
    """
    Modos: ok | retry_fail | timeout
    """
    await asyncio.sleep(0.2)  # latência base
 
    if simulate_mode == "timeout":
        print("  [ORDER SERVICE] simulando lentidão...")
        await asyncio.sleep(10)  # vai estourar o timeout
 
    if simulate_mode == "retry_fail":
        if not hasattr(call_order_service, "_attempts"):
            call_order_service._attempts = 0
        call_order_service._attempts += 1
        if call_order_service._attempts < 3:
            raise ConnectionError("Order Service temporariamente indisponível")
        call_order_service._attempts = 0  # reset
 
    return {
        "order_id": order["order_id"],
        "status": "confirmed",
        "items": order["items"],
        "total": order["total"],
        "created_at": datetime.now().isoformat(),
    }
 
async def call_payment_service(order: dict, simulate_mode: str = "ok") -> dict:
    """
    Modos: ok | fallback_fail
    """
    await asyncio.sleep(0.3)
 
    if simulate_mode == "fallback_fail":
        raise RuntimeError("Payment Gateway offline")
 
    return {
        "payment_id": f"PAY-{int(time.time())}",
        "order_id": order["order_id"],
        "method": order.get("payment_method", "cartão"),
        "status": "approved",
        "approved_at": datetime.now().isoformat(),
    }
 
async def call_notification_service(order_result: dict) -> None:
    """Notificação assíncrona - falha silenciosamente com log."""
    await asyncio.sleep(0.1)
    if random.random() < 0.2:  # 20% chance de falha (demonstração)
        raise RuntimeError("SMTP indisponível")
    print(f"  [NOTIFICATION] E-mail enviado para pedido {order_result['order_id']}")
 
async def publish_to_broker(event: dict, simulate_offline: bool = False) -> None:
    """Publica evento no broker. Fallback: salva em JSON local."""
    if simulate_offline:
        raise ConnectionError("Message Broker offline")
    await asyncio.sleep(0.05)
    print(f"  [BROKER] Evento publicado: {event['type']} / pedido {event['order_id']}")
 
# ─── ORQUESTRADOR PRINCIPAL ───────────────────────────────────────────────────
 
async def process_order(order: dict, simulate: dict = None) -> dict:
    """
    Fluxo principal:
      1. Order Service (sync / RPC) — com Retry + Timeout
      2. Payment Service (sync / RPC) — com Timeout + Fallback
      3. Broker (async)             — com Fallback para JSON
      4. Notification (async)       — best-effort
    """
    sim = simulate or {}
    result = {"order_id": order["order_id"], "steps": []}
 
    print(f"\n{'='*55}")
    print(f"PROCESSANDO PEDIDO {order['order_id']}")
    print(f"{'='*55}")
 
    # ── 1. ORDER SERVICE ──────────────────────────────────
    print("\n→ [1/4] Order Service (sync, RPC)")
    try:
        order_mode = sim.get("order", "ok")
        order_result = await with_timeout(
            with_retry(
                lambda: call_order_service(order, order_mode),
                max_attempts=3,
                label="OrderService",
            ),
            seconds=5,
            label="OrderService",
        )
        print(f"  ✓ Pedido confirmado: {order_result['order_id']}")
        result["steps"].append({"step": "order", "status": "ok", "data": order_result})
    except TimeoutError as e:
        print(f"  ✗ {e}")
        # Fallback: enfileira localmente
        msg = save_fallback_order(order)
        result["steps"].append({"step": "order", "status": "timeout_fallback", "message": msg})
        order_result = {**order, "status": "queued_fallback"}
    except Exception as e:
        result["steps"].append({"step": "order", "status": "error", "message": str(e)})
        return {**result, "final_status": "failed", "message": str(e)}
 
    # ── 2. PAYMENT SERVICE ────────────────────────────────
    print("\n→ [2/4] Payment Service (sync, RPC)")
    try:
        pay_mode = sim.get("payment", "ok")
        payment_result = await with_timeout(
            call_payment_service(order, pay_mode),
            seconds=10,
            label="PaymentService",
        )
        print(f"  ✓ Pagamento aprovado: {payment_result['payment_id']}")
        result["steps"].append({"step": "payment", "status": "ok", "data": payment_result})
    except (RuntimeError, TimeoutError) as e:
        print(f"  ✗ {e}")
        # Fallback: pagamento na entrega
        fallback_pay = payment_fallback(order)
        print(f"  ↩ FALLBACK: {fallback_pay['message']}")
        payment_result = fallback_pay
        result["steps"].append({"step": "payment", "status": "fallback", "data": fallback_pay})
 
    # ── 3. BROKER (ASYNC) ─────────────────────────────────
    print("\n→ [3/4] Message Broker (async, mensageria)")
    broker_offline = sim.get("broker_offline", False)
    try:
        event = {
            "type": "ORDER_COMPLETED",
            "order_id": order["order_id"],
            "payment": payment_result,
            "ts": datetime.now().isoformat(),
        }
        await publish_to_broker(event, simulate_offline=broker_offline)
        result["steps"].append({"step": "broker", "status": "ok"})
    except ConnectionError as e:
        print(f"  ✗ {e}")
        # Fallback: salva evento em JSON local
        msg = save_fallback_order({"type": "BROKER_FALLBACK", **event})
        print(f"  ↩ FALLBACK: {msg}")
        result["steps"].append({"step": "broker", "status": "fallback", "message": msg})
 
    # ── 4. NOTIFICATION (ASYNC, best-effort) ──────────────
    print("\n→ [4/4] Notification Service (async, best-effort)")
    try:
        await with_retry(
            lambda: call_notification_service(order_result),
            max_attempts=3,
            base_delay=0.2,
            label="Notification",
        )
        result["steps"].append({"step": "notification", "status": "ok"})
    except Exception as e:
        print(f"  ✗ Notificação falhou após retries: {e} (log salvo, será reprocessado)")
        result["steps"].append({"step": "notification", "status": "log_retry", "message": str(e)})
 
    result["final_status"] = "success"
    result["payment"] = payment_result
    result["message"] = "Pedido processado com sucesso!"
    print(f"\n{'='*55}")
    print(f"✓ PEDIDO {order['order_id']} FINALIZADO")
    print(f"{'='*55}\n")
    return result
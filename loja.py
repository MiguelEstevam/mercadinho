"""
Mercadinho 24h - Tela de Compra (CLI)
Fluxo feliz + casos de teste
"""
import asyncio
import uuid
import json
from datetime import datetime
from gateway import process_order
 
# ──────────────────────────────────────────────────
CATALOG = {
    "1": {"name": "Água Mineral 500ml", "price": 2.50},
    "2": {"name": "Refrigerante Lata",   "price": 5.00},
    "3": {"name": "Salgadinho",           "price": 4.50},
    "4": {"name": "Chocolate",            "price": 6.00},
    "5": {"name": "Café Cápsula",         "price": 3.50},
    "6": {"name": "Energético",           "price": 8.00},
    "7": {"name": "Sorvete",              "price": 7.50},
    "8": {"name": "Sanduíche",            "price": 12.00},
}
 
PAYMENT_METHODS = {
    "1": "cartão de crédito",
    "2": "PIX",
    "3": "cartão de débito",
}
 
# ──────────────────────────────────────────────────
 
def clear():
    print("\n" + "─" * 55)
 
def print_header():
    print("=" * 55)
    print("        🛒  MERCADINHO 24H  🛒")
    print("=" * 55)
 
def print_catalog():
    print("\n📦 PRODUTOS DISPONÍVEIS:")
    for code, item in CATALOG.items():
        print(f"  [{code}] {item['name']:<25} R$ {item['price']:.2f}")
    print("  [0] Finalizar seleção")
 
def build_cart() -> list:
    cart = []
    while True:
        print_catalog()
        code = input("\nDigite o código do produto (0 para finalizar): ").strip()
        if code == "0":
            break
        if code not in CATALOG:
            print("  ⚠ Código inválido.")
            continue
        item = CATALOG[code]
        qty = input(f"  Quantidade de '{item['name']}': ").strip()
        try:
            qty = int(qty)
            if qty <= 0:
                raise ValueError
        except ValueError:
            print("  ⚠ Quantidade inválida.")
            continue
        cart.append({"name": item["name"], "price": item["price"], "qty": qty, "subtotal": item["price"] * qty})
        print(f"  ✓ Adicionado: {qty}x {item['name']}")
    return cart
 
def print_cart(cart: list):
    if not cart:
        print("  Carrinho vazio.")
        return
    print("\n🛒 SEU CARRINHO:")
    print(f"  {'Produto':<25} {'Qtd':>4} {'Unit':>8} {'Subtotal':>10}")
    print(f"  {'─'*25} {'─'*4} {'─'*8} {'─'*10}")
    total = 0
    for item in cart:
        print(f"  {item['name']:<25} {item['qty']:>4} R${item['price']:>6.2f} R${item['subtotal']:>8.2f}")
        total += item["subtotal"]
    print(f"  {'─'*52}")
    print(f"  {'TOTAL':>38} R${total:>8.2f}")
    return total
 
def choose_payment() -> str:
    print("\n💳 FORMA DE PAGAMENTO:")
    for code, method in PAYMENT_METHODS.items():
        print(f"  [{code}] {method}")
    while True:
        choice = input("Escolha: ").strip()
        if choice in PAYMENT_METHODS:
            return PAYMENT_METHODS[choice]
        print("  ⚠ Opção inválida.")
 
def print_result(result: dict):
    clear()
    if result["final_status"] == "success":
        print("\n✅  COMPRA FINALIZADA COM SUCESSO!")
    else:
        print("\n❌  ERRO NO PROCESSAMENTO")
 
    print(f"\n  Pedido:  {result['order_id']}")
    pay = result.get("payment", {})
    if pay.get("status") == "fallback" or pay.get("status") == "accepted_fallback":
        print(f"  Pagamento: {pay.get('message', pay.get('payment_method', '-'))}")
    else:
        print(f"  Pagamento: {pay.get('method', '-')} — {pay.get('status', '-')}")
 
    print("\n  Etapas processadas:")
    icons = {"ok": "✓", "fallback": "↩", "timeout_fallback": "⏱↩", "log_retry": "⚠", "error": "✗"}
    for step in result["steps"]:
        icon = icons.get(step["status"], "?")
        msg = step.get("message") or step.get("data", {}).get("status", "")
        print(f"    {icon} {step['step'].upper():<15} [{step['status']}] {msg}")
 
    print(f"\n  {result.get('message', '')}")
 
# ──────────────────────────────────────────────────
# MENU PRINCIPAL
# ──────────────────────────────────────────────────
 
MODES = {
    "1": {"label": "Compra normal (fluxo feliz)",         "simulate": {}},
    "2": {"label": "Teste RETRY — Order Service instável","simulate": {"order": "retry_fail"}},
    "3": {"label": "Teste TIMEOUT — Order Service lento", "simulate": {"order": "timeout"}},
    "4": {"label": "Teste FALLBACK — Payment offline",    "simulate": {"payment": "fallback_fail"}},
    "5": {"label": "Teste FALLBACK — Broker offline",     "simulate": {"broker_offline": True}},
}
 
async def main():
    print_header()
    print("\n🧪 MODO DE EXECUÇÃO:")
    for k, v in MODES.items():
        print(f"  [{k}] {v['label']}")
 
    while True:
        mode_key = input("\nEscolha o modo: ").strip()
        if mode_key in MODES:
            break
        print("  ⚠ Opção inválida.")
 
    mode = MODES[mode_key]
    print(f"\n  Modo selecionado: {mode['label']}")
 
    # Montar carrinho
    cart = build_cart()
    if not cart:
        print("\nCarrinho vazio. Encerrando.")
        return
 
    total = print_cart(cart)
    payment_method = choose_payment()
 
    print(f"\n  💡 Simulação ativa: {json.dumps(mode['simulate']) or 'nenhuma'}")
    confirm = input("\nConfirmar pedido? [S/n]: ").strip().lower()
    if confirm == "n":
        print("Pedido cancelado.")
        return
 
    order = {
        "order_id": f"ORD-{uuid.uuid4().hex[:8].upper()}",
        "items": cart,
        "total": total,
        "payment_method": payment_method,
        "created_at": datetime.now().isoformat(),
    }
 
    print("\n⏳ Processando...\n")
    result = await process_order(order, simulate=mode["simulate"])
    print_result(result)
 
if __name__ == "__main__":
    asyncio.run(main())
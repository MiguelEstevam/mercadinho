"""
Servidor Web - Mercadinho 24h
Backend API para integração com frontend
"""
import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from aiohttp import web
from gateway import process_order

# Catálogo de produtos
CATALOG = {
    "1": {"id": "1", "name": "Água Mineral 500ml", "price": 2.50, "emoji": "💧"},
    "2": {"id": "2", "name": "Refrigerante Lata", "price": 5.00, "emoji": "🥤"},
    "3": {"id": "3", "name": "Salgadinho", "price": 4.50, "emoji": "🍿"},
    "4": {"id": "4", "name": "Chocolate", "price": 6.00, "emoji": "🍫"},
    "5": {"id": "5", "name": "Café Cápsula", "price": 3.50, "emoji": "☕"},
    "6": {"id": "6", "name": "Energético", "price": 8.00, "emoji": "⚡"},
    "7": {"id": "7", "name": "Sorvete", "price": 7.50, "emoji": "🍦"},
    "8": {"id": "8", "name": "Sanduíche", "price": 12.00, "emoji": "🥪"},
}

MODES = {
    "normal": {"label": "Compra normal (fluxo feliz)", "simulate": {}},
    "retry": {"label": "Teste RETRY — Order Service instável", "simulate": {"order": "retry_fail"}},
    "timeout": {"label": "Teste TIMEOUT — Order Service lento", "simulate": {"order": "timeout"}},
    "payment_fallback": {"label": "Teste FALLBACK — Payment offline", "simulate": {"payment": "fallback_fail"}},
    "broker_fallback": {"label": "Teste FALLBACK — Broker offline", "simulate": {"broker_offline": True}},
}

# Rotas
async def get_catalog(request):
    """Retorna catálogo de produtos"""
    return web.json_response(list(CATALOG.values()))

async def get_modes(request):
    """Retorna modos de simulação disponíveis"""
    return web.json_response([
        {"id": k, **v} for k, v in MODES.items()
    ])

async def create_order(request):
    """Processa um novo pedido"""
    try:
        data = await request.json()
        
        # Validar dados
        if not data.get("items") or not isinstance(data["items"], list):
            return web.json_response(
                {"error": "Items inválidos"}, 
                status=400
            )
        
        # Montar pedido
        order = {
            "order_id": f"ORD-{uuid.uuid4().hex[:8].upper()}",
            "items": data["items"],
            "total": data.get("total", 0),
            "payment_method": data.get("payment_method", "cartão"),
            "created_at": datetime.now().isoformat(),
        }
        
        # Obter modo de simulação
        mode_id = data.get("mode", "normal")
        simulate = MODES.get(mode_id, {}).get("simulate", {})
        
        # Processar pedido
        result = await process_order(order, simulate=simulate)
        
        return web.json_response(result)
        
    except Exception as e:
        print(f"Erro ao processar pedido: {e}")
        return web.json_response(
            {"error": str(e)}, 
            status=500
        )

async def index(request):
    """Serve o frontend HTML"""
    html_file = Path(__file__).parent / "index.html"
    if html_file.exists():
        return web.FileResponse(html_file)
    return web.Response(text="Frontend não encontrado", status=404)

# Configurar aplicação
app = web.Application()

# CORS middleware para desenvolvimento
async def cors_middleware(app, handler):
    async def middleware(request):
        if request.method == "OPTIONS":
            return web.Response(
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type",
                }
            )
        response = await handler(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response
    return middleware

app.middlewares.append(cors_middleware)

# Rotas
app.router.add_get("/", index)
app.router.add_get("/api/catalog", get_catalog)
app.router.add_get("/api/modes", get_modes)
app.router.add_post("/api/orders", create_order)

if __name__ == "__main__":
    print("\n" + "="*55)
    print("🛒  MERCADINHO 24H - Servidor Web")
    print("="*55)
    print("\n➜  Acesse: http://localhost:8080")
    print("➜  Pressione Ctrl+C para parar\n")
    
    web.run_app(app, host="0.0.0.0", port=8080, print=None)

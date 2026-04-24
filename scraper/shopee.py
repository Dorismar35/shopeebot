import os
import time
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("scraper")

DESCONTO_MINIMO   = int(os.getenv("DESCONTO_MINIMO", 30))
PRECO_MINIMO      = float(os.getenv("PRECO_MINIMO", 10))
PRECO_MAXIMO      = float(os.getenv("PRECO_MAXIMO", 500))
AVALIACAO_MINIMA  = float(os.getenv("AVALIACAO_MINIMA", 4.0))
VENDAS_MINIMAS    = int(os.getenv("VENDAS_MINIMAS", 100))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

AFFILIATE_ID = os.getenv("SHOPEE_AFFILIATE_ID", "")


def _link_afiliado(url_produto: str) -> str:
    """Transforma link normal em link de afiliado Shopee."""
    if not AFFILIATE_ID:
        return url_produto
    return f"https://shope.ee/afiliado?pid={AFFILIATE_ID}&url={url_produto}"


def buscar_ofertas_api() -> list[dict]:
    """
    Busca ofertas via API oficial da Shopee Afiliados.
    Se não houver chaves configuradas, retorna o modo demo.
    """
    app_id = os.getenv("SHOPEE_APP_ID")
    secret = os.getenv("SHOPEE_SECRET")

    if not app_id or not secret:
        logger.warning("SHOPEE_APP_ID ou SHOPEE_SECRET não configurados. Usando modo demo.")
        return _dados_demo()

    try:
        url = "https://open-api.affiliate.shopee.com.br/graphql"
        query = """
        {
          productOfferV2(listType: 0, sortType: 2, limit: 50) {
            nodes {
              itemId productName shopName imageUrl priceMin priceMax
              priceDiscount sales ratingStar offerLink discountPercentage
            }
          }
        }
        """
        import hmac, hashlib
        timestamp = str(int(time.time()))
        payload_str = f"{app_id}{timestamp}{query}"
        signature = hmac.new(secret.encode(), payload_str.encode(), hashlib.sha256).hexdigest()

        headers = {
            **HEADERS,
            "Authorization": f"SHA256 Credential={app_id},Timestamp={timestamp},Signature={signature}",
            "Content-Type": "application/json",
        }
        resp = requests.post(url, json={"query": query}, headers=headers, timeout=15)
        if resp.status_code == 200:
            nodes = resp.json()["data"]["productOfferV2"]["nodes"]
            return _filtrar(nodes)
        else:
            logger.error(f"Erro na API Shopee: {resp.status_code} - {resp.text}")
            return _dados_demo()

    except Exception as e:
        logger.error(f"Erro na API Shopee: {e}")
        return _dados_demo()


def _filtrar(produtos: list[dict]) -> list[dict]:
    """Aplica filtros de qualidade nos produtos da API."""
    resultado = []
    for p in produtos:
        try:
            desconto   = float(p.get("discountPercentage", 0))
            preco      = float(p.get("priceMin", 0)) / 100000
            avaliacao  = float(p.get("ratingStar", 0))
            vendas     = int(p.get("sales", 0))

            if desconto < DESCONTO_MINIMO: continue
            if not (PRECO_MINIMO <= preco <= PRECO_MAXIMO): continue
            if avaliacao < AVALIACAO_MINIMA: continue
            if vendas < VENDAS_MINIMAS: continue

            resultado.append({
                "nome":        p.get("productName", "Produto"),
                "loja":        p.get("shopName", ""),
                "imagem_url":  p.get("imageUrl", ""),
                "preco":       preco,
                "desconto":    int(desconto),
                "avaliacao":   avaliacao,
                "vendas":      vendas,
                "link":        _link_afiliado(p.get("offerLink", "")),
            })
        except:
            continue
    return resultado


def _dados_demo() -> list[dict]:
    """Retorna dados fictícios bonitos para testar o bot enquanto as chaves não chegam."""
    return [
        {
            "nome":       "Fone Bluetooth TWS Pro X9",
            "loja":       "TechStore Oficial",
            "imagem_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800",
            "preco":      49.90,
            "desconto":   55,
            "avaliacao":  4.8,
            "vendas":     3200,
            "link":       "https://shopee.com.br/demo",
        },
        {
            "nome":       "Relógio Smartwatch IP68",
            "loja":       "SmartShop BR",
            "imagem_url": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800",
            "preco":      89.90,
            "desconto":   48,
            "avaliacao":  4.6,
            "vendas":     1800,
            "link":       "https://shopee.com.br/demo2",
        },
        {
            "nome":       "Kit Gamer Teclado e Mouse RGB",
            "loja":       "GameMaster",
            "imagem_url": "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=800",
            "preco":      129.90,
            "desconto":   35,
            "avaliacao":  4.7,
            "vendas":     950,
            "link":       "https://shopee.com.br/demo3",
        },
    ]

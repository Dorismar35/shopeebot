import os
import io
import textwrap
import logging
import requests
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

logger = logging.getLogger("gerador")

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

ASSETS_DIR = Path(__file__).parent.parent / "assets"
OUTPUT_DIR = Path(__file__).parent.parent / "banco" / "imagens"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Tamanho TikTok (vertical 9:16)
LARGURA  = 1080
ALTURA   = 1920


def gerar_legenda_gemini(produto: dict) -> str:
    """Usa Gemini para gerar legenda chamativa para o TikTok."""
    if not GEMINI_KEY:
        return _legenda_padrao(produto)
    try:
        model = genai.GenerativeModel("gemini-flash-latest")
        prompt = f"""
Você é um especialista em marketing para TikTok brasileiro.
Crie uma legenda CURTA e CHAMATIVA (máximo 150 caracteres) para um post de oferta.

Produto: {produto['nome']}
Desconto: {produto['desconto']}% OFF
Preço: R$ {produto['preco']:.2f}
Avaliação: {produto['avaliacao']} estrelas

Use emojis, seja empolgante, use gírias brasileiras.
Termine com: #shopee #oferta #promoção #tiktokbrasil
Responda APENAS a legenda, sem explicações.
"""
        resp = model.generate_content(prompt)
        return resp.text.strip()
    except Exception as e:
        logger.error(f"Erro Gemini: {e}")
        return _legenda_padrao(produto)


def gerar_roteiro_gemini(produto: dict) -> str:
    """Usa Gemini para gerar um roteiro de narração para o vídeo."""
    if not GEMINI_KEY:
        return f"Olha essa oferta incrível! {produto['nome']} com {produto['desconto']}% de desconto. Aproveita!"
    try:
        model = genai.GenerativeModel("gemini-flash-latest")
        prompt = f"""
Você é um influencer brasileiro de promoções.
Crie um roteiro de narração CURTO (máximo 15 segundos de fala) para um vídeo de oferta.

Produto: {produto['nome']}
Desconto: {produto['desconto']}% OFF
Preço: R$ {produto['preco']:.2f}

O tom deve ser amigável, empolgado e direto. 
Fale sobre o benefício do produto e o preço baixo.
Responda APENAS o texto que será falado, sem introduções ou observações.
"""
        resp = model.generate_content(prompt)
        return resp.text.strip().replace('"', '').replace('*', '')
    except Exception as e:
        logger.error(f"Erro Gemini Roteiro: {e}")
        return f"Olha essa oferta incrível! {produto['nome']} com {produto['desconto']}% de desconto. Aproveita!"


def _legenda_padrao(produto: dict) -> str:
    return (
        f"🔥 {produto['desconto']}% OFF em {produto['nome'][:40]}! "
        f"Por apenas R$ {produto['preco']:.2f} 😱 "
        f"Corre que é por tempo limitado! "
        f"#shopee #oferta #promoção #tiktokbrasil"
    )


def _baixar_imagem_produto(url: str) -> Image.Image | None:
    """Baixa a imagem do produto usando headers para evitar bloqueios."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        return img
    except Exception as e:
        logger.warning(f"Falha ao baixar imagem de {url}: {e}")
        return None


def _fonte(tamanho: int, negrito: bool = False):
    """Tenta carregar fonte, cai em padrão se não achar."""
    fontes_candidatas = [
        "C:/Windows/Fonts/arialbd.ttf" if negrito else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if negrito
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for caminho in fontes_candidatas:
        if Path(caminho).exists():
            return ImageFont.truetype(caminho, tamanho)
    return ImageFont.load_default()


def gerar_imagem(produto: dict, legenda: str) -> Path:
    """
    Gera imagem vertical no formato TikTok (1080×1920).
    Retorna o caminho da imagem salva.
    """
    # Fundo gradiente escuro
    fundo = Image.new("RGB", (LARGURA, ALTURA), color="#0a0a0a")
    draw  = ImageDraw.Draw(fundo)

    # Gradiente laranja no topo (cor Shopee)
    for i in range(300):
        alpha = int(255 * (1 - i / 300))
        cor   = (238, 77, 45, alpha)  # Laranja Shopee
        draw.rectangle([(0, i), (LARGURA, i + 1)], fill=f"#{'%02x%02x%02x' % (238, int(77*(1-i/300)), int(45*(1-i/300)))}")

    # Logo / título topo
    fonte_titulo = _fonte(72, negrito=True)
    draw.text((LARGURA // 2, 80), "🛍️ OFERTA SHOPEE", font=fonte_titulo, fill="white", anchor="mm")

    # Badge de desconto
    badge_x, badge_y = LARGURA - 160, 200
    draw.ellipse([(badge_x, badge_y), (badge_x + 200, badge_y + 200)], fill="#ee4d2d")
    fonte_desconto = _fonte(80, negrito=True)
    draw.text((badge_x + 100, badge_y + 80), f"-{produto['desconto']}%", font=fonte_desconto, fill="white", anchor="mm")
    fonte_off = _fonte(36)
    draw.text((badge_x + 100, badge_y + 155), "OFF", font=fonte_off, fill="white", anchor="mm")

    # Imagem do produto (centro)
    img_produto = _baixar_imagem_produto(produto["imagem_url"])
    if img_produto:
        img_produto = img_produto.resize((800, 800), Image.LANCZOS)
        # Fundo branco arredondado para o produto
        fundo_produto = Image.new("RGBA", (820, 820), (255, 255, 255, 255))
        fundo.paste(fundo_produto, (130, 380), fundo_produto)
        if img_produto.mode == "RGBA":
            fundo.paste(img_produto, (140, 390), img_produto)
        else:
            fundo.paste(img_produto, (140, 390))
    else:
        draw.rectangle([(130, 380), (950, 1180)], fill="#1a1a1a")
        draw.text((LARGURA // 2, 780), "📦", font=_fonte(200), fill="#ee4d2d", anchor="mm")

    # Nome do produto
    fonte_nome = _fonte(52, negrito=True)
    nome_curto = textwrap.fill(produto["nome"][:80], width=22)
    draw.text((LARGURA // 2, 1230), nome_curto, font=fonte_nome, fill="white", anchor="mm", align="center")

    # Preço
    fonte_preco = _fonte(96, negrito=True)
    draw.text((LARGURA // 2, 1420), f"R$ {produto['preco']:.2f}", font=fonte_preco, fill="#ee4d2d", anchor="mm")

    # Avaliação
    estrelas = "⭐" * int(produto["avaliacao"])
    fonte_av  = _fonte(44)
    draw.text((LARGURA // 2, 1510), f"{estrelas} {produto['avaliacao']} ({produto['vendas']} vendas)",
              font=fonte_av, fill="#ffd700", anchor="mm")

    # Call to action
    draw.rectangle([(100, 1580), (LARGURA - 100, 1680)], fill="#ee4d2d")
    fonte_cta = _fonte(56, negrito=True)
    draw.text((LARGURA // 2, 1630), "🔗 LINK NA BIO!", font=fonte_cta, fill="white", anchor="mm")

    # Legenda (hashtags no fundo)
    fonte_hash = _fonte(32)
    hashtags   = " ".join([w for w in legenda.split() if w.startswith("#")])
    draw.text((LARGURA // 2, 1750), hashtags[:60], font=fonte_hash, fill="#888888", anchor="mm")

    # Rodapé
    draw.text((LARGURA // 2, 1850), "Oferta por tempo limitado • Shopee Brasil",
              font=_fonte(30), fill="#555555", anchor="mm")

    # Salvar
    nome_arquivo = f"{produto['nome'][:30].replace(' ', '_').replace('/', '')}_{produto['desconto']}off.jpg"
    caminho      = OUTPUT_DIR / nome_arquivo
    fundo.convert("RGB").save(str(caminho), "JPEG", quality=95)
    logger.info(f"Imagem gerada: {caminho}")
    return caminho

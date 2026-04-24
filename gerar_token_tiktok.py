import webbrowser
import hashlib
import base64
import secrets
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests

CLIENT_KEY = "sbawnzpcic2googv0i"
CLIENT_SECRET = "sd3xEzNQZnY2XkuzT9dC0ceeprJJ1Ro3"
REDIRECT_URI = "https://squire-sculptor-flaxseed.ngrok-free.dev/callback"

code_verifier = secrets.token_urlsafe(64)
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
).rstrip(b"=").decode()

auth_url = (
    f"https://www.tiktok.com/v2/auth/authorize/"
    f"?client_key={CLIENT_KEY}"
    f"&scope=video.publish,video.upload"
    f"&response_type=code"
    f"&redirect_uri={REDIRECT_URI}"
    f"&state=shopeebot"
    f"&code_challenge={code_challenge}"
    f"&code_challenge_method=S256"
)

print(f"URL de Autorização: {auth_url}")
print("Abrindo navegador...")
webbrowser.open(auth_url)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if "code" in params:
            code = params["code"][0]
            print(f"Código recebido!")
            resp = requests.post(
                "https://open.tiktokapis.com/v2/oauth/token/",
                data={
                    "client_key": CLIENT_KEY,
                    "client_secret": CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": REDIRECT_URI,
                    "code_verifier": code_verifier,
                }
            )
            token_data = resp.json()
            print(f"Resposta: {token_data}")
            access_token = token_data.get("access_token", "")
            refresh_token = token_data.get("refresh_token", "")
            if access_token:
                import re
                with open(".env", "r") as f:
                    content = f.read()
                content = re.sub(r"TIKTOK_ACCESS_TOKEN=.*", f"TIKTOK_ACCESS_TOKEN={access_token}", content)
                if refresh_token:
                    content = re.sub(r"TIKTOK_REFRESH_TOKEN=.*", f"TIKTOK_REFRESH_TOKEN={refresh_token}", content)
                with open(".env", "w") as f:
                    f.write(content)
                print("TOKENS SALVOS COM SUCESSO!")
                print(f"ACCESS_TOKEN: {access_token}")
                print(f"REFRESH_TOKEN: {refresh_token}")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Autorizado! Pode fechar esta janela.")
    def log_message(self, *args):
        pass

print("Aguardando autorização...")
HTTPServer(("localhost", 8080), Handler).handle_request()

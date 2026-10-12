from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

	app_name: str = "Neural Terminal Backend"
	debug: bool = False

	cloudflare_account_id: str
	cloudflare_d1_database_id: str
	cloudflare_api_token: str
	cloudflare_api_base_url: str = "https://api.cloudflare.com/client/v4"

	server_port: int = 3000
	ai_api_key: str = ""

	jwt_secret_key: str
	jwt_algorithm: str = "HS256"
	access_token_expire_minutes: int = 30
	refresh_token_expire_days: int = 7

	# Format "<count>/<number><unit>", unit one of s, m, h, d (e.g. "5/1m", "10/1h", "5/15m").
	rate_limit_enabled: bool = True
	rate_limit_default: str = "300/1m"
	rate_limit_login_ip: str = "20/1m"
	rate_limit_login_account: str = "5/1m"
	rate_limit_signup: str = "10/1h"
	rate_limit_refresh: str = "30/1m"
	rate_limit_sensitive: str = "5/15m"
	# Only enable behind a trusted reverse proxy (reads client IP from X-Forwarded-For).
	trust_proxy_headers: bool = False

	# TODO(production): set CORS_ALLOWED_ORIGINS in .env to the deployed frontend URL(s).
	# Empty means no browser origin is allowed.
	cors_allowed_origins: str = ""

	@property
	def cors_origins(self) -> list[str]:
		return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

	@property
	def d1_query_url(self) -> str:
		return (
			f"{self.cloudflare_api_base_url}/accounts/{self.cloudflare_account_id}"
			f"/d1/database/{self.cloudflare_d1_database_id}/query"
		)


settings = Settings()

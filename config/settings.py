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

	@property
	def d1_query_url(self) -> str:
		return (
			f"{self.cloudflare_api_base_url}/accounts/{self.cloudflare_account_id}"
			f"/d1/database/{self.cloudflare_d1_database_id}/query"
		)


settings = Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

	app_name: str = "Neural Terminal Backend"
	debug: bool = False

	db_url: str | None = None
	db_host: str = "localhost"
	db_port: int = 5432
	db_user: str = ""
	db_password: str = ""
	db_name: str = "neural_terminal"

	server_port: int = 3000
	ai_api_key: str = ""

	jwt_secret_key: str
	jwt_algorithm: str = "HS256"
	access_token_expire_minutes: int = 30
	refresh_token_expire_days: int = 7

	@property
	def database_url(self) -> str:
		if self.db_url:
			return self.db_url
		return (
			f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
			f"@{self.db_host}:{self.db_port}/{self.db_name}"
		)


settings = Settings()

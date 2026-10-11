from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field, model_validator, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict
from .paths import PROJECT_ROOT

class ClientConfig(BaseModel):
    base_url: str
    api_key: str
    model: str
    proxy: Optional[str] = None

class Settings(BaseSettings): 
    PROJECT_NAME: str = "Bangladesh Engineering Workshop" 
    VERSION: str = "0.0.5"
    ENV: str = Field(default="development", validation_alias="APP_ENV")

    # Flask configurations
    SECRET_KEY: str = Field(..., validation_alias="SECRET_KEY")
    API_HOST: str = Field(default="127.0.0.1", validation_alias=AliasChoices("API_HOST", "APP_HOST"))
    API_PORT: int = Field(default=5000, validation_alias=AliasChoices("API_PORT", "APP_PORT"))
    FRONTEND_URL: str = Field(default="http://localhost:3000", validation_alias="FRONTEND_URL")
    FRONTEND_PORT: int = Field(default=3000, validation_alias="FRONTEND_PORT")
    ENABLE_TAILSCALE: bool = Field(default=False, validation_alias=AliasChoices("ENABLE_TAILSCALE", "TAILSCALE"))
    PUBLIC_URL: Optional[str] = Field(default=None, validation_alias="PUBLIC_URL")
    
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = Field(..., validation_alias="SQLALCHEMY_TRACK_MODIFICATIONS")
    BABEL_DEFAULT_LOCALE: str = Field(..., validation_alias="BABEL_DEFAULT_LOCALE")
    BABEL_TRANSLATION_DIRECTORIES: str = Field(..., validation_alias="BABEL_TRANSLATION_DIRECTORIES")

    # Database
    DATABASE_NAME: str = Field(..., validation_alias="DATABASE_NAME")
    DELETE_PASSWORD: str = Field(..., validation_alias="DELETE_PASSWORD")
    DELETE_PASSWORD_ENABLED: bool = Field(..., validation_alias="DELETE_PASSWORD_ENABLED")

    # Admin Login
    ADMIN_USERNAME: str = Field(..., validation_alias="ADMIN_USERNAME")
    ADMIN_PASSWORD: str = Field(..., validation_alias="ADMIN_PASSWORD")

    # Business Info for SEO
    BUSINESS_NAME: str = Field(..., validation_alias="BUSINESS_NAME")
    BUSINESS_DESC: str = Field(..., validation_alias="BUSINESS_DESC")
    BUSINESS_ADDRESS: str = Field(..., validation_alias="BUSINESS_ADDRESS")
    BUSINESS_PHONE: str = Field(..., validation_alias="BUSINESS_PHONE")
    BUSINESS_EMAIL: str = Field(..., validation_alias="BUSINESS_EMAIL")
    BUSINESS_MAP_URL: str = Field(..., validation_alias="BUSINESS_MAP_URL")
    BUSINESS_OPENING_HOURS: str = Field(..., validation_alias="BUSINESS_OPENING_HOURS")
    BUSINESS_OPEN_TIME: str = Field(..., validation_alias="BUSINESS_OPEN_TIME")
    BUSINESS_CLOSE_TIME: str = Field(..., validation_alias="BUSINESS_CLOSE_TIME")
    BUSINESS_LATITUDE: float = Field(..., validation_alias="BUSINESS_LATITUDE")
    BUSINESS_LONGITUDE: float = Field(..., validation_alias="BUSINESS_LONGITUDE")

    LLM_TEMPERATURE: float = Field(default=0.7, validation_alias="LLM_TEMPERATURE")
    LLM_MAX_TOKENS: int = Field(default=2048, validation_alias="LLM_MAX_TOKENS")
    LLM_RETRIES: int = Field(default=3, validation_alias="LLM_RETRIES")
    LLM_CLIENTS: list[ClientConfig] = Field(default_factory=list)
    AGENT_PORFILE: str = Field(default=".profile/agents", validation_alias="AGENT_PORFILE")

    @property
    def APP_HOST(self) -> str:
        return self.API_HOST

    @property
    def APP_PORT(self) -> int:
        return self.API_PORT

    @property
    def DATABASE_URL(self) -> str:
        return f"sqlite:///{PROJECT_ROOT / self.DATABASE_NAME}"

    # Directories (optional — have sensible defaults relative to project root)
    log_dir_rel: str = Field(..., validation_alias="LOG_DIR")
    models_dir_rel: str = Field(..., validation_alias="MODELS_DIR")
    upload_dir_rel: str = Field(..., validation_alias="UPLOAD_DIR")
    data_dir_rel: str = Field(..., validation_alias="DATA_DIR")

    # Files
    shops_json_rel: str = Field(..., validation_alias="SHOPS_JSON")
    odt_file_rel: str = Field(..., validation_alias="ODT_FILE")

    @model_validator(mode="before")
    @classmethod
    def assemble_client_configs(cls, values: dict) -> dict:
        grouped: dict[str, dict[str, str]] = {}
        for key, val in values.items():
            k = key.lower()
            if not k.startswith("client_configs_"):
                continue
            parts = k.split("_", 3)
            if len(parts) >= 4:
                idx, field_name = parts[2], parts[3]
                grouped.setdefault(idx, {})[field_name] = str(val)

        clients: list[ClientConfig] = []
        for _, data in sorted(grouped.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
            base_url = data.get("base_url")
            api_key = data.get("api_key")
            model = data.get("model")
            if base_url and api_key and model:
                clients.append(
                    ClientConfig(
                        base_url=base_url,
                        api_key=api_key,
                        model=model,
                        proxy=data.get("proxy_http"),
                    )
                )

        values["LLM_CLIENTS"] = clients
        return values

    def _resolve(self, val: str) -> Path:
        val = val.strip()
        # Handle /.hidden -> ~/.hidden (Forgotten tilde)
        if val.startswith("/."):
            val = "~/" + val[2:] if val.startswith("/./") else "~/" + val[1:]

        # Handle .hidden (if it's not ./ or ../) -> treat as home relative for our tools
        if val.startswith(".") and not val.startswith("./") and not val.startswith("../"):
            val = "~/" + val

        p = Path(val).expanduser()
        return p if p.is_absolute() else PROJECT_ROOT / p

    @property
    def LOG_DIR(self) -> Path: return self._resolve(self.log_dir_rel)

    @property
    def MODELS_DIR(self) -> Path: return self._resolve(self.models_dir_rel)

    @property
    def UPLOAD_DIR(self) -> Path: return self._resolve(self.upload_dir_rel)

    @property
    def DATA_DIR(self) -> Path: return self._resolve(self.data_dir_rel)

    @property
    def SHOPS_JSON_PATH(self) -> Path: return self._resolve(self.shops_json_rel)

    @property
    def ODT_FILE_PATH(self) -> Path: return self._resolve(self.odt_file_rel)

    @property
    def EXTRACTED_ODT_DIR(self) -> Path: return self.DATA_DIR / "extracted_odt"

    @property
    def SALES_VOUCHER_DIR(self) -> Path: return self.UPLOAD_DIR / "sales_voucher"

    @property
    def PURCHASE_VOUCHER_DIR(self) -> Path: return self.UPLOAD_DIR / "purchase_voucher"

    @property
    def WORK_ORDER_DIR(self) -> Path: return self.UPLOAD_DIR / "work_orders"

    @property
    def GALLERY_DIR(self) -> Path: return self.UPLOAD_DIR / "gallery"

    @property
    def is_production(self) -> bool: return self.ENV.lower() == "production"

    @property
    def is_development(self) -> bool: return self.ENV.lower() == "development"

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

Settings = Settings()

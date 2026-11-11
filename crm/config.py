"""Configuración: settings.toml (valores por defecto) + .env / variables de entorno (override).

Precedencia, de mayor a menor:
    1. Variable de entorno real del proceso
    2. Fichero .env
    3. settings.toml

El nombre de la variable es la ruta de la clave en mayúsculas unida con "_":
    [services] groq_api  ->  SERVICES_GROQ_API
Solo se pueden sobrescribir claves que existan en settings.toml, y el valor se convierte
al tipo del valor por defecto (bool, int, float, lista separada por comas o texto).

Uso:
    from crm.config import settings
    settings.services.groq_api
    settings.database.url
"""

import os
import tomllib
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_FILE = PROJECT_ROOT / "settings.toml"
ENV_FILE = PROJECT_ROOT / ".env"

_TRUE = {"1", "true", "yes", "on", "si", "sí"}
_FALSE = {"0", "false", "no", "off", ""}


class Section:
    """Acceso por atributo a un bloque de configuración (solo lectura)."""

    def __init__(self, data: dict[str, Any]):
        object.__setattr__(self, "_data", data)

    def __getattr__(self, name: str) -> Any:
        """Return a key; nested tables come back as Section."""
        try:
            value = self._data[name]
        except KeyError:
            raise AttributeError(f"No existe la clave de configuración '{name}'") from None
        return Section(value) if isinstance(value, dict) else value

    def __setattr__(self, name: str, value: Any) -> None:
        """Reject writes: configuration is read-only."""
        raise AttributeError("La configuración es de solo lectura")

    def __repr__(self) -> str:
        """Show the wrapped data."""
        return f"Section({self._data!r})"

    def as_dict(self) -> dict[str, Any]:
        """Return the underlying dictionary."""
        return self._data


def _coerce(raw: str, default: Any, name: str) -> Any:
    """Convierte el texto del entorno al tipo del valor por defecto."""
    try:
        if isinstance(default, bool):  # antes que int: bool es subclase de int
            low = raw.strip().lower()
            if low in _TRUE:
                return True
            if low in _FALSE:
                return False
            raise ValueError(raw)
        if isinstance(default, int):
            return int(raw)
        if isinstance(default, float):
            return float(raw)
        if isinstance(default, list):
            return [x.strip() for x in raw.split(",") if x.strip()]
    except ValueError:
        raise ValueError(f"Valor inválido para {name}: {raw!r}") from None
    return raw


def _apply_overrides(data: dict[str, Any], env: dict[str, str | None], prefix: tuple[str, ...] = ()):
    """Overwrite, in place, every leaf of `data` that has a matching variable in `env`."""
    for key, default in data.items():
        path = (*prefix, key)
        if isinstance(default, dict):
            _apply_overrides(default, env, path)
            continue
        name = "_".join(path).upper()
        raw = env.get(name)
        if raw is not None:
            data[key] = _coerce(raw, default, name)


def _validate_environment(data: dict[str, Any]) -> None:
    """Fail fast if [app] environment is not one of [app] allowed_environments (if the section exists)."""
    app = data.get("app")
    if app is None:
        return
    if app["environment"] not in app["allowed_environments"]:
        raise ValueError(
            f"Valor inválido para APP_ENVIRONMENT: {app['environment']!r} "
            f"(permitidos: {', '.join(app['allowed_environments'])})"
        )


def load_settings(
    settings_file: Path = SETTINGS_FILE,
    env_file: Path | None = ENV_FILE,
    environ: dict[str, str] | None = None,
) -> Section:
    """Carga settings.toml y le aplica .env y luego las variables de entorno del proceso."""
    with open(settings_file, "rb") as f:
        data = tomllib.load(f)
    env: dict[str, str | None] = {}
    if env_file is not None and Path(env_file).is_file():
        env.update(dotenv_values(env_file))
    env.update(os.environ if environ is None else environ)
    _apply_overrides(data, env)
    _validate_environment(data)
    return Section(data)


settings = load_settings()

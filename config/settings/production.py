from .base import *  # noqa: F401, F403

DEBUG = False
ALLOWED_HOSTS = [os.environ.get("PRODUCTION_HOST", "")]  # noqa: F405
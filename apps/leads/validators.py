import re
import logging
from typing import Optional, NamedTuple


class ValidationResult(NamedTuple):
    """Represents the result of validating a phone number."""
    is_valid: bool
    normalized: Optional[str]


class IranMobileValidator:
    """Utility class for validating and normalizing Iranian mobile phone numbers with logging support.

    This class supports:
      - Persian/Arabic digits conversion to English
      - Removal of separators (space, dash, parentheses, etc.)
      - Validation using simple or strict regex patterns
      - Normalization to either E.164 (+98...) or local (09...) format
      - Detailed logging at each step

    Attributes:
        strict (bool): If True, only validates known operator prefixes (090/091/092/093/099).
        output_format (str): Determines normalization output. Can be "e164" or "local".
        logger (logging.Logger): Logger instance used for debug and error messages.
    """

    _SIMPLE_PATTERN = re.compile(r'^(?:\+?98|0098|0)?9\d{9}$')
    _STRICT_PATTERN = re.compile(r'^(?:\+?98|0098|0)?9(?:0|1|2|3|9)\d{8}$')
    _DIGIT_MAP = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",  # Persian + Arabic-Indic
        "01234567890123456789"
    )

    def __init__(self, strict: bool = True, output_format: str = "e164", logger: Optional[logging.Logger] = None, debug: bool = True) -> None:
        """Initialize validator with strictness, output format, optional logger, and debug mode.

        Args:
            strict: Whether to use strict operator prefix validation.
            output_format: Either "e164" (e.g., +989121234567) or "local" (e.g., 09121234567).
            logger: Optional custom logger. If not provided, a default logger is configured.
            debug: Whether to enable debug logging for the default logger.
        """
        self.strict = strict
        if output_format not in ("e164", "local"):
            raise ValueError('output_format must be "e164" or "local"')
        self.output_format = output_format
        self.debug = debug

        self.logger = logger or self._create_default_logger(debug)
        self.logger.debug("IranMobileValidator initialized (strict=%s, output_format=%s, debug=%s)", strict, output_format, debug)

    # ----------------------------------------------------------------------
    # Logger setup
    # ----------------------------------------------------------------------

    def _create_default_logger(self, debug: bool) -> logging.Logger:
        """Create and configure a default logger if none is provided."""
        logger = logging.getLogger(self.__class__.__name__)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        logger.setLevel(logging.DEBUG if debug else logging.ERROR)
        return logger

    # ----------------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------------

    def validate(self, raw: str) -> ValidationResult:
        """Validate and normalize a raw input number with detailed logging.

        Args:
            raw: Input number in any common format (e.g., Persian digits, with spaces or +98).

        Returns:
            ValidationResult: Named tuple with (is_valid, normalized).
        """
        self.logger.debug("Starting validation for input: %r", raw)

        if not isinstance(raw, str):
            self.logger.error("Invalid input type: expected str, got %s", type(raw).__name__)
            return ValidationResult(False, None)

        cleaned = self._clean(raw)
        self.logger.debug("Cleaned input: %s", cleaned)

        if not self._matches_pattern(cleaned):
            self.logger.info("Validation failed: pattern mismatch for %s", cleaned)
            return ValidationResult(False, None)

        normalized = self._normalize(cleaned)
        if not normalized:
            self.logger.info("Validation failed: normalization unsuccessful for %s", cleaned)
            return ValidationResult(False, None)

        self.logger.debug("Validation successful: %s -> %s", raw, normalized)
        return ValidationResult(True, normalized)

    # ----------------------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------------------

    def _clean(self, s: str) -> str:
        """Convert digits to English and remove separators."""
        s_translated = s.translate(self._DIGIT_MAP)
        cleaned = re.sub(r'[\s\-\(\)_\.]', '', s_translated)
        self.logger.debug("_clean: %s -> %s", s, cleaned)
        return cleaned

    def _matches_pattern(self, s: str) -> bool:
        """Check if the cleaned number matches the validation regex."""
        pattern = self._STRICT_PATTERN if self.strict else self._SIMPLE_PATTERN
        matched = bool(pattern.fullmatch(s))
        self.logger.debug("_matches_pattern(%s) -> %s", s, matched)
        return matched

    def _normalize(self, s: str) -> Optional[str]:
        """Normalize number to the desired output format (e164 or local)."""
        self.logger.debug("Normalizing number: %s", s)

        # Already in E.164 format
        if re.fullmatch(r'^\+989\d{9}$', s):
            result = self._to_format(s)
            self.logger.debug("Already E.164: %s -> %s", s, result)
            return result

        # 00989XXXXXXXXX → +989XXXXXXXXX
        if re.fullmatch(r'^00989\d{9}$', s):
            result = self._to_format('+' + s[2:])
            self.logger.debug("0098 format detected: %s -> %s", s, result)
            return result

        # 09XXXXXXXXX → +989XXXXXXXXX
        if re.fullmatch(r'^09\d{9}$', s):
            result = self._to_format('+98' + s[1:])
            self.logger.debug("Local format detected: %s -> %s", s, result)
            return result

        # 9XXXXXXXXX → +989XXXXXXXXX
        if re.fullmatch(r'^9\d{9}$', s):
            result = self._to_format('+98' + s)
            self.logger.debug("Raw 9XXXXXXXXX format detected: %s -> %s", s, result)
            return result

        self.logger.warning("Normalization failed for: %s", s)
        return None

    def _to_format(self, e164: str) -> str:
        """Convert normalized E.164 number to requested output format."""
        if self.output_format == "e164":
            self.logger.debug("Returning E.164 format: %s", e164)
            return e164
        local_format = '0' + e164[3:]
        self.logger.debug("Converted to local format: %s -> %s", e164, local_format)
        return local_format


# ----------------------------------------------------------------------
# Example usage
# ----------------------------------------------------------------------
if __name__ == "__main__":
    validator = IranMobileValidator(strict=True, output_format="e164", debug=False)
    print(validator.validate("۰۹۱۲۱۲۳۴۵۶۷"))
    print(validator.validate("+98 912 123 4567"))
    print(validator.validate("00989351234567"))
    print(validator.validate("09411234567"))
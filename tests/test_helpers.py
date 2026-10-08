"""Tests for src/helpers — auth, exceptions, utils, upload, retry."""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestExceptions:
    """Verify custom exception hierarchy."""

    def test_validation_error_is_exception(self):
        from src.helpers.exceptions import ValidationError
        with pytest.raises(ValidationError):
            raise ValidationError("test error")

    def test_validation_error_message(self):
        from src.helpers.exceptions import ValidationError
        try:
            raise ValidationError("field X required")
        except ValidationError as e:
            assert "field X required" in str(e)

    def test_not_found_error(self):
        from src.helpers.exceptions import NotFoundError
        with pytest.raises(NotFoundError):
            raise NotFoundError("Shop", 42)

    def test_not_found_error_message(self):
        from src.helpers.exceptions import NotFoundError
        try:
            raise NotFoundError("Buyer", 7)
        except NotFoundError as e:
            assert "Buyer" in str(e)

    def test_auth_error(self):
        from src.helpers.exceptions import AuthorizationError
        with pytest.raises(AuthorizationError):
            raise AuthorizationError("Wrong password")


class TestAuth:
    """Verify delete password verification."""

    def test_correct_password_passes(self):
        """Correct password should not raise."""
        from src.helpers.auth import verify_delete_password
        from src.config import Settings
        # Should not raise
        verify_delete_password(Settings.DELETE_PASSWORD)

    def test_wrong_password_raises(self):
        """Wrong password should raise ValidationError."""
        from src.helpers.auth import verify_delete_password
        from src.helpers.exceptions import ValidationError
        with pytest.raises(ValidationError):
            verify_delete_password("wrong_password_xyz")

    def test_empty_password_raises(self):
        """Empty password should raise ValidationError."""
        from src.helpers.auth import verify_delete_password
        from src.helpers.exceptions import ValidationError
        with pytest.raises(ValidationError):
            verify_delete_password("")


class TestUtils:
    """Verify utility functions."""

    def test_expand_designation_known(self):
        """Known designation should expand."""
        from src.helpers.utils import expand_designation
        result = expand_designation("MD")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_expand_designation_unknown(self):
        """Unknown designation should return as-is."""
        from src.helpers.utils import expand_designation
        result = expand_designation("XYZ_UNKNOWN")
        assert result == "XYZ_UNKNOWN"

    def test_parse_contact_info_email(self):
        """Email string should be detected as email type."""
        from src.helpers.utils import parse_contact_info
        result = parse_contact_info("test@gmail.com")
        assert result['type'] == 'email'
        assert result['value'] == "test@gmail.com"

    def test_parse_contact_info_corporate_email(self):
        """Corporate custom domain email should be detected as email, not web."""
        from src.helpers.utils import parse_contact_info
        result = parse_contact_info("info@bengal-workshop.com")
        assert result['type'] == 'email'
        assert result['value'] == "info@bengal-workshop.com"

    def test_parse_contact_info_website(self):
        """Website should be detected as web type."""
        from src.helpers.utils import parse_contact_info
        result = parse_contact_info("www.example.com")
        assert result['type'] == 'web'

    def test_parse_contact_info_empty(self):
        """Empty string should return text type with '-'."""
        from src.helpers.utils import parse_contact_info
        result = parse_contact_info("")
        assert result['type'] == 'text'
        assert result['value'] == '-'

    def test_parse_contact_info_phone(self):
        """Phone number should return text type."""
        from src.helpers.utils import parse_contact_info
        result = parse_contact_info("01711111111")
        assert result['type'] == 'text'

    def test_parse_tags_empty(self):
        """Empty string should return empty list."""
        from src.helpers.utils import parse_tags
        assert parse_tags("") == []

    def test_parse_tags_csv(self):
        """CSV string should split into list of dicts."""
        from src.helpers.utils import parse_tags
        result = parse_tags("steel, iron, copper")
        assert len(result) == 3
        assert result[0]['value'] == 'steel'


class TestSafeCoercion:
    """Verify safe_float/safe_int crash guards."""

    def test_safe_float_rejects_garbage(self):
        import pytest
        from src.helpers.utils import safe_float
        from src.helpers.exceptions import ValidationError
        with pytest.raises(ValidationError):
            safe_float("abc", field="quantity")

    def test_safe_int_rejects_garbage(self):
        import pytest
        from src.helpers.utils import safe_int
        from src.helpers.exceptions import ValidationError
        with pytest.raises(ValidationError):
            safe_int("abc", field="supplier_id")

    def test_safe_float_empty_returns_zero(self):
        from src.helpers.utils import safe_float
        assert safe_float("", field="quantity") == 0.0
        assert safe_float(None, field="quantity") == 0.0

    def test_safe_int_empty_returns_zero(self):
        from src.helpers.utils import safe_int
        assert safe_int("", field="supplier_id") == 0
        assert safe_int(None, field="supplier_id") == 0

    def test_safe_float_valid(self):
        from src.helpers.utils import safe_float
        assert safe_float("2.5", field="quantity") == 2.5
        assert safe_float(" 3 ", field="quantity") == 3.0

    def test_safe_int_valid(self):
        from src.helpers.utils import safe_int
        assert safe_int("42", field="supplier_id") == 42

    def test_buyer_to_dict_none_date(self):
        from src.db.database import Buyer
        b = Buyer(company_name="x", created_at=None)
        assert b.to_dict()["created_at"] is None


class TestRetry:
    """Verify retry decorator."""

    def test_retry_on_success(self):
        """Function that succeeds should return normally."""
        from src.helpers.retry import retry

        @retry(max_retries=3, base_delay=0.01)
        def good_func():
            return "ok"

        assert good_func() == "ok"

    def test_retry_on_failure(self):
        """Function that always fails should raise after max_attempts."""
        from src.helpers.retry import retry

        call_count = 0

        @retry(max_retries=2, base_delay=0.01)
        def bad_func():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            bad_func()
        assert call_count == 3  # 1 original + 2 retries

    def test_retry_eventual_success(self):
        """Function that fails then succeeds should work."""
        from src.helpers.retry import retry

        attempts = 0

        @retry(max_retries=3, base_delay=0.01)
        def flaky_func():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise RuntimeError("not yet")
            return "done"

        assert flaky_func() == "done"
        assert attempts == 3


class TestUpload:
    """Verify file upload helper."""

    def test_allowed_file_extension(self):
        """Known extensions should be allowed."""
        from src.helpers.upload import allowed_file
        assert allowed_file("photo.jpg") is True
        assert allowed_file("doc.pdf") is True

    def test_disallowed_file_extension(self):
        """Unknown/dangerous extensions should be blocked."""
        from src.helpers.upload import allowed_file
        assert allowed_file("hack.exe") is False
        assert allowed_file("script.sh") is False

    def test_no_extension(self):
        """File without extension should be blocked."""
        from src.helpers.upload import allowed_file
        assert allowed_file("noext") is False

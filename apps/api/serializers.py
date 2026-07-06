from rest_framework import serializers
from apps.leads.models import Lead, Message
from apps.leads.validators import IranMobileValidator


class LeadRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for handling initial Lead registration."""

    class Meta:
        """Meta configuration for the serializer."""
        model = Lead
        fields = ["first_name", "last_name", "phone_number"]
        extra_kwargs = {
            "phone_number": {
                "validators": [],  # Remove default unique validator to allow upsert in service layer
            }
        }

    def validate_phone_number(self, value: str) -> str:
        """Validate and normalize the phone number using the custom validator."""
        validator = IranMobileValidator(strict=True, output_format="local", debug=False)
        result = validator.validate(value)
        if not result.is_valid:
            raise serializers.ValidationError("Invalid Iranian mobile number.")
        return str(result.normalized)


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for representing a chat message."""

    class Meta:
        """Meta configuration for the serializer."""
        model = Message
        fields = ["sender", "content", "timestamp"]
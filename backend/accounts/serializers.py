from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ('email', 'username', 'password', 'display_name', 'timezone')

    def validate_username(self, value):
        # username appears in URL, so keep it URL safe
        if not value.isalnum() and '-' not in value and '_' not in value:
            raise serializers.ValidationError(
                "Username can only contain letters, numbers, hyphens, and underscores."
            )
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value.lower()

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'display_name', 'bio', 'timezone')
        read_only_fields = ('id', 'email', 'username')


class PublicUserSerializer(serializers.ModelSerializer):
    """What we expose on the public booking page."""
    class Meta:
        model = User
        fields = ('username', 'display_name', 'bio', 'timezone')

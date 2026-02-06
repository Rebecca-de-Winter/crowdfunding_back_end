from rest_framework import serializers
from .models import CustomUser

class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = '__all__'
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {"write_only": True}
            }
        

    def create(self, validated_data):
        return CustomUser.objects.create_user(**validated_data)
    
class SignUpSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ["id", "username", "password", "first_name", "last_name", "email"]

    def create(self, validated_data):
        return CustomUser.objects.create_user(**validated_data)
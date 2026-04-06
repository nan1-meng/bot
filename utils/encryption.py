# 文件路径: utils/encryption.py
from cryptography.fernet import Fernet
from config import ENCRYPTION_KEY

cipher = Fernet(ENCRYPTION_KEY.encode())

def encrypt(plain_text: str) -> str:
    """加密明文字符串"""
    return cipher.encrypt(plain_text.encode()).decode()

def decrypt(encrypted_text: str) -> str:
    """解密密文字符串"""
    return cipher.decrypt(encrypted_text.encode()).decode()
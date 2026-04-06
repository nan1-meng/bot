# 文件路径: services/auth_service.py
import bcrypt
from dao.user_dao import UserDAO

def hash_password(password: str) -> str:
    """对密码进行哈希加密"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """验证密码是否正确"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def authenticate(username: str, password: str):
    """用户认证，成功返回用户对象，失败返回 None"""
    user = UserDAO.get_by_username(username)
    if user and verify_password(password, user.password_hash):
        return user
    return None

def change_password(user_id: int, old_password: str, new_password: str) -> bool:
    """修改用户密码，成功返回 True"""
    user = UserDAO.get_by_id(user_id)
    if not user:
        return False
    if not verify_password(old_password, user.password_hash):
        return False
    user.password_hash = hash_password(new_password)
    UserDAO.update(user)
    return True
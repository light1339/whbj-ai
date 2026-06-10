# scripts/init_user.py
import asyncio
import sys
import os
import argparse # 导入参数解析库

# 1. 强行把 backend 文件夹塞进寻路地图
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import uuid
import bcrypt
from datetime import datetime
from app.core.mdb import users_collection # 确保路径正确

async def create_user(username, password, role="employee", kb_list=None):
    try:
        # 🔍 查重
        existing_user = await users_collection.find_one({"username": username})
        if existing_user:
            print(f"[提示] 用户 {username} 已存在，跳过创建。")
            return

        # 🔐 加密
        password_bytes = password.encode('utf-8')
        hashed_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')
        
        user_data = {
            "user_id": str(uuid.uuid4()),
            "username": username,
            "email": f"{username}@example.com",
            "password_hash": hashed_password,
            "role": role,
            "kb_access": kb_list or ["default"],
            "created_at": datetime.utcnow()
        }
        
        await users_collection.insert_one(user_data)
        print(f"[成功] 用户 [{username}] (角色: {role}) 已入库！")
        
    except Exception as e:
        print(f"[失败] {str(e)}")

if __name__ == "__main__":
    # 配置命令行参数
    parser = argparse.ArgumentParser(description="快速添加用户工具")
    parser.add_argument("--user", required=True, help="用户名")
    parser.add_argument("--pwd", required=True, help="明文密码")
    parser.add_argument("--role", default="employee", help="角色 (employee/hr/boss)")
    parser.add_argument("--kb", default="default", help="可访问知识库: default,manage 或 default,manage(逗号分隔)")

    args = parser.parse_args()
    kb_list = [k.strip() for k in args.kb.split(",") if k.strip()]
    asyncio.run(create_user(args.user, args.pwd, args.role, kb_list))
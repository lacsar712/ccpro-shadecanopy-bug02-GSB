from config.settings import *  # noqa: F401,F403

# 测试使用文件级 SQLite：并发请求由独立线程/独立连接处理，
# 需要共享同一个数据库文件。
_TEST_DB = BASE_DIR / "test_db.sqlite3"  # noqa: F405
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _TEST_DB,
        "TEST": {"NAME": str(_TEST_DB)},
        # IMMEDIATE：BEGIN 时即取写锁，使并发写在同一行上串行化，
        # 对齐 PostgreSQL READ COMMITTED 下“行锁等待后按最新行版本
        # 重新判定 UPDATE ... WHERE”的语义。
        "OPTIONS": {"transaction_mode": "IMMEDIATE"},
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# 设计：配置化 CORS 允许来源

在 `src/api_service.py` 增加单一解析函数，读取逗号分隔的 `CORS_ALLOWED_ORIGINS`。缺省值为当前两个本地来源，避免改变开发拓扑。

解析后的每项必须是无路径、无查询参数、无片段的 `http://` 或 `https://` 来源；空项、通配符和重复项均作为配置错误失败关闭。FastAPI `CORSMiddleware` 直接使用该函数的返回值。

`.env.example` 只给出占位示例，不写入实际部署域名或凭据。

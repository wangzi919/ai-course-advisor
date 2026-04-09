// web-server.js - Claude MCP 聊天服務器（統一版本）
import express from 'express';
import { createServer } from 'http';
import cookieParser from 'cookie-parser';
import { RawMCPClient } from './raw-mcp-client.js';
import config from './config/environment.js';
import { MongooseConnectionManager } from './database/MongooseConnectionManager.js'
import { Logger } from './utils/logger.js';
import { createAPIRoutes } from './routes/api.js';
import { optionalAuth } from './middleware/auth.js';

// 初始化配置
const app = express();
const server = createServer(app);
const dbManager = new MongooseConnectionManager();
await dbManager.connect();
app.use(express.json());
app.use(cookieParser());

// 認證中間件 - 自動解析所有請求的用戶資訊
app.use(optionalAuth);

app.use(express.static('public'));

const mcpClient = new RawMCPClient();

// 初始化 MCP
Logger.server('正在啟動 Claude MCP 服務器（原始模式）...');
await mcpClient.initialize();

// 等待工具載入
setTimeout(() => {
  const tools = mcpClient.getClaudeTools();
  Logger.server(`工具載入完成！共 ${tools.length} 個工具可用`);
}, 5000);

// 設定 REST API 路由
app.use('/api', createAPIRoutes(mcpClient));

// 靜態 HTML 頁面
app.get('/', (req, res) => {
  res.sendFile('index.html', { root: 'public' });
});

// 完整版頁面路由
app.get('/full', (req, res) => {
  res.sendFile('index_long.html', { root: 'public' });
});

const PORT = config.port;
server.listen(PORT, () => {
  Logger.server(`服務器運行在 http://localhost:${PORT}`);
});

// 優雅關閉
process.on('SIGINT', async () => {
  Logger.server('正在關閉服務器...');
  await mcpClient.cleanup();
  process.exit(0);
});

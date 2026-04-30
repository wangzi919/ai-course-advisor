// web-server.js - Claude MCP 聊天服務器（統一版本）
import express from 'express';
import { createServer } from 'http';
import cookieParser from 'cookie-parser';
import config from './config/environment.js';
import { MongooseConnectionManager } from './database/MongooseConnectionManager.js'
import { Logger } from './utils/logger.js';
import { createAPIRoutes } from './routes/api.js';
import { optionalAuth } from './middleware/auth.js';

// 初始化配置
const app = express();
const server = createServer(app);
const dbManager = new MongooseConnectionManager();

// 嘗試連接資料庫，失敗時繼續執行
try {
  await dbManager.connect();
  Logger.server('✅ MongoDB 連接成功');
} catch (error) {
  Logger.server('⚠️  MongoDB 連接失敗，服務將在無資料庫模式下運行');
  Logger.server(`錯誤訊息: ${error.message}`);
}

app.use(express.json());
app.use(cookieParser());

// 認證中間件 - 自動解析所有請求的用戶資訊
app.use(optionalAuth);

app.use(express.static('public'));

// 設定 REST API 路由
app.use('/api', createAPIRoutes());

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

  // 關閉 MongoDB 連接
  if (dbManager) {
    Logger.server('正在關閉 MongoDB 連接...');
    await dbManager.disconnect();
  }

  Logger.server('✅ 所有連接已關閉');
  process.exit(0);
});

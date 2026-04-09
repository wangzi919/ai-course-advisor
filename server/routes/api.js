import { Router } from 'express';
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// 建立一個假的記憶體資料庫
const inMemoryDB = new Map();

export const createAPIRoutes = () => {
    const router = Router();
    
    // 獲取對話歷史資料
    router.get('/conversations/:id', (req, res) => {
        const id = req.params.id;
        const messages = inMemoryDB.get(id) || [];
        res.json({ id: id, messages: messages, title: "測試對話", updatedAt: new Date() });
    });
    
    // 獲取所有對話清單
    router.get('/conversations', (req, res) => {
        const convList = Array.from(inMemoryDB.entries()).map(([id, msgs]) => ({
            id,
            title: msgs.find(m => m.role === 'user')?.content.substring(0, 15) || '新對話',
            updatedAt: new Date()
        }));
        res.json({ conversations: convList, pagination: { page: 1, hasMore: false } });
    });

    // 刪除對話
    router.delete('/conversations/:id', (req, res) => {
        inMemoryDB.delete(req.params.id);
        res.send('deleted');
    });

    // 串流
    router.post('/chat/stream', (req, res) => {
        res.setHeader('Content-Type', 'text/event-stream; charset=utf-8');
        res.setHeader('Cache-Control', 'no-cache');
        res.setHeader('Connection', 'keep-alive');
        
        let conversationId = req.body.conversationId || 'nchu-' + Date.now();
        let currentMessages = inMemoryDB.get(conversationId) || [];
        
        // 將新的 user messages 塞入 DB
        let requestMessages = req.body.messages || [];
        if (requestMessages.length > 0) {
            // 如果前端只丟來最後一句，我們應該加上之前的
            const latestMsg = requestMessages[requestMessages.length-1];
            currentMessages.push({ role: latestMsg.role, content: latestMsg.content, createdAt: new Date() });
            inMemoryDB.set(conversationId, currentMessages);
            requestMessages = [...currentMessages]; // 傳給 AI 的是全部上下文
        } else {
            res.end();
            return;
        }
        
        const sendEvent = (data) => {
            res.write(`data: ${JSON.stringify(data)}\n\n`);
        };

        sendEvent({
            type: 'connected',
            data: { conversation_id: conversationId, isNewConversation: !req.body.conversationId }
        });

        sendEvent({
            type: 'response',
            data: { type: 'response_start', data: { model: 'gemini' } }
        });

        let assistantContent = "";
        
        // 呼叫您指定的 icl_runner Python 腳本
        const userQuery = requestMessages[requestMessages.length-1].content;
        const pythonScriptPath = path.resolve(__dirname, '../LLMs_in_the_Imaginarium/Exploitation/web_icl_runner.py');
        
        const pythonProcess = spawn('python', [pythonScriptPath, '--query', userQuery]);
        
        pythonProcess.stdout.on('data', (data) => {
            const chunk = data.toString();
            assistantContent += chunk;
            sendEvent({
                type: 'response',
                data: { type: 'text_chunk', chunk: chunk }
            });
        });
        
        pythonProcess.stderr.on('data', (data) => {
            console.error(`Python stderr: ${data}`);
        });

        pythonProcess.on('close', (code) => {
            if (code !== 0) {
                sendEvent({ type: 'error', data: { error: `Python 模型執行失敗 (代碼: ${code})` } });
                res.end();
            } else {
                currentMessages.push({ role: 'assistant', content: assistantContent, createdAt: new Date() });
                inMemoryDB.set(conversationId, currentMessages);
                
                sendEvent({ type: 'response', data: { type: 'response_end' } });
                sendEvent({ type: 'done', data: { conversation_id: conversationId } });
                res.end();
            }
        });
        
    });
    
    // 假裝 SSO 登入過
    router.get('/sso/auth/me', (req, res) => {
        res.json({ user: { id: "000TEST", name: "User", role: "student" } });
    });
    
    return router;
};

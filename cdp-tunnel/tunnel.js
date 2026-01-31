const http = require('http');
const WebSocket = require('ws');

const CHROME_DEBUG_PORT = 9222;
const TUNNEL_PORT = 9333;

// Get Chrome's websocket debug URL
async function getChromeWsUrl() {
  return new Promise((resolve, reject) => {
    http.get(`http://127.0.0.1:${CHROME_DEBUG_PORT}/json/version`, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const info = JSON.parse(data);
          resolve(info.webSocketDebuggerUrl);
        } catch (e) {
          reject(e);
        }
      });
    }).on('error', reject);
  });
}

// Proxy server that forwards CDP commands
const server = http.createServer((req, res) => {
  // Normalize URL (remove trailing slash)
  let url = req.url;
  if (url.endsWith('/') && url.length > 1) {
    url = url.slice(0, -1);
  }
  
  if (url === '/json/version') {
    http.get(`http://127.0.0.1:${CHROME_DEBUG_PORT}/json/version`, (proxyRes) => {
      res.writeHead(proxyRes.statusCode, proxyRes.headers);
      proxyRes.pipe(res);
    }).on('error', (e) => {
      res.writeHead(502);
      res.end(JSON.stringify({ error: e.message }));
    });
  } else if (url === '/json' || url === '/json/list') {
    http.get(`http://127.0.0.1:${CHROME_DEBUG_PORT}${url}`, (proxyRes) => {
      res.writeHead(proxyRes.statusCode, proxyRes.headers);
      proxyRes.pipe(res);
    }).on('error', (e) => {
      res.writeHead(502);
      res.end(JSON.stringify({ error: e.message }));
    });
  } else if (url.startsWith('/json/')) {
    // Forward any other /json/* endpoints
    http.get(`http://127.0.0.1:${CHROME_DEBUG_PORT}${url}`, (proxyRes) => {
      res.writeHead(proxyRes.statusCode, proxyRes.headers);
      proxyRes.pipe(res);
    }).on('error', (e) => {
      res.writeHead(502);
      res.end(JSON.stringify({ error: e.message }));
    });
  } else {
    res.writeHead(404);
    res.end('Not found');
  }
});

// WebSocket proxy for CDP
const wss = new WebSocket.Server({ server });

wss.on('connection', async (clientWs, req) => {
  console.log(`[${new Date().toISOString()}] New connection from ${req.socket.remoteAddress}`);
  
  try {
    // Extract target from URL or use browser endpoint
    let targetUrl;
    if (req.url && req.url !== '/') {
      targetUrl = `ws://127.0.0.1:${CHROME_DEBUG_PORT}${req.url}`;
    } else {
      const wsUrl = await getChromeWsUrl();
      targetUrl = wsUrl;
    }
    
    console.log(`[${new Date().toISOString()}] Connecting to Chrome: ${targetUrl}`);
    const chromeWs = new WebSocket(targetUrl);
    
    chromeWs.on('open', () => {
      console.log(`[${new Date().toISOString()}] Connected to Chrome`);
    });
    
    chromeWs.on('message', (data) => {
      if (clientWs.readyState === WebSocket.OPEN) {
        clientWs.send(data);
      }
    });
    
    clientWs.on('message', (data) => {
      if (chromeWs.readyState === WebSocket.OPEN) {
        chromeWs.send(data);
      }
    });
    
    chromeWs.on('close', () => {
      console.log(`[${new Date().toISOString()}] Chrome connection closed`);
      clientWs.close();
    });
    
    clientWs.on('close', () => {
      console.log(`[${new Date().toISOString()}] Client disconnected`);
      chromeWs.close();
    });
    
    chromeWs.on('error', (e) => {
      console.error(`[${new Date().toISOString()}] Chrome error:`, e.message);
      clientWs.close();
    });
    
  } catch (e) {
    console.error(`[${new Date().toISOString()}] Connection error:`, e.message);
    clientWs.close();
  }
});

server.listen(TUNNEL_PORT, '0.0.0.0', () => {
  console.log(`CDP Tunnel running on port ${TUNNEL_PORT}`);
  console.log(`Connect from VPS: ws://100.102.41.120:${TUNNEL_PORT}`);
});

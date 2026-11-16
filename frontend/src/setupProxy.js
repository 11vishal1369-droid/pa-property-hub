const { createProxyMiddleware } = require("http-proxy-middleware");

// Dev/preview only: the web content service runs separately from the admin backend (/api).
module.exports = function (app) {
  app.use(createProxyMiddleware("/webcontent-api", { target: "http://127.0.0.1:8002", changeOrigin: false }));
};

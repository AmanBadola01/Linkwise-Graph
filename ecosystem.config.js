// PM2 production deploy (Excellence Cloud, permanent ports 20324/20325).
// Frontend (public): http://116.202.210.102:20324  Backend: 0.0.0.0:20325
const path = require("path");
const ROOT = __dirname;

module.exports = {
  apps: [
    {
      name: "linkwise-backend",
      cwd: ROOT,
      script: path.join(ROOT, ".venv/bin/uvicorn"),
      args: "backend.app.main:app --host 0.0.0.0 --port 20325",
      interpreter: "none",
      env: { ENVIRONMENT: "production", PYTHONUNBUFFERED: "1" },
      autorestart: true,
      max_restarts: 10,
      restart_delay: 3000,
      out_file: path.join(ROOT, ".tools/pm2-backend-out.log"),
      error_file: path.join(ROOT, ".tools/pm2-backend-error.log"),
    },
    {
      name: "linkwise-frontend",
      cwd: path.join(ROOT, "frontend"),
      script: "node_modules/next/dist/bin/next",
      args: "start -H 0.0.0.0 -p 20324",
      interpreter: "node",
      env: {
        NODE_ENV: "production",
        LINKWISE_BACKEND_URL: "http://127.0.0.1:20325",
      },
      autorestart: true,
      max_restarts: 10,
      restart_delay: 3000,
      out_file: path.join(ROOT, ".tools/pm2-frontend-out.log"),
      error_file: path.join(ROOT, ".tools/pm2-frontend-error.log"),
    },
  ],
};

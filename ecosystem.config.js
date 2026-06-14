// ecosystem.config.js – pm2 process manager configuration for the fix‑r2‑image‑pipeline
module.exports = {
  apps: [
    {
      // Human‑readable name shown by `pm2 ls`
      name: "fix-r2-image-pipeline",

      // Entry‑point script (the main python file for the pipeline)
      script: "main.py",

      // Use the virtual‑env python interpreter so the same deps are used as during development
      interpreter: "/home/panic/Projects/fix_r2_image_python/venv/bin/python",

      // Environment variables – add any you need here (example shown)
      env: {
        PYTHONUNBUFFERED: "1"
      },

      // Restart policy – typical for a long‑running worker
      autorestart: true,
      watch: false,
      max_restarts: 10,
      restart_delay: 3000,

      // Log handling – pm2 will rotate these automatically
      output: "./logs/out.log",
      error: "./logs/err.log",
      log_date_format: "YYYY-MM-DD HH:mm Z"
    }
  ]
};

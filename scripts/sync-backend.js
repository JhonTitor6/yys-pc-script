#!/usr/bin/env node
/**
 * 把 PyInstaller 产物 dist/backend/ 同步到 gui/build/backend/，
 * 以便 electron-builder 通过 extraResources 把它打包到 resources/backend/。
 *
 * 行为：
 *   - 首次：移动 dist/backend -> gui/build/backend
 *   - 后续：增量复制（rsync 风格），避免每次都重新打包
 *
 * 用法：
 *   node scripts/sync-backend.js
 */

const fs = require('fs');
const path = require('path');

const PROJECT_ROOT = path.resolve(__dirname, '..');
const SRC = path.join(PROJECT_ROOT, 'dist', 'backend');
const DST = path.join(PROJECT_ROOT, 'gui', 'build', 'backend');

function copyDir(srcDir, dstDir) {
  if (!fs.existsSync(dstDir)) {
    fs.mkdirSync(dstDir, { recursive: true });
  }
  for (const entry of fs.readdirSync(srcDir, { withFileTypes: true })) {
    const s = path.join(srcDir, entry.name);
    const d = path.join(dstDir, entry.name);
    if (entry.isDirectory()) {
      copyDir(s, d);
    } else if (entry.isFile()) {
      fs.copyFileSync(s, d);
    }
  }
}

function main() {
  if (!fs.existsSync(SRC)) {
    console.error(`[sync-backend] 找不到 ${SRC}`);
    console.error('[sync-backend] 请先运行 npm run build:backend');
    process.exit(1);
  }

  fs.mkdirSync(path.dirname(DST), { recursive: true });

  // 目标存在则先清空，避免遗留旧文件
  if (fs.existsSync(DST)) {
    fs.rmSync(DST, { recursive: true, force: true });
  }

  copyDir(SRC, DST);
  console.log(`[sync-backend] 已同步 ${SRC} -> ${DST}`);

  // 验证关键文件
  const yysBackend = path.join(DST, 'yys-backend.exe');
  if (!fs.existsSync(yysBackend)) {
    console.error(`[sync-backend] 警告：${yysBackend} 不存在`);
    process.exit(1);
  }
}

main();

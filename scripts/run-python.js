#!/usr/bin/env node
/**
 * 在 npm scripts 中以一致方式调用项目指定 conda 环境里的 Python。
 *
 * 用法：
 *   node scripts/run-python.js <python args...>
 *   node scripts/run-python.js -m PyInstaller build_backend.spec --clean
 *
 * Python 解析顺序：
 *   1) 环境变量 YYS_PYTHON
 *   2) Windows 默认 conda 环境：D:/ProgramData/anaconda3/envs/win_macro/python.exe
 *   3) 退回系统 PATH 中的 python
 */

const { spawn } = require('child_process');
const path = require('path');

const DEFAULT_PYTHON = 'D:/ProgramData/anaconda3/envs/win_macro/python.exe';

function resolvePython() {
  return process.env.YYS_PYTHON || DEFAULT_PYTHON || 'python';
}

const python = resolvePython();
const args = process.argv.slice(2);

if (args.length === 0) {
  console.error('[run-python] 用法：node scripts/run-python.js <python args...>');
  process.exit(2);
}

console.log(`[run-python] ${python} ${args.join(' ')}`);

const child = spawn(python, args, {
  stdio: 'inherit',
  cwd: path.resolve(__dirname, '..'),
  shell: false,
});

child.on('error', (err) => {
  console.error(`[run-python] 启动 Python 失败: ${err.message}`);
  console.error(`[run-python] 提示：设置 YYS_PYTHON 环境变量指向正确的 python.exe`);
  process.exit(1);
});

child.on('close', (code) => {
  process.exit(code ?? 0);
});

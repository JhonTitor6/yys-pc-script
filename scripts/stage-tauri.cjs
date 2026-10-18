// 只打包页面实际依赖；生产图片仅生成 ID 白名单，不复制到前端。
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const gui = path.join(root, 'gui');
const output = path.join(gui, 'build', 'tauri-frontend');
const files = ['index.html', 'renderer.js', 'styles.css', 'desktop-bridge.js', 'icon.ico', 'node_modules/cropperjs/dist/cropper.min.js'];
function writeChanged(target, content) {
  for (let current = target; current !== root; current = path.dirname(current)) {
    if (fs.existsSync(current) && fs.lstatSync(current).isSymbolicLink()) throw new Error(`不允许 staging 链接：${current}`);
  }
  fs.mkdirSync(path.dirname(target), { recursive: true });
  if (!fs.existsSync(target) || !fs.readFileSync(target).equals(content)) fs.writeFileSync(target, content);
}
if (fs.existsSync(output)) verify(output);
for (const file of files) writeChanged(path.join(output, file), fs.readFileSync(path.join(gui, file)));
// 与 win_util.image.production_image_ids 的生产资源契约一致。
const excluded = new Set(['test', 'tests', 'debug', 'logs', 'example', 'recordings']);
const ids = [];
function scan(directory) {
  for (const item of fs.readdirSync(directory, { withFileTypes: true })) {
    if (item.isSymbolicLink()) throw new Error(`不允许资源链接：${item.name}`);
    const full = path.join(directory, item.name);
    if (item.isDirectory() && !excluded.has(item.name.toLowerCase())) scan(full);
    else if (item.isFile() && /\.(bmp|png)$/i.test(item.name)) ids.push(path.relative(root, full).split(path.sep).join('/'));
  }
}
scan(path.join(root, 'yys'));
writeChanged(path.join(gui, 'build', 'tauri-image-resources.json'), Buffer.from(JSON.stringify(ids.sort())));
function verify(directory) {
  for (const item of fs.readdirSync(directory, { withFileTypes: true })) {
    const full = path.join(directory, item.name);
    if (item.isSymbolicLink()) throw new Error('staging 不允许符号链接');
    if (item.isDirectory()) verify(full);
    else if (!files.includes(path.relative(output, full).split(path.sep).join('/'))) throw new Error(`staging 存在非白名单文件：${full}`);
  }
}
verify(output);
console.log(`Tauri staging：${files.length} 个静态文件，${ids.length} 个图片资源 ID`);
